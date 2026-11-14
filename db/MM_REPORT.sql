-- MM_REPORT.sql -- what the reports of sales, VAT and minimum stock read (reports/mkreports.py), and
-- their Greek words (the XML of a report is ASCII). Run by INSTALL.sql.
--
--   MM_SALES_DAY      the sales of each day: receipts (their number and total), invoices, credit notes
--   MM_VAT_DAY        each day and VAT rate: net and VAT of the sales and of the purchases (a credit
--                     note takes off)
--   MM_MIN_STOCK      the items under their minimum stock, with what is missing and the supplier of
--                     their last purchase
-- Only what is posted (a cancelled receipt is not a sale).

create or replace view mm_sales_day as
select d.doc_date day,
       count(case when d.doc_type = 'ALP' then 1 end) alp_docs,
       nvl(sum(case when d.doc_type = 'ALP' then d.total end), 0) alp_total,
       nvl(sum(case when d.doc_type = 'TPY' then d.total end), 0) tpy_total,
       nvl(sum(case when d.doc_type = 'PPY' then d.total end), 0) ppy_total,
       nvl(sum(case when d.doc_type = 'PPY' then -d.total else d.total end), 0) total
from mm_doc d
where d.status = 'P' and d.doc_type in ('ALP', 'TPY', 'PPY')
group by d.doc_date;

create or replace view mm_vat_day as
select d.doc_date day, l.vat_code, l.vat_rate,
       sum(case when t.side = 'S' then -t.stock_sign * l.net else 0 end) s_net,
       sum(case when t.side = 'S' then -t.stock_sign * l.vat else 0 end) s_vat,
       sum(case when t.side = 'P' then t.stock_sign * l.net else 0 end) p_net,
       sum(case when t.side = 'P' then t.stock_sign * l.vat else 0 end) p_vat
from mm_doc d
join mm_doc_type t on t.code = d.doc_type
join mm_doc_line l on l.doc_id = d.id
where d.status = 'P'
group by d.doc_date, l.vat_code, l.vat_rate;

create or replace view mm_min_stock as
select c.name category, i.code, i.name, i.unit, i.stock + 0 stock, i.min_stock,
       i.min_stock - (i.stock + 0) missing,
       (select max(s.name) keep (dense_rank last order by d.doc_date, d.id)
        from mm_doc d join mm_doc_line l on l.doc_id = d.id join mm_supplier s on s.id = d.supplier_id
        where l.item_id = i.id and d.doc_type = 'TAG' and d.status = 'P') supplier
from mm_item i
join mm_category c on c.id = i.category_id
where i.active = 'Y' and i.is_model = 'N' and i.kit = 'N' and i.stock + 0 < i.min_stock;

create or replace package mm_report as
  -- the title of a report: SALES, VAT, MIN_STOCK
  function title(p_report varchar2) return varchar2;
  -- 'Διάστημα: 01/01/2026 - 31/12/2026', or with no period 'Ημερομηνία: <today>'
  function period(p_from varchar2 default null, p_to varchar2 default null) return varchar2;
  -- the heading of a column, the words of the totals
  function label(p_key varchar2) return varchar2;
  -- a quantity as text: 12, 0,215 (no zeros after the point)
  function qty(p_qty number) return varchar2;
end mm_report;
/

create or replace package body mm_report as
  function title(p_report varchar2) return varchar2 is
  begin
    return case upper(p_report)
      when 'SALES' then 'Πωλήσεις ανά ημέρα'
      when 'VAT' then 'ΦΠΑ πωλήσεων και αγορών'
      when 'MIN_STOCK' then 'Είδη κάτω από το ελάχιστο απόθεμα'
      else p_report end;
  end;

  function period(p_from varchar2 default null, p_to varchar2 default null) return varchar2 is
  begin
    if p_from is null and p_to is null then
      return 'Ημερομηνία: ' || to_char(sysdate, 'DD/MM/YYYY');
    end if;
    return 'Διάστημα: ' || p_from || ' - ' || p_to;
  end;

  function label(p_key varchar2) return varchar2 is
  begin
    return case upper(p_key)
      when 'DAY' then 'Ημέρα'
      when 'ALP_DOCS' then 'Αποδείξεις'
      when 'ALP_TOTAL' then 'Λιανική'
      when 'TPY_TOTAL' then 'Τιμολόγια'
      when 'PPY_TOTAL' then 'Πιστωτικά'
      when 'TOTAL' then 'Σύνολο'
      when 'VAT_TEXT' then 'ΦΠΑ'
      when 'S_NET' then 'Καθαρά πωλ.'
      when 'S_VAT' then 'ΦΠΑ πωλ.'
      when 'P_NET' then 'Καθαρά αγορ.'
      when 'P_VAT' then 'ΦΠΑ αγορ.'
      when 'PAYABLE' then 'Προς απόδοση'
      when 'CODE' then 'Κωδικός'
      when 'NAME' then 'Περιγραφή'
      when 'UNIT' then 'Μον.'
      when 'STOCK' then 'Απόθεμα'
      when 'MIN_STOCK' then 'Ελάχιστο'
      when 'MISSING' then 'Λείπουν'
      when 'SUPPLIER' then 'Τελευταίος προμηθευτής'
      when 'SUBTOTAL' then 'Σύνολο μήνα'
      when 'SUBTOTAL_CAT' then 'Είδη κατηγορίας'
      when 'GRAND' then 'Γενικό σύνολο'
      when 'GRAND_CAT' then 'Είδη συνολικά'
      when 'PAGE' then 'Σελίδα'
      else p_key end;
  end;

  function qty(p_qty number) return varchar2 is
  begin
    return rtrim(rtrim(to_char(p_qty, 'FM999G999G990D999'), '0'), '.,');
  end;
end mm_report;
/
