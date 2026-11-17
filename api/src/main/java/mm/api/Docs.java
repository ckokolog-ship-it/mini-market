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
 * The documents of the office (as the form MM_INVOICES: every kind but the retail receipts) and the
 * receipts and payments (as MM_PAYMENTS), through MM_CORE. MANAGER and above.
 *
 * <pre>
 *   GET  /api/doc-types                            the kinds of documents (what each does)
 *   GET  /api/docs?type=&status=&q=&limit=&offset=  the documents, the last first
 *   GET  /api/docs/notes?type=&customer_id=&supplier_id=   the posted notes not in an invoice yet
 *   GET  /api/docs/{id}                            one: its lines; an invoice its notes, a note its invoice
 *   POST /api/docs {doc_type, customer_id|supplier_id, payment, doc_date}   a new draft
 *   POST /api/docs {from_note, doc_date}           a new draft invoice of a note (invoice_from)
 *   POST /api/docs/{id}/lines {code, qty, price, discount, expires}   a line (a card of a sale: qty of them);
 *                                                  expires YYYY-MM-DD: goods received (DPA, TAD)
 *   POST /api/docs/{id}/lines/{line} {qty, price, discount, expires}  a line changed; qty 0: out; expires
 *                                                  "" or null: none (only the fields given change)
 *   POST /api/docs/{id}/notes {note_id}            one more note into the draft invoice
 *   POST /api/docs/{id}/post | cancel | delete     posted (its number), cancelled, a draft deleted
 *   POST /api/docs/{id}/credit                     goods back: a draft return note of its lines
 *   POST /api/docs/from-min-stock {supplier_id}    the orders to the suppliers: drafts DPA of what is
 *                                                  under the minimum stock (mm_core.order_missing)
 *   GET  /api/docs/{id}/mydata                     the XML of myDATA (checked by the XSD of AADE)
 *   POST /api/docs/{id}/mydata  .../mydata/cancel  sent to myDATA now; cancelled there and here (MyData)
 *   GET  /api/payments?kind=R|P&q=&limit=&offset=  receipts (R) and payments (P)
 *   POST /api/payments {kind, partner_id, amount, method, pay_date, notes, register}
 *   POST /api/payments/{id}/cancel
 * </pre>
 */
final class Docs {
    private static final int MAX_LIMIT = 500;

    private Docs() {
    }

