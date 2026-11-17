package mm.api;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The till of the pages (as the form MM_POS): a register by its code, its Z, the draft receipt of the
 * register (made at the first scan), its lines, paid by cash or card. Every call returns the state of the
 * register, as the screen shows it. CASHIER and above.
 *
 * <pre>
 *   GET  /api/pos                              the registers, each with its open Z (or none)
 *   GET  /api/pos/{register}                   its Z (with what it holds so far), the draft, the last receipts
 *   POST /api/pos/{register}/open {cash}       a Z opened, with the cash in the drawer
 *   POST /api/pos/{register}/close             the Z closed: its totals in "closed"
 *   POST /api/pos/{register}/cash {amount, note}   money in (+) or out (-) of the drawer
 *   POST /api/pos/{register}/scan {code, qty}  an item by barcode or code (a card of mobile: one, the
 *                                              oldest), or a card by its serial (a scratch ticket: its barcode)
 *   POST /api/pos/{register}/prize {amount, ticket}   a prize of a scratch ticket, paid from the drawer
 *   POST /api/pos/{register}/lines/{id} {qty}  the quantity of a line (0: the line out)
 *   POST /api/pos/{register}/void              the draft out (an order in it: open again)
 *   POST /api/pos/{register}/order {id}        an order (Orders), all of its lines, into the receipt
 *   GET  /api/pos/{register}/receipt/{id}      a receipt of the register to print (80 mm): the header and
 *                                              the footer of the shop, its lines, its VAT, the PINs of
 *                                              its cards sold today (each print in MM_PIN_LOG, by whom)
 *   GET  /api/pos/settings                     the header and the footer of the receipts
 *   POST /api/pos/settings {header, footer}    (MANAGER)
 *   POST /api/pos/{register}/pay {payment CASH|CARD, given}   posted: its number, total, what was due
 *                                              (less a deposit of its order) and the change
 * </pre>
 */
final class Pos {
    private Pos() {
    }

