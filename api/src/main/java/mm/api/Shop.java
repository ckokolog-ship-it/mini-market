package mm.api;

import java.math.BigDecimal;
import java.security.SecureRandom;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * The page of the shop for its customers (/shop/, the WiFi of the shop): no login. Only what a customer
 * may see (the active items with their retail price and whether there are any: no cost, no stock, no
 * cards with a PIN) and an order of a name and a phone, for today; the shop confirms it (a call) and it
 * goes on as any order (Orders: picked, ready, the till). The page of its status by a token, not by its
 * number.
 *
 * <pre>
 *   GET  /api/shop/info                        the name of the shop (the first line of the receipts)
 *   GET  /api/shop/categories                  the categories with items to order
 *   GET  /api/shop/items?q=&category=&limit=&offset=   the items: code, name, unit, price, available
 *   POST /api/shop/orders {name, phone, notes, lines: [{code, qty}]}   an order: its token
 *   GET  /api/shop/orders/{token}              its status, its lines, its total
 *   POST /api/shop/orders/{token}/cancel       cancelled, while the shop has not confirmed it
 * </pre>
 * At most MM_SHOP_ORDERS orders (10) an address in 10 minutes; 40 lines, up to 99 of each.
 */
final class Shop {
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int PER_TEN_MINUTES = Integer.parseInt(Main.env("MM_SHOP_ORDERS", "10"));
    private static final Map<String, Deque<Long>> SENT = new ConcurrentHashMap<>();
    private static final String ITEMS = """
            from mm_item i
            join mm_category c on c.id = i.category_id
            join mm_item_avail a on a.item_id = i.id
            where i.active = 'Y' and i.is_model = 'N' and i.serial_tracked = 'N' and i.price > 0""";

    private Shop() {
    }

