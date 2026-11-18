package mm.api;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The rights of a user (MM_RIGHTS: its roles, the screens, their fields and actions) on the calls of the
 * service: each call is a screen (read: R) or an action of it (W), checked before it runs (403 forbidden);
 * the fields of a screen the user may not read: null in what it returns.
 *
 * <pre>
 *   GET /api/auth/rights      the menu of the user (its groups, their screens with a page) and its rights:
 *                             {"ITEMS": "R", "ITEMS.COST": "N", "POS.OPEN_Z": "W", ...}
 * </pre>
 */
final class Rights {
    private Rights() {
    }

    /** the rights of a user: SCREEN or SCREEN.ITEM to N, R, W */
    static Map<String, String> load(Connection c, long userId) throws SQLException {
        Map<String, String> m = new HashMap<>();
        for (Map<String, Object> r : Db.rows(c, """
                select object_code, item_code, lvl from mm_user_right where user_id = ?""", userId)) {
            Object item = r.get("item_code");
            m.put(r.get("object_code") + (item == null ? "" : "." + item), (String) r.get("lvl"));
        }
        return m;
    }

    static String lvl(Api.User u, String screen, String item) {
        return u.rights().getOrDefault(item == null ? screen : screen + "." + item, "N");
    }

    static boolean may(Api.User u, String screen, String item, String level) {
        return "NRW".indexOf(lvl(u, screen, item)) >= "NRW".indexOf(level);
    }

    static void need(Api.User u, String screen, String item, String level) {
        if (!may(u, screen, item, level)) {
            throw new Http.Fail(403, "forbidden", "Δεν επιτρέπεται: " + (item == null ? screen : screen + "." + item));
        }
    }

    /** one of the screens, at least read (e.g. the customers: their own screen, or picked in a document) */
    static void needAny(Api.User u, String... screens) {
        for (String s : screens) {
            if (may(u, s, null, "R")) {
                return;
            }
        }
        throw new Http.Fail(403, "forbidden", "Δεν επιτρέπεται: " + String.join(" / ", screens));
    }