    static Object get(Connection c, Api.User u, String[] p) throws SQLException {
        if (p.length == 2 && "settings".equals(p[1])) {
            return settings(c);
        }
        if (p.length == 4 && "receipt".equals(p[2])) {
            return receipt(c, u, register(c, p[1]), Http.id(p[3]));
        }
        if (p.length == 1) {
            return Map.of("rows", Db.rows(c, """
                    select r.id, r.code, r.name, z.id z_id, z.z_no, z.opened_at
                    from mm_register r left join mm_z z on z.register_id = r.id and z.status = 'O'
                    where r.active = 'Y' order by r.code"""));
        }
        if (p.length == 2) {
            return state(c, register(c, p[1]));
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    static Object post(Connection c, Api.User u, String[] p, Map<String, Object> in) throws SQLException {
        if (p.length == 2 && "settings".equals(p[1])) {
            if (!u.atLeast("MANAGER")) {
                throw new Http.Fail(403, "forbidden", "only MANAGER or above");
            }
            for (String k : new String[] {"header", "footer"}) {
                String v = Http.text(in, k, false);
                if (v != null && v.length() > 400) {
                    throw new Http.Fail(400, "too_long", k + ": up to 400 characters");
                }
                try (java.sql.PreparedStatement st = c.prepareStatement("""
                        merge into mm_setting s using (select ? name, ? value from dual) v on (s.name = v.name)
                        when matched then update set s.value = v.value
                        when not matched then insert (name, value) values (v.name, v.value)""")) {
                    st.setString(1, "RECEIPT_" + k.toUpperCase(java.util.Locale.ROOT));
                    st.setString(2, v);
                    st.executeUpdate();
                }
            }
            return settings(c);
        }
        if (p.length < 3) {
            throw new Http.Fail(404, "not_found", "no such endpoint");
        }
        long reg = register(c, p[1]);
        Map<String, Object> extra = new LinkedHashMap<>();
        switch (p[2]) {
            case "open" -> {
                if (p.length != 3) {
                    break;
                }
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.open_z(?, ?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setLong(2, reg);
                    cs.setBigDecimal(3, Http.decimal(in, "cash", BigDecimal.ZERO));
                    cs.execute();
                }
                return state(c, reg);
            }
            case "close" -> {
                if (p.length != 3) {
                    break;
                }
                long z;
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.close_z(?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setLong(2, reg);
                    cs.execute();
                    z = cs.getLong(1);
                }
                Map<String, Object> closed = Db.rows(c, """
                        select id, z_no, opened_at, closed_at, docs, net, vat, total, cash, card
                        from mm_z where id = ?""", z).get(0);
                closed.put("vat_rows", Db.rows(c, """
                        select vat_code, net, vat, total from mm_z_vat where z_id = ? order by vat_code""", z));
                extra.put("closed", closed);
                return with(state(c, reg), extra);
            }
            case "prize" -> {                // a prize of a scratch ticket, paid from the drawer
                if (p.length != 3) {
                    break;
                }
                try (CallableStatement cs = c.prepareCall("begin mm_core.scratch_prize(?, ?, ?); end;")) {
                    cs.setLong(1, reg);
                    cs.setBigDecimal(2, Http.decimal(in, "amount", null));
                    cs.setString(3, Http.text(in, "ticket", false));
                    cs.execute();
                }
                return state(c, reg);
            }
            case "cash" -> {
                if (p.length != 3) {
                    break;
                }
                try (CallableStatement cs = c.prepareCall("begin mm_core.cash_in_out(?, ?, ?); end;")) {
                    cs.setLong(1, reg);
                    cs.setBigDecimal(2, Http.decimal(in, "amount", null));
                    cs.setString(3, Http.text(in, "note", false));
                    cs.execute();
                }
                return state(c, reg);
            }
            case "scan" -> {
                if (p.length != 3) {
                    break;
                }
                scan(c, reg, Http.text(in, "code", true), Http.decimal(in, "qty", BigDecimal.ONE));
                return state(c, reg);
            }
            case "lines" -> {
                if (p.length != 4) {
                    break;
                }
                long line = Http.id(p[3]);
                Long d = draft(c, reg);
                List<Map<String, Object>> l = d == null ? List.of() : Db.rows(c, """
                        select l.price, l.discount, i.serial_tracked
                        from mm_doc_line l join mm_item i on i.id = l.item_id
                        where l.id = ? and l.doc_id = ?""", line, d);
                if (l.isEmpty()) {
                    throw new Http.Fail(404, "not_found", "no such line in the receipt of this register");
                }
                BigDecimal q = Http.decimal(in, "qty", null);
                if (q == null || q.signum() < 0) {
                    throw new Http.Fail(400, "bad_number", "qty: 0 or more");
                }
                if (q.signum() == 0) {
                    try (CallableStatement cs = c.prepareCall("begin mm_core.delete_line(?); end;")) {
                        cs.setLong(1, line);
                        cs.execute();
                    }
                } else {
                    if ("Y".equals(l.get(0).get("serial_tracked"))) {
                        throw new Http.Fail(400, "serial", "a card of mobile: scan one more, or the line out");
                    }
                    try (CallableStatement cs = c.prepareCall("begin mm_core.update_line(?, ?, ?, ?); end;")) {
                        cs.setLong(1, line);
                        cs.setBigDecimal(2, q);
                        cs.setBigDecimal(3, (BigDecimal) l.get(0).get("price"));
                        cs.setBigDecimal(4, (BigDecimal) l.get(0).get("discount"));
                        cs.execute();
                    }
                }
                return state(c, reg);
            }
            case "void" -> {
                if (p.length != 3) {
                    break;
                }
                Long d = draft(c, reg);
                if (d != null) {
                    try (CallableStatement cs = c.prepareCall("begin mm_core.delete_doc(?); end;")) {
                        cs.setLong(1, d);
                        cs.execute();
                    }
                }
                return state(c, reg);
            }
            case "order" -> {
                if (p.length != 3) {
                    break;
                }
                if (openZ(c, reg) == null) {
                    throw new Http.Fail(409, "z_closed", "Το ταμείο δεν έχει ανοιχτό Ζ: «Άνοιγμα Ζ»");
                }
                Long d = draft(c, reg);
                if (d != null) {
                    Object n = Db.rows(c, "select count(*) n from mm_doc_line where doc_id = ?", d).get(0).get("n");
                    if (((BigDecimal) n).signum() > 0) {
                        throw new Http.Fail(409, "receipt_open", "Υπάρχει ανοιχτή απόδειξη: πλήρωσέ την ή ακύρωσέ την πρώτα");
                    }
                    try (CallableStatement cs = c.prepareCall("begin mm_core.delete_doc(?); end;")) {
                        cs.setLong(1, d);
                        cs.execute();
                    }
                }
                try (CallableStatement cs = c.prepareCall("begin ? := mm_core.deliver(?, ?); end;")) {
                    cs.registerOutParameter(1, Types.NUMERIC);
                    cs.setLong(2, Http.id(String.valueOf(in.get("id")).replaceAll("\\.0$", "")));
                    cs.setLong(3, reg);
                    cs.execute();
                }
                return state(c, reg);
            }
            case "pay" -> {
                if (p.length != 3) {
                    break;
                }
                extra.put("paid", pay(c, reg, in));
                return with(state(c, reg), extra);
            }
            default -> {
            }
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    private static Map<String, Object> with(Object state, Map<String, Object> extra) {
        @SuppressWarnings("unchecked")
        Map<String, Object> m = (Map<String, Object>) state;
        m.putAll(extra);
        return m;
    }

    private static long register(Connection c, String code) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, "select id from mm_register where code = upper(?) and active = 'Y'",
                java.net.URLDecoder.decode(code, java.nio.charset.StandardCharsets.UTF_8));
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such register: " + code);
        }
        return ((BigDecimal) r.get(0).get("id")).longValue();
    }

    private static Long draft(Connection c, long reg) throws SQLException {
        Object d = Db.rows(c, "select max(id) id from mm_doc where register_id = ? and doc_type = 'ALP' and status = 'D'",
                reg).get(0).get("id");
        return d == null ? null : ((BigDecimal) d).longValue();
    }

    private static long draftOrNew(Connection c, long reg) throws SQLException {
        Long d = draft(c, reg);
        if (d != null) {
            return d;
        }
        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.new_doc('ALP', null, null, ?, 'CASH'); end;")) {
            cs.registerOutParameter(1, Types.NUMERIC);
            cs.setLong(2, reg);
            cs.execute();
            return cs.getLong(1);
        }
    }

