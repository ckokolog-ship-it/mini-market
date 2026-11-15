package mm.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.sql.Connection;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The endpoints (all GET, JSON). Dates in and out as YYYY-MM-DD; a period: ?from=&to= (from the 1st of
 * January to today when not given).
 *
 * <pre>
 *   /api/health                                the service and its database
 *   /api/items?q=&limit=&offset=               the items (code, barcode, name, price, stock ...)
 *   /api/items/{barcode or code}               one item, as the till finds it, with what is reserved
 *   /api/customers?q=   /api/customers/{id}    the customers; one with its balance
 *   /api/suppliers?q=   /api/suppliers/{id}    the suppliers; one with its balance
 *   /api/ledger/{item|customer|supplier}/{id}  a ledger (MM_LEDGER): carry-over, moves, totals
 *   /api/reports/sales   /api/reports/vat   /api/reports/min-stock
 * </pre>
 */
final class Api {
    private static final int MAX_LIMIT = 500;
    private final Db db;

    Api(Db db) {
        this.db = db;
    }

    void register(HttpServer server) {
        server.createContext("/api/", this::handle);
    }

    private void handle(HttpExchange ex) throws IOException {
        // (not "try (ex)": that closes the exchange before a catch could send its error)
        try {
            String raw = ex.getRequestURI().getRawPath();
            String low = raw.toLowerCase();
            if (low.contains("..") || low.contains("%2e") || low.contains("%2f") || low.contains("//")) {
                throw new Http.Fail(400, "bad_path", "bad path");
            }
            if (!"GET".equals(ex.getRequestMethod())) {
                ex.getResponseHeaders().set("Allow", "GET");
                throw new Http.Fail(405, "method_not_allowed", "only GET");
            }
            String[] p = raw.substring("/api/".length()).split("/");
            Map<String, String> q = Http.query(ex);
            Object body;
            try (Connection c = db.connection()) {
                try {
                    body = route(c, p, q);
                } finally {
                    c.rollback();          // nothing here writes; the temporary rows of the session go
                }
            }
            Http.send(ex, 200, body);
        } catch (Http.Fail f) {
            Http.send(ex, f.status, Http.error(f.code, f.getMessage()));
        } catch (SQLException e) {
            Http.Fail f = Http.fromSql(e);
            Http.send(ex, f.status, Http.error(f.code, f.getMessage()));
        } catch (RuntimeException e) {
            System.err.println("== mm-api: " + e);
            Http.send(ex, 500, Http.error("internal", "internal error"));
        } finally {
            ex.close();
        }
    }