    static Object get(Connection c, String[] p, Map<String, String> q) throws SQLException {
        if (p.length == 2 && "info".equals(p[1])) {
            Object h = Db.rows(c, "select max(value) v from mm_setting where name = 'RECEIPT_HEADER'").get(0).get("v");
            String name = h == null ? "Mini market" : String.valueOf(h).split("\n")[0].trim();
            return Map.of("name", name.isEmpty() ? "Mini market" : name);
        }
        if (p.length == 2 && "categories".equals(p[1])) {
            return Map.of("rows", Db.rows(c, "select c.id, c.name, count(*) items " + ITEMS
                    + " group by c.id, c.name order by c.name"));
        }
        if (p.length == 2 && "items".equals(p[1])) {
            String s = q.getOrDefault("q", "").trim();
            String like = s.isEmpty() ? null : s;
            String cat = q.get("category");
            Long catId = cat == null || cat.isBlank() ? null : Http.id(cat);
            int limit = Http.number(q, "limit", 60, 1, 200);
            int offset = Http.number(q, "offset", 0, 0, Integer.MAX_VALUE);
            String where = ITEMS + """
                     and (? is null or upper(i.name) like '%' || upper(?) || '%' or i.code = upper(?) or i.barcode = ?)
                      and (? is null or c.id = ?)""";
            List<Map<String, Object>> rows = Db.rows(c, """
                    select i.code, i.name, c.name category, i.unit, i.price,
                           case when a.available > 0 then 'Y' else 'N' end available
                    """ + where + " order by c.name, i.name offset ? rows fetch next ? rows only",
                    like, like, like, like, catId, catId, offset, limit);
            Object total = Db.rows(c, "select count(*) n " + where, like, like, like, like, catId, catId).get(0).get("n");
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("limit", limit);
            out.put("offset", offset);
            out.put("total", total);
            out.put("rows", rows);
            return out;
        }
        if (p.length == 3 && "orders".equals(p[1])) {
            return status(c, p[2]);
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    static Object post(Connection c, String[] p, Map<String, Object> in, String address) throws SQLException {
        if (p.length == 2 && "orders".equals(p[1])) {
            limit(address);
            return order(c, in);
        }
        if (p.length == 4 && "orders".equals(p[1]) && "cancel".equals(p[3])) {
            token(p[2]);
            try (CallableStatement cs = c.prepareCall("begin mm_core.cancel_online(?); end;")) {
                cs.setString(1, p[2]);
                cs.execute();
            }
            return status(c, p[2]);
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    /** at most PER_TEN_MINUTES orders of an address in 10 minutes */
    private static void limit(String address) {
        long now = System.currentTimeMillis();
        Deque<Long> d = SENT.computeIfAbsent(address, k -> new ArrayDeque<>());
        synchronized (d) {
            while (!d.isEmpty() && now - d.peekFirst() > 600_000L) {
                d.pollFirst();
            }
            if (d.size() >= PER_TEN_MINUTES) {
                throw new Http.Fail(429, "too_many", "Πολλές παραγγελίες από αυτή τη συσκευή: δοκίμασε σε λίγο");
            }
            d.addLast(now);
        }
    }

    private static String token(String t) {
        if (t == null || !t.matches("[0-9a-f]{48}")) {
            throw new Http.Fail(404, "not_found", "Δεν υπάρχει αυτή η παραγγελία");
        }
        return t;
    }

    private static Object order(Connection c, Map<String, Object> in) throws SQLException {
        String name = Http.text(in, "name", true).trim();
        String phone = Http.text(in, "phone", true).replaceAll("[\\s-]", "");
        if (name.isEmpty() || name.length() > 60) {
            throw new Http.Fail(400, "bad_name", "Το όνομα: έως 60 γράμματα");
        }
        String notes = Http.text(in, "notes", false);
        if (notes != null && notes.length() > 300) {
            throw new Http.Fail(400, "bad_notes", "Η σημείωση: έως 300 γράμματα");
        }
        Object raw = in.get("lines");
        if (!(raw instanceof List<?> lines) || lines.isEmpty() || lines.size() > 40) {
            throw new Http.Fail(400, "bad_lines", "Το καλάθι: από 1 έως 40 είδη");
        }
        byte[] b = new byte[24];
        RANDOM.nextBytes(b);
        String token = HexFormat.of().formatHex(b);
        long id;
        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.online_order(?, ?, ?, ?); end;")) {
            cs.registerOutParameter(1, Types.NUMERIC);
            cs.setString(2, name);
            cs.setString(3, phone);
            cs.setString(4, notes);
            cs.setString(5, token);
            cs.execute();
            id = cs.getLong(1);
        }
        Map<String, BigDecimal> want = new LinkedHashMap<>();
        for (Object o : lines) {
            if (!(o instanceof Map<?, ?> m)) {
                throw new Http.Fail(400, "bad_lines", "a line: {code, qty}");
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> line = (Map<String, Object>) m;
            String code = Http.text(line, "code", true);
            BigDecimal qty = Http.decimal(line, "qty", BigDecimal.ONE);
            if (qty.signum() <= 0 || qty.compareTo(BigDecimal.valueOf(99)) > 0) {
                throw new Http.Fail(400, "bad_number", "Ποσότητα από 0 έως 99");
            }
            want.merge(code, qty, BigDecimal::add);
        }
        for (Map.Entry<String, BigDecimal> e : want.entrySet()) {
            List<Map<String, Object>> item = Db.rows(c, "select i.id " + ITEMS + " and i.code = ?", e.getKey());
            if (item.isEmpty()) {
                throw new Http.Fail(404, "not_found", "Δεν υπάρχει το είδος " + e.getKey());
            }
            try (CallableStatement cs = c.prepareCall("begin mm_core.reserve(?, ?, ?); end;")) {
                cs.setLong(1, id);
                cs.setObject(2, item.get(0).get("id"));
                cs.setBigDecimal(3, e.getValue().min(BigDecimal.valueOf(99)));
                cs.execute();
            }
        }
        return status(c, token);
    }

    private static Map<String, Object> status(Connection c, String t) throws SQLException {
        token(t);
        List<Map<String, Object>> r = Db.rows(c, """
                select id, name, pickup_date, created_at, confirmed_at, ready_at, status, public_token token
                from mm_reservation where public_token = ? and source = 'O'""", t);
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "Δεν υπάρχει αυτή η παραγγελία");
        }
        Map<String, Object> out = new LinkedHashMap<>(r.get(0));
        String st = (String) out.get("status");
        out.put("state", "D".equals(st) ? "delivered" : "C".equals(st) ? "cancelled"
                : out.get("ready_at") != null ? "ready" : out.get("confirmed_at") != null ? "confirmed" : "sent");
        out.put("lines", Db.rows(c, """
                select i.code, i.name, i.unit, l.qty, l.price, round(l.qty * l.price, 2) total
                from mm_reservation_line l join mm_item i on i.id = l.item_id
                where l.reservation_id = ? order by i.name""", out.get("id")));
        out.put("total", Db.rows(c, "select nvl(sum(round(qty * price, 2)), 0) t from mm_reservation_line where reservation_id = ?",
                out.get("id")).get(0).get("t"));
        return out;
    }
}
