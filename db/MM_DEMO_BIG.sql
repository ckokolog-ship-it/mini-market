-- MM_DEMO_BIG.sql -- a year of the shop, for the reports: after INSTALL.sql demo, as the owner,
-- from this folder (NLS_LANG=GREEK_GREECE.AL32UTF8, as for INSTALL.sql):
--
--   sqlplus mm/<password>@FREEPDB1 @MM_DEMO_BIG.sql          (the last 365 days)
--   sqlplus mm/<password>@FREEPDB1 @MM_DEMO_BIG.sql 90       (the last 90 days)
--
-- Everything goes through MM_CORE, as at the till and in the office, so the stock, the numbers,
-- the VAT and the Z add up (MM_CHECK.sql at the end): a second cash register, T2, with a Z every
-- day (Sunday few receipts), the retail receipts (cash or card, a card of mobile now and then, a
-- cancelled one), an invoice on credit to a customer every other day (now and then a credit note),
-- the purchases from the suppliers every Monday (what was sold), the cards of mobile on the 1st
-- of the month, and every Friday the receipts from the customers and the payments to the
-- suppliers (the dairy and the press are late the last three weeks: their items go under the minimum
-- stock). Each row gets the date and the hour of its day.
-- Once: if the register T2 exists, nothing is done. The same random numbers every time
-- (dbms_random.seed), so two databases get the same year.
-- About 9.000 documents and 30.000 lines: some minutes.
set define on
set verify off
set feedback off
set serveroutput on
whenever sqlerror exit failure rollback
set termout off
column 1 new_value 1
select '' "1" from dual where rownum = 0;
column days new_value days noprint
select case when regexp_like('&1', '^[0-9]+$') then '&1' else '365' end days from dual;
set termout on

