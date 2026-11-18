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
-- (the layers of FIFO with an expiry and something left: in their warehouse, a transfer with its goods; the
-- document that brought each: the receipt, or the transfer; the supplier of the receipt the goods came with)
create or replace view mm_expiry as
select f.item_id, i.code, i.name, i.unit, c.name category, f.id fifo_id, f.doc_line_id line_id,
       f.warehouse_id, w.code warehouse, w.name warehouse_name, f.expires, f.expires - trunc(sysdate) days_left,
       f.qty, f.left_, d.id doc_id, d.doc_type, d.doc_no, d.doc_date,
       (select max(s.name) keep (dense_rank last order by o.id) from mm_doc_line ol join mm_doc od on od.id = ol.doc_id
          join mm_supplier s on s.id = od.supplier_id join mm_fifo o on o.doc_line_id = ol.id
        where o.item_id = f.item_id and o.expires = f.expires and od.supplier_id is not null) supplier
from mm_fifo f
join mm_item i on i.id = f.item_id
join mm_category c on c.id = i.category_id
join mm_warehouse w on w.id = f.warehouse_id
left join mm_stock_move m on m.id = f.move_id
left join mm_doc d on d.id = m.doc_id
where f.expires is not null and f.left_ > 0;

-- FIFO: the value of the stock of each item (its layers left, each at its cost; a shortage below 0, at
-- the cost it was taken), the cost by piece of what is left, and the cost of the next piece out; and
-- the value by the last cost (VALUE_LAST: the stock at the cost of the last purchase)
create or replace view mm_fifo_value as
select i.id item_id, i.code, i.name, i.unit, c.name category, i.stock + 0 stock, i.cost last_cost,
       nvl(sum(f.left_ * f.unit_cost), 0) value,
       round(sum(case when f.left_ > 0 then f.left_ * f.unit_cost end)
             / nullif(sum(case when f.left_ > 0 then f.left_ end), 0), 4) unit_cost,
       min(case when f.left_ > 0 then f.unit_cost end) keep (dense_rank first order by case when f.left_ > 0 then f.id end) next_cost,
       round((i.stock + 0) * nvl(i.cost, 0), 2) value_last
from mm_item i
join mm_category c on c.id = i.category_id
left join mm_fifo f on f.item_id = i.id
group by i.id, i.code, i.name, i.unit, c.name, i.stock + 0, i.cost;

-- the cost of each move of the stock by FIFO (COST): what it took out (its layers, at their costs; given
-- back by a cancellation: below 0) less what it brought in (a return of a customer: a layer); and by the
-- last cost (COST_LAST: its quantity at the cost of the last purchase then). The cost of the sales of a
-- period: the moves of its documents of sale
create or replace view mm_move_cost as
select s.id move_id, s.item_id, s.kind, s.doc_id, s.doc_line_id, s.move_at, s.qty, s.note,
       nvl((select sum(o.cost) from mm_fifo_out o where o.move_id = s.id), 0)
       - nvl((select sum(f.qty * f.unit_cost) from mm_fifo f where f.move_id = s.id), 0) cost,
       round(-s.qty * nvl(s.unit_last, 0), 4) cost_last
from mm_stock_move s;

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

-- the sales by document (receipts, invoices, less credit notes): its day, its warehouse, its register, who posted
-- it, its value, what it cost (FIFO, the last cost); the reports by store, by register, by cashier
create or replace view mm_sales_doc as
select d.id doc_id, d.doc_date day, d.doc_type,
       nvl(d.warehouse_id, (select min(id) from mm_warehouse where main = 'Y')) warehouse_id, d.register_id,
       nvl(d.posted_by, '-') posted_by, t.vat_sign docs, t.vat_sign * d.net net, t.vat_sign * d.total total,
       nvl((select sum(m.cost) from mm_move_cost m where m.doc_id = d.id), 0) cost_fifo,
       nvl((select sum(m.cost_last) from mm_move_cost m where m.doc_id = d.id), 0) cost_last
from mm_doc d
join mm_doc_type t on t.code = d.doc_type
where d.status = 'P' and t.side = 'S' and t.vat_sign <> 0;

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