    /** the menu and the rights of the user (GET /api/auth/rights) */
    static Map<String, Object> of(Connection c, Api.User u) throws SQLException {
        List<Map<String, Object>> rows = Db.rows(c, """
                select group_code, group_name, code, name, route, lvl from mm_user_menu
                where user_id = ? and route is not null order by group_sort, group_code, sort_no, code""", u.id());
        List<Map<String, Object>> menu = new java.util.ArrayList<>();
        Map<String, Object> g = null;
        for (Map<String, Object> r : rows) {
            if (g == null || !java.util.Objects.equals(g.get("code"), r.get("group_code"))) {
                g = new LinkedHashMap<>();
                g.put("code", r.get("group_code"));
                g.put("name", r.get("group_name"));
                g.put("screens", new java.util.ArrayList<Map<String, Object>>());
                menu.add(g);
            }
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("code", r.get("code"));
            s.put("name", r.get("name"));
            s.put("route", r.get("route"));
            s.put("lvl", r.get("lvl"));
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> l = (List<Map<String, Object>>) g.get("screens");
            l.add(s);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("menu", menu);
        out.put("rights", new java.util.TreeMap<>(u.rights()));
        return out;
    }

    /** a call: its screen, or the action of it, checked before it runs */
    static void check(Api.User u, String method, String[] p) {
        int n = p.length;
        String head = p[0];
        String a2 = n > 2 ? p[2] : null;
        if ("GET".equals(method)) {
            switch (head) {
                case "pos" -> need(u, "POS", null, "R");
                case "orders" -> need(u, "ORDERS", null, "R");
                case "docs", "doc-types" -> need(u, "DOCS", null, "R");
                case "payments" -> need(u, "PAYMENTS", null, "R");
                case "counts" -> need(u, "COUNTS", null, "R");
                case "items" -> need(u, "ITEMS", null, "R");
                case "customers" -> needAny(u, "CUSTOMERS", "DOCS", "PAYMENTS");
                case "suppliers" -> needAny(u, "SUPPLIERS", "DOCS", "PAYMENTS");
                case "ledger" -> need(u, "LEDGERS", null, "R");
                case "scratch" -> need(u, "SCRATCH", null, "R");
                case "warehouses" -> {
                    if (n > 1) {
                        need(u, "WAREHOUSES", null, "R");
                    }
                }
                case "expiry" -> need(u, "EXPIRY", null, "R");
                case "users" -> need(u, "USERS", null, "R");
                case "roles", "menu" -> need(u, "ROLES", null, "R");
                case "audit" -> need(u, "AUDIT", null, "R");
                case "chart" -> need(u, "CHART", null, "R");
                case "day", "backup" -> need(u, "DAY", null, "R");
                case "reports" -> {
                    if (n == 2 && report(p[1]) != null) {          // (another: not found)
                        need(u, report(p[1]), null, "R");
                    }
                }
                default -> {
                }
            }
            return;
        }
        switch (head) {
            case "pos" -> {
                if (n == 2 && "settings".equals(p[1])) {
                    need(u, "POS", "SETTINGS", "W");
                } else {
                    need(u, "POS", switch (a2 == null ? "" : a2) {
                        case "open" -> "OPEN_Z";
                        case "close" -> "CLOSE_Z";
                        case "cash" -> "CASH";
                        case "prize" -> "PRIZE";
                        case "warehouse" -> "WAREHOUSE";
                        case "void" -> "VOID";
                        default -> null;
                    }, "W");
                }
            }
            case "orders" -> need(u, "ORDERS", switch (a2 == null ? "" : a2) {
                case "confirm" -> "CONFIRM";
                case "cancel" -> "CANCEL";
                case "note" -> "NOTE";
                default -> null;
            }, "W");
            case "docs" -> {
                if (n == 1) {
                    need(u, "DOCS", "CREATE", "W");
                } else if (n == 2 && "from-min-stock".equals(p[1])) {
                    need(u, "REP_MIN_STOCK", "ORDER", "W");
                } else {
                    need(u, "DOCS", switch (a2 == null ? "" : a2) {
                        case "post" -> "POST";
                        case "cancel" -> "CANCEL";
                        case "mydata" -> "MYDATA";
                        case "credit" -> "CREATE";
                        default -> null;
                    }, "W");
                }
            }
            case "payments" -> need(u, "PAYMENTS", n == 1 ? "CREATE" : "cancel".equals(a2) ? "CANCEL" : null, "W");
            case "scratch" -> need(u, "SCRATCH", n == 2 ? switch (p[1]) {
                case "games" -> "GAME";
                case "packs" -> "LOAD";
                case "returns" -> "RETURN";
                default -> null;
            } : null, "W");
            case "warehouses" -> need(u, "WAREHOUSES", n == 1 ? "CREATE" : "min".equals(a2) ? "MIN"
                    : "transfer".equals(a2) ? "TRANSFER" : null, "W");
            case "users" -> {
                if (n == 3 && "roles".equals(a2)) {
                    need(u, "ROLES", null, "W");                    // (the roles of a user: its rights)
                } else {
                    need(u, "USERS", n == 1 ? "CREATE" : null, "W");
                }
            }
            case "roles", "menu" -> need(u, "ROLES", null, "W");
            case "reports" -> need(u, "STOCK_VALUE", "COST_METHOD", "W");
            case "expiry" -> need(u, "EXPIRY", "WITHDRAW", "W");
            case "customers" -> need(u, "CUSTOMERS", "card".equals(a2) ? "CARD" : null, "W");
            case "counts" -> need(u, "COUNTS", n == 1 ? "CREATE" : "post".equals(a2) ? "POST"
                    : "cancel".equals(a2) ? "CANCEL" : null, "W");
            default -> {
            }
        }
    }

    /** the screen of a report of the pages */
    static String report(String name) {
        return switch (name) {
            case "sales" -> "REP_SALES";
            case "sales-by" -> "REP_SALES_BY";
            case "vat" -> "REP_VAT";
            case "min-stock" -> "REP_MIN_STOCK";
            case "trial-items" -> "TRIAL_ITEMS";
            case "trial-customers" -> "TRIAL_CUSTOMERS";
            case "trial-suppliers" -> "TRIAL_SUPPLIERS";
            case "profit" -> "PROFIT";
            case "stock-value" -> "STOCK_VALUE";
            default -> null;
        };
    }

    // the fields of a screen in what the calls return: field of the rights to the keys it covers
    private static final Map<String, String[]> ITEM_KEYS = Map.of(
            "PRICE", new String[] {"price"},
            "WHOLESALE_PRICE", new String[] {"wholesale_price"},
            "COST", new String[] {"cost"},
            "FIFO", new String[] {"fifo", "fifo_value", "fifo_unit", "fifo_next"},
            "STOCK", new String[] {"stock", "reserved", "available"},
            "MIN_STOCK", new String[] {"min_stock"});
    private static final Map<String, String[]> PARTNER_KEYS = Map.of(
            "AFM", new String[] {"afm", "doy"},
            "CONTACT", new String[] {"phone", "email", "address"},
            "BALANCE", new String[] {"balance"},
            "POINTS", new String[] {"points", "card"});

    /** what a GET returns, without the fields the user may not read (null) */
    @SuppressWarnings("unchecked")
    static Object mask(Api.User u, String[] p, Object body) {
        if ("reports".equals(p[0]) && p.length == 2 && "sales-by".equals(p[1])) {
            if (!may(u, "PROFIT", null, "R")) {
                hideIn(body, java.util.Set.of("cost", "profit"));      // (the costs: with the gross profit)
            }
            return body;
        }
        String screen;
        Map<String, String[]> keys;
        switch (p[0]) {
            case "items" -> {
                screen = "ITEMS";
                keys = ITEM_KEYS;
            }
            case "customers" -> {
                screen = "CUSTOMERS";
                keys = PARTNER_KEYS;
            }
            case "suppliers" -> {
                screen = "SUPPLIERS";
                keys = PARTNER_KEYS;
            }
            case "warehouses" -> {
                screen = "WAREHOUSES";
                keys = Map.of("VALUE", new String[] {"value"});
            }
            default -> {
                return body;
            }
        }
        java.util.Set<String> hide = new java.util.HashSet<>();
        for (Map.Entry<String, String[]> e : keys.entrySet()) {
            if (!may(u, screen, e.getKey(), "R")) {
                hide.addAll(List.of(e.getValue()));
            }
        }
        if ("warehouses".equals(p[0]) && p.length == 1 && !may(u, "WAREHOUSES", null, "R")) {
            hide.addAll(List.of("items", "value", "registers", "under_min"));   // (the list, for the choices)
        }
        if ("items".equals(p[0]) && !may(u, "ITEMS", "MIN_STOCK", "R")) {
            hide.add("min_stock");
        }
        if (!hide.isEmpty()) {
            hideIn(body, hide);
        }
        return body;
    }

    @SuppressWarnings("unchecked")
    private static void hideIn(Object o, java.util.Set<String> hide) {
        if (o instanceof Map<?, ?> m) {
            for (Map.Entry<String, Object> e : ((Map<String, Object>) m).entrySet()) {
                if (hide.contains(e.getKey())) {
                    e.setValue(null);
                } else {
                    hideIn(e.getValue(), hide);
                }
            }
        } else if (o instanceof List<?> l) {
            for (Object x : l) {
                hideIn(x, hide);
            }
        }
    }
}