declare
  c_days constant pls_integer := &days;
  type t_ids is table of number index by pls_integer;
  type t_codes is table of varchar2(20) index by pls_integer;
  sale t_ids;           -- the items of the receipts
  unit t_codes;         -- their unit
  sort_ t_codes;        -- K a basket (only when one is ready), C clothes and shoes (seldom), else -
  kits t_ids;           -- the baskets: put together every Monday
  staple t_ids;         -- bread, milk, water, the newspaper: in many receipts
  whole t_ids;          -- the items of the invoices to the shops
  card t_ids;           -- the cards of mobile
  cust t_ids;           -- the customers
  tpy t_ids;            -- the invoices of the year (for the credit notes)
  ntpy pls_integer := 0;
  reg number;
  pins boolean;
  d date;
  z number;
  doc number;
  ln number;
  v number;
  n pls_integer;
  m_doc number; m_move number; m_cash number; m_pay number; m_ser number;
  ndocs pls_integer;
  a1 varchar2(9); a2 varchar2(9); a3 varchar2(9); a4 varchar2(9); a5 varchar2(9);  -- the new suppliers
  dy varchar2(3);       -- MON .. SUN
  d0 date := trunc(sysdate) - c_days;   -- the first day
  v_afm varchar2(9);

  -- a made-up AFM with its right check digit: the first eight digits times 2^8..2^1, mod 11, mod 10
  function afm(p8 varchar2) return varchar2 is
    s pls_integer := 0;
  begin
    for k in 1 .. 8 loop
      s := s + to_number(substr(p8, k, 1)) * power(2, 9 - k);
    end loop;
    return p8 || mod(mod(s, 11), 10);
  end;

  function pick(a t_ids) return number is
  begin
    return a(trunc(dbms_random.value(1, a.count + 1)));
  end;

  function chance(p number) return boolean is
  begin
    return dbms_random.value < p;
  end;

  -- the quantity of a line of a receipt: mostly 1; by weight 200 g to 1,2 kg
  function qty_of(k pls_integer) return number is
  begin
    if unit(k) = 'KG' then
      return round(dbms_random.value(0.2, 1.2), 3);
    end if;
    return case when chance(0.7) then 1 when chance(0.7) then 2 else trunc(dbms_random.value(3, 7)) end;
  end;

  -- a purchase from a supplier: its items for four weeks, by what went out in the last 4 weeks
  -- (at least 20; by weight 10 kg), and 48 more of what the shops buy (an invoice takes up to 48);
  -- the first one 100 (15 kg); the cards of mobile 15 at a time with their serials
  procedure purchase(p_supplier number, p_first boolean) is
    q number;
    lines pls_integer := 0;
  begin
    doc := mm_core.new_doc('TAG', p_supplier_id => p_supplier, p_payment => 'CREDIT', p_doc_date => d);
    for i in (select i.id, i.unit, i.serial_tracked, i.stock + 0 stock,
                     case when c.name in ('Ποτά', 'Σνακ', 'Καφές και ροφήματα', 'Γαλακτοκομικά', 'Είδη καθαριότητας')
                          then 48 else 0 end shops,
                     (select -nvl(sum(m.qty), 0) from mm_stock_move m
                      where m.item_id = i.id and m.qty < 0 and m.move_at >= d - 28) went
              from mm_item i join mm_category c on c.id = i.category_id
              where i.active = 'Y' and i.kit = 'N' and i.is_model = 'N'
                and case c.name
                      when 'Αρτοποιήματα' then '999000055'
                      when 'Γαλακτοκομικά' then '999000067'
                      when 'Ποτά' then '999000079'
                      when 'Τύπος' then '999000080'
                      when 'Σνακ' then '999000092'
                      when 'Τυριά και αλλαντικά' then a1
                      when 'Καφές και ροφήματα' then a2
                      when 'Είδη καθαριότητας' then a3
                      when 'Ρούχα' then a4
                      when 'Παπούτσια' then a4
                      when 'Κάρτες κινητής' then a5
                    end = (select afm from mm_supplier where id = p_supplier)
              order by i.code) loop
      if i.serial_tracked = 'Y' then
        q := 15;
      elsif p_first then
        q := case i.unit when 'KG' then 15 else 100 end;
      else
        q := greatest(case i.unit when 'KG' then 10 else 20 end, 28 * i.went / least(28, d - d0))
             + i.shops - greatest(i.stock, 0);
        q := case i.unit when 'KG' then round(q, 1) else ceil(q / 6) * 6 end;
      end if;
      if q > 0 then
        ln := mm_core.add_line(doc, i.id, q);
        lines := lines + 1;
        if i.serial_tracked = 'Y' then
          for k in 1 .. q loop
            v := mm_core.add_serial(ln, 'H' || i.id || '-' || to_char(d, 'yymmdd') || '-' || lpad(k, 2, '0'),
                                    case when pins then lpad(trunc(dbms_random.value(0, 1e12)), 12, '0') end);
          end loop;
        end if;
      end if;
    end loop;
    if lines = 0 then
      mm_core.delete_doc(doc);
    else
      v := mm_core.post_doc(doc);
    end if;
  end;

  -- the open balance of a customer (+ he owes) or of a supplier (+ we owe)
  function balance(p_customer number, p_supplier number) return number is
    b number;
    p number;
  begin
    select nvl(sum(case when d.doc_type in ('TPY', 'TAG') then d.total else -d.total end), 0) into b
    from mm_doc d
    where d.status = 'P' and d.doc_type in ('TPY', 'PPY', 'TAG', 'PAG')
      and (d.customer_id = p_customer or d.supplier_id = p_supplier);
    select nvl(sum(amount), 0) into p from mm_payment
    where status = 'P' and (customer_id = p_customer or supplier_id = p_supplier);
    return b - p;
  end;
