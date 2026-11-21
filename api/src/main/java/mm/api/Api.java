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
 *   GET /api/auth/rights                       its menu and its rights (Rights: every call is checked by them)
 *   /api/health                                the service and its database   (anyone)
 *   /api/items?q=&limit=&offset=               the items (code, barcode, name, price, stock ...)
 *   /api/items/{barcode or code}               one item, as the till finds it, with what is reserved
 *   /api/customers?q=   /api/customers/{id}    the customers; one with its balance
 *   /api/suppliers?q=   /api/suppliers/{id}    the suppliers; one with its balance
 *   /api/ledger/{item|customer|supplier}/{id}  a ledger (MM_LEDGER): carry-over, moves, totals;
 *                                              with ?limit=&offset= a page of its moves, its carry_in, carry_out
 *   /api/reports/sales   /api/reports/vat   /api/reports/min-stock
 *   /api/scratch/...                           the scratch tickets in packs: see Scratch (MANAGER)
 *   /api/warehouses                            the warehouses (the main one first), what each has; an item: its
 *                                              stock in each. POST /api/warehouses {code, name}, /api/warehouses/{id}
 *                                              {name, active} (MANAGER)
 *   /api/warehouses/{id}                       a branch and its minimum stock: the items, what is missing,
 *                                              what the central store has; its drafts DEN. POST .../min
 *                                              {code, min} (0: none), POST .../transfer: what is missing,
 *                                              a draft DEN from the central store (MANAGER)
 *   /api/users   POST /api/users {username, full_name, role, password, warehouse_id, register_id}
 *   POST /api/users/{id} {full_name, role, active, password, unlock, warehouse_id, register_id}
 *                                              the users and where each works: its store, its register
 *                                              (mm_auth.set_place; the till: mm_auth.may_use) (ADMIN)
 *   /api/audit?from=&to=&user=&action=&q=&limit=&offset=   the history of what was done and the logins
 *                                              (MM_AUDIT_ALL), the newest first (AUDIT)
 *   /api/expiry?days=   POST /api/expiry/withdraw   the goods expiring, expired; one taken out (Expiry.java)
 *   /api/chart?to=&days=                       the charts of the sales: by day (and a year before), by hour
 *                                              (MANAGER, Chart.java)
 *   /api/day?date=                             the summary of a day: its Z, sales, VAT, items, scratch, orders,
 *                                              myDATA, minimum stock, backup (MANAGER, Day.java)
 *   /api/backup                              the last backup (db/backup.ps1, db/backup.sh): state OK, OLD, FAILED,
 *                                            NEVER; os: windows or linux, of this server (MANAGER)
 *   /api/reports/trial-items|trial-customers|trial-suppliers?from=&to=&all=1   the trial balances
 *   /api/reports/profit?from=&to=&method=   /api/reports/stock-value?method=   the gross profit, the value
 *                                              of the stock: FIFO or LAST (the cost of the last purchase)
 *   POST /api/reports/cost-method {method}     the way the shop counts its costs: FIFO or LAST
 *                                              (ισοζύγια): a row each with the totals of its ledger, no moves
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
    /** who is calling: from the token of the request (MM_AUTH); its rights (MM_RIGHTS, Rights) */
    record User(long id, String username, String role, String token, Map<String, String> rights) {
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
                        Rights.check(u, method, p);                  // the screen, the action of the call
                        // who and from where, for the history of what is done (MM_AUDIT: its triggers)
                        Db.exec(c, "begin dbms_session.set_identifier(?); dbms_application_info.set_module('mm-api', null); end;",
                                u.username());
                        body = "POST".equals(method) ? post(c, u, p, in) : Rights.mask(u, p, route(c, u, p, q));
                    }
                    c.commit();            // what a POST wrote (a GET: only the last_seen of its session)
                } catch (SQLException | RuntimeException e) {
                    c.rollback();
                    throw e;
                } finally {
                    try {                  // (the connection back to the pool: no one's)
                        Db.exec(c, "begin dbms_session.clear_identifier; dbms_application_info.set_module(null, null); end;");
                    } catch (SQLException e) {
                        System.err.println("== mm-api: " + e);
                    }
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
            return new User(cs.getLong(2), cs.getString(3), cs.getString(4), token, Rights.load(c, cs.getLong(2)));
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
            out.putAll(place(c, name));
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
            return Pos.post(c, u, p, in);
        }
        if ("orders".equals(p[0])) {
            return Orders.post(c, u, p, in);
        }
        if ("docs".equals(p[0]) || "payments".equals(p[0])) {
            return Docs.post(c, p, in);
        }
        if ("scratch".equals(p[0])) {
            return Scratch.post(c, p, in);
        }
        if ("tiles".equals(p[0])) {
            return Tiles.post(c, p, in);
        }
        if ("warehouses".equals(p[0])) {          // a new warehouse; one renamed, (not) active
            if (n == 1) {
                String code = String.valueOf(Http.text(in, "code", true)).trim().toUpperCase(java.util.Locale.ROOT);
                String name = String.valueOf(Http.text(in, "name", true)).trim();
                if (!code.matches("[A-Z0-9]{1,10}") || name.isEmpty() || name.length() > 60) {
                    throw new Http.Fail(400, "bad_warehouse", "code: 1 to 10 letters or digits (A-Z, 0-9); name: up to 60");
                }
                if (!Db.rows(c, "select id from mm_warehouse where code = ?", code).isEmpty()) {
                    throw new Http.Fail(400, "bad_warehouse", "Υπάρχει ήδη αποθήκη " + code);
                }
                Db.exec(c, "begin insert into mm_warehouse (code, name) values (?, ?); end;", code, name);
                return warehouses(c);
            }
            if (n == 3 && "min".equals(p[2])) {      // the minimum of an item there (0: none)
                long id = Http.id(p[1]);
                String code = String.valueOf(Http.text(in, "code", true)).trim();
                Object item = Db.rows(c, "select mm_core.find_item(?, 'N') id from dual", code).get(0).get("id");
                if (item == null) {
                    throw new Http.Fail(404, "not_found", "no item " + code);
                }
                Db.exec(c, "begin mm_core.set_min(?, ?, ?); end;", id, item,
                        Http.decimal(in, "min", java.math.BigDecimal.ZERO));
                return warehouseMin(c, id);
            }
            if (n == 3 && "transfer".equals(p[2])) { // what is missing, from the central store: a draft DEN
                long id = Http.id(p[1]);
                int lines;
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.transfer_missing(?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setLong(2, id);
                    cs.execute();
                    lines = cs.getInt(1);
                }
                Map<String, Object> out = new java.util.LinkedHashMap<>(warehouseMin(c, id));
                out.put("lines", lines);
                return out;
            }
            if (n == 2) {
                long id = Http.id(p[1]);
                List<Map<String, Object>> w = Db.rows(c, "select main from mm_warehouse where id = ?", id);
                if (w.isEmpty()) {
                    throw new Http.Fail(404, "not_found", "no such warehouse: " + id);
                }
                String name = Http.text(in, "name", false);
                if (name != null && !name.isBlank()) {
                    Db.exec(c, "begin update mm_warehouse set name = ? where id = ?; end;", name.trim(), id);
                }
                if (in.containsKey("active")) {
                    boolean on = Boolean.TRUE.equals(in.get("active"));
                    if (!on && "Y".equals(w.get(0).get("main"))) {
                        throw new Http.Fail(400, "bad_warehouse", "Η κεντρική αποθήκη μένει ενεργή");
                    }
                    Db.exec(c, "begin update mm_warehouse set active = ? where id = ?; end;", on ? "Y" : "N", id);
                }
                return warehouses(c);
            }
        }
        if ("roles".equals(p[0]) || "menu".equals(p[0])) {
            return Roles.post(c, p, in);
        }
        if ("users".equals(p[0]) && n == 3 && "roles".equals(p[2])) {   // the roles of a user (ROLES W: Rights)
            List<Map<String, Object>> r = Db.rows(c, "select username from mm_user where id = ?", Http.id(p[1]));
            if (r.isEmpty()) {
                throw new Http.Fail(404, "not_found", "no such user: " + p[1]);
            }
            Object codes = in.get("roles");
            if (!(codes instanceof List<?> l)) {
                throw new Http.Fail(400, "bad_roles", "roles: a list of the codes of roles");
            }
            Roles.userRoles(c, (String) r.get(0).get("username"), l);
            return users(c);
        }
        if ("users".equals(p[0])) {               // a new user; one changed: role, active, password, place
            // (its password, its place: actions of their own; an administrator, made or changed: only by one
            // who has all the rights, so that a right to the users is not a way to all of them)
            if (in.get("password") != null && n == 2) {
                Rights.need(u, "USERS", "PASSWORD", "W");
            }
            if (in.containsKey("warehouse_id") || in.containsKey("register_id")) {
                Rights.need(u, "USERS", "PLACE", "W");
            }
            boolean admin = "ADMIN".equalsIgnoreCase(String.valueOf(in.get("role"))) || n == 2 && !Db.rows(c, """
                    select 1 from mm_user_role ur join mm_role r on r.id = ur.role_id and r.all_rights = 'Y'
                    where ur.user_id = ?""", Http.id(p[1])).isEmpty();
            if (admin) {
                Rights.need(u, "ROLES", null, "W");
            }
            String name;
            if (n == 1) {
                name = String.valueOf(Http.text(in, "username", true)).trim().toLowerCase(java.util.Locale.ROOT);
                try (CallableStatement cs = c.prepareCall("begin ? := mm_auth.create_user(?, ?, ?, ?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setString(2, name);
                    cs.setString(3, Http.text(in, "full_name", false));
                    cs.setString(4, Http.text(in, "role", true));
                    cs.setString(5, Http.text(in, "password", true));
                    cs.execute();
                }
            } else if (n == 2) {
                List<Map<String, Object>> r = Db.rows(c, "select username from mm_user where id = ?", Http.id(p[1]));
                if (r.isEmpty()) {
                    throw new Http.Fail(404, "not_found", "no such user: " + p[1]);
                }
                name = (String) r.get(0).get("username");
                if (in.containsKey("full_name")) {
                    Db.exec(c, "begin update mm_user set full_name = ? where username = ?; end;", Http.text(in, "full_name", false), name);
                }
                if (in.get("role") != null) {
                    Db.exec(c, "begin mm_auth.set_role(?, ?); end;", name, Http.text(in, "role", true));
                }
                if (in.containsKey("active")) {
                    Db.exec(c, "begin mm_auth.set_active(?, ?); end;", name, Boolean.TRUE.equals(in.get("active")) ? "Y" : "N");
                }
                if (in.get("password") != null) {
                    Db.exec(c, "begin mm_auth.set_password(?, ?); end;", name, Http.text(in, "password", true));
                }
                if (Boolean.TRUE.equals(in.get("unlock"))) {
                    Db.exec(c, "begin mm_auth.unlock(?); end;", name);
                }
            } else {
                throw new Http.Fail(404, "not_found", "no such endpoint");
            }
            if (n == 1 || in.containsKey("warehouse_id") || in.containsKey("register_id")) {
                Object wh = in.get("warehouse_id");
                Object reg = in.get("register_id");
                Db.exec(c, "begin mm_auth.set_place(?, ?, ?); end;", name,
                        wh == null ? null : idOf(wh, "warehouse_id"), reg == null ? null : idOf(reg, "register_id"));
            }
            return users(c);
        }
        if ("reports".equals(p[0]) && n == 2 && "cost-method".equals(p[1])) {   // the way the costs are counted
            String m = String.valueOf(Http.text(in, "method", true)).trim().toUpperCase(java.util.Locale.ROOT);
            if (!"FIFO".equals(m) && !"LAST".equals(m)) {
                throw new Http.Fail(400, "bad_method", "method: FIFO or LAST");
            }
            Db.exec(c, """
                    merge into mm_setting s using (select 'COST_METHOD' name, ? value from dual) v on (s.name = v.name)
                    when matched then update set s.value = v.value
                    when not matched then insert (name, value) values (v.name, v.value)""", m);
            return Map.of("method", m);
        }
        if ("expiry".equals(p[0])) {
            return Expiry.post(c, p, in);
        }
        if ("customers".equals(p[0]) && n == 3 && "card".equals(p[2])) {   // a card for the points
            long id = Http.id(p[1]);
            Db.exec(c, "declare v varchar2(20); begin v := mm_core.new_card(?); end;", id);
            return partner(c, "mm_customer", "C", id);
        }
        if ("counts".equals(p[0])) {
            if (n == 1) {
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.start_count(?, ?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setString(2, Http.text(in, "name", false));
                    Object wh = in.get("warehouse_id");
                    if (wh instanceof Number w) {
                        cs.setLong(3, w.longValue());
                    } else {
                        cs.setNull(3, Types.NUMERIC);
                    }
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

    /** the history of what was done and the logins (MM_AUDIT_ALL), the newest first: from, to (days), user,
     *  action (its start, e.g. DOC_ or AUTH_), q (in what it was of, its detail); a page of it */
    @SuppressWarnings("unchecked")
    static Map<String, Object> audit(Connection c, Map<String, String> q) throws SQLException {
        int limit = Http.number(q, "limit", 50, 1, MAX_LIMIT);
        int offset = Http.number(q, "offset", 0, 0, Integer.MAX_VALUE);
        LocalDate to = Http.date(q, "to", LocalDate.now());
        LocalDate fr = Http.date(q, "from", to.minusDays(30));
        String user = Optional.ofNullable(q.get("user")).map(String::trim).filter(x -> !x.isEmpty()).orElse(null);
        String action = Optional.ofNullable(q.get("action")).map(x -> x.trim().toUpperCase(java.util.Locale.ROOT))
                .filter(x -> !x.isEmpty()).orElse(null);
        String text = Optional.ofNullable(q.get("q")).map(String::trim).filter(x -> !x.isEmpty()).orElse(null);
        String where = """
                 from mm_audit_all
                where at >= ? and at < ? + 1
                  and (? is null or lower(username) = lower(?))
                  and (? is null or action like ? || '%')
                  and (? is null or upper(ref_text || ' ' || detail) like '%' || upper(?) || '%')""";
        Object[] b = {fr, to, user, user, action, action, text, text};
        Object[] pg = java.util.Arrays.copyOf(b, b.length + 2);
        pg[b.length] = offset;
        pg[b.length + 1] = limit;
        Map<String, Object> out = new LinkedHashMap<>((Map<String, Object>) page(Db.rows(c,
                "select id, at, username, source, action, ref_type, ref_id, ref_text, detail" + where
                + " order by at desc, id desc offset ? rows fetch next ? rows only", pg), limit, offset,
                Db.rows(c, "select count(*) n" + where, b).get(0).get("n")));
        out.put("from", fr.toString());
        out.put("to", to.toString());
        out.put("users", Db.rows(c, "select distinct username from mm_audit_all where username is not null order by 1"));
        return out;
    }

    /** where a user works: its store (warehouse) and its register; null: everywhere */
    static Map<String, Object> place(Connection c, String username) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, """
                select u.warehouse_id, w.code warehouse, w.name warehouse_name, u.register_id, g.code register,
                       g.name register_name
                from mm_user u left join mm_warehouse w on w.id = u.warehouse_id left join mm_register g on g.id = u.register_id
                where u.username = lower(?)""", username);
        return r.isEmpty() ? Map.of() : r.get(0);
    }

    /** the users (no password): role, active, locked, store, register, the last login */
    static Map<String, Object> users(Connection c) throws SQLException {
        return Map.of("rows", Db.rows(c, """
                select u.id, u.username, u.full_name, u.role, u.active,
                       case when u.locked_until > sysdate then 'Y' else 'N' end locked,
                       u.warehouse_id, w.code warehouse, w.name warehouse_name, u.register_id, g.code register,
                       (select max(l.at) from mm_auth_log l where l.username = u.username and l.event = 'LOGIN') last_login,
                       (select listagg(r.code, ',') within group (order by r.system desc, r.id) from mm_user_role ur
                        join mm_role r on r.id = ur.role_id where ur.user_id = u.id) roles
                from mm_user u left join mm_warehouse w on w.id = u.warehouse_id left join mm_register g on g.id = u.register_id
                order by u.username"""));
    }

    private static long idOf(Object v, String name) {
        if (v instanceof Number x) {
            return x.longValue();
        }
        try {
            return Long.parseLong(String.valueOf(v).trim());
        } catch (NumberFormatException e) {
            throw new Http.Fail(400, "bad_" + name, name + ": a number");
        }
    }

    /** the warehouses (the main one first), with what each has: items with stock, its value by FIFO */
    static Map<String, Object> warehouses(Connection c) throws SQLException {
        return Map.of("rows", Db.rows(c, """
                select w.id, w.code, w.name, w.main, w.active,
                       (select count(*) from mm_warehouse_stock s where s.warehouse_id = w.id and s.stock <> 0) items,
                       (select nvl(sum(f.left_ * f.unit_cost), 0) from mm_fifo f where f.warehouse_id = w.id) value,
                       (select count(*) from mm_register r where nvl(r.warehouse_id, mm_core.main_warehouse) = w.id
                          and r.active = 'Y') registers,
                       case w.main when 'Y' then (select count(*) from mm_item i where i.active = 'Y' and i.is_model = 'N'
                                                    and i.kit = 'N' and i.stock + 0 < i.min_stock)   -- (as MM_MIN_STOCK)
                            else (select count(*) from mm_warehouse_min m
                                  left join mm_warehouse_stock s on s.item_id = m.item_id and s.warehouse_id = m.warehouse_id
                                  join mm_item i on i.id = m.item_id and i.active = 'Y'
                                  where m.warehouse_id = w.id and nvl(s.stock, 0) < m.min_stock) end under_min
                from mm_warehouse w
                order by case w.main when 'Y' then 0 else 1 end, w.code"""));
    }

    /** a branch and its minimum stock: the items with a minimum there (what it has, what is missing, what
     *  the central store has), the drafts DEN to it from the central store */
    static Map<String, Object> warehouseMin(Connection c, long id) throws SQLException {
        List<Map<String, Object>> w = Db.rows(c, "select id, code, name, main, active from mm_warehouse where id = ?", id);
        if (w.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such warehouse: " + id);
        }
        Map<String, Object> out = new java.util.LinkedHashMap<>();
        out.put("warehouse", w.get(0));
        out.put("rows", Db.rows(c, """
                select i.id item_id, i.code, i.name, i.unit, nvl(s.stock, 0) stock, m.min_stock,
                       greatest(m.min_stock - nvl(s.stock, 0), 0) missing,
                       nvl((select sum(k.qty) from mm_stock_move k where k.item_id = i.id
                              and k.warehouse_id = mm_core.main_warehouse), 0) central
                from mm_warehouse_min m
                join mm_item i on i.id = m.item_id
                left join mm_warehouse_stock s on s.item_id = m.item_id and s.warehouse_id = m.warehouse_id
                where m.warehouse_id = ?
                order by case when nvl(s.stock, 0) < m.min_stock then 0 else 1 end, i.code""", id));
        out.put("drafts", Db.rows(c, """
                select d.id, d.doc_date, d.total, (select count(*) from mm_doc_line l where l.doc_id = d.id) lines
                from mm_doc d
                where d.doc_type = 'DEN' and d.status = 'D' and d.to_warehouse_id = ?
                  and d.warehouse_id = mm_core.main_warehouse
                order by d.id""", id));
        return out;
    }

    private Object count(Connection c, long id) throws SQLException {
        List<Map<String, Object>> h = Db.rows(c, """
                select c.id, c.name, c.status, c.created_at, c.posted_at, c.warehouse_id, w.code warehouse, w.name warehouse_name
                from mm_count c left join mm_warehouse w on w.id = c.warehouse_id where c.id = ?""", id);
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
                if (n == 2 && "rights".equals(p[1])) {
                    return Rights.of(c, u);
                }
                if (n == 2 && "me".equals(p[1])) {
                    Map<String, Object> out = new LinkedHashMap<>();
                    out.put("username", u.username());
                    out.put("role", u.role());
                    out.putAll(place(c, u.username()));
                    return out;
                }
            }
            case "pos" -> {
                return Pos.get(c, u, p);
            }
            case "orders" -> {
                return Orders.get(c, p, q);
            }
            case "docs", "doc-types", "payments" -> {
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
            case "scratch" -> {
                if (n == 1) {
                    return Scratch.get(c);
                }
            }
            case "tiles" -> {               // the buttons of the till (the page Κουμπιά ταμείου)
                if (n == 1) {
                    return Tiles.page(c);
                }
            }
            case "warehouses" -> {          // the warehouses: the main one first
                if (n == 1) {
                    return warehouses(c);
                }
                if (n == 2) {               // a branch and its minimum stock
                    return warehouseMin(c, Http.id(p[1]));
                }
            }
            case "expiry" -> {
                if (n == 1) {
                    return Expiry.get(c, q);
                }
            }
            case "audit" -> {               // the history of what was done (MM_AUDIT_ALL)
                if (n == 1) {
                    return audit(c, q);
                }
            }
            case "roles", "menu" -> {       // the roles, their rights, the menu (Roles)
                return Roles.get(c, p);
            }
            case "users" -> {               // the users: their role, store, register (ADMIN)
                if (n == 1) {
                    return users(c);
                }
            }
            case "chart" -> {
                if (n == 1) {
                    return Chart.get(c, q);
                }
            }
            case "day" -> {
                if (n == 1) {
                    return Day.get(c, q);
                }
            }
            case "backup" -> {
                if (n == 1) {
                    Map<String, Object> b = new LinkedHashMap<>(
                            Db.rows(c, "select state, days, ok_at, ok_file, failed_at, error from mm_backup_state").get(0));
                    // the system of this server: the pages say the command of the backup there
                    b.put("os", System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).contains("win") ? "windows" : "linux");
                    return b;
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
        Map<String, Object> out = rows.get(0);
        // its stock in each warehouse (the main one first)
        out.put("warehouses", Db.rows(c, """
                select w.id, w.code, w.name, w.main, nvl(s.stock, 0) stock,
                       case w.main when 'Y' then (select min_stock from mm_item where id = s0.item_id)
                            else nvl((select m.min_stock from mm_warehouse_min m
                                      where m.warehouse_id = w.id and m.item_id = s0.item_id), 0) end min_stock
                from mm_warehouse w cross join (select ? item_id from dual) s0
                left join mm_warehouse_stock s on s.warehouse_id = w.id and s.item_id = s0.item_id
                where w.active = 'Y' or nvl(s.stock, 0) <> 0
                order by case w.main when 'Y' then 0 else 1 end, w.code""", v));
        // FIFO: its layers with something left (each receipt at its cost), the value of its stock
        out.put("fifo", Db.rows(c, """
                select f.in_at, f.qty, f.unit_cost, f.left_, d.id doc_id, d.doc_type, d.doc_no
                from mm_fifo f left join mm_stock_move s on s.id = f.move_id left join mm_doc d on d.id = s.doc_id
                where f.item_id = ? and f.left_ <> 0 order by f.id""", v));
        out.putAll(Db.rows(c, "select value fifo_value, unit_cost fifo_unit, next_cost fifo_next from mm_fifo_value where item_id = ?", v).get(0));
        return out;
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
        if ("C".equals(kind)) {                // its card and its points, the last moves of them
            r.putAll(Db.rows(c, "select card, points from mm_customer where id = ?", id).get(0));
            r.put("point_moves", Db.rows(c, """
                    select m.move_at, m.points, m.note, d.doc_no, d.id doc_id
                    from mm_points m left join mm_doc d on d.id = m.doc_id
                    where m.customer_id = ? order by m.id desc fetch first 30 rows only""", id));
        }
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

    /**
     * the gross profit of the items in a period: what was sold (the net of the invoices and the receipts,
     * less the credit notes), what it cost (the moves of the stock of the documents of sale) by FIFO and
     * by the last cost, COST the one of the method (the first two binds: FIFO or LAST), the quantity out
     */
    static final String PROFIT = """
            select i.id item_id, i.code, i.name, i.unit, nvl(c.qty, 0) qty, nvl(r.revenue, 0) revenue,
                   round(nvl(c.cost_fifo, 0), 2) cost_fifo, round(nvl(c.cost_last, 0), 2) cost_last,
                   round(nvl(case ? when 'LAST' then c.cost_last else c.cost_fifo end, 0), 2) cost,
                   nvl(r.revenue, 0) - round(nvl(case ? when 'LAST' then c.cost_last else c.cost_fifo end, 0), 2) profit
            from (select l.item_id, sum(t.vat_sign * l.net) revenue
                  from mm_doc_line l join mm_doc d on d.id = l.doc_id join mm_doc_type t on t.code = d.doc_type
                  where d.status = 'P' and t.side = 'S' and t.vat_sign <> 0 and d.doc_date between ? and ?
                  group by l.item_id) r
            full join (select m.item_id, sum(-m.qty) qty, sum(m.cost) cost_fifo, sum(m.cost_last) cost_last
                       from mm_move_cost m join mm_doc d on d.id = m.doc_id join mm_doc_type t on t.code = d.doc_type
                       where t.side = 'S' and d.doc_date between ? and ?
                       group by m.item_id) c on c.item_id = r.item_id
            join mm_item i on i.id = nvl(r.item_id, c.item_id)
            where nvl(r.revenue, 0) <> 0 or nvl(c.cost_fifo, 0) <> 0 or nvl(c.cost_last, 0) <> 0
            order by profit desc, i.code""";

    /** the way the costs are counted: ?method=FIFO|LAST, else MM_SETTING COST_METHOD, else FIFO */
    static String costMethod(Connection c, Map<String, String> q) throws SQLException {
        String m = q == null ? null : q.get("method");
        if (m == null || m.isBlank()) {
            m = (String) Db.rows(c, "select max(value) v from mm_setting where name = 'COST_METHOD'").get(0).get("v");
        }
        return "LAST".equalsIgnoreCase(m == null ? "" : m.trim()) ? "LAST" : "FIFO";
    }

    private Object report(Connection c, String name, Map<String, String> q) throws SQLException {
        LocalDate f = from(q);
        LocalDate t = to(q);
        Map<String, Object> out = new LinkedHashMap<>();
        switch (name) {
            case "sales-by" -> {           // the sales of each store, register, cashier (MM_SALES_DOC)
                String by = q.getOrDefault("by", "warehouse");
                String m = costMethod(c, q);
                String[] k = switch (by) {
                    case "warehouse" -> new String[] {"s.warehouse_id",
                        "(select w.code || ' ' || w.name from mm_warehouse w where w.id = s.warehouse_id)"};
                    case "register" -> new String[] {"s.register_id",
                        "nvl((select g.code || ' ' || g.name from mm_register g where g.id = s.register_id), '-')"};
                    case "user" -> new String[] {"s.posted_by",
                        "nvl((select u.full_name from mm_user u where u.username = s.posted_by), s.posted_by)"};
                    default -> throw new Http.Fail(400, "bad_by", "by: warehouse, register or user");
                };
                out.put("from", f.toString());
                out.put("to", t.toString());
                out.put("by", by);
                out.put("method", m);
                out.put("rows", Db.rows(c, "select to_char(" + k[0] + ") key, " + k[1] + " name, sum(s.docs) docs, sum(s.net) net, "
                        + "sum(s.total) total, round(sum(s.total) / nullif(sum(s.docs), 0), 2) avg_total, "
                        + "round(sum(case ? when 'LAST' then s.cost_last else s.cost_fifo end), 2) cost, "
                        + "sum(s.net) - round(sum(case ? when 'LAST' then s.cost_last else s.cost_fifo end), 2) profit "
                        + "from mm_sales_doc s where s.day between ? and ? group by " + k[0] + " order by sum(s.total) desc", m, m, f, t));
            }
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
            case "trial-items", "trial-customers", "trial-suppliers" -> {
                String what = switch (name) {
                    case "trial-items" -> "I";
                    case "trial-customers" -> "C";
                    default -> "S";
                };
                out.put("from", f.toString());
                out.put("to", t.toString());
                List<Map<String, Object>> rows = Db.rows(c, """
                        select id, code, name, unit, open_bal, debit, credit, close_bal
                        from table(mm_ledger.trial_rows(?, ?, ?, ?))""", what, f, t, "1".equals(q.get("all")) ? "Y" : "N");
                out.put("rows", rows);
                out.put("totals", Db.rows(c, """
                        select nvl(sum(open_bal), 0) open_bal, nvl(sum(debit), 0) debit, nvl(sum(credit), 0) credit,
                               nvl(sum(close_bal), 0) close_bal
                        from table(mm_ledger.trial_rows(?, ?, ?, 'N'))""", what, f, t).get(0));
            }
            case "profit" -> {             // the gross profit: the sales less what they cost (FIFO or LAST)
                String m = costMethod(c, q);
                out.put("method", m);
                out.put("default_method", costMethod(c, null));
                out.put("from", f.toString());
                out.put("to", t.toString());
                out.put("rows", Db.rows(c, PROFIT, m, m, f, t, f, t));
                out.put("stock_diff", Db.rows(c, """
                        select nvl(sum(case ? when 'LAST' then cost_last else cost end), 0) cost from mm_move_cost
                        where kind = 'ADJ' and move_at >= ? and move_at < ? + 1""", m, f, t).get(0).get("cost"));
            }
            case "consumption" -> {        // the consumptions (DAN): by warehouse, reason, item, at cost
                String m = costMethod(c, q);
                String wh = q.get("warehouse") == null || q.get("warehouse").isBlank() ? null : q.get("warehouse").trim();
                out.put("from", f.toString());
                out.put("to", t.toString());
                out.put("method", m);
                out.put("warehouse", wh);
                out.put("rows", Db.rows(c, """
                        select warehouse, warehouse_name, reason, code, name, unit, sum(qty) qty,
                               round(sum(case ? when 'LAST' then cost_last else cost_fifo end), 2) cost, count(distinct doc_id) docs
                        from mm_consumption
                        where day between ? and ? and (? is null or warehouse = upper(?))
                        group by warehouse, warehouse_name, reason, code, name, unit
                        order by warehouse, reason, sum(case ? when 'LAST' then cost_last else cost_fifo end) desc, code""",
                        m, f, t, wh, wh, m));
            }
            case "stock-value" -> {        // the value of the stock now: FIFO and by the last cost
                String m = costMethod(c, q);
                out.put("method", m);
                out.put("default_method", costMethod(c, null));
                String wh = q.get("warehouse");
                out.put("warehouse", wh == null || wh.isBlank() ? null : wh);
                out.put("rows", wh == null || wh.isBlank() ? Db.rows(c, """
                        select item_id, code, name, unit, category, stock, value value_fifo, value_last,
                               case ? when 'LAST' then value_last else value end value, unit_cost, next_cost, last_cost
                        from mm_fifo_value where stock <> 0 or value <> 0 order by category, code""", m)
                        : Db.rows(c, """
                        select i.id item_id, i.code, i.name, i.unit, k.name category, nvl(s.stock, 0) stock,
                               nvl(f.value, 0) value_fifo, round(nvl(s.stock, 0) * nvl(i.cost, 0), 2) value_last,
                               case ? when 'LAST' then round(nvl(s.stock, 0) * nvl(i.cost, 0), 2) else nvl(f.value, 0) end value,
                               f.unit_cost, f.next_cost, i.cost last_cost
                        from mm_item i
                        join mm_category k on k.id = i.category_id
                        join mm_warehouse w on w.code = upper(?)
                        left join mm_warehouse_stock s on s.item_id = i.id and s.warehouse_id = w.id
                        left join (select item_id, warehouse_id, sum(left_ * unit_cost) value,
                                          round(sum(case when left_ > 0 then left_ * unit_cost end)
                                                / nullif(sum(case when left_ > 0 then left_ end), 0), 4) unit_cost,
                                          min(case when left_ > 0 then unit_cost end)
                                            keep (dense_rank first order by case when left_ > 0 then id end) next_cost
                                   from mm_fifo group by item_id, warehouse_id) f
                          on f.item_id = i.id and f.warehouse_id = w.id
                        where nvl(s.stock, 0) <> 0 or nvl(f.value, 0) <> 0
                        order by k.name, i.code""", m, wh.trim()));
            }
            default -> throw new Http.Fail(404, "not_found", "reports: sales, vat, min-stock, trial-items, trial-customers, trial-suppliers, profit or stock-value");
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
