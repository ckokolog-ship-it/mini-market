package mm.api;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The summary of a day (σύνοψη ημέρας), for a manager after the Z: in one answer what the pages show in
 * many. MANAGER.
 *
 * <pre>
 *   GET /api/day?date=YYYY-MM-DD   (default today)
 *     zs        the Z of the registers on that day: receipts, total, cash, card, money in and out, drawer
 *     sales     the sales of the day (MM_SALES_DAY), vat its VAT by rate (MM_VAT_DAY)
 *     profit    its gross profit: revenue (net), cost (FIFO or LAST: COST_METHOD), profit
 *     top       the 10 items sold most (by value) out of the stock that day (less what came back)
 *     scratch   the scratch tickets sold and their value, the prizes paid
 *     orders    the orders written that day (online of them), the open ones now (online not confirmed)
 *     mydata    the invoices of the day to myDATA by state; waiting or failed now (any day)
 *     min_stock how many items are under their minimum now
 *     expiry    the receipts of goods expired (something left of them) and expiring in EXPIRY_DAYS, now
 *     backup    the state of the backup (MM_BACKUP_STATE)
 * </pre>
 */
final class Day {
    private Day() {
    }

    static Object get(Connection c, Map<String, String> q) throws SQLException {
        LocalDate d = Http.date(q, "date", LocalDate.now());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("date", d.toString());
        out.put("zs", Db.rows(c, """
                select r.code register, r.name register_name, z.z_no, z.status, z.opened_at, z.closed_at,
                       (select count(*) from mm_doc x where x.z_id = z.id and x.status = 'P') docs,
                       (select nvl(sum(-t.stock_sign * x.total), 0) from mm_doc x join mm_doc_type t on t.code = x.doc_type
                         where x.z_id = z.id and x.status = 'P') total,
                       nvl(sum(case when m.kind in ('SALE', 'REFUND', 'DEPOSIT') and m.payment = 'CASH' then m.amount end), 0) cash,
                       nvl(sum(case when m.kind in ('SALE', 'REFUND', 'DEPOSIT') and m.payment = 'CARD' then m.amount end), 0) card,
                       nvl(sum(case when m.kind = 'IN' then m.amount end), 0) money_in,
                       nvl(sum(case when m.kind = 'OUT' then m.amount end), 0) money_out,
                       nvl(sum(case when m.payment = 'CASH' then m.amount end), 0) drawer
                from mm_z z join mm_register r on r.id = z.register_id
                left join mm_cash_move m on m.z_id = z.id
                where z.opened_at < ? + 1 and (z.closed_at is null or z.closed_at >= ?)
                group by r.code, r.name, z.id, z.z_no, z.status, z.opened_at, z.closed_at
                order by r.code, z.z_no""", d, d));
        List<Map<String, Object>> s = Db.rows(c, """
                select alp_docs, alp_total, tpy_total, ppy_total, total from mm_sales_day where day = ?""", d);
        out.put("sales", s.isEmpty() ? Map.of("alp_docs", 0, "alp_total", 0, "tpy_total", 0, "ppy_total", 0, "total", 0)
                : s.get(0));
        // the gross profit of the day (the sales less what they cost, as the shop counts its costs)
        String method = Api.costMethod(c, null);
        Map<String, Object> profit = new LinkedHashMap<>(Db.rows(c, """
                select nvl(sum(revenue), 0) revenue, nvl(sum(cost), 0) cost, nvl(sum(profit), 0) profit
                from (""" + Api.PROFIT + ")", method, method, d, d, d, d).get(0));
        profit.put("method", method);
        out.put("profit", profit);
        out.put("vat", Db.rows(c, """
                select vat_code, vat_rate, sum(s_net) net, sum(s_vat) vat from mm_vat_day where day = ?
                group by vat_code, vat_rate having sum(s_net) <> 0 or sum(s_vat) <> 0 order by vat_code""", d));
        out.put("top", Db.rows(c, """
                select i.code, i.name, i.unit, sum(-t.stock_sign * l.qty) qty, sum(-t.stock_sign * l.total) total
                from mm_doc_line l join mm_doc x on x.id = l.doc_id join mm_doc_type t on t.code = x.doc_type
                join mm_item i on i.id = l.item_id
                where x.status = 'P' and x.doc_date = ? and t.side = 'S' and t.stock_sign <> 0
                group by i.code, i.name, i.unit having sum(-t.stock_sign * l.qty) > 0
                order by sum(-t.stock_sign * l.total) desc, i.code fetch first 10 rows only""", d));
        Map<String, Object> scratch = new LinkedHashMap<>(Db.rows(c, """
                select count(*) tickets, nvl(sum(i.price), 0) value
                from mm_serial s join mm_scratch_game g on g.item_id = s.item_id and g.game = substr(s.serial, 1, 4)
                join mm_item i on i.id = s.item_id
                where s.status = 'S' and s.sold_at >= ? and s.sold_at < ? + 1""", d, d).get(0));
        scratch.putAll(Db.rows(c, """
                select count(*) prizes, -nvl(sum(amount), 0) prizes_total from mm_cash_move
                where kind = 'OUT' and note like 'Κέρδος σκρατς%' and move_at >= ? and move_at < ? + 1""", d, d).get(0));
        out.put("scratch", scratch);
        out.put("orders", Db.rows(c, """
                select (select count(*) from mm_reservation where created_at >= ? and created_at < ? + 1) new_,
                       (select count(*) from mm_reservation where source = 'O' and created_at >= ? and created_at < ? + 1) online_new,
                       (select count(*) from mm_reservation where status = 'O') open_now,
                       (select count(*) from mm_reservation where status = 'O' and source = 'O' and confirmed_at is null) to_confirm
                from dual""", d, d, d, d).get(0));
        Map<String, Object> my = new LinkedHashMap<>();
        my.put("day", Db.rows(c, """
                select nvl(x.mydata_state, '-') state, count(*) n from mm_doc x join mm_doc_type t on t.code = x.doc_type
                where t.mydata_type is not null and x.status in ('P', 'C') and x.doc_date = ?
                group by nvl(x.mydata_state, '-') order by 1""", d));
        my.putAll(Db.rows(c, """
                select count(case when mydata_state = 'Q' then 1 end) waiting, count(case when mydata_state = 'E' then 1 end) failed
                from mm_doc""").get(0));
        out.put("mydata", my);
        out.put("min_stock", Db.rows(c, "select count(*) n from mm_min_stock").get(0).get("n"));
        Map<String, Object> exp = new LinkedHashMap<>(Db.rows(c, """
                select count(case when days_left < 0 then 1 end) expired,
                       count(case when days_left between 0 and ? then 1 end) soon
                from mm_expiry""", Expiry.days(c)).get(0));
        exp.put("days", Expiry.days(c));
        out.put("expiry", exp);
        out.put("backup", Db.rows(c, "select state, days, ok_at, failed_at, error from mm_backup_state").get(0));
        return out;
    }
}
