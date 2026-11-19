package mm.api;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The buttons of the till (a cafe: coffees, juices, sweets without a barcode): groups of buttons, in each
 * the items as tiles, and the short number of an item (PLU, typed at the till instead of a scan). Every
 * rule is in mm_core (tile_group_save, tile_add, tile_move, set_plu ...); errors MM-132.
 *
 * <pre>
 *   GET  /api/pos/tiles                        the till: the active groups with their tiles (active items),
 *                                              and "frequent": the 8 tiles sold most in the last 7 days
 *   GET  /api/tiles                            the page Κουμπιά ταμείου: every group (and the inactive), its tiles
 *   POST /api/tiles/groups {name, color, active}           a new group, at the end
 *   POST /api/tiles/groups/{id} {name, color, active}      a group changed
 *   POST /api/tiles/groups/{id}/move {dir}     one place before (-1) or after (+1)
 *   POST /api/tiles/groups/{id}/delete         out, with its tiles
 *   POST /api/tiles/groups/{id}/tiles {code}   an item (its code, barcode or PLU) into the group, at its end
 *   POST /api/tiles/{id}/move {dir}            a tile one place before or after
 *   POST /api/tiles/{id}/delete                a tile out (the item stays)
 *   POST /api/tiles/plu {code, plu}            the PLU of an item (null: none)   (TILES: PLU)
 * </pre>
 * Each POST returns the page again, as GET /api/tiles.
 */
final class Tiles {
    private Tiles() {
    }

    private static final String TILES = """
            select t.id, t.group_id, t.item_id, i.code, i.name, i.price, i.plu, i.active
            from mm_tile t join mm_item i on i.id = t.item_id
            order by t.sort_no, t.id""";

    /** the till: the active groups, their tiles of active items; the most sold of the last 7 days */
    static Map<String, Object> forTill(Connection c) throws SQLException {
        List<Map<String, Object>> groups = Db.rows(c,
                "select id, name, color from mm_tile_group where active = 'Y' order by sort_no, id");
        List<Map<String, Object>> tiles = Db.rows(c, TILES);
        for (Map<String, Object> g : groups) {
            List<Map<String, Object>> mine = new ArrayList<>();
            for (Map<String, Object> t : tiles) {
                if (t.get("group_id").equals(g.get("id")) && "Y".equals(t.get("active"))) {
                    mine.add(t);
                }
            }
            g.put("tiles", mine);
        }
        List<Map<String, Object>> frequent = Db.rows(c, """
                select i.id item_id, i.code, i.name, i.price, i.plu, sum(l.qty) sold
                from mm_doc_line l
                join mm_doc d on d.id = l.doc_id and d.doc_type = 'ALP' and d.status = 'P' and d.doc_date >= trunc(sysdate) - 7
                join mm_item i on i.id = l.item_id and i.active = 'Y'
                where exists (select 1 from mm_tile t join mm_tile_group g on g.id = t.group_id and g.active = 'Y'
                              where t.item_id = i.id)
                group by i.id, i.code, i.name, i.price, i.plu
                order by sold desc, i.code fetch first 8 rows only""");
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("groups", groups);
        out.put("frequent", frequent);
        return out;
    }

    /** the page: every group, its tiles */
    static Map<String, Object> page(Connection c) throws SQLException {
        List<Map<String, Object>> groups = Db.rows(c,
                "select id, name, color, active from mm_tile_group order by sort_no, id");
        List<Map<String, Object>> tiles = Db.rows(c, TILES);
        for (Map<String, Object> g : groups) {
            List<Map<String, Object>> mine = new ArrayList<>();
            for (Map<String, Object> t : tiles) {
                if (t.get("group_id").equals(g.get("id"))) {
                    mine.add(t);
                }
            }
            g.put("tiles", mine);
        }
        return Map.of("groups", groups);
    }

    static Object post(Connection c, String[] p, Map<String, Object> in) throws SQLException {
        int n = p.length;
        if (n == 2 && "plu".equals(p[1])) {
            long item = item(c, Http.text(in, "code", true));
            BigDecimal plu = Http.decimal(in, "plu", null);
            Db.exec(c, "begin mm_core.set_plu(?, ?); end;", item, plu);
            return page(c);
        }
        if (n >= 2 && "groups".equals(p[1])) {
            if (n == 2 || n == 3) {
                Object id = n == 3 ? Http.id(p[2]) : null;
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.tile_group_save(?, ?, ?, ?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    if (id == null) {
                        cs.setNull(2, Types.NUMERIC);
                    } else {
                        cs.setLong(2, (Long) id);
                    }
                    cs.setString(3, Http.text(in, "name", false));
                    cs.setString(4, Http.text(in, "color", false));
                    cs.setString(5, Http.text(in, "active", false));
                    cs.execute();
                }
                return page(c);
            }
            long g = Http.id(p[2]);
            if (n == 4) {
                switch (p[3]) {
                    case "move" -> {
                        Db.exec(c, "begin mm_core.tile_move('G', ?, ?); end;", g, dir(in));
                        return page(c);
                    }
                    case "delete" -> {
                        Db.exec(c, "begin mm_core.tile_group_delete(?); end;", g);
                        return page(c);
                    }
                    case "tiles" -> {
                        long item = item(c, Http.text(in, "code", true));
                        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.tile_add(?, ?); end;")) {
                            cs.registerOutParameter(1, Types.NUMERIC);
                            cs.setLong(2, g);
                            cs.setLong(3, item);
                            cs.execute();
                        }
                        return page(c);
                    }
                    default -> {
                    }
                }
            }
            throw new Http.Fail(404, "not_found", "no such endpoint");
        }
        if (n == 3) {
            long t = Http.id(p[1]);
            switch (p[2]) {
                case "move" -> {
                    Db.exec(c, "begin mm_core.tile_move('T', ?, ?); end;", t, dir(in));
                    return page(c);
                }
                case "delete" -> {
                    Db.exec(c, "begin mm_core.tile_delete(?); end;", t);
                    return page(c);
                }
                default -> {
                }
            }
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    private static int dir(Map<String, Object> in) {
        BigDecimal d = Http.decimal(in, "dir", null);
        if (d == null || (d.intValue() != -1 && d.intValue() != 1)) {
            throw new Http.Fail(400, "bad_dir", "dir: -1 or 1");
        }
        return d.intValue();
    }

    /** an item by its code, barcode or PLU (the inactive too: the page shows them) */
    private static long item(Connection c, String code) throws SQLException {
        Object v = Db.rows(c, "select mm_core.find_item(?, 'N') id from dual", code.trim()).get(0).get("id");
        if (v == null) {
            throw new Http.Fail(404, "not_found", "Δεν βρέθηκε είδος: " + code.trim());
        }
        return ((BigDecimal) v).longValue();
    }
}