    private static Long openZ(Connection c, long reg) throws SQLException {
        Object z = Db.rows(c, "select mm_core.open_z_of(?) z from dual", reg).get(0).get("z");
        return z == null ? null : ((BigDecimal) z).longValue();
    }

    /** as the form: an item (its qty; a card of mobile: one, the oldest), or a card by its serial */
    private static void scan(Connection c, long reg, String code, BigDecimal qty) throws SQLException {
        if (openZ(c, reg) == null) {
            throw new Http.Fail(409, "z_closed", "Το ταμείο δεν έχει ανοιχτό Ζ: «Άνοιγμα Ζ»");
        }
        Object v = Db.rows(c, "select mm_core.find_item(?) id from dual", code).get(0).get("id");
        if (v == null) {
            Object n = Db.rows(c, "select count(*) n from mm_serial where serial = ? and status = 'A'", code).get(0).get("n");
            if (((BigDecimal) n).signum() == 0) {
                // sold already (a scratch ticket scanned twice): say so, and where
                List<Map<String, Object>> sold = Db.rows(c, """
                        select case d.doc_type when 'ALP' then 'ΑΛΠ' else d.doc_type end || ' ' || d.doc_no doc,
                               to_char(s.sold_at, 'DD/MM HH24:MI') at_
                        from mm_serial s left join mm_doc d on d.id = s.out_doc_id
                        where s.serial = ? and s.status in ('S', 'R') order by s.id desc fetch first 1 rows only""", code);
                if (!sold.isEmpty()) {
                    Map<String, Object> x = sold.get(0);
                    throw new Http.Fail(409, "sold", "Το " + code + " έχει ήδη " + (x.get("at_") == null
                            ? "μπει σε απόδειξη" : "πουληθεί (" + x.get("doc") + ", " + x.get("at_") + ")"));
                }
                throw new Http.Fail(404, "not_found", "Δεν βρέθηκε είδος ή κάρτα: " + code);
            }
            long d = draftOrNew(c, reg);
            try (CallableStatement cs = c.prepareCall("begin ? := mm_core.sell_serial(?, null, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setLong(2, d);
                cs.setString(3, code);
                cs.execute();
            }
            return;
        }
        String tracked = (String) Db.rows(c, "select serial_tracked s from mm_item where id = ?", v).get(0).get("s");
        long d = draftOrNew(c, reg);
        if ("Y".equals(tracked)) {
            try (CallableStatement cs = c.prepareCall("begin ? := mm_core.sell_serial(?, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setLong(2, d);
                cs.setObject(3, v);
                cs.execute();
            }
        } else {
            if (qty.signum() <= 0) {
                throw new Http.Fail(400, "bad_number", "qty: more than 0");
            }
            try (CallableStatement cs = c.prepareCall("begin ? := mm_core.add_line(?, ?, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setLong(2, d);
                cs.setObject(3, v);
                cs.setBigDecimal(4, qty);
                cs.execute();
            }
        }
    }

    private static Map<String, Object> pay(Connection c, long reg, Map<String, Object> in) throws SQLException {
        Long d = draft(c, reg);
        if (d == null) {
            throw new Http.Fail(409, "no_receipt", "Δεν υπάρχει απόδειξη: σάρωσε πρώτα τα είδη");
        }
        String how = String.valueOf(Http.text(in, "payment", true)).toUpperCase(java.util.Locale.ROOT);
        if (!"CASH".equals(how) && !"CARD".equals(how)) {
            throw new Http.Fail(400, "bad_payment", "payment: CASH or CARD");
        }
        try (CallableStatement cs = c.prepareCall("begin mm_core.set_payment(?, ?); end;")) {
            cs.setLong(1, d);
            cs.setString(2, how);
            cs.execute();
        }
        long no;
        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.post_doc(?); end;")) {
            cs.registerOutParameter(1, Types.NUMERIC);
            cs.setLong(2, d);
            cs.execute();
            no = cs.getLong(1);
        }
        Map<String, Object> doc = Db.rows(c, "select total, deposit from mm_doc where id = ?", d).get(0);
        BigDecimal total = (BigDecimal) doc.get("total");
        BigDecimal due = total.subtract((BigDecimal) doc.get("deposit"));
        BigDecimal given = Http.decimal(in, "given", null);
        BigDecimal change = null;
        if ("CASH".equals(how) && given != null) {
            if (given.compareTo(due) < 0) {
                // (the caller rolls back: nothing posted)
                throw new Http.Fail(400, "not_enough", "Δόθηκαν " + given.toPlainString() + ", η απόδειξη είναι "
                        + due.toPlainString());
            }
            change = given.subtract(due);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", d);
        out.put("doc_no", no);
        out.put("payment", how);
        out.put("total", total);
        out.put("due", due);
        out.put("given", given);
        out.put("change", change);
        return out;
    }

    /** the register, its open Z (what it holds so far), the draft with its lines, the last receipts */
    private static Object state(Connection c, long reg) throws SQLException {
        Map<String, Object> out = Db.rows(c, "select id, code, name from mm_register where id = ?", reg).get(0);
        Long z = openZ(c, reg);
        if (z == null) {
            out.put("z", null);
        } else {
            out.put("z", Db.rows(c, """
                    select z.id, z.z_no, z.opened_at,
                           (select count(*) from mm_doc d where d.z_id = z.id and d.status = 'P') docs,
                           nvl(sum(case when m.kind in ('SALE', 'REFUND', 'DEPOSIT') and m.payment = 'CASH' then m.amount end), 0) cash,
                           nvl(sum(case when m.kind in ('SALE', 'REFUND', 'DEPOSIT') and m.payment = 'CARD' then m.amount end), 0) card,
                           nvl(sum(case when m.payment = 'CASH' then m.amount end), 0) drawer
                    from mm_z z left join mm_cash_move m on m.z_id = z.id
                    where z.id = ? group by z.id, z.z_no, z.opened_at""", z).get(0));
        }
        Long d = draft(c, reg);
        if (d == null) {
            out.put("receipt", null);
        } else {
            Map<String, Object> r = Db.rows(c, """
                    select d.id, d.net, d.vat, d.total, d.deposit, d.total - d.deposit due,
                           (select max(x.id) from mm_reservation x where x.doc_id = d.id) order_id
                    from mm_doc d where d.id = ?""", d).get(0);
            r.put("lines", Db.rows(c, """
                    select l.id, l.line_no, i.code, i.name, i.unit, i.serial_tracked, l.qty, l.price, l.discount,
                           l.total,
                           (select listagg(s.serial, ', ') within group (order by s.serial) from mm_serial s
                            where s.out_line_id = l.id) serials
                    from mm_doc_line l join mm_item i on i.id = l.item_id
                    where l.doc_id = ? order by l.line_no""", d));
            out.put("receipt", r);
        }
        out.put("last", z == null ? List.of() : Db.rows(c, """
                select id, doc_no, created_at, payment, total, status from mm_doc
                where z_id = ? and doc_type = 'ALP' and status in ('P', 'C')
                order by id desc fetch first 5 rows only""", z));
        return out;
    }

    private static Map<String, Object> settings(Connection c) throws SQLException {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("header", null);
        out.put("footer", null);
        for (Map<String, Object> r : Db.rows(c, "select name, value from mm_setting where name in ('RECEIPT_HEADER', 'RECEIPT_FOOTER')")) {
            out.put("RECEIPT_HEADER".equals(r.get("name")) ? "header" : "footer", r.get("value"));
        }
        return out;
    }

    /** a posted (or cancelled) receipt of this register, as printed: the PINs of its cards sold today */
    private static Object receipt(Connection c, Api.User u, long reg, long id) throws SQLException {
        List<Map<String, Object>> h = Db.rows(c, """
                select d.id, d.doc_no, d.created_at, d.status, d.payment, d.net, d.vat, d.total, d.deposit,
                       d.total - d.deposit due, r.code register, r.name register_name, z.z_no
                from mm_doc d join mm_register r on r.id = d.register_id left join mm_z z on z.id = d.z_id
                where d.id = ? and d.register_id = ? and d.doc_type = 'ALP' and d.status in ('P', 'C')""", id, reg);
        if (h.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such receipt of this register: " + id);
        }
        Map<String, Object> out = new LinkedHashMap<>(h.get(0));
        out.putAll(settings(c));
        out.put("lines", Db.rows(c, """
                select l.id, i.code, i.name, i.unit, l.qty, l.price, l.discount, l.vat_code, l.vat_rate, l.total
                from mm_doc_line l join mm_item i on i.id = l.item_id
                where l.doc_id = ? order by l.line_no""", id));
        out.put("vat_rows", Db.rows(c, """
                select vat_code, vat_rate, sum(net) net, sum(vat) vat, sum(total) total
                from mm_doc_line where doc_id = ? group by vat_code, vat_rate order by vat_code""", id));
        List<Map<String, Object>> cards = Db.rows(c, """
                select s.id, s.serial, i.name, case when s.pin_enc is null then 'N' else 'Y' end has_pin
                from mm_serial s join mm_item i on i.id = s.item_id
                where s.out_doc_id = ? and s.status = 'S' order by s.serial""", id);
        if (!cards.isEmpty() && "P".equals(out.get("status"))) {
            // who printed the PINs: the user of the login (MM_PIN_LOG), not a name typed
            try (CallableStatement cs = c.prepareCall("begin dbms_session.set_identifier(?); end;")) {
                cs.setString(1, u.username());
                cs.execute();
            }
            try {
                for (Map<String, Object> card : cards) {
                    if (!"Y".equals(card.get("has_pin"))) {
                        continue;
                    }
                    try (CallableStatement cs = c.prepareCall("begin ? := mm_core.receipt_pin(?); end;")) {
                        cs.registerOutParameter(1, Types.VARCHAR);
                        cs.setObject(2, card.get("id"));
                        cs.execute();
                        card.put("pin", cs.getString(1));
                    } catch (SQLException e) {
                        card.put("pin", null);              // not sold today (MM-144), no MM_PIN
                    }
                }
            } finally {
                try (CallableStatement cs = c.prepareCall("begin dbms_session.clear_identifier; end;")) {
                    cs.execute();
                }
            }
        }
        cards.forEach(card -> card.remove("has_pin"));
        out.put("cards", cards);
        return out;
    }
}
