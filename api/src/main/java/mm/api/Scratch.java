package mm.api;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The scratch tickets (σκρατς): bought in packs (e.g. 300 of 1 €), sold one by one by the barcode of each
 * ticket (its game 4 digits, its pack 7, its number 3: its serial too, MM_SCRATCH_GAME and mm_core.load_pack
 * of db/MM_CORE.sql). MANAGER; a prize at the till: Pos (/api/pos/{register}/prize).
 *
 * <pre>
 *   GET  /api/scratch                         the games, the packs (tickets, sold, left), the prizes by day
 *   POST /api/scratch/games {game, code, pack_size}   a game (έκδοση) and the item it is sold as
 *   POST /api/scratch/packs {code, count}     a pack loaded: the barcode of one of its tickets (14 digits)
 *                                             or its game and pack (11); count: else the size of its game
 * </pre>
 */
final class Scratch {
    private Scratch() {
    }

    static Map<String, Object> get(Connection c) throws SQLException {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("games", Db.rows(c, """
                select g.game, g.pack_size, i.id item_id, i.code, i.name, i.price,
                       (select count(*) from mm_serial s where s.item_id = g.item_id and s.status = 'A'
                          and s.serial like g.game || '%') left_
                from mm_scratch_game g join mm_item i on i.id = g.item_id order by g.game"""));
        out.put("packs", Db.rows(c, """
                select game, pack, code, name, price, tickets, sold, left_, loaded_at, last_sold
                from mm_scratch_pack order by loaded_at desc, game, pack fetch first 100 rows only"""));
        // the prizes paid from the drawers (mm_core.scratch_prize), by day, the last 31 days
        out.put("prizes", Db.rows(c, """
                select trunc(move_at) day, count(*) prizes, -sum(amount) total
                from mm_cash_move where kind = 'OUT' and note like 'Κέρδος σκρατς%' and move_at > trunc(sysdate) - 31
                group by trunc(move_at) order by 1 desc"""));
        return out;
    }

    static Object post(Connection c, String[] p, Map<String, Object> in) throws SQLException {
        if (p.length == 2 && "games".equals(p[1])) {
            String code = Http.text(in, "code", true);
            Object item = Db.rows(c, "select mm_core.find_item(?) id from dual", code).get(0).get("id");
            if (item == null) {
                throw new Http.Fail(404, "not_found", "Δεν βρέθηκε είδος: " + code);
            }
            try (CallableStatement cs = c.prepareCall("begin mm_core.scratch_game(?, ?, ?); end;")) {
                cs.setString(1, Http.text(in, "game", true).trim());
                cs.setObject(2, item);
                cs.setBigDecimal(3, Http.decimal(in, "pack_size", BigDecimal.valueOf(300)));
                cs.execute();
            }
            return get(c);
        }
        if (p.length == 2 && "packs".equals(p[1])) {
            int n;
            try (CallableStatement cs = c.prepareCall("begin ? := mm_core.load_pack(?, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setString(2, Http.text(in, "code", true));
                BigDecimal count = Http.decimal(in, "count", null);
                if (count == null) {
                    cs.setNull(3, Types.NUMERIC);
                } else {
                    cs.setBigDecimal(3, count);
                }
                cs.execute();
                n = cs.getInt(1);
            }
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("loaded", n);
            out.putAll(get(c));
            return out;
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }
}
