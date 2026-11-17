-- MM_REPORT.sql -- what the reports of sales, VAT and minimum stock read (reports/mkreports.py), and
-- their Greek words (the XML of a report is ASCII). Run by INSTALL.sql.
--
--   MM_SALES_DAY      the sales of each day: receipts (their number and total), invoices (and TDA), credit notes
--   MM_VAT_DAY        each day and VAT rate: net and VAT of the sales and of the purchases (a credit
--                     note takes off)
--   MM_MIN_STOCK      the items under their minimum stock, with what is missing and the supplier of
--                     their last purchase
-- Only what is posted (a cancelled receipt is not a sale).

create or replace view mm_sales_day as
select d.doc_date day,
       count(case when d.doc_type = 'ALP' then 1 end) alp_docs,
       nvl(sum(case when d.doc_type = 'ALP' then d.total end), 0) alp_total,
       nvl(sum(case when d.doc_type in ('TPY', 'TDA') then d.total end), 0) tpy_total,
       nvl(sum(case when d.doc_type = 'PPY' then d.total end), 0) ppy_total,
       nvl(sum(t.vat_sign * d.total), 0) total
from mm_doc d
join mm_doc_type t on t.code = d.doc_type
where d.status = 'P' and t.side = 'S' and t.vat_sign <> 0
group by d.doc_date;

create or replace view mm_vat_day as
select d.doc_date day, l.vat_code, l.vat_rate,
       sum(case when t.side = 'S' then t.vat_sign * l.net else 0 end) s_net,
       sum(case when t.side = 'S' then t.vat_sign * l.vat else 0 end) s_vat,
       sum(case when t.side = 'P' then t.vat_sign * l.net else 0 end) p_net,
       sum(case when t.side = 'P' then t.vat_sign * l.vat else 0 end) p_vat
from mm_doc d
join mm_doc_type t on t.code = d.doc_type
join mm_doc_line l on l.doc_id = d.id
where d.status = 'P' and t.vat_sign <> 0      -- the notes: no VAT (their invoice has it)
group by d.doc_date, l.vat_code, l.vat_rate;

-- the goods with a date of expiry (MM_DOC_LINE.EXPIRES of the goods received): what is left of each
-- receipt, by FIFO: the stock of an item is of its newest receipts first (the oldest went first), so a
-- receipt has what the stock has after the receipts newer than it, up to its own quantity. Only the
-- lines with something left; DAYS_LEFT: negative, expired
create or replace view mm_expiry as
select x.item_id, x.code, x.name, x.unit, x.category, x.line_id, x.expires, x.expires - trunc(sysdate) days_left,
       x.qty, x.left_, x.doc_id, x.doc_type, x.doc_no, x.doc_date, x.supplier
from (select l.item_id, i.code, i.name, i.unit, c.name category, l.id line_id, l.expires, l.qty,
             least(l.qty, greatest(0, (i.stock + 0) - nvl(sum(l.qty) over (partition by l.item_id
                   order by d.doc_date desc, l.id desc rows between unbounded preceding and 1 preceding), 0))) left_,
             d.id doc_id, d.doc_type, d.doc_no, d.doc_date, s.name supplier
      from mm_doc_line l
      join mm_doc d on d.id = l.doc_id
      join mm_doc_type t on t.code = d.doc_type
      join mm_item i on i.id = l.item_id
      join mm_category c on c.id = i.category_id
      left join mm_supplier s on s.id = d.supplier_id
      where d.status = 'P' and t.side = 'P' and t.stock_sign = 1 and l.qty > 0) x
where x.expires is not null and x.left_ > 0;

create or replace view mm_min_stock as
select c.name category, i.code, i.name, i.unit, i.stock + 0 stock, i.min_stock,
       i.min_stock - (i.stock + 0) missing,
       (select max(s.name) keep (dense_rank last order by d.doc_date, d.id)
        from mm_doc d join mm_doc_line l on l.doc_id = d.id join mm_supplier s on s.id = d.supplier_id
        where l.item_id = i.id and d.doc_type in ('DPA', 'TAD') and d.status = 'P') supplier,
       i.id item_id, i.serial_tracked,
       (select max(d.supplier_id) keep (dense_rank last order by d.doc_date, d.id)
        from mm_doc d join mm_doc_line l on l.doc_id = d.id
        where l.item_id = i.id and d.doc_type in ('DPA', 'TAD') and d.status = 'P') supplier_id
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
      when 'TRIAL_I' then 'Ισοζύγιο ειδών'
      when 'TRIAL_C' then 'Ισοζύγιο πελατών'
      when 'TRIAL_S' then 'Ισοζύγιο προμηθευτών'
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
      -- the trial balances (ισοζύγια: mm_ledger.trial_rows)
      when 'OPEN_Q' then 'Από μεταφορά'
      when 'IN_Q' then 'Εισαγωγές'
      when 'OUT_Q' then 'Εξαγωγές'
      when 'END_Q' then 'Απόθεμα'
      when 'AFM' then 'ΑΦΜ'
      when 'PARTNER' then 'Επωνυμία'
      when 'OPEN_BAL' then 'Από μεταφορά'
      when 'DEBIT' then 'Χρέωση'
      when 'CREDIT' then 'Πίστωση'
      when 'CLOSE_BAL' then 'Υπόλοιπο'
      when 'CUSTOMERS' then 'Πελάτες'
      when 'SUPPLIERS' then 'Προμηθευτές'
      else p_key end;
  end;

  function qty(p_qty number) return varchar2 is
  begin
    return rtrim(rtrim(to_char(p_qty, 'FM999G999G990D999'), '0'), '.,');
  end;
end mm_report;
/