begin
  select count(*) into n from mm_register where code = 'T2';
  if n > 0 then
    dbms_output.put_line('== the register T2 exists: the year of the demo is already there');
    return;
  end if;
  dbms_random.seed(20261114);
  a1 := afm('99920001'); a2 := afm('99920002'); a3 := afm('99920003'); a4 := afm('99920004'); a5 := afm('99920005');
  select count(*) into n from user_objects where object_name = 'MM_PIN' and object_type = 'PACKAGE BODY'
                                              and status = 'VALID';
  pins := n > 0;

  -- the second register, the new customers and suppliers
  insert into mm_register (code, name) values ('T2', 'Ταμείο 2') returning id into reg;
  n := 0;
  for c in (select column_value name from table(sys.odcivarchar2list(
              'Καφετέρια Το Λιμάνι', 'Ταβέρνα Τα Δειλινά', 'Φούρνος Η Ζύμη', 'Ψητοπωλείο Ο Νίκος',
              'Καφενείο Ο Μύλος', 'Ζαχαροπλαστείο Η Γλύκα', 'Μπαρ Ακρογιαλιά', 'Ουζερί Το Κύμα',
              'Κάντινα Γηπέδου', 'Καφέ Πλατάνι', 'Εστιατόριο Η Αυλή', 'Πιτσαρία Ο Φούρνος',
              'Ξενοδοχείο Αχαΐα', 'Φροντιστήριο Πρόοδος', 'Γυμναστήριο Ενέργεια', 'Κομμωτήριο Στυλ',
              'Συνεργείο Ο Μάκης', 'Βιβλιοπωλείο Η Σελίδα', 'Παιδικός Σταθμός Χαρά', 'Σύλλογος Γονέων 5ου')))
  loop
    n := n + 1;
    v_afm := afm('9991' || lpad(n, 4, '0'));
    insert into mm_customer (name, afm, doy, address, phone)
    values (c.name, v_afm, case mod(n, 3) when 0 then 'Α΄ Πατρών' when 1 then 'Β΄ Πατρών' else 'Γ΄ Πατρών' end,
            'Οδός ' || n || ', Πάτρα', '26100' || lpad(1000 + n, 5, '0'));
  end loop;
  insert into mm_supplier (name, afm, doy, address, phone) values ('Τυροκομείο Ολύμπου', a1, 'Καλαβρύτων', 'Καλάβρυτα', '2692000021');
  insert into mm_supplier (name, afm, doy, address, phone) values ('Καφεκοπτείο Αχαΐας', a2, 'Α΄ Πατρών', 'Καραϊσκάκη 40, Πάτρα', '2610000022');
  insert into mm_supplier (name, afm, doy, address, phone) values ('Χημικά Καθαρισμού Πάτρας', a3, 'ΦΑΕ Πατρών', 'ΒΙΠΕ Πατρών', '2610000023');
  insert into mm_supplier (name, afm, doy, address, phone) values ('Ένδυση και Υπόδηση ΑΕ', a4, 'ΦΑΕ Αθηνών', 'Ερμού 12, Αθήνα', '2100000024');
  insert into mm_supplier (name, afm, doy, address, phone) values ('Διανομή Καρτών Κινητής ΟΕ', a5, 'Β΄ Πατρών', 'Κανακάρη 90, Πάτρα', '2610000025');
  -- the demo of INSTALL.sql counted the stock, put together the baskets and loaded 5 cards today:
  -- that was the day before the first one (else its cards would be sold before they came)
  update mm_stock_move set move_at = d0 - 1 + 9 / 24 where doc_id is null and move_at >= trunc(sysdate);
  update mm_serial set created_at = d0 - 1 + 9 / 24 where in_doc_id is null and created_at >= trunc(sysdate);
  commit;

  -- what is sold
  for i in (select i.id, i.unit, c.name cat, i.code, i.kit from mm_item i join mm_category c on c.id = i.category_id
            where i.active = 'Y' and i.is_model = 'N' order by i.code) loop
    if i.cat = 'Κάρτες κινητής' then
      card(card.count + 1) := i.id;
    else
      sale(sale.count + 1) := i.id;
      unit(sale.count) := i.unit;
      sort_(sale.count) := case when i.kit = 'Y' then 'K' when i.cat in ('Ρούχα', 'Παπούτσια') then 'C' else '-' end;
      if i.kit = 'Y' then
        kits(kits.count + 1) := i.id;
      end if;
      if i.code in ('ART01', 'ART03', 'GAL01', 'POT01', 'TYP01', 'SNK02') then
        staple(staple.count + 1) := sale.count;
      end if;
      if i.cat in ('Ποτά', 'Σνακ', 'Καφές και ροφήματα', 'Γαλακτοκομικά', 'Είδη καθαριότητας') then
        whole(whole.count + 1) := i.id;
      end if;
    end if;
  end loop;
  select id bulk collect into cust from mm_customer where active = 'Y' order by id;

  for day_ in 1 .. c_days loop
    d := d0 - 1 + day_;
    dy := to_char(d, 'DY', 'nls_date_language=english');
    select nvl(max(id), 0) into m_doc from mm_doc;
    select nvl(max(id), 0) into m_move from mm_stock_move;
    select nvl(max(id), 0) into m_cash from mm_cash_move;
    select nvl(max(id), 0) into m_pay from mm_payment;
    select nvl(max(id), 0) into m_ser from mm_serial;

    -- Monday (and the first day): the purchases; the 1st of the month: the cards
    if day_ = 1 or dy = 'MON' or extract(day from d) = 1 then
      for s in (select id, afm from mm_supplier order by id) loop
        if s.afm = a5 then
          if day_ = 1 or extract(day from d) = 1 then
            purchase(s.id, day_ = 1);
          end if;
        elsif (day_ = 1 or dy = 'MON')
              -- the last three weeks the dairy and the press are late: their items go under the
              -- minimum stock (the report MM_MIN_STOCK)
              and not (day_ > c_days - 21 and s.afm in ('999000067', '999000080')) then
          purchase(s.id, day_ = 1);
        end if;
      end loop;
      -- the baskets: back to 3 ready ones
      if day_ = 1 or dy = 'MON' then
        for k in 1 .. kits.count loop
          select 3 - greatest(stock + 0, 0) into v from mm_item where id = kits(k);
          if v > 0 then
            mm_core.assemble_kit(kits(k), v, 'Καλάθια της εβδομάδας');
          end if;
        end loop;
      end if;
    end if;

    -- the till: Saturday the most, Sunday few
    z := mm_core.open_z(reg, 100);
    ndocs := greatest(1, round(dbms_random.normal * 4 +
               case dy when 'SUN' then 8 when 'SAT' then 28 else 20 end));
    for k in 1 .. ndocs loop
      doc := mm_core.new_doc('ALP', p_register_id => reg, p_payment => case when chance(0.3) then 'CARD' else 'CASH' end,
                             p_doc_date => d);
      if chance(0.5) then
        n := staple(trunc(dbms_random.value(1, staple.count + 1)));
        ln := mm_core.add_line(doc, sale(n), qty_of(n));
      end if;
      for j in 1 .. trunc(dbms_random.value(1, case when chance(0.8) then 4 else 9 end)) loop
        n := trunc(dbms_random.value(1, sale.count + 1));
        if sort_(n) = 'C' and chance(0.85) then
          n := trunc(dbms_random.value(1, sale.count + 1));        -- clothes and shoes: seldom
        end if;
        if sort_(n) = 'K' then
          select count(*) into v from mm_item where id = sale(n) and stock + 0 > 0;
          if v = 0 or chance(0.7) then
            n := staple(trunc(dbms_random.value(1, staple.count + 1)));
          end if;
        end if;
        if sort_(n) = 'K' then
          ln := mm_core.add_line(doc, sale(n), 1);
        else
          ln := mm_core.add_line(doc, sale(n), qty_of(n));
        end if;
      end loop;
      if chance(0.08) then
        begin
          v := mm_core.sell_serial(doc, pick(card));
        exception
          when others then
            if sqlcode <> -20140 then raise; end if;     -- MM-140: no card left of it
        end;
      end if;
      v := mm_core.post_doc(doc);
      if chance(0.01) then
        mm_core.cancel_doc(doc);
      end if;
      -- as at the till: the stock is reservable, the next receipt sees this one after the commit
      commit;
    end loop;
    v := mm_core.close_z(reg);

    -- every other day an invoice on credit to a shop; now and then a credit note of an older one
    if mod(day_, 2) = 0 then
      doc := mm_core.new_doc('TPY', p_customer_id => pick(cust), p_payment => 'CREDIT', p_doc_date => d);
      for j in 1 .. trunc(dbms_random.value(3, 9)) loop
        ln := mm_core.add_line(doc, pick(whole), 6 * trunc(dbms_random.value(1, 9)));
      end loop;
      v := mm_core.post_doc(doc);
      ntpy := ntpy + 1;
      tpy(ntpy) := doc;
      if ntpy > 3 and chance(0.1) then
        -- goods back: the first line of an invoice, a third of it
        doc := mm_core.credit_note(tpy(trunc(dbms_random.value(ntpy - 3, ntpy))));
        update mm_doc set doc_date = d where id = doc;
        for l in (select id, qty, price, discount, line_no from mm_doc_line where doc_id = doc order by line_no) loop
          if l.line_no = 1 then
            mm_core.update_line(l.id, greatest(1, round(l.qty / 3)), l.price, l.discount);
          else
            mm_core.delete_line(l.id);
          end if;
        end loop;
        v := mm_core.post_doc(doc);
      end if;
    end if;

    -- Friday: the money of the invoices
    if dy = 'FRI' then
      for c in (select id from mm_customer order by id) loop
        v := balance(c.id, null);
        if v > 20 and chance(0.6) then
          v := mm_core.receive(c.id, round(v * dbms_random.value(0.5, 1)), 'BANK', d, p_notes => 'Έναντι');
        end if;
      end loop;
      for s in (select id from mm_supplier order by id) loop
        v := balance(null, s.id);
        if v > 50 and chance(0.7) then
          v := mm_core.pay(s.id, round(v * dbms_random.value(0.6, 1), 2), 'BANK', d, p_notes => 'Έναντι');
        end if;
      end loop;
    end if;

    -- the hours of the day: the purchases at 8, the receipts from 8 to 21 in their order, the
    -- invoices at 13, the payments at 12
    select count(*) into ndocs from mm_doc where id > m_doc and doc_type = 'ALP';
    update mm_z set opened_at = d + 8 / 24, closed_at = d + 21 / 24 where id = z;
    update mm_doc x
    set created_at = case
          when doc_type in ('TAG', 'PAG') then d + 8 / 24
          when doc_type = 'ALP' then d + (8 + 13 * (select count(*) from mm_doc y
                                                    where y.id > m_doc and y.id <= x.id and y.doc_type = 'ALP')
                                              / (ndocs + 1)) / 24
          else d + 13 / 24 end
    where id > m_doc;
    update mm_stock_move m
    set move_at = nvl((select created_at from mm_doc where id = m.doc_id), d + 8 / 24)
    where id > m_move;
    update mm_cash_move m
    set move_at = nvl((select created_at from mm_doc where id = m.doc_id), d + 8 / 24)
    where id > m_cash;
    update mm_payment set created_at = d + 12 / 24 where id > m_pay;
    update mm_serial set created_at = d + 8 / 24 where id > m_ser;
    update mm_serial s set sold_at = (select created_at from mm_doc where id = s.out_doc_id)
    where status = 'S' and out_doc_id > m_doc;
    commit;
  end loop;

  -- the numbers in the order of the dates (the demo of INSTALL.sql, of today, took the first ones)
  for t in (select code from mm_doc_type) loop
    update mm_doc set doc_no = doc_no + 1000000000 where doc_type = t.code and doc_no is not null;
    merge into mm_doc x
    using (select id, row_number() over (order by doc_date, created_at, id) no_
           from mm_doc where doc_type = t.code and doc_no is not null) s
    on (x.id = s.id)
    when matched then update set x.doc_no = s.no_;
    update mm_doc_type set next_no = (select nvl(max(doc_no), 0) + 1 from mm_doc where doc_type = t.code)
    where code = t.code;
  end loop;
  commit;
  dbms_output.put_line('== ' || c_days || ' days');
end;
/
set feedback on
select 'documents' what, count(*) n from mm_doc
union all select 'lines', count(*) from mm_doc_line
union all select 'moves of the stock', count(*) from mm_stock_move
union all select 'moves of the registers', count(*) from mm_cash_move
union all select 'Z', count(*) from mm_z
union all select 'receipts and payments', count(*) from mm_payment
union all select 'cards (serials)', count(*) from mm_serial
union all select 'customers', count(*) from mm_customer
union all select 'suppliers', count(*) from mm_supplier;
@MM_CHECK.sql