    static Object get(Connection c, String[] p, Map<String, String> q) throws SQLException {
        if ("doc-types".equals(p[0])) {
            return Map.of("rows", Db.rows(c, """
                    select code, name, side, stock_sign, partner_sign, vat_sign, ref_type, prices_incl_vat, partner_needed
                    from mm_doc_type order by side desc, code"""));
        }
        if ("payments".equals(p[0]) && p.length == 1) {
            return payments(c, q);
        }
        if ("docs".equals(p[0])) {
            if (p.length == 1) {
                return list(c, q);
            }
            if (p.length == 2 && "notes".equals(p[1])) {
                return Map.of("rows", Db.rows(c, """
                        select d.id, d.doc_type, d.doc_no, d.doc_date, d.customer_id, d.supplier_id,
                               nvl(cu.name, s.name) partner, d.total
                        from mm_doc d
                        left join mm_customer cu on cu.id = d.customer_id
                        left join mm_supplier s on s.id = d.supplier_id
                        where d.status = 'P' and d.invoice_id is null
                          and d.doc_type in (select ref_type from mm_doc_type where ref_type is not null)
                          and (? is null or d.doc_type = ?)
                          and (? is null or d.customer_id = ?) and (? is null or d.supplier_id = ?)
                        order by nvl(cu.name, s.name), d.doc_date, d.id""",
                        q.get("type"), q.get("type"), num(q.get("customer_id")), num(q.get("customer_id")),
                        num(q.get("supplier_id")), num(q.get("supplier_id"))));
            }
            if (p.length == 2) {
                return doc(c, Http.id(p[1]));
            }
            if (p.length == 3 && "mydata".equals(p[2])) {
                return Map.of("xml", MyData.xml(c, Http.id(p[1])));
            }
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    private static Long num(String s) {
        return s == null || s.isBlank() ? null : Http.id(s);
    }

    private static long idOf(Object v, String name) {
        if (v == null) {
            throw new Http.Fail(400, "missing", name);
        }
        return Http.id(String.valueOf(v).replaceAll("\\.0$", ""));
    }

    private static LocalDate dateOf(Map<String, Object> in, String name) {
        String s = Http.text(in, name, false);
        try {
            return s == null ? LocalDate.now() : LocalDate.parse(s);
        } catch (java.time.format.DateTimeParseException e) {
            throw new Http.Fail(400, "bad_date", name + ": YYYY-MM-DD");
        }
    }

    private static Object list(Connection c, Map<String, String> q) throws SQLException {
        String type = q.get("type");
        String st = q.get("status");
        String s = q.getOrDefault("q", "").trim();
        String like = s.isEmpty() ? null : s;
        int limit = Http.number(q, "limit", 50, 1, MAX_LIMIT);
        int offset = Http.number(q, "offset", 0, 0, Integer.MAX_VALUE);
        String where = """
                from mm_doc d
                left join mm_customer cu on cu.id = d.customer_id
                left join mm_supplier s on s.id = d.supplier_id
                left join mm_doc i on i.id = d.invoice_id
                where d.doc_type <> 'ALP' and (? is null or d.doc_type = ?) and (? is null or d.status = ?)
                  and (? is null or upper(nvl(cu.name, s.name)) like '%' || upper(?) || '%' or to_char(d.doc_no) = ?)""";
        List<Map<String, Object>> rows = Db.rows(c, """
                select d.id, d.doc_type, d.doc_no, d.doc_date, d.status, d.customer_id, d.supplier_id,
                       nvl(cu.name, s.name) partner, d.payment, d.net, d.vat, d.total,
                       d.invoice_id, case when i.id is not null then i.doc_type || ' ' || i.doc_no end invoice_text
                """ + where + """
                order by d.doc_date desc, d.id desc
                offset ? rows fetch next ? rows only""", type, type, st, st, like, like, like, offset, limit);
        Object total = Db.rows(c, "select count(*) n " + where, type, type, st, st, like, like, like).get(0).get("n");
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("limit", limit);
        out.put("offset", offset);
        out.put("total", total);
        out.put("rows", rows);
        return out;
    }

    static Map<String, Object> doc(Connection c, long id) throws SQLException {
        List<Map<String, Object>> h = Db.rows(c, """
                select d.id, d.doc_type, t.name type_name, t.side, t.stock_sign, t.partner_sign, t.ref_type,
                       d.doc_no, d.doc_date, d.status, d.customer_id, d.supplier_id, nvl(cu.name, s.name) partner,
                       nvl(cu.afm, s.afm) partner_afm, nvl(cu.doy, s.doy) partner_doy, nvl(cu.address, s.address) partner_address,
                       d.payment, d.net, d.vat, d.total, d.notes, d.ref_doc_id, case when r.id is not null then r.doc_type || ' ' || r.doc_no end ref_text,
                       d.invoice_id, case when i.id is not null then i.doc_type || ' ' || i.doc_no end invoice_text,
                       t.mydata_type, d.mydata_state, d.mydata_mark, d.mydata_uid, d.mydata_qr, d.mydata_error,
                       d.mydata_at, d.mydata_cancel_mark
                from mm_doc d
                join mm_doc_type t on t.code = d.doc_type
                left join mm_customer cu on cu.id = d.customer_id
                left join mm_supplier s on s.id = d.supplier_id
                left join mm_doc r on r.id = d.ref_doc_id
                left join mm_doc i on i.id = d.invoice_id
                where d.id = ? and d.doc_type <> 'ALP'""", id);
        if (h.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such document: " + id);
        }
        Map<String, Object> out = new LinkedHashMap<>(h.get(0));
        out.put("lines", Db.rows(c, """
                select l.id, l.line_no, i.id item_id, i.code, i.name, i.unit, i.serial_tracked, l.qty, l.price,
                       l.discount, l.vat_rate, l.net, l.vat, l.total, l.expires,
                       (select listagg(s.serial, ', ') within group (order by s.serial) from mm_serial s
                        where s.out_line_id = l.id or s.in_line_id = l.id) serials
                from mm_doc_line l join mm_item i on i.id = l.item_id
                where l.doc_id = ? order by l.line_no""", id));
        out.put("notes_in", Db.rows(c, """
                select id, doc_type, doc_no, doc_date, total from mm_doc where invoice_id = ? order by id""", id));
        return out;
    }

    private static Map<String, Object> draft(Connection c, long id) throws SQLException {
        Map<String, Object> d = doc(c, id);
        if (!"D".equals(d.get("status"))) {
            throw new Http.Fail(409, "not_draft", "Το παραστατικό δεν είναι πρόχειρο");
        }
        return d;
    }

    /** the date of expiry of a line, when the body has one ("" or null: none) */
    private static void expires(Connection c, long line, Map<String, Object> in) throws SQLException {
        if (!in.containsKey("expires")) {
            return;
        }
        Object v = in.get("expires");
        java.sql.Date d = null;
        if (v != null && !String.valueOf(v).isBlank()) {
            try {
                d = java.sql.Date.valueOf(java.time.LocalDate.parse(String.valueOf(v).trim()));
            } catch (java.time.format.DateTimeParseException e) {
                throw new Http.Fail(400, "bad_date", "expires: YYYY-MM-DD");
            }
        }
        try (CallableStatement cs = c.prepareCall("begin mm_core.set_expiry(?, ?); end;")) {
            cs.setLong(1, line);
            if (d == null) {
                cs.setNull(2, Types.DATE);
            } else {
                cs.setDate(2, d);
            }
            cs.execute();
        }
    }

    private static void call(Connection c, String sql, Object... binds) throws SQLException {
        try (CallableStatement cs = c.prepareCall(sql)) {
            for (int k = 0; k < binds.length; k++) {
                if (binds[k] == null) {
                    cs.setNull(k + 1, Types.VARCHAR);
                } else if (binds[k] instanceof LocalDate d) {
                    cs.setDate(k + 1, java.sql.Date.valueOf(d));
                } else {
                    cs.setObject(k + 1, binds[k]);
                }
            }
            cs.execute();
        }
    }

    private static long fn(Connection c, String sql, Object... binds) throws SQLException {
        try (CallableStatement cs = c.prepareCall(sql)) {
            cs.registerOutParameter(1, Types.NUMERIC);
            for (int k = 0; k < binds.length; k++) {
                if (binds[k] == null) {
                    cs.setNull(k + 2, Types.VARCHAR);
                } else if (binds[k] instanceof LocalDate d) {
                    cs.setDate(k + 2, java.sql.Date.valueOf(d));
                } else {
                    cs.setObject(k + 2, binds[k]);
                }
            }
            cs.execute();
            return cs.getLong(1);
        }
    }

    static Object post(Connection c, String[] p, Map<String, Object> in) throws SQLException {
        if ("payments".equals(p[0])) {
            if (p.length == 1) {
                return newPayment(c, in);
            }
            if (p.length == 3 && "cancel".equals(p[2])) {
                long id = Http.id(p[1]);
                call(c, "begin mm_core.cancel_payment(?); end;", id);
                return payment(c, id);
            }
            throw new Http.Fail(404, "not_found", "no such endpoint");
        }
        if (!"docs".equals(p[0])) {
            throw new Http.Fail(404, "not_found", "no such endpoint");
        }
        if (p.length == 1) {
            if (in.get("from_note") != null) {
                return doc(c, fn(c, "begin ? := mm_core.invoice_from(?, ?); end;",
                        idOf(in.get("from_note"), "from_note"), dateOf(in, "doc_date")));
            }
            String type = String.valueOf(Http.text(in, "doc_type", true)).toUpperCase(java.util.Locale.ROOT);
            if ("ALP".equals(type)) {
                throw new Http.Fail(400, "bad_type", "Οι αποδείξεις λιανικής γίνονται στο ταμείο");
            }
            Object cu = in.get("customer_id");
            Object su = in.get("supplier_id");
            String pay = String.valueOf(in.getOrDefault("payment", "CREDIT")).toUpperCase(java.util.Locale.ROOT);
            return doc(c, fn(c, "begin ? := mm_core.new_doc(?, ?, ?, null, ?, ?); end;", type,
                    cu == null ? null : idOf(cu, "customer_id"), su == null ? null : idOf(su, "supplier_id"),
                    pay, dateOf(in, "doc_date")));
        }
        if (p.length == 2 && "from-min-stock".equals(p[1])) {   // the orders to the suppliers (drafts DPA)
            Object sup = in.get("supplier_id");
            int n;
            try (CallableStatement cs = c.prepareCall("begin ? := mm_core.order_missing(?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                if (sup == null) {
                    cs.setNull(2, Types.NUMERIC);
                } else {
                    cs.setLong(2, Http.id(String.valueOf(sup).replaceAll("\\.0$", "")));
                }
                cs.execute();
                n = cs.getInt(1);
            }
            Map<String, Object> out = new java.util.LinkedHashMap<>();
            out.put("lines", n);
            out.put("drafts", Db.rows(c, """
                    select d.id, d.doc_type, s.name supplier, d.total,
                           (select count(*) from mm_doc_line l where l.doc_id = d.id) lines
                    from mm_doc d join mm_supplier s on s.id = d.supplier_id
                    where d.doc_type = 'DPA' and d.status = 'D' order by s.name, d.id"""));
            return out;
        }
        long id = Http.id(p[1]);
        if (p.length == 3 && "mydata".equals(p[2])) {             // sent to AADE now (myDATA)
            MyData.send(c, id);
            return doc(c, id);
        }
        if (p.length == 4 && "mydata".equals(p[2]) && "cancel".equals(p[3])) {
            MyData.cancel(c, id);
            return doc(c, id);
        }
        if (p.length == 3) {
            switch (p[2]) {
                case "lines" -> {
                    Map<String, Object> d = draft(c, id);
                    String code = Http.text(in, "code", true);
                    Object v = Db.rows(c, "select mm_core.find_item(?) id from dual", code).get(0).get("id");
                    if (v == null) {
                        throw new Http.Fail(404, "not_found", "Δεν βρέθηκε είδος: " + code);
                    }
                    BigDecimal qty = Http.decimal(in, "qty", BigDecimal.ONE);
                    String tracked = (String) Db.rows(c, "select serial_tracked s from mm_item where id = ?", v).get(0).get("s");
                    boolean saleOut = "S".equals(d.get("side")) && ((BigDecimal) d.get("stock_sign")).intValue() == -1;
                    if ("Y".equals(tracked) && saleOut) {
                        fn(c, "begin ? := mm_core.sell_serials(?, ?, ?); end;", id, v, qty);   // the oldest cards
                    } else if ("Y".equals(tracked) && ((BigDecimal) d.get("stock_sign")).intValue() == 1) {
                        throw new Http.Fail(400, "serials", "Κάρτες με serials φορτώνονται από τη φόρμα «Τιμολόγια» (το serial και το PIN της καθεμιάς)");
                    } else {
                        long line = fn(c, "begin ? := mm_core.add_line(?, ?, ?, ?, ?); end;", id, v, qty,
                                Http.decimal(in, "price", null), Http.decimal(in, "discount", BigDecimal.ZERO));
                        expires(c, line, in);
                    }
                    return doc(c, id);
                }
                case "notes" -> {
                    call(c, "begin mm_core.add_note(?, ?); end;", id, idOf(in.get("note_id"), "note_id"));
                    return doc(c, id);
                }
                case "post" -> {
                    fn(c, "begin ? := mm_core.post_doc(?); end;", id);
                    return doc(c, id);
                }
                case "cancel" -> {
                    doc(c, id);
                    call(c, "begin mm_core.cancel_doc(?); end;", id);
                    return doc(c, id);
                }
                case "delete" -> {
                    draft(c, id);
                    call(c, "begin mm_core.delete_doc(?); end;", id);
                    return Map.of("ok", true, "id", id);
                }
                case "credit" -> {
                    doc(c, id);
                    return doc(c, fn(c, "begin ? := mm_core.credit_note(?); end;", id));
                }
                default -> {
                }
            }
        }
        if (p.length == 4 && "lines".equals(p[2])) {
            draft(c, id);
            long line = Http.id(p[3]);
            List<Map<String, Object>> l = Db.rows(c, """
                    select l.price, l.discount, i.serial_tracked from mm_doc_line l join mm_item i on i.id = l.item_id
                    where l.id = ? and l.doc_id = ?""", line, id);
            if (l.isEmpty()) {
                throw new Http.Fail(404, "not_found", "no such line in the document");
            }
            expires(c, line, in);
            BigDecimal qty = Http.decimal(in, "qty", null);
            if (qty == null && !in.containsKey("price") && !in.containsKey("discount")) {
                return doc(c, id);                      // its date of expiry only
            }
            if (qty != null && qty.signum() == 0) {
                call(c, "begin mm_core.delete_line(?); end;", line);
            } else {
                if (qty == null || qty.signum() < 0) {
                    throw new Http.Fail(400, "bad_number", "qty: 0 or more");
                }
                if ("Y".equals(l.get(0).get("serial_tracked"))) {
                    throw new Http.Fail(400, "serials", "Γραμμή με κάρτες: βγάλ' τη (0) και βάλ' την ξανά");
                }
                call(c, "begin mm_core.update_line(?, ?, ?, ?); end;", line, qty,
                        Http.decimal(in, "price", (BigDecimal) l.get(0).get("price")),
                        Http.decimal(in, "discount", (BigDecimal) l.get(0).get("discount")));
            }
            return doc(c, id);
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    // -- receipts and payments ----------------------------------------------------------------------
    private static final String PAYMENT = """
            select p.id, p.kind, p.pay_date, p.customer_id, p.supplier_id, nvl(cu.name, s.name) partner, p.amount,
                   p.method, p.status, p.notes, r.code register, p.created_at
            from mm_payment p
            left join mm_customer cu on cu.id = p.customer_id
            left join mm_supplier s on s.id = p.supplier_id
            left join mm_register r on r.id = p.register_id
            """;

    private static Map<String, Object> payment(Connection c, long id) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, PAYMENT + " where p.id = ?", id);
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such payment: " + id);
        }
        return r.get(0);
    }

    private static Object payments(Connection c, Map<String, String> q) throws SQLException {
        String kind = q.get("kind");
        String s = q.getOrDefault("q", "").trim();
        String like = s.isEmpty() ? null : s;
        int limit = Http.number(q, "limit", 50, 1, MAX_LIMIT);
        int offset = Http.number(q, "offset", 0, 0, Integer.MAX_VALUE);
        String where = " where (? is null or p.kind = ?) and (? is null or upper(nvl(cu.name, s.name)) like '%' || upper(?) || '%')";
        List<Map<String, Object>> rows = Db.rows(c, PAYMENT + where + " order by p.pay_date desc, p.id desc offset ? rows fetch next ? rows only",
                kind, kind, like, like, offset, limit);
        Object total = Db.rows(c, """
                select count(*) n from mm_payment p
                left join mm_customer cu on cu.id = p.customer_id
                left join mm_supplier s on s.id = p.supplier_id""" + where, kind, kind, like, like).get(0).get("n");
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("limit", limit);
        out.put("offset", offset);
        out.put("total", total);
        out.put("rows", rows);
        return out;
    }

    private static Object newPayment(Connection c, Map<String, Object> in) throws SQLException {
        String kind = String.valueOf(Http.text(in, "kind", true)).toUpperCase(java.util.Locale.ROOT);
        if (!"R".equals(kind) && !"P".equals(kind)) {
            throw new Http.Fail(400, "bad_kind", "kind: R (receipt from a customer) or P (payment to a supplier)");
        }
        Object reg = null;
        String code = Http.text(in, "register", false);
        if (code != null) {
            List<Map<String, Object>> r = Db.rows(c, "select id from mm_register where code = upper(?)", code);
            if (r.isEmpty()) {
                throw new Http.Fail(404, "not_found", "no such register: " + code);
            }
            reg = r.get(0).get("id");
        }
        String method = String.valueOf(in.getOrDefault("method", "R".equals(kind) ? "CASH" : "BANK")).toUpperCase(java.util.Locale.ROOT);
        long id = fn(c, "begin ? := mm_core." + ("R".equals(kind) ? "receive" : "pay") + "(?, ?, ?, ?, ?, ?); end;",
                idOf(in.get("partner_id"), "partner_id"), Http.decimal(in, "amount", null), method,
                dateOf(in, "pay_date"), reg, Http.text(in, "notes", false));
        return payment(c, id);
    }
}
