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
 *   GET  /api/pos                              the registers the user may work on (mm_auth.may_use: its
 *                                              store, its register: mine Y), each with its open Z (or none);
 *                                              another register: 403 not_your_register
 *   GET  /api/pos/{register}                   its Z (with what it holds so far), the draft, the last receipts
 *   POST /api/pos/{register}/open {cash}       a Z opened, with the cash in the drawer
 *   POST /api/pos/{register}/close             the Z closed: its totals in "closed"
 *   POST /api/pos/{register}/cash {amount, note}   money in (+) or out (-) of the drawer
 *   GET  /api/pos/tiles                        the buttons of the till (Tiles: groups, tiles, the frequent)
 *   POST /api/pos/{register}/item {item_id, qty, options}   a button of the till: the item, as a scan of its
 *                                              code, with the options chosen (their ids; none: the defaults)
 *   POST /api/pos/{register}/scan {code, qty}  an item by barcode, code or short number (PLU) (a card of mobile: one, the
 *                                              oldest), or a card by its serial (a scratch ticket: its barcode)
 *   POST /api/pos/{register}/prize {amount, ticket}   a prize of a scratch ticket, paid from the drawer
 *   POST /api/pos/{register}/customer {code}   the customer of the receipt (points): its card (a scan of it
 *                                              at /scan works as well) or its phone; none: out of the receipt
 *   POST /api/pos/{register}/customer/new {name, phone}   a new customer with a card, into the receipt
 *   POST /api/pos/{register}/points {points}   points of its customer used on the receipt (0: none)
 *   POST /api/pos/{register}/warehouse {warehouse_id}   the warehouse its sales are from (MANAGER)
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
        if (p.length == 2 && "tiles".equals(p[1])) {
            return Tiles.forTill(c);
        }
        if (p.length == 4 && "receipt".equals(p[2])) {
            return receipt(c, u, register(c, u, p[1]), Http.id(p[3]));
        }
        if (p.length == 1) {
            // the registers the user may work on (its store, its register); its own register: "mine"
            return Map.of("rows", Db.rows(c, """
                    select r.id, r.code, r.name, z.id z_id, z.z_no, z.opened_at,
                           case when r.id = (select register_id from mm_user where id = ?) then 'Y' else 'N' end mine
                    from mm_register r left join mm_z z on z.register_id = r.id and z.status = 'O'
                    where r.active = 'Y' and mm_auth.may_use(?, r.id) = 'Y' order by r.code""", u.id(), u.id()));
        }
        if (p.length == 2) {
            return state(c, register(c, u, p[1]));
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    static Object post(Connection c, Api.User u, String[] p, Map<String, Object> in) throws SQLException {
        if (p.length == 2 && "settings".equals(p[1])) {
            // (the right of it: Rights.check)
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
        long reg = register(c, u, p[1]);
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
            case "item" -> {                    // a button of the till: an item by its id, as a scan of its code
                if (p.length != 3) {
                    break;
                }
                BigDecimal id = Http.decimal(in, "item_id", null);
                List<Map<String, Object>> it = id == null ? List.of()
                        : Db.rows(c, "select code from mm_item where id = ? and active = 'Y'", id);
                if (it.isEmpty()) {
                    throw new Http.Fail(404, "not_found", "Δεν βρέθηκε ενεργό είδος " + id);
                }
                Object opts = in.get("options");
                String csv = null;
                if (opts instanceof List<?> l) {
                    StringBuilder sb = new StringBuilder();
                    for (Object o : l) {
                        BigDecimal x;
                        try {
                            x = new BigDecimal(String.valueOf(o));
                        } catch (NumberFormatException e) {
                            throw new Http.Fail(400, "bad_options", "options: the ids of the options");
                        }
                        sb.append(sb.length() > 0 ? "," : "").append(x.toBigInteger());
                    }
                    csv = sb.length() > 0 ? sb.toString() : null;
                } else if (opts != null) {
                    throw new Http.Fail(400, "bad_options", "options: a list of the ids of the options");
                }
                scan(c, reg, (String) it.get(0).get("code"), Http.decimal(in, "qty", BigDecimal.ONE), csv);
                return state(c, reg);
            }
            case "warehouse" -> {               // the warehouse of the register: its sales from there (MANAGER)
                if (p.length != 3) {
                    break;
                }
                // (the right of it: Rights.check)
                if (draft(c, reg) != null) {
                    throw new Http.Fail(409, "receipt_open", "Η απόδειξη που γράφεται: πρώτα πληρωμή ή ακύρωση");
                }
                Object w = in.get("warehouse_id");
                if (!(w instanceof Number) || Db.rows(c, "select id from mm_warehouse where id = ? and active = 'Y'",
                        ((Number) w).longValue()).isEmpty()) {
                    throw new Http.Fail(400, "bad_warehouse", "warehouse_id: an active warehouse");
                }
                Db.exec(c, "begin update mm_register set warehouse_id = ? where id = ?; end;", ((Number) w).longValue(), reg);
                return state(c, reg);
            }
            case "customer" -> {
                if (p.length == 4 && "new".equals(p[3])) {
                    String name = Http.text(in, "name", true).trim();
                    String phone = Http.text(in, "phone", false);
                    if (name.isEmpty() || name.length() > 100 || (phone != null && phone.length() > 20)) {
                        throw new Http.Fail(400, "bad_customer", "name: 1 to 100 characters, phone up to 20");
                    }
                    if (openZ(c, reg) == null) {
                        throw new Http.Fail(409, "z_closed", "Το ταμείο δεν έχει ανοιχτό Ζ: «Άνοιγμα Ζ»");
                    }
                    long id;
                    try (CallableStatement cs = c.prepareCall(
                            "begin insert into mm_customer (name, phone) values (?, ?) returning id into ?; end;")) {
                        cs.setString(1, name);
                        cs.setString(2, phone == null || phone.isBlank() ? null : phone.trim());
                        cs.registerOutParameter(3, Types.NUMERIC);
                        cs.execute();
                        id = cs.getLong(3);
                    }
                    Db.exec(c, "declare v varchar2(20); begin v := mm_core.new_card(?); end;", id);
                    customer(c, reg, id);
                    return state(c, reg);
                }
                if (p.length != 3) {
                    break;
                }
                String code = Http.text(in, "code", false);
                if (code == null || code.isBlank()) {
                    if (draft(c, reg) != null) {
                        customer(c, reg, null);
                    }
                    return state(c, reg);
                }
                Object id = Db.rows(c, "select mm_core.card_customer(?) id from dual", code).get(0).get("id");
                if (id == null) {
                    String phone = code.replaceAll("[^0-9+]", "");
                    List<Map<String, Object>> r = phone.isEmpty() ? List.of() : Db.rows(c, """
                            select id from mm_customer where active = 'Y' and card is not null
                            and regexp_replace(phone, '[^0-9+]', '') = ? fetch first 2 rows only""", phone);
                    if (r.size() != 1) {
                        throw new Http.Fail(404, "not_found", r.isEmpty() ? "Δεν βρέθηκε πελάτης με κάρτα: " + code
                                : "Πολλοί πελάτες με το τηλέφωνο " + code + ": σάρωσε την κάρτα");
                    }
                    id = r.get(0).get("id");
                }
                customer(c, reg, ((BigDecimal) id).longValue());
                return state(c, reg);
            }
            case "points" -> {
                if (p.length != 3) {
                    break;
                }
                Long d = draft(c, reg);
                if (d == null) {
                    throw new Http.Fail(409, "no_receipt", "Δεν υπάρχει απόδειξη: σάρωσε πρώτα τα είδη");
                }
                try (CallableStatement cs = c.prepareCall("begin mm_core.use_points(?, ?); end;")) {
                    cs.setLong(1, d);
                    cs.setBigDecimal(2, Http.decimal(in, "points", BigDecimal.ZERO));
                    cs.execute();
                }
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

    /** a register by its code, if the user may work on it (mm_auth.may_use: its store, its register) */
    private static long register(Connection c, Api.User u, String code) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, """
                select id, mm_auth.may_use(?, id) may from mm_register where code = upper(?) and active = 'Y'""",
                u.id(), java.net.URLDecoder.decode(code, java.nio.charset.StandardCharsets.UTF_8));
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such register: " + code);
        }
        if (!"Y".equals(r.get(0).get("may"))) {
            throw new Http.Fail(403, "not_your_register", "Το ταμείο " + code.toUpperCase(java.util.Locale.ROOT)
                    + " δεν είναι του καταστήματός σου");
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

    /** the customer of the receipt (a new receipt if none yet); null: none */
    private static void customer(Connection c, long reg, Long id) throws SQLException {
        if (openZ(c, reg) == null) {
            throw new Http.Fail(409, "z_closed", "Το ταμείο δεν έχει ανοιχτό Ζ: «Άνοιγμα Ζ»");
        }
        long d = draftOrNew(c, reg);
        try (CallableStatement cs = c.prepareCall("begin mm_core.set_doc_customer(?, ?); end;")) {
            cs.setLong(1, d);
            cs.setObject(2, id);
            cs.execute();
        }
    }

    private static Long openZ(Connection c, long reg) throws SQLException {
        Object z = Db.rows(c, "select mm_core.open_z_of(?) z from dual", reg).get(0).get("z");
        return z == null ? null : ((BigDecimal) z).longValue();
    }

    /** as the form: an item (its qty; a card of mobile: one, the oldest), or a card by its serial */
    private static void scan(Connection c, long reg, String code, BigDecimal qty) throws SQLException {
        scan(c, reg, code, qty, null);
    }

    /** an item with options (the ids, comma separated; null: none chosen, the defaults of its groups) */
    private static void scan(Connection c, long reg, String code, BigDecimal qty, String options) throws SQLException {
        if (openZ(c, reg) == null) {
            throw new Http.Fail(409, "z_closed", "Το ταμείο δεν έχει ανοιχτό Ζ: «Άνοιγμα Ζ»");
        }
        Object v = Db.rows(c, "select mm_core.find_item(?) id from dual", code).get(0).get("id");
        if (v == null) {
            Object who = Db.rows(c, "select mm_core.card_customer(?) id from dual", code).get(0).get("id");
            if (who != null) {                      // the card of a customer: the customer of the receipt
                customer(c, reg, ((BigDecimal) who).longValue());
                return;
            }
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
            // an item with options (a coffee: sugar, milk): its line through add_line_options (the defaults)
            boolean withOptions = options != null || ((BigDecimal) Db.rows(c, """
                    select count(*) n from mm_item_option io join mm_option_group g on g.id = io.group_id
                    where io.item_id = ? and g.active = 'Y'""", v).get(0).get("n")).signum() > 0;
            try (CallableStatement cs = c.prepareCall(withOptions
                    ? "begin ? := mm_core.add_line_options(?, ?, ?, ?); end;" : "begin ? := mm_core.add_line(?, ?, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setLong(2, d);
                cs.setObject(3, v);
                cs.setBigDecimal(4, qty);
                if (withOptions) {
                    cs.setString(5, options);
                }
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
        // the number at the counter (an item of the buttons of the till: a cafe), of the day
        try (CallableStatement cs = c.prepareCall("begin ? := mm_core.counter_ticket(?); end;")) {
            cs.registerOutParameter(1, Types.NUMERIC);
            cs.setLong(2, d);
            cs.execute();
            out.put("ticket_no", cs.getObject(1));
        }
        return out;
    }

    /** the register, its open Z (what it holds so far), the draft with its lines, the last receipts */
    private static Object state(Connection c, long reg) throws SQLException {
        Map<String, Object> out = Db.rows(c, """
                select r.id, r.code, r.name, w.id warehouse_id, w.code warehouse, w.name warehouse_name
                from mm_register r join mm_warehouse w on w.id = nvl(r.warehouse_id, mm_core.main_warehouse)
                where r.id = ?""", reg).get(0);
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
                           (select max(x.id) from mm_reservation x where x.doc_id = d.id) order_id,
                           d.disc_amount, d.disc_reason, d.points_used, d.customer_id
                    from mm_doc d where d.id = ?""", d).get(0);
            Object cust = r.remove("customer_id");
            r.put("customer", cust == null ? null : Db.rows(c, """
                    select id, name, phone, card, points, trunc(? * ?) earn
                    from mm_customer where id = ?""", r.get("total"), points(c).get("per_euro"), cust).get(0));
            r.put("lines", Db.rows(c, """
                    select l.id, l.line_no, i.code, i.name, i.unit, i.serial_tracked, l.qty, l.price, l.discount,
                           l.total, l.options,
                           (select listagg(s.serial, ', ') within group (order by s.serial) from mm_serial s
                            where s.out_line_id = l.id) serials
                    from mm_doc_line l join mm_item i on i.id = l.item_id
                    where l.doc_id = ? order by l.line_no""", d));
            out.put("receipt", r);
        }
        out.put("points", points(c));
        out.put("last", z == null ? List.of() : Db.rows(c, """
                select id, doc_no, created_at, payment, total, status, ticket_no from mm_doc
                where z_id = ? and doc_type = 'ALP' and status in ('P', 'C')
                order by id desc fetch first 5 rows only""", z));
        return out;
    }

    /** the points: for each euro, the value of one, at least this many used (MM_SETTING, as mm_core) */
    static Map<String, Object> points(Connection c) throws SQLException {
        return Db.rows(c, """
                select nvl(max(case name when 'POINTS_PER_EURO' then v end), 1) per_euro,
                       nvl(max(case name when 'POINT_VALUE' then v end), 0.01) value,
                       nvl(max(case name when 'POINTS_MIN' then v end), 100) min
                from (select name, to_number(value default null on conversion error, '9999999990D9999',
                             'NLS_NUMERIC_CHARACTERS=''.,''') v
                      from mm_setting where name in ('POINTS_PER_EURO', 'POINT_VALUE', 'POINTS_MIN'))""").get(0);
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
                       d.total - d.deposit due, r.code register, r.name register_name, z.z_no,
                       d.disc_amount, d.disc_reason, d.points_used, cu.name customer, cu.card, cu.points,
                       (select nvl(sum(m.points), 0) from mm_points m where m.doc_id = d.id
                          and m.note = 'Αγορά') points_earned,
                       (select nvl(max(us.full_name), d.posted_by) from mm_user us where us.username = d.posted_by) cashier,
                       d.ticket_no
                from mm_doc d join mm_register r on r.id = d.register_id left join mm_z z on z.id = d.z_id
                left join mm_customer cu on cu.id = d.customer_id
                where d.id = ? and d.register_id = ? and d.doc_type = 'ALP' and d.status in ('P', 'C')""", id, reg);
        if (h.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such receipt of this register: " + id);
        }
        Map<String, Object> out = new LinkedHashMap<>(h.get(0));
        out.putAll(settings(c));
        out.put("lines", Db.rows(c, """
                select l.id, i.code, i.name, i.unit, l.qty, l.price, l.discount, l.vat_code, l.vat_rate, l.total,
                       l.options, case when exists (select 1 from mm_tile t where t.item_id = l.item_id) then 'Y' else 'N' end counter
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
