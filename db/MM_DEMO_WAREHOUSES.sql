-- MM_DEMO_WAREHOUSES.sql -- two branches to see the warehouses: their own stock, registers and sales, the
-- goods sent to them from the central store at cost (Δελτίο ενδοδιακίνησης, DEN), a count in one, goods
-- sent back. After INSTALL.sql demo, as the owner, from this folder (NLS_LANG=GREEK_GREECE.AL32UTF8, as
-- for INSTALL.sql):
--
--   sqlplus mm/<password>@FREEPDB1 @MM_DEMO_WAREHOUSES.sql
--
-- It makes real documents (receipts, delivery notes, transfers): for a database to try things on.
-- Everything goes through MM_CORE, as at the till and in the office, so the stock of each warehouse,
-- its layers of FIFO, the Z and MM_CHECK add up. The days: the last 10. Once: if the warehouse Y1
-- exists, nothing is done.
--
--   Y1  Υποκατάστημα Ρίου     its register R1; goods sent twice from the central store: the milk and the
--                             coffee first all of the old stock and more, then again after new goods came
--                             in at a higher cost (its layers at three costs); sold there; a count of it
--                             (two items: one less, one more)
--   Y2  Υποκατάστημα Αιγίου   its register R2; goods sent once; sold there; what did not sell, some of
--                             it sent back to the central store (at the costs it came with)
--
-- Then: the page Αποθήκες (the branches, their items, their value), the till (the warehouse of each
-- register), Αξία αποθήκης by warehouse, an item (its stock in each), the transfers (DEN) in
-- «Τιμολόγια και δελτία».
set define off
set feedback off
set serveroutput on
whenever sqlerror exit failure rollback

declare
  d0 date := trunc(sysdate) - 9;
  main number;
  y1 number;
  y2 number;
  r1 number;
  r2 number;
  z number;
  v number;
  docs pls_integer := 0;
  old_gal number;                         -- the old stock of the central store (π), before it buys
  old_kaf number;

  function id_of(p_code varchar2) return number is
    v number;
  begin
    select id into v from mm_item where code = p_code;
    return v;
  end;

  -- what the central store has of an item now (none below 0)
  function old_of(p_code varchar2) return number is
    v number;
    it number := id_of(p_code);
  begin
    select greatest(nvl(sum(qty), 0), 0) into v from mm_stock_move where item_id = it and warehouse_id = main;
    return v;
  end;

  -- a document of lines 'CODE:qty;...' (a price, ':price', for a receipt of goods); posted
  function doc(p_type varchar2, p_lines varchar2, p_day pls_integer, p_from number default null,
               p_to number default null, p_reg number default null, p_supplier varchar2 default null) return number is
    d number;
    l number;
    s varchar2(400);
    sup number;
  begin
    if p_supplier is not null then
      select id into sup from mm_supplier where afm = p_supplier;
    end if;
    d := mm_core.new_doc(p_type, null, sup, p_reg, case when p_reg is null then 'CREDIT' else 'CASH' end,
                         d0 + p_day, p_from, p_to);
    for k in 1 .. regexp_count(p_lines, '[^;]+') loop
      s := regexp_substr(p_lines, '[^;]+', 1, k);
      l := mm_core.add_line(d, id_of(regexp_substr(s, '[^:]+', 1, 1)),
                            to_number(regexp_substr(s, '[^:]+', 1, 2)),
                            to_number(regexp_substr(s, '[^:]+', 1, 3), '9999D99', 'NLS_NUMERIC_CHARACTERS=''.,'''));
    end loop;
    l := mm_core.post_doc(d);
    docs := docs + 1;
    return d;
  end;
