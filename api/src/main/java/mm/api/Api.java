package mm.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * The endpoints (JSON). Dates in and out as YYYY-MM-DD; a period: ?from=&to= (from the 1st of January to
 * today when not given). A login first (POST /api/auth/login): then "Authorization: Bearer <token>" on
 * every call but /api/health. The roles: CASHIER (the items, the counts), MANAGER (and the customers,
 * the suppliers, the ledgers, the reports, a count started, posted, cancelled), ADMIN (all).
 *
 * <pre>
 *   POST /api/auth/login {username, password}  its token (12 hours), role       (anyone)
 *   POST /api/auth/logout   GET /api/auth/me   the end of the session; who it is
 *   /api/health                                the service and its database   (anyone)
 *   /api/items?q=&limit=&offset=               the items (code, barcode, name, price, stock ...)
 *   /api/items/{barcode or code}               one item, as the till finds it, with what is reserved
 *   /api/customers?q=   /api/customers/{id}    the customers; one with its balance
 *   /api/suppliers?q=   /api/suppliers/{id}    the suppliers; one with its balance
 *   /api/ledger/{item|customer|supplier}/{id}  a ledger (MM_LEDGER): carry-over, moves, totals;
 *                                              with ?limit=&offset= a page of its moves, its carry_in, carry_out
 *   /api/reports/sales   /api/reports/vat   /api/reports/min-stock
 *   GET /api/counts   GET /api/counts/{id}      the counts of the stock; one with its lines
 *   POST /api/counts {name}                     a new count                    (MANAGER)
 *   POST /api/counts/{id}/scan {code, qty, mode ADD|SET, device}   a scan of a phone
 *   POST /api/counts/{id}/post   .../cancel     the count to the stock, or dropped (MANAGER)
 *   /api/pos/...                               the till: see Pos
 *   /api/orders/...                            the orders: see Orders
 *   /api/shop/...                              the page of the customers, no login: see Shop
 *   /api/docs/..., /api/doc-types, /api/payments/...   the office: invoices, notes, receipts (MANAGER): see Docs
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

    /** who is calling: from the token of the request (MM_AUTH) */
    record User(long id, String username, String role, String token) {
        boolean atLeast(String r) {
            return rank(role) >= rank(r);
        }

        private static int rank(String r) {
            return switch (r) {
                case "ADMIN" -> 3;
                case "MANAGER" -> 2;
                default -> 1;
            };
        }
    }

    /**
     * The origins of other pages that may call the service (CORS): the app of Android (its pages from the
     * phone itself, http://localhost). MM_API_CORS: others, by commas; "none": no other.
     */
    private static final java.util.Set<String> ORIGINS = origins(Main.env("MM_API_CORS", "http://localhost"));

    static java.util.Set<String> origins(String v) {
        java.util.Set<String> out = new java.util.HashSet<>();
        for (String o : v.split(",")) {
            String t = o.trim().replaceAll("/+$", "");
            if (!t.isEmpty() && !"none".equalsIgnoreCase(t)) {
                out.add(t);
            }
        }
        return out;
    }

    private void handle(HttpExchange ex) throws IOException {
        // (not "try (ex)": that closes the exchange before a catch could send its error)
        try {
            String origin = ex.getRequestHeaders().getFirst("Origin");
            if (origin != null && ORIGINS.contains(origin)) {
                var h = ex.getResponseHeaders();
                h.set("Access-Control-Allow-Origin", origin);
                h.set("Vary", "Origin");
                if ("OPTIONS".equals(ex.getRequestMethod())) {          // the question before a call
                    h.set("Access-Control-Allow-Methods", "GET, POST");
                    h.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
                    h.set("Access-Control-Max-Age", "600");
                    ex.sendResponseHeaders(204, -1);
                    return;
                }
            }
            String raw = ex.getRequestURI().getRawPath();
            String low = raw.toLowerCase();
            if (low.contains("..") || low.contains("%2e") || low.contains("%2f") || low.contains("//")) {
                throw new Http.Fail(400, "bad_path", "bad path");
            }
            String method = ex.getRequestMethod();
            if (!"GET".equals(method) && !"POST".equals(method)) {
                ex.getResponseHeaders().set("Allow", "GET, POST");
                throw new Http.Fail(405, "method_not_allowed", "GET or POST");
            }
            String[] p = raw.substring("/api/".length()).split("/");
            Map<String, String> q = Http.query(ex);
            Map<String, Object> in = "POST".equals(method) ? Http.body(ex) : Map.of();
            Object body;
            try (Connection c = db.connection()) {
                try {
                    if ("POST".equals(method) && p.length == 2 && "auth".equals(p[0]) && "login".equals(p[1])) {
                        body = login(c, in, ex);
                    } else if ("GET".equals(method) && p.length == 1 && "health".equals(p[0])) {
                        body = route(c, null, p, q);
                    } else if ("shop".equals(p[0])) {         // the page of the customers: no login
                        body = "POST".equals(method) ? Shop.post(c, p, in, ex.getRemoteAddress().getAddress().getHostAddress())
                                : Shop.get(c, p, q);
                    } else {
                        User u = user(c, ex);
                        body = "POST".equals(method) ? post(c, u, p, in) : route(c, u, p, q);
                    }
                    c.commit();            // what a POST wrote (a GET: only the last_seen of its session)
                } catch (SQLException | RuntimeException e) {
                    c.rollback();
                    throw e;
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

    /** the token of "Authorization: Bearer ..." checked by the database; else 401 */
    private static User user(Connection c, HttpExchange ex) throws SQLException {
        String h = ex.getRequestHeaders().getFirst("Authorization");
        if (h == null || !h.startsWith("Bearer ")) {
            throw new Http.Fail(401, "auth_required", "login first: POST /api/auth/login");
        }
        String token = h.substring("Bearer ".length()).trim();
        try (CallableStatement cs = c.prepareCall("begin mm_auth.check_token(?, ?, ?, ?); end;")) {
            cs.setString(1, token);
            cs.registerOutParameter(2, Types.NUMERIC);
            cs.registerOutParameter(3, Types.VARCHAR);
            cs.registerOutParameter(4, Types.VARCHAR);
            cs.execute();
            return new User(cs.getLong(2), cs.getString(3), cs.getString(4), token);
        }
    }

    private static void need(User u, String role) {
        if (!u.atLeast(role)) {
            throw new Http.Fail(403, "forbidden", "only " + role + " or above");
        }
    }

    private static String client(HttpExchange ex) {
        String ua = ex.getRequestHeaders().getFirst("User-Agent");
        String s = ex.getRemoteAddress().getAddress().getHostAddress() + (ua == null ? "" : " " + ua);
        return s.length() > 60 ? s.substring(0, 60) : s;
    }

    private Object login(Connection c, Map<String, Object> in, HttpExchange ex) throws SQLException {
        String name = Http.text(in, "username", true);
        try (CallableStatement cs = c.prepareCall("begin mm_auth.login(?, ?, ?, ?, ?, ?); end;")) {
            cs.setString(1, name);
            cs.setString(2, Http.text(in, "password", true));
            cs.setString(3, client(ex));
            cs.registerOutParameter(4, Types.VARCHAR);
            cs.registerOutParameter(5, Types.VARCHAR);
            cs.registerOutParameter(6, Types.TIMESTAMP);
            cs.execute();
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("token", cs.getString(4));
            out.put("username", name.toLowerCase(java.util.Locale.ROOT));
            out.put("role", cs.getString(5));
            out.put("expires", cs.getTimestamp(6).toLocalDateTime().toString());
            return out;
        }
    }

    /** the calls that write */
    private Object post(Connection c, User u, String[] p, Map<String, Object> in) throws SQLException {
        int n = p.length;
        if ("auth".equals(p[0]) && n == 2 && "logout".equals(p[1])) {
            try (CallableStatement cs = c.prepareCall("begin mm_auth.logout(?); end;")) {
                cs.setString(1, u.token());
                cs.execute();
            }
            return Map.of("ok", true, "username", u.username());
        }
        if ("pos".equals(p[0])) {
            return Pos.post(c, p, in);
        }
        if ("orders".equals(p[0])) {
            return Orders.post(c, u, p, in);
        }
        if ("docs".equals(p[0]) || "payments".equals(p[0])) {
            need(u, "MANAGER");
            return Docs.post(c, p, in);
        }
        if ("counts".equals(p[0])) {
            if (n == 1) {
                need(u, "MANAGER");
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.start_count(?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setString(2, Http.text(in, "name", false));
                    cs.execute();
                    return count(c, cs.getLong(1));
                }
            }
            if (n == 3) {
                long id = Http.id(p[1]);
                switch (p[2]) {
                    case "scan" -> {
                        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.scan(?, ?, ?, ?, ?); end;")) {
                            cs.registerOutParameter(1, Types.NUMERIC);
                            cs.setLong(2, id);
                            cs.setString(3, Http.text(in, "code", true));
                            cs.setBigDecimal(4, Http.decimal(in, "qty", java.math.BigDecimal.ONE));
                            cs.setString(5, Optional.ofNullable(Http.text(in, "mode", false)).orElse("ADD").toUpperCase());
                            String dev = Optional.ofNullable(Http.text(in, "device", false)).orElse(u.username());
                            cs.setString(6, dev.length() > 40 ? dev.substring(0, 40) : dev);
                            cs.execute();
                            return Db.rows(c, """
                                    select l.id line_id, i.id item_id, i.code, i.name, i.unit, l.counted_qty,
                                           l.system_qty, l.counted_qty - l.system_qty diff, l.device
                                    from mm_count_line l join mm_item i on i.id = l.item_id
                                    where l.count_id = ? and l.item_id = ?""", id, cs.getLong(1)).get(0);
                        }
                    }
                    case "post", "cancel" -> {
                        need(u, "MANAGER");
                        try (CallableStatement cs = c.prepareCall("post".equals(p[2])
                                ? "begin mm_core.post_count(?); end;" : "begin mm_core.cancel_count(?); end;")) {
                            cs.setLong(1, id);
                            cs.execute();
                        }
                        return count(c, id);
                    }
                    default -> {
                    }
                }
            }
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    private Object count(Connection c, long id) throws SQLException {
        List<Map<String, Object>> h = Db.rows(c, """
                select id, name, status, created_at, posted_at from mm_count where id = ?""", id);
        if (h.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such count: " + id);
        }
        Map<String, Object> out = h.get(0);
        out.put("lines", Db.rows(c, """
                select l.id line_id, i.id item_id, i.code, i.name, i.unit, l.counted_qty, l.system_qty,
                       l.counted_qty - l.system_qty diff, l.scanned_at, l.device
                from mm_count_line l join mm_item i on i.id = l.item_id
                where l.count_id = ? order by i.code""", id));
        return out;
    }

    private Object route(Connection c, User u, String[] p, Map<String, String> q) throws SQLException {
        String head = p[0];
        int n = p.length;
        switch (head) {
            case "health" -> {
                if (n == 1) {
                    Db.rows(c, "select 1 from dual");
                    return Map.of("status", "ok", "db", "ok");
                }
            }
            case "auth" -> {
                if (n == 2 && "me".equals(p[1])) {
                    return Map.of("username", u.username(), "role", u.role());
                }
            }
            case "pos" -> {
                return Pos.get(c, p);
            }
            case "orders" -> {
                return Orders.get(c, p, q);
            }
            case "docs", "doc-types", "payments" -> {
                need(u, "MANAGER");
                return Docs.get(c, p, q);
            }
            case "counts" -> {
                if (n == 1) {
                    return Map.of("rows", Db.rows(c, """
                            select c.id, c.name, c.status, c.created_at, c.posted_at,
                                   (select count(*) from mm_count_line l where l.count_id = c.id) lines
                            from mm_count c
                            where c.status = 'O' or c.created_at > sysdate - 90
                            order by c.id desc"""));
                }
                if (n == 2) {
                    return count(c, Http.id(p[1]));
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
                need(u, "MANAGER");
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
                need(u, "MANAGER");
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
                need(u, "MANAGER");
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
        String where = """
                from mm_item i join mm_category c on c.id = i.category_id
                where i.is_model = 'N'
                  and (? is null or upper(i.name) like '%' || upper(?) || '%' or i.code like upper(?) || '%'
                       or i.barcode = ?)""";
        List<Map<String, Object>> rows = Db.rows(c, """
                select i.id, i.code, i.barcode, i.name, c.name category, i.unit, i.vat_code, i.price,
                       i.wholesale_price, i.stock + 0 stock, i.min_stock, i.active, i.serial_tracked, i.kit
                """ + where + """
                order by i.code
                offset ? rows fetch next ? rows only""", s, s, s, s, offset, limit);
        Object total = Db.rows(c, "select count(*) n " + where, s, s, s, s).get(0).get("n");
        return page(rows, limit, offset, total);
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
        String where = " from " + table + " where (? is null or upper(name) like '%' || upper(?) || '%' or afm = ?)";
        List<Map<String, Object>> rows = Db.rows(c, "select id, name, afm, doy, address, phone, email, active" + where
                + " order by name offset ? rows fetch next ? rows only", s, s, s, offset, limit);
        Object total = Db.rows(c, "select count(*) n" + where, s, s, s).get(0).get("n");
        return page(rows, limit, offset, total);
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
        if (q.get("limit") == null) {
            out.put("rows", rows);                 // all of it: the carry-over row first, then the moves
            return out;
        }
        // a page of the moves (?limit=&offset=), as a page of the report: the totals before its first row
        // (from the carry-over) and with its last (to the carry-over)
        int limit = Http.number(q, "limit", 50, 1, MAX_LIMIT);
        List<Map<String, Object>> moves = rows.subList(1, rows.size());
        int lastPage = moves.isEmpty() ? 0 : (moves.size() - 1) / limit * limit;      // past the end: the last page
        int offset = Math.min(Http.number(q, "offset", 0, 0, Integer.MAX_VALUE) / limit * limit, lastPage);
        int end = Math.min(moves.size(), offset + limit);
        java.math.BigDecimal d = java.math.BigDecimal.ZERO;
        java.math.BigDecimal cr = java.math.BigDecimal.ZERO;
        Map<String, Object> in = null;
        Map<String, Object> last = null;
        for (int i = 0; i < end; i++) {
            if (i == offset) {
                in = carry(d, cr, i == 0 ? rows.get(0).get("balance") : moves.get(i - 1).get("balance"));
            }
            Map<String, Object> m = moves.get(i);
            d = d.add(m.get("debit") == null ? java.math.BigDecimal.ZERO : (java.math.BigDecimal) m.get("debit"));
            cr = cr.add(m.get("credit") == null ? java.math.BigDecimal.ZERO : (java.math.BigDecimal) m.get("credit"));
            last = m;
        }
        if (in == null) {                          // no moves at all
            in = carry(d, cr, rows.get(0).get("balance"));
        }
        out.put("limit", limit);
        out.put("offset", offset);
        out.put("total", moves.size());
        out.put("carry_in", in);
        out.put("carry_out", carry(d, cr, last == null ? rows.get(0).get("balance") : last.get("balance")));
        out.put("rows", new java.util.ArrayList<>(moves.subList(offset, end)));
        return out;
    }

    private static Map<String, Object> carry(Object debit, Object credit, Object balance) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("debit", debit);
        m.put("credit", credit);
        m.put("balance", balance);
        return m;
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

    private static Object page(List<Map<String, Object>> rows, int limit, int offset, Object total) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("limit", limit);
        out.put("offset", offset);
        out.put("total", total);
        out.put("rows", rows);
        return out;
    }
}
