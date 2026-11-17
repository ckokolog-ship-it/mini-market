package mm.api;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The charts of the sales (γράφημα πωλήσεων): the days of a period up to a day, each with the same day
 * of a year before (364 days back: the same day of the week), the hours of the day, the totals. MANAGER.
 *
 * <pre>
 *   GET /api/chart?to=YYYY-MM-DD&amp;days=30   (to: default today; days 7 to 364)
 *     days     day, total (all the sales, MM_SALES_DAY), receipts, their total, last_year (the total then)
 *     hours    hour 0-23: the receipts of the period posted then, their total (less what came back)
 *     sums     total, last_year, receipts, their total, avg_receipt
 * </pre>
 */
final class Chart {
    private Chart() {
    }

    static Object get(Connection c, Map<String, String> q) throws SQLException {
        LocalDate to = Http.date(q, "to", LocalDate.now());
        int n = Http.number(q, "days", 30, 7, 364);
        LocalDate from = to.minusDays(n - 1L);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("from", from.toString());
        out.put("to", to.toString());
        out.put("days", Db.rows(c, """
                select d.day, nvl(s.total, 0) total, nvl(s.alp_docs, 0) receipts, nvl(s.alp_total, 0) receipts_total,
                       nvl(p.total, 0) last_year
                from (select ? + level - 1 day from dual connect by level <= ?) d
                left join mm_sales_day s on s.day = d.day
                left join mm_sales_day p on p.day = d.day - 364
                order by d.day""", from, n));
        out.put("hours", Db.rows(c, """
                select h.hour, nvl(x.receipts, 0) receipts, nvl(x.total, 0) total
                from (select level - 1 hour from dual connect by level <= 24) h
                left join (select to_number(to_char(d.created_at, 'HH24')) hour, count(*) receipts,
                                  sum(d.total) total
                           from mm_doc d
                           where d.doc_type = 'ALP' and d.status = 'P' and d.doc_date between ? and ?
                           group by to_number(to_char(d.created_at, 'HH24'))) x on x.hour = h.hour
                order by h.hour""", from, to));
        out.put("sums", Db.rows(c, """
                select nvl(sum(case when day >= ? then total end), 0) total,
                       nvl(sum(case when day < ? then total end), 0) last_year,
                       nvl(sum(case when day >= ? then alp_docs end), 0) receipts,
                       nvl(sum(case when day >= ? then alp_total end), 0) receipts_total,
                       round(nvl(sum(case when day >= ? then alp_total end), 0)
                             / nullif(sum(case when day >= ? then alp_docs end), 0), 2) avg_receipt
                from mm_sales_day
                where day between ? and ? or day between ? and ?""",
                from, from, from, from, from, from, from, to, from.minusDays(364), to.minusDays(364)).get(0));
        return out;
    }
}
