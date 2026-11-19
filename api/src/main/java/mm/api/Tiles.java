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
 *   POST /api/tiles/options {name, pick, required, active}       a new group of options (pick O: one of
 *                                              them, M: any; required: a group O)
 *   POST /api/tiles/options/{id} {name, pick, required, active}  a group of options changed
 *   POST /api/tiles/options/{id}/move {dir}    /delete   (used on a receipt: not, inactive instead)
 *   POST /api/tiles/options/{id}/add {name, price, default}       an option into the group
 *   POST /api/tiles/option/{id} {name, price, default, active}    an option changed
 *   POST /api/tiles/option/{id}/move {dir}     /delete
 *   POST /api/tiles/item-options {code, group_id, on}   a group of options on an item (on: true) or off
 *   POST /api/tiles/recipe {code, component, qty}      the recipe of an item (a kit never assembled: a sale
 *                                              takes its materials): a material (its code) and how much
 *                                              of it (0: out)
 *   POST /api/tiles/option/{id}/component {component, qty}   the materials of an option: more (qty > 0)
 *                                              or less of one of the recipe (< 0); 0: out
 * </pre>
 * The page: the recipe of each tile ("recipe", its cost by the last price of each material "recipe_cost"),
 * the materials of each option ("components").
 * The till: each tile has the ids of its groups of options ("option_groups"), the groups with their active
 * options in "options". The page: every group of options, its options, and the groups of each tile.
 * Each POST returns the page again, as GET /api/tiles.
 */
final class Tiles {
    private Tiles() {
    }

    private static final String TILES = """
            select t.id, t.group_id, t.item_id, i.code, i.name, i.price, i.plu, i.active
            from mm_tile t join mm_item i on i.id = t.item_id
            order by t.sort_no, t.id""";

    /** the groups of options of each item (active only: the till; all: the page), in their order */
    private static Map<Object, List<Object>> itemGroups(Connection c, boolean activeOnly) throws SQLException {
        Map<Object, List<Object>> out = new LinkedHashMap<>();
        for (Map<String, Object> r : Db.rows(c, """
                select io.item_id, g.id from mm_item_option io join mm_option_group g on g.id = io.group_id
                where (? = 'N' or g.active = 'Y') order by g.sort_no, g.id""", activeOnly ? "Y" : "N")) {
            out.computeIfAbsent(r.get("item_id"), k -> new ArrayList<>()).add(r.get("id"));
        }
        return out;
    }

    /** the groups of options with their options (activeOnly: the till) */
    private static List<Map<String, Object>> optionGroups(Connection c, boolean activeOnly) throws SQLException {
        String a = activeOnly ? "Y" : "N";
        List<Map<String, Object>> groups = Db.rows(c, """
                select id, name, pick, required, active from mm_option_group
                where (? = 'N' or active = 'Y') order by sort_no, id""", a);
        List<Map<String, Object>> opts = Db.rows(c, """
                select id, group_id, name, price, is_default, active,
                       (select count(*) from mm_doc_line_option x where x.option_id = o.id) used
                from mm_option o where (? = 'N' or active = 'Y') order by sort_no, id""", a);
        for (Map<String, Object> g : groups) {
            List<Map<String, Object>> mine = new ArrayList<>();
            for (Map<String, Object> o : opts) {
                if (o.get("group_id").equals(g.get("id"))) {
                    mine.add(o);
                }
            }
            g.put("options", mine);
        }
        return groups;
    }

    private static void withGroups(List<Map<String, Object>> tiles, Map<Object, List<Object>> ig) {
        for (Map<String, Object> t : tiles) {
            t.put("option_groups", ig.getOrDefault(t.get("item_id"), List.of()));
        }
    }

    /** the till: the active groups, their tiles of active items; the most sold of the last 7 days */
    static Map<String, Object> forTill(Connection c) throws SQLException {
        List<Map<String, Object>> groups = Db.rows(c,
                "select id, name, color from mm_tile_group where active = 'Y' order by sort_no, id");
        List<Map<String, Object>> tiles = Db.rows(c, TILES);
        Map<Object, List<Object>> ig = itemGroups(c, true);
        withGroups(tiles, ig);
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
        withGroups(frequent, ig);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("groups", groups);
        out.put("frequent", frequent);
        out.put("options", optionGroups(c, true));
        return out;
    }

