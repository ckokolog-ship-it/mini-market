-- MM_DEMO_FIFO.sql -- FIFO to see: goods bought at more than one cost, sold across them, for the reports
-- «Μικτό κέρδος» and «Αξία αποθήκης» (FIFO beside the last cost) and the page of each item (its stock
-- by receipt). After INSTALL.sql demo, as the owner, from this folder (NLS_LANG=GREEK_GREECE.AL32UTF8,
-- as for INSTALL.sql):
--
--   sqlplus mm/<password>@FREEPDB1 @MM_DEMO_FIFO.sql
--
-- NOT on the database of the shop: it makes receipts and invoices (of a register of its own, T9).
-- Everything goes through MM_CORE, as at the till and in the office, so the layers and their costs are
-- those of the system (MM_FIFO, MM_FIFO_OUT), the stock, the Z and MM_CHECK add up. The days: the last
-- 14. Once: if the register T9 exists, nothing is done.
--
-- Each item has its stock of before (the first count of the demo: one layer at the cost of the item):
-- the old stock, «π». Each sale is of the old stock and more, so it goes from it into the new receipts:
--
--   1 GAL01 milk       the cost goes up: 24 x 1,18, 24 x 1,25; sold π + 10 (the old, then 10 at 1,18),
--                      then 30 (14 at 1,18, 16 at 1,25)
--   2 POT05 beer       one receipt, two lines: 48 x 0,80 (an offer of the supplier) and 24 x 0,95 (x at a,
--                      y at b); sold π + 60: the old, the 48 at 0,80, 12 at 0,95
--   3 KAF01 coffee     the cost goes down: 20 x 2,20, then 20 x 2,00; sold π + 25: FIFO above the last cost
--   4 SNK02 chocolate  sold before it came: π + 10, the 10 a shortage (at the cost of its newest layer); then
--                      30 x 0,85 come: the shortage filled first, 20 left at 0,85
--   5 POT06 wine       12 x 4,60; a sale of π + 5 cancelled (its layers back); a receipt of 6 x 4,80
--                      cancelled (it goes out); sold π + 5: the old, 5 at 4,60
--   6 GAL02 yoghurt    12 x 2,90; sold π + 6 (the old, 6 at 2,90); 3 back from a customer (a return note DEP)
--   7 ART01 bread      an invoice that is its delivery note too (TAD): 40 x 1,25; sold π + 5
set define off
set feedback off
set serveroutput on
whenever sqlerror exit failure rollback

declare
  reg number;
  z number;
  d0 date := trunc(sysdate) - 13;
  cust number;
  doc number;
  ln number;
  v number;
  sales varchar2(4000) := ',';      -- the documents of this script, for the summary at the end

  function id_of(p_code varchar2) return number is
    v number;
  begin
    select id into v from mm_item where code = p_code;
    return v;
  end;

  function supplier(p_afm varchar2) return number is
    v number;
  begin
    select id into v from mm_supplier where afm = p_afm;
    return v;
  end;

  -- a receipt of goods (DPA) of a supplier: lines (code, qty, price) as 'CODE:qty:price;...'
  function buy(p_afm varchar2, p_lines varchar2, p_day pls_integer, p_type varchar2 default 'DPA') return number is
    d number := mm_core.new_doc(p_type, null, supplier(p_afm), null, 'CREDIT', d0 + p_day);
    l number;
    s varchar2(400);
  begin
    for k in 1 .. regexp_count(p_lines, '[^;]+') loop
      s := regexp_substr(p_lines, '[^;]+', 1, k);
      l := mm_core.add_line(d, id_of(regexp_substr(s, '[^:]+', 1, 1)),
                            to_number(regexp_substr(s, '[^:]+', 1, 2), '9999D99', 'NLS_NUMERIC_CHARACTERS=''.,'''),
                            to_number(regexp_substr(s, '[^:]+', 1, 3), '9999D99', 'NLS_NUMERIC_CHARACTERS=''.,'''));
    end loop;
    l := mm_core.post_doc(d);
    sales := sales || d || ',';
    return d;
  end;

  -- the stock of an item now (none below 0)
  function stock_of(p_code varchar2) return number is
    v number;
  begin
    select greatest(stock + 0, 0) into v from mm_item where code = p_code;
    return v;
  end;

  -- a retail receipt of the register T9, at the price of the item, cash
  function sell(p_code varchar2, p_qty number, p_day pls_integer) return number is
    d number := mm_core.new_doc('ALP', null, null, reg, 'CASH', d0 + p_day);
    l number;
  begin
    l := mm_core.add_line(d, id_of(p_code), p_qty);
    l := mm_core.post_doc(d);
    sales := sales || d || ',';
    return d;
  end;
