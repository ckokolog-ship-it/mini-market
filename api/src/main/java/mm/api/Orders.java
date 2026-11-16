package mm.api;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The orders: a reservation (MM_RESERVATION) written from the pages, by a phone in the shop or on a
 * call, its lines reserved (the stock "reserved" until it is delivered), picked from the shelves, ready,
 * then at the till all of it into a receipt (POST /api/pos/{register}/order) or, for a customer on
 * credit, a delivery note. CASHIER and above; the delivery note MANAGER.
 *
 * <pre>
 *   GET  /api/orders?status=O|D|C|all&q=          the orders (the open ones first by their day)
 *   GET  /api/orders/{id}                         one with its lines
 *   GET  /api/orders/new                          the orders of the customers not confirmed yet: count, last_id, last_name
 *   POST /api/orders {name, phone, customer_id, pickup_date, notes}   a new one (by whom: the login)
 *   POST /api/orders/{id}/lines {code, qty, mode ADD|SET}   an item in (ADD: one more of it), 0 out
 *   POST /api/orders/{id}/pick {item_id, qty}     what of a line was picked
 *   POST /api/orders/{id}/ready {ready}           ready (all picked) or not
 *   POST /api/orders/{id}/cancel {register}       cancelled (a deposit back through that register)
 *   POST /api/orders/{id}/note                    a delivery note, posted (MANAGER)
 *   POST /api/orders/{id}/confirm                 an order of a customer (the page /shop/) confirmed
 * </pre>
 */
final class Orders {
    private Orders() {
    }