    private Object route(Connection c, String[] p, Map<String, String> q) throws SQLException {
        String head = p[0];
        int n = p.length;
        switch (head) {
            case "health" -> {
                if (n == 1) {
                    Db.rows(c, "select 1 from dual");
                    return Map.of("status", "ok", "db", "ok");
                }
            }
            case "items" -> {
                if (n == 1) {
                    return items(c, q);
                }
                if (n == 2) {
                    return item(c, java.net.URLDecoder.decode(p[1], java.nio.charset.StandardCharsets.UTF_8));
                }
            }
            case "customers", "suppliers" -> {
                String table = "customers".equals(head) ? "mm_customer" : "mm_supplier";
                String kind = "customers".equals(head) ? "C" : "S";
                if (n == 1) {
                    return partners(c, table, q);
                }
                if (n == 2) {
                    return partner(c, table, kind, Http.id(p[1]));
                }
            }
            case "ledger" -> {
                if (n == 3) {
                    String what = switch (p[1]) {
                        case "item" -> "I";
                        case "customer" -> "C";
                        case "supplier" -> "S";
                        default -> throw new Http.Fail(404, "not_found", "ledger: item, customer or supplier");
                    };
                    return ledger(c, what, Http.id(p[2]), q);
                }
            }
            case "reports" -> {
                if (n == 2) {
                    return report(c, p[1], q);
                }
            }
            default -> {
            }
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    private static LocalDate from(Map<String, String> q) {
        return Http.date(q, "from", LocalDate.now().withDayOfYear(1));
    }

    private static LocalDate to(Map<String, String> q) {
        return Http.date(q, "to", LocalDate.now());
    }

    private static String like(Map<String, String> q) {
        String s = q.getOrDefault("q", "").trim();
        return s.isEmpty() ? null : s;
    }

    private Object items(Connection c, Map<String, String> q) throws SQLException {
        String s = like(q);
        int limit = Http.number(q, "limit", 50, 1, MAX_LIMIT);
        int offset = Http.number(q, "offset", 0, 0, Integer.MAX_VALUE);
        List<Map<String, Object>> rows = Db.rows(c, """
                select i.id, i.code, i.barcode, i.name, c.name category, i.unit, i.vat_code, i.price,
                       i.wholesale_price, i.stock + 0 stock, i.min_stock, i.active, i.serial_tracked, i.kit
                from mm_item i join mm_category c on c.id = i.category_id
                where i.is_model = 'N'
                  and (? is null or upper(i.name) like '%' || upper(?) || '%' or i.code like upper(?) || '%'
                       or i.barcode = ?)
                order by i.code
                offset ? rows fetch next ? rows only""", s, s, s, s, offset, limit);
        return page(rows, limit, offset);
    }

    private Object item(Connection c, String code) throws SQLException {
        List<Map<String, Object>> id = Db.rows(c, "select mm_core.find_item(?, 'N') id from dual", code);
        Object v = id.get(0).get("id");
        if (v == null) {
            throw new Http.Fail(404, "not_found", "no item " + code);
        }
        List<Map<String, Object>> rows = Db.rows(c, """
                select i.id, i.code, i.barcode, i.name, c.name category, i.unit, i.vat_code, v.rate vat_rate,
                       i.price, i.wholesale_price, i.cost, i.stock + 0 stock, a.reserved, a.available, i.min_stock,
                       i.active, i.serial_tracked, i.kit, i.max_per_sale,
                       (select count(*) from mm_serial s where s.item_id = i.id and s.status = 'A') cards
                from mm_item i
                join mm_category c on c.id = i.category_id
                join mm_vat v on v.code = i.vat_code
                join mm_item_avail a on a.item_id = i.id
                where i.id = ?""", v);
        return rows.get(0);
    }

    private Object partners(Connection c, String table, Map<String, String> q) throws SQLException {
        String s = like(q);
        int limit = Http.number(q, "limit", 50, 1, MAX_LIMIT);
        int offset = Http.number(q, "offset", 0, 0, Integer.MAX_VALUE);
        List<Map<String, Object>> rows = Db.rows(c, "select id, name, afm, doy, address, phone, email, active from "
                + table + " where (? is null or upper(name) like '%' || upper(?) || '%' or afm = ?)"
                + " order by name offset ? rows fetch next ? rows only", s, s, s, offset, limit);
        return page(rows, limit, offset);
    }

    private Object partner(Connection c, String table, String kind, long id) throws SQLException {
        List<Map<String, Object>> rows = Db.rows(c, "select id, name, afm, doy, address, phone, email, active from "
                + table + " where id = ?", id);
        if (rows.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such id: " + id);
        }
        Map<String, Object> r = rows.get(0);
        List<Map<String, Object>> b = Db.rows(c, """
                select balance from table(mm_ledger.partner_rows(?, ?, date '1900-01-01', trunc(sysdate)))
                order by seq desc fetch first 1 rows only""", kind, id);
        r.put("balance", b.isEmpty() ? null : b.get(0).get("balance"));
        return r;
    }

    private Object ledger(Connection c, String what, long id, Map<String, String> q) throws SQLException {
        LocalDate f = from(q);
        LocalDate t = to(q);
        String title = (String) Db.rows(c, "select mm_ledger.title(?, ?) title from dual", what, id).get(0).get("title");
        if (title == null || title.endsWith(": ")) {
            throw new Http.Fail(404, "not_found", "no such id: " + id);
        }
        List<Map<String, Object>> rows = "I".equals(what)
                ? Db.rows(c, """
                        select seq, kind, ldate, doc_id, doc_text, partner, descr, debit, credit, balance
                        from table(mm_ledger.item_rows(?, ?, ?)) order by seq""", id, f, t)
                : Db.rows(c, """
                        select seq, kind, ldate, doc_id, doc_text, partner, descr, debit, credit, balance
                        from table(mm_ledger.partner_rows(?, ?, ?, ?)) order by seq""", what, id, f, t);
        java.math.BigDecimal debit = java.math.BigDecimal.ZERO;
        java.math.BigDecimal credit = java.math.BigDecimal.ZERO;
        for (Map<String, Object> r : rows) {
            if ("M".equals(r.get("kind"))) {
                debit = debit.add(r.get("debit") == null ? java.math.BigDecimal.ZERO : (java.math.BigDecimal) r.get("debit"));
                credit = credit.add(r.get("credit") == null ? java.math.BigDecimal.ZERO : (java.math.BigDecimal) r.get("credit"));
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("title", title);
        out.put("from", f.toString());
        out.put("to", t.toString());
        out.put("open", rows.get(0).get("balance"));
        out.put("debit", debit);
        out.put("credit", credit);
        out.put("close", rows.get(rows.size() - 1).get("balance"));
        out.put("rows", rows);
        return out;
    }

    private Object report(Connection c, String name, Map<String, String> q) throws SQLException {
        LocalDate f = from(q);
        LocalDate t = to(q);
        Map<String, Object> out = new LinkedHashMap<>();
        switch (name) {
            case "sales" -> {
                out.put("from", f.toString());
                out.put("to", t.toString());
                out.put("rows", Db.rows(c, """
                        select day, alp_docs, alp_total, tpy_total, ppy_total, total
                        from mm_sales_day where day between ? and ? order by day""", f, t));
            }
            case "vat" -> {
                out.put("from", f.toString());
                out.put("to", t.toString());
                out.put("rows", Db.rows(c, """
                        select to_char(day, 'YYYY-MM') month, vat_code, vat_rate, sum(s_net) s_net, sum(s_vat) s_vat,
                               sum(p_net) p_net, sum(p_vat) p_vat, sum(s_vat) - sum(p_vat) payable
                        from mm_vat_day where day between ? and ?
                        group by to_char(day, 'YYYY-MM'), vat_code, vat_rate order by 1, 2""", f, t));
            }
            case "min-stock" -> out.put("rows", Db.rows(c, """
                    select category, code, name, unit, stock, min_stock, missing, supplier
                    from mm_min_stock order by category, code"""));
            default -> throw new Http.Fail(404, "not_found", "reports: sales, vat or min-stock");
        }
        return out;
    }

    private static Object page(List<Map<String, Object>> rows, int limit, int offset) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("limit", limit);
        out.put("offset", offset);
        out.put("rows", rows);
        return out;
    }
}