begin
  select count(*) into v from mm_register where code = 'T9';
  if v > 0 then
    dbms_output.put_line('== MM_DEMO_FIFO: the register T9 exists already: nothing done');
    return;
  end if;
  insert into mm_register (code, name) values ('T9', 'Ταμείο επίδειξης FIFO') returning id into reg;
  z := mm_core.open_z(reg, 50);
  select min(id) into cust from mm_customer where afm is not null;

  -- 1 milk: the cost up; each sale across two layers
  v := stock_of('GAL01');
  doc := buy('999000067', 'GAL01:24:1.18', 0);
  doc := buy('999000067', 'GAL01:24:1.25', 4);
  doc := sell('GAL01', v + 10, 5);
  doc := sell('GAL01', 30, 10);
  -- 2 beer: one receipt, two lines at two costs
  v := stock_of('POT05');
  doc := buy('999000079', 'POT05:48:0.80;POT05:24:0.95', 1);
  doc := sell('POT05', v + 60, 6);
  -- 3 coffee: the cost down
  v := stock_of('KAF01');
  doc := buy('999000092', 'KAF01:20:2.20', 2);
  doc := buy('999000092', 'KAF01:20:2.00', 9);
  doc := sell('KAF01', v + 25, 11);
  -- 4 chocolate: sold before it came, then it came
  doc := sell('SNK02', stock_of('SNK02') + 10, 3);
  doc := buy('999000092', 'SNK02:30:0.85', 7);
  -- 5 wine: a sale cancelled, a receipt cancelled
  v := stock_of('POT06');
  doc := buy('999000079', 'POT06:12:4.60', 1);
  doc := sell('POT06', v + 5, 6);
  mm_core.cancel_doc(doc);
  doc := buy('999000079', 'POT06:6:4.80', 7);
  mm_core.cancel_doc(doc);
  doc := sell('POT06', v + 5, 12);
  -- 6 yoghurt: goods back from a customer
  v := stock_of('GAL02');
  doc := buy('999000067', 'GAL02:12:2.90', 2);
  doc := sell('GAL02', v + 6, 9);
  doc := mm_core.new_doc('DEP', cust, null, null, 'CREDIT', d0 + 11);
  ln := mm_core.add_line(doc, id_of('GAL02'), 3);
  ln := mm_core.post_doc(doc);
  sales := sales || doc || ',';
  -- 7 bread: an invoice that is its delivery note too
  v := stock_of('ART01');
  doc := buy('999000055', 'ART01:40:1.25', 3, 'TAD');
  doc := sell('ART01', v + 5, 13);
  z := mm_core.close_z(reg);
  commit;

  -- what came of it: by item, the cost of what was sold by FIFO and by the last cost, the stock by both
  dbms_output.put_line('== MM_DEMO_FIFO: the register T9, ' || (regexp_count(sales, ',') - 1) || ' documents');
  dbms_output.put_line(rpad('item', 8) || lpad('sold', 7) || lpad('FIFO', 10) || lpad('last', 10)
                       || lpad('stock', 8) || lpad('FIFO', 10) || lpad('last', 10));
  for r in (select i.code, nvl(sum(-m.qty), 0) qty, nvl(sum(m.cost), 0) fifo, nvl(sum(m.cost_last), 0) last_,
                   max(v.stock) stock, max(v.value) value, max(v.value_last) value_last
            from mm_item i
            join mm_fifo_value v on v.item_id = i.id
            left join mm_move_cost m on m.item_id = i.id
              and instr(',' || (select listagg(id, ',') from mm_doc where register_id = reg) || ',', ',' || m.doc_id || ',') > 0
            where i.code in ('GAL01', 'POT05', 'KAF01', 'SNK02', 'POT06', 'GAL02', 'ART01')
            group by i.code order by i.code) loop
    dbms_output.put_line(rpad(r.code, 8) || lpad(r.qty, 7) || lpad(to_char(r.fifo, 'FM99990.00'), 10)
                         || lpad(to_char(r.last_, 'FM99990.00'), 10) || lpad(r.stock, 8)
                         || lpad(to_char(r.value, 'FM99990.00'), 10) || lpad(to_char(r.value_last, 'FM99990.00'), 10));
  end loop;
  select count(*) into v from mm_check;
  dbms_output.put_line('== MM CHECK ' || case when v = 0 then 'OK' else v || ' rows: select * from mm_check' end);
end;
/