begin
  select count(*) into v from mm_warehouse where code = 'Y1';
  if v > 0 then
    dbms_output.put_line('== MM_DEMO_WAREHOUSES: the warehouse Y1 exists already: nothing done');
    return;
  end if;
  main := mm_core.main_warehouse;
  insert into mm_warehouse (code, name) values ('Y1', 'Υποκατάστημα Ρίου') returning id into y1;
  insert into mm_warehouse (code, name) values ('Y2', 'Υποκατάστημα Αιγίου') returning id into y2;
  insert into mm_register (code, name, warehouse_id) values ('R1', 'Ταμείο Ρίου', y1) returning id into r1;
  insert into mm_register (code, name, warehouse_id) values ('R2', 'Ταμείο Αιγίου', y2) returning id into r2;

  old_gal := old_of('GAL01');
  old_kaf := old_of('KAF01');
  -- the central store has its old stock (the first count of the demo, at the cost of the item): π.
  -- It buys at new costs what it will send; the first goods to Y1 are all of π and more, so they go
  -- from the old cost into the new ones
  v := doc('DPA', 'GAL01:48:1.15;ART01:40:1.22;POT01:96:0.21;POT05:48:0.88;KAF01:24:2.45;SNK02:40:0.82;SNK01:24:1.02',
           0, p_supplier => '999000092');
  -- sent to the branches at the cost of each layer (DEN)
  v := doc('DEN', 'GAL01:' || (old_gal + 10) || ';ART01:20;POT01:48;POT05:24;KAF01:' || (old_kaf + 5)
                  || ';SNK02:20', 1, main, y1);
  v := doc('DEN', 'GAL01:12;ART01:10;POT01:24;SNK01:12;SNK02:10', 1, main, y2);
  -- new goods at a higher cost; Y1 gets more of them: its layers at both costs
  v := doc('DPA', 'GAL01:48:1.29;KAF01:24:2.65', 4, p_supplier => '999000067');
  v := doc('DEN', 'GAL01:30;KAF01:10', 5, main, y1);

  -- sold at the branches (their registers, their warehouses)
  z := mm_core.open_z(r1, 50);
  v := doc('ALP', 'GAL01:6;ART01:4;POT05:6', 2, p_reg => r1);
  v := doc('ALP', 'POT01:12;SNK02:5', 3, p_reg => r1);
  v := doc('ALP', 'GAL01:18;KAF01:3', 6, p_reg => r1);
  v := doc('ALP', 'GAL01:10;ART01:6;KAF01:4;POT05:8', 8, p_reg => r1);
  z := mm_core.close_z(r1);
  z := mm_core.open_z(r2, 30);
  v := doc('ALP', 'GAL01:4;ART01:3;POT01:6', 2, p_reg => r2);
  v := doc('ALP', 'SNK01:2;SNK02:3;GAL01:3', 4, p_reg => r2);
  v := doc('ALP', 'ART01:2;POT01:4', 7, p_reg => r2);
  z := mm_core.close_z(r2);

  -- a count of Y1: two items, one less than the system says, one more
  declare
    c number := mm_core.start_count('Απογραφή Ρίου (επίδειξη)', y1);
    it number;
    sys_ number;
  begin
    for x in (select 'POT01' code, -2 diff from dual union all select 'SNK02', 1 from dual) loop
      it := id_of(x.code);
      select nvl(sum(qty), 0) into sys_ from mm_stock_move where item_id = it and warehouse_id = y1;
      it := mm_core.scan(c, x.code, greatest(sys_ + x.diff, 0), 'SET', 'demo');
    end loop;
    mm_core.post_count(c);
  end;

  -- what did not sell in Y2, some of it back to the central store (at the costs it came with)
  v := doc('DEN', 'SNK01:6;POT01:8', 9, y2, main);
  commit;

  dbms_output.put_line('== MM_DEMO_WAREHOUSES: Y1, Y2, their registers R1, R2; ' || docs || ' documents and a count');
  dbms_output.put_line(rpad('warehouse', 24) || lpad('items', 7) || lpad('value', 12));
  for w in (select w.code || ' ' || w.name name,
                   (select count(*) from mm_warehouse_stock s where s.warehouse_id = w.id and s.stock <> 0) items,
                   (select nvl(sum(f.left_ * f.unit_cost), 0) from mm_fifo f where f.warehouse_id = w.id) value
            from mm_warehouse w order by case w.main when 'Y' then 0 else 1 end, w.code) loop
    dbms_output.put_line(rpad(substr(w.name, 1, 24), 24) || lpad(w.items, 7) || lpad(to_char(w.value, 'FM9999990.00'), 12));
  end loop;
  select count(*) into v from mm_check;
  dbms_output.put_line('== MM CHECK ' || case when v = 0 then 'OK' else v || ' rows: select * from mm_check' end);
end;
/