    static Object get(Connection c, String[] p, Map<String, String> q) throws SQLException {
        if (p.length == 1) {
            String st = q.getOrDefault("status", "O").toUpperCase(java.util.Locale.ROOT);
            String s = q.getOrDefault("q", "").trim();
            return Map.of("rows", Db.rows(c, """
                    select r.id, r.name, r.phone, r.customer_id, cu.name customer, r.pickup_date, r.status, r.deposit,
                           r.created_by, r.created_at, r.ready_at, r.source, r.confirmed_at, r.doc_id,
                           case when d.id is not null then d.doc_type || ' ' || d.doc_no end doc_text,
                           (select count(*) from mm_reservation_line l where l.reservation_id = r.id) lines,
                           (select nvl(sum(l.qty * l.price), 0) from mm_reservation_line l where l.reservation_id = r.id) total
                    from mm_reservation r
                    left join mm_customer cu on cu.id = r.customer_id
                    left join mm_doc d on d.id = r.doc_id
                    where (? = 'ALL' or r.status = ?)
                      and (? is null or upper(r.name) like '%' || upper(?) || '%' or r.phone like '%' || ? || '%'
                           or to_char(r.id) = ?)
                      and (r.status = 'O' or r.created_at > sysdate - 90)
                    order by case r.status when 'O' then 0 else 1 end, r.pickup_date, r.id
                    fetch first 200 rows only""", st, st, s.isEmpty() ? null : s, s, s, s));
        }
        if (p.length == 2 && "new".equals(p[1])) {
            // the orders of the customers (/shop/) waiting for a call: for the bell of the pages
            return Db.rows(c, """
                    select count(*) count, max(id) last_id, max(name) keep (dense_rank last order by id) last_name
                    from mm_reservation where source = 'O' and status = 'O' and confirmed_at is null""").get(0);
        }
        if (p.length == 2) {
            return order(c, Http.id(p[1]));
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    static Object post(Connection c, Api.User u, String[] p, Map<String, Object> in) throws SQLException {
        if (p.length == 1) {
            String date = Http.text(in, "pickup_date", false);
            LocalDate day;
            try {
                day = date == null ? LocalDate.now() : LocalDate.parse(date);
            } catch (java.time.format.DateTimeParseException e) {
                throw new Http.Fail(400, "bad_date", "pickup_date: YYYY-MM-DD");
            }
            Object cust = in.get("customer_id");
            try (CallableStatement cs = c.prepareCall("begin ? := mm_core.new_reservation(?, ?, ?, ?, ?, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setString(2, Http.text(in, "name", true));
                cs.setString(3, Http.text(in, "phone", true));
                cs.setDate(4, java.sql.Date.valueOf(day));
                if (cust == null) {
                    cs.setNull(5, Types.NUMERIC);
                } else {
                    cs.setLong(5, Http.id(String.valueOf(cust).replaceAll("\\.0$", "")));
                }
                cs.setString(6, Http.text(in, "notes", false));
                cs.setString(7, u.username());
                cs.execute();
                return order(c, cs.getLong(1));
            }
        }
        long id = Http.id(p[1]);
        if (p.length == 3) {
            switch (p[2]) {
                case "lines" -> {
                    String code = Http.text(in, "code", true);
                    Object v = Db.rows(c, "select mm_core.find_item(?) id from dual", code).get(0).get("id");
                    if (v == null) {
                        throw new Http.Fail(404, "not_found", "Δεν βρέθηκε είδος: " + code);
                    }
                    BigDecimal qty = Http.decimal(in, "qty", BigDecimal.ONE);
                    if ("ADD".equalsIgnoreCase(String.valueOf(in.getOrDefault("mode", "ADD")))) {
                        List<Map<String, Object>> has = Db.rows(c,
                                "select qty from mm_reservation_line where reservation_id = ? and item_id = ?", id, v);
                        if (!has.isEmpty()) {
                            qty = qty.add((BigDecimal) has.get(0).get("qty"));
                        }
                    }
                    try (CallableStatement cs = c.prepareCall("begin mm_core.reserve(?, ?, ?); end;")) {
                        cs.setLong(1, id);
                        cs.setObject(2, v);
                        cs.setBigDecimal(3, qty);
                        cs.execute();
                    }
                    unready(c, id);                     // a change: to be ready again
                    return order(c, id);
                }
                case "pick" -> {
                    try (CallableStatement cs = c.prepareCall("begin mm_core.pick(?, ?, ?); end;")) {
                        cs.setLong(1, id);
                        cs.setLong(2, Http.id(String.valueOf(in.get("item_id")).replaceAll("\\.0$", "")));
                        cs.setBigDecimal(3, Http.decimal(in, "qty", null));
                        cs.execute();
                    }
                    return order(c, id);
                }
                case "confirm" -> {
                    try (CallableStatement cs = c.prepareCall("begin mm_core.confirm_order(?); end;")) {
                        cs.setLong(1, id);
                        cs.execute();
                    }
                    return order(c, id);
                }
                case "ready" -> {
                    try (CallableStatement cs = c.prepareCall("begin mm_core.set_ready(?, ?); end;")) {
                        cs.setLong(1, id);
                        cs.setString(2, Boolean.FALSE.equals(in.get("ready")) ? "N" : "Y");
                        cs.execute();
                    }
                    return order(c, id);
                }
                case "cancel" -> {
                    Object reg = null;
                    String code = Http.text(in, "register", false);
                    if (code != null) {
                        List<Map<String, Object>> r = Db.rows(c, "select id from mm_register where code = upper(?)", code);
                        if (r.isEmpty()) {
                            throw new Http.Fail(404, "not_found", "no such register: " + code);
                        }
                        reg = r.get(0).get("id");
                    }
                    try (CallableStatement cs = c.prepareCall("begin mm_core.cancel_reservation(?, ?); end;")) {
                        cs.setLong(1, id);
                        cs.setObject(2, reg);
                        cs.execute();
                    }
                    return order(c, id);
                }
                case "note" -> {
                    if (!u.atLeast("MANAGER")) {
                        throw new Http.Fail(403, "forbidden", "only MANAGER or above");
                    }
                    long d;
                    try (CallableStatement cs = c.prepareCall("begin ? := mm_core.deliver_note(?); end;")) {
                        cs.registerOutParameter(1, Types.NUMERIC);
                        cs.setLong(2, id);
                        cs.execute();
                        d = cs.getLong(1);
                    }
                    try (CallableStatement cs = c.prepareCall("begin ? := mm_core.post_doc(?); end;")) {
                        cs.registerOutParameter(1, Types.NUMERIC);
                        cs.setLong(2, d);
                        cs.execute();
                    }
                    return order(c, id);
                }
                default -> {
                }
            }
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    private static void unready(Connection c, long id) throws SQLException {
        try (CallableStatement cs = c.prepareCall("begin mm_core.set_ready(?, 'N'); end;")) {
            cs.setLong(1, id);
            cs.execute();
        }
    }

    static Map<String, Object> order(Connection c, long id) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, """
                select r.id, r.name, r.phone, r.customer_id, cu.name customer, r.pickup_date, r.status, r.deposit,
                       r.notes, r.created_by, r.created_at, r.ready_at, r.source, r.confirmed_at, r.doc_id,
                       case when d.id is not null then d.doc_type || ' ' || d.doc_no end doc_text,
                       d.status doc_status
                from mm_reservation r
                left join mm_customer cu on cu.id = r.customer_id
                left join mm_doc d on d.id = r.doc_id
                where r.id = ?""", id);
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such order: " + id);
        }
        Map<String, Object> out = new LinkedHashMap<>(r.get(0));
        out.put("lines", Db.rows(c, """
                select l.id, i.id item_id, i.code, i.barcode, i.name, i.unit, l.qty, l.price, l.picked,
                       round(l.qty * l.price, 2) total, a.available
                from mm_reservation_line l join mm_item i on i.id = l.item_id
                join mm_item_avail a on a.item_id = i.id
                where l.reservation_id = ? order by i.code""", id));
        out.put("total", Db.rows(c, """
                select nvl(sum(round(qty * price, 2)), 0) t from mm_reservation_line where reservation_id = ?""", id)
                .get(0).get("t"));
        return out;
    }
}