    /** the page: every group, its tiles */
    static Map<String, Object> page(Connection c) throws SQLException {
        List<Map<String, Object>> groups = Db.rows(c,
                "select id, name, color, active from mm_tile_group order by sort_no, id");
        List<Map<String, Object>> tiles = Db.rows(c, TILES);
        withGroups(tiles, itemGroups(c, false));
        List<Map<String, Object>> recipe = Db.rows(c, """
                select k.kit_id item_id, i.id component_id, i.code, i.name, i.unit, k.qty, i.cost
                from mm_kit_component k join mm_item i on i.id = k.component_id order by i.code""");
        for (Map<String, Object> t : tiles) {
            List<Map<String, Object>> mine = new ArrayList<>();
            BigDecimal cost = BigDecimal.ZERO;
            for (Map<String, Object> r : recipe) {
                if (r.get("item_id").equals(t.get("item_id"))) {
                    mine.add(r);
                    cost = cost.add(((BigDecimal) r.get("qty")).multiply((BigDecimal) r.get("cost")));
                }
            }
            t.put("recipe", mine);
            t.put("recipe_cost", mine.isEmpty() ? null : cost.setScale(2, java.math.RoundingMode.HALF_UP));
        }
        for (Map<String, Object> g : groups) {
            List<Map<String, Object>> mine = new ArrayList<>();
            for (Map<String, Object> t : tiles) {
                if (t.get("group_id").equals(g.get("id"))) {
                    mine.add(t);
                }
            }
            g.put("tiles", mine);
        }
        List<Map<String, Object>> options = optionGroups(c, false);
        List<Map<String, Object>> comps = Db.rows(c, """
                select oc.option_id, i.id component_id, i.code, i.name, i.unit, oc.qty, i.cost
                from mm_option_component oc join mm_item i on i.id = oc.component_id order by i.code""");
        for (Map<String, Object> g : options) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> os = (List<Map<String, Object>>) g.get("options");
            for (Map<String, Object> o : os) {
                List<Map<String, Object>> mine = new ArrayList<>();
                for (Map<String, Object> x : comps) {
                    if (x.get("option_id").equals(o.get("id"))) {
                        mine.add(x);
                    }
                }
                o.put("components", mine);
            }
        }
        return Map.of("groups", groups, "options", options);
    }

    static Object post(Connection c, String[] p, Map<String, Object> in) throws SQLException {
        int n = p.length;
        if (n == 2 && "recipe".equals(p[1])) {
            long item = item(c, Http.text(in, "code", true));
            long comp = item(c, Http.text(in, "component", true));
            Db.exec(c, "begin mm_core.set_component(?, ?, ?); end;", item, comp, qtyOf(in));
            return page(c);
        }
        if (n == 2 && "item-options".equals(p[1])) {
            long item = item(c, Http.text(in, "code", true));
            BigDecimal g = Http.decimal(in, "group_id", null);
            if (g == null) {
                throw new Http.Fail(400, "missing", "group_id");
            }
            Db.exec(c, "begin mm_core.item_option(?, ?, ?); end;", item, g, yes(in.get("on")) ? "Y" : "N");
            return page(c);
        }
        if (n >= 2 && "options".equals(p[1])) {
            if (n == 2 || n == 3) {
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.option_group_save(?, ?, ?, ?, ?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    if (n == 3) {
                        cs.setLong(2, Http.id(p[2]));
                    } else {
                        cs.setNull(2, Types.NUMERIC);
                    }
                    cs.setString(3, Http.text(in, "name", false));
                    cs.setString(4, Http.text(in, "pick", false));
                    cs.setString(5, flag(in, "required"));
                    cs.setString(6, flag(in, "active"));
                    cs.execute();
                }
                return page(c);
            }
            long g = Http.id(p[2]);
            if (n == 4) {
                switch (p[3]) {
                    case "move" -> {
                        Db.exec(c, "begin mm_core.option_move('G', ?, ?); end;", g, dir(in));
                        return page(c);
                    }
                    case "delete" -> {
                        Db.exec(c, "begin mm_core.option_group_delete(?); end;", g);
                        return page(c);
                    }
                    case "add" -> {
                        saveOption(c, null, g, in);
                        return page(c);
                    }
                    default -> {
                    }
                }
            }
            throw new Http.Fail(404, "not_found", "no such endpoint");
        }
        if (n >= 3 && "option".equals(p[1])) {
            long o = Http.id(p[2]);
            if (n == 3) {
                saveOption(c, o, null, in);
                return page(c);
            }
            if (n == 4 && "move".equals(p[3])) {
                Db.exec(c, "begin mm_core.option_move('O', ?, ?); end;", o, dir(in));
                return page(c);
            }
            if (n == 4 && "delete".equals(p[3])) {
                Db.exec(c, "begin mm_core.option_delete(?); end;", o);
                return page(c);
            }
            if (n == 4 && "component".equals(p[3])) {
                long comp = item(c, Http.text(in, "component", true));
                Db.exec(c, "begin mm_core.option_component(?, ?, ?); end;", o, comp, qtyOf(in));
                return page(c);
            }
            throw new Http.Fail(404, "not_found", "no such endpoint");
        }
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

    private static void saveOption(Connection c, Long id, Long group, Map<String, Object> in) throws SQLException {
        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.option_save(?, ?, ?, ?, ?, ?); end;")) {
            cs.registerOutParameter(1, Types.NUMERIC);
            if (id == null) {
                cs.setNull(2, Types.NUMERIC);
            } else {
                cs.setLong(2, id);
            }
            if (group == null) {
                cs.setNull(3, Types.NUMERIC);
            } else {
                cs.setLong(3, group);
            }
            cs.setString(4, Http.text(in, "name", false));
            cs.setBigDecimal(5, Http.decimal(in, "price", null));
            cs.setString(6, flag(in, "default"));
            cs.setString(7, flag(in, "active"));
            cs.execute();
        }
    }

    /** true / "Y" -> Y, false / "N" -> N, absent -> null (as it is) */
    private static String flag(Map<String, Object> in, String k) {
        Object v = in.get(k);
        return v == null ? null : yes(v) ? "Y" : "N";
    }

    private static boolean yes(Object v) {
        return Boolean.TRUE.equals(v) || "Y".equals(v) || "true".equals(v);
    }

    private static BigDecimal qtyOf(Map<String, Object> in) {
        BigDecimal q = Http.decimal(in, "qty", null);
        if (q == null) {
            throw new Http.Fail(400, "missing", "qty");
        }
        return q;
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
