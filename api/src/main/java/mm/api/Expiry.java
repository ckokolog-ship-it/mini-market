package mm.api;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The expiry of the goods (λήξεις): the date of each line of goods received (Docs: {expires}), what is
 * left of it by FIFO (MM_EXPIRY of db/MM_REPORT.sql); those expiring in the next days or expired; what
 * is left of one taken out of the stock (a move of the stock by hand). MANAGER.
 *
 * <pre>
 *   GET  /api/expiry?days=N&warehouse=CODE      expired, and expiring in N days (default MM_SETTING
 *                                               EXPIRY_DAYS, else 7): rows (each with its warehouse), days;
 *                                               of one warehouse (none: all)
 *   POST /api/expiry/withdraw {fifo_id, qty}    out of the stock of its warehouse (qty: default what is
 *                                               left of it); {line_id}: the first of that receipt
 * </pre>
 */
final class Expiry {
    private Expiry() {
    }

    /** the days ahead the shop wants to see (MM_SETTING EXPIRY_DAYS, else 7) */
    static int days(Connection c) throws SQLException {
        Object v = Db.rows(c, """
                select to_number(max(value) default null on conversion error) n
                from mm_setting where name = 'EXPIRY_DAYS'""").get(0).get("n");
        return v == null ? 7 : Math.max(0, Math.min(365, ((BigDecimal) v).intValue()));
    }

    static Map<String, Object> get(Connection c, Map<String, String> q) throws SQLException {
        int n = Http.number(q, "days", days(c), 0, 365);
        String wh = q.get("warehouse") == null || q.get("warehouse").isBlank() ? null : q.get("warehouse").trim();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("days", n);
        out.put("warehouse", wh);
        out.put("rows", Db.rows(c, """
                select item_id, code, name, unit, category, fifo_id, line_id, warehouse_id, warehouse, warehouse_name,
                       expires, days_left, qty, left_, doc_id, doc_type, doc_no, doc_date, supplier
                from mm_expiry where days_left <= ? and (? is null or warehouse = upper(?))
                order by expires, code, warehouse""", n, wh, wh));
        return out;
    }

    static Object post(Connection c, String[] p, Map<String, Object> in) throws SQLException {
        if (p.length == 2 && "withdraw".equals(p[1])) {
            Object fifo = in.get("fifo_id");
            Object line = in.get("line_id");
            if (!(fifo instanceof Number) && !(line instanceof Number)) {
                throw new Http.Fail(400, "missing", "fifo_id");
            }
            List<Map<String, Object>> r = fifo instanceof Number f ? Db.rows(c, """
                    select item_id, code, left_, to_char(expires, 'DD/MM/YYYY') expires, doc_type, doc_no, warehouse_id
                    from mm_expiry where fifo_id = ?""", f.longValue()) : Db.rows(c, """
                    select item_id, code, left_, to_char(expires, 'DD/MM/YYYY') expires, doc_type, doc_no, warehouse_id
                    from mm_expiry where line_id = ? order by fifo_id fetch first 1 row only""", ((Number) line).longValue());
            if (r.isEmpty()) {
                throw new Http.Fail(404, "not_found", "Δεν μένει τίποτα από αυτή την παραλαβή");
            }
            Map<String, Object> x = r.get(0);
            BigDecimal left = (BigDecimal) x.get("left_");
            BigDecimal qty = Http.decimal(in, "qty", left);
            if (qty.signum() <= 0 || qty.compareTo(left) > 0) {
                throw new Http.Fail(400, "bad_number", "qty: πάνω από 0, έως " + left.toPlainString());
            }
            try (CallableStatement cs = c.prepareCall("begin mm_core.adjust_stock(?, ?, ?, ?); end;")) {
                cs.setObject(1, x.get("item_id"));
                cs.setBigDecimal(2, qty.negate());
                cs.setString(3, "Απόσυρση: λήξη " + x.get("expires") + " (" + x.get("doc_type") + " " + x.get("doc_no") + ")");
                cs.setObject(4, x.get("warehouse_id"));            // (out of its warehouse)
                cs.execute();
            }
            // the stock is reservable: this transaction reads it without its own change, so the move is
            // committed before the list is read again (the move is all of this call)
            c.commit();
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("withdrawn", qty);
            out.put("code", x.get("code"));
            out.putAll(get(c, Map.of()));
            return out;
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }
}
