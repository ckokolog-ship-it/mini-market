-- MM_DEMO.sql -- demo rows: categories, 30 items, customers, suppliers, a cash register and the
-- first count of the stock. Run by INSTALL.sql; only what is missing is added (by name or code).
-- The barcodes are EAN-13 of the 200-299 range (for use inside the shop), the AFM are made up
-- (their check digit is right, they belong to nobody we know).

insert into mm_category (name)
select v.name from (values
  ('Αρτοποιήματα'), ('Γαλακτοκομικά'), ('Τυριά και αλλαντικά'), ('Ποτά'), ('Καφές και ροφήματα'),
  ('Σνακ'), ('Είδη καθαριότητας'), ('Τύπος')) v (name)
where not exists (select 1 from mm_category c where c.name = v.name);

insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock)
select v.code, v.barcode, v.name, c.id, v.vat_code, v.unit, v.price, v.cost, v.min_stock
from (values
  ('ART01', '2000000000015', 'Ψωμί χωριάτικο 1 kg',        'Αρτοποιήματα',        'B', 'PCS',  2.10, 1.20, 10),
  ('ART02', '2000000000022', 'Φρυγανιές σίτου 250 g',       'Αρτοποιήματα',        'B', 'PCS',  1.85, 1.05,  6),
  ('ART03', '2000000000039', 'Κουλούρι Θεσσαλονίκης',       'Αρτοποιήματα',        'B', 'PCS',  0.60, 0.30, 20),
  ('GAL01', '2000000000046', 'Γάλα φρέσκο 1 L',             'Γαλακτοκομικά',       'B', 'PCS',  1.79, 1.10, 24),
  ('GAL02', '2000000000053', 'Γιαούρτι στραγγιστό 1 kg',    'Γαλακτοκομικά',       'B', 'PCS',  4.20, 2.70,  8),
  ('GAL03', '2000000000060', 'Βούτυρο 250 g',               'Γαλακτοκομικά',       'B', 'PCS',  3.40, 2.10,  6),
  ('GAL04', '2000000000077', 'Αυγά 6 τεμάχια',              'Γαλακτοκομικά',       'B', 'PCS',  2.90, 1.80, 12),
  ('TYR01', '2000000000084', 'Φέτα ΠΟΠ χύμα',               'Τυριά και αλλαντικά', 'B', 'KG',  11.90, 7.80,  3),
  ('TYR02', '2000000000091', 'Κασέρι χύμα',                 'Τυριά και αλλαντικά', 'B', 'KG',  12.50, 8.20,  2),
  ('TYR03', '2000000000107', 'Γαλοπούλα καπνιστή χύμα',     'Τυριά και αλλαντικά', 'B', 'KG',  13.80, 8.90,  2),
  ('POT01', '2000000000114', 'Νερό 1,5 L',                  'Ποτά',                'B', 'PCS',  0.45, 0.20, 48),
  ('POT02', '2000000000121', 'Νερό 6 x 1,5 L',              'Ποτά',                'B', 'PCS',  2.40, 1.20, 10),
  ('POT03', '2000000000138', 'Αναψυκτικό κόλα 330 ml',      'Ποτά',                'A', 'PCS',  1.10, 0.55, 24),
  ('POT04', '2000000000145', 'Χυμός πορτοκάλι 1 L',         'Ποτά',                'B', 'PCS',  2.30, 1.40, 12),
  ('POT05', '2000000000152', 'Μπίρα 500 ml',                'Ποτά',                'A', 'PCS',  1.60, 0.85, 24),
  ('POT06', '2000000000169', 'Κρασί λευκό 750 ml',          'Ποτά',                'A', 'PCS',  7.50, 4.20,  6),
  ('KAF01', '2000000000176', 'Καφές ελληνικός 194 g',       'Καφές και ροφήματα',  'B', 'PCS',  3.95, 2.40, 10),
  ('KAF02', '2000000000183', 'Καφές φίλτρου 250 g',         'Καφές και ροφήματα',  'B', 'PCS',  4.60, 2.80,  6),
  ('KAF03', '2000000000190', 'Τσάι του βουνού',             'Καφές και ροφήματα',  'B', 'PCS',  2.20, 1.10,  5),
  ('SNK01', '2000000000206', 'Πατατάκια 150 g',             'Σνακ',                'A', 'PCS',  1.90, 1.00, 12),
  ('SNK02', '2000000000213', 'Σοκολάτα γάλακτος 100 g',     'Σνακ',                'A', 'PCS',  1.50, 0.80, 20),
  ('SNK03', '2000000000220', 'Μπισκότα βουτήματος 225 g',   'Σνακ',                'B', 'PCS',  1.70, 0.95, 10),
  ('SNK04', '2000000000237', 'Παστέλι με σουσάμι',          'Σνακ',                'B', 'PCS',  0.90, 0.45, 15),
  ('KTH01', '2000000000244', 'Απορρυπαντικό πιάτων 750 ml', 'Είδη καθαριότητας',   'A', 'PCS',  2.60, 1.40,  6),
  ('KTH02', '2000000000251', 'Χαρτί υγείας 8 ρολά',         'Είδη καθαριότητας',   'A', 'PCS',  4.90, 2.90,  8),
  ('KTH03', '2000000000268', 'Χλωρίνη 2 L',                 'Είδη καθαριότητας',   'A', 'PCS',  1.95, 0.95,  6),
  ('KTH04', '2000000000275', 'Σακούλες απορριμμάτων 10 τμχ','Είδη καθαριότητας',   'A', 'PCS',  2.10, 1.05,  5),
  ('TYP01', '2000000000282', 'Εφημερίδα ημερήσια',          'Τύπος',               'C', 'PCS',  1.50, 1.10, 10),
  ('TYP02', '2000000000299', 'Περιοδικό εβδομαδιαίο',       'Τύπος',               'C', 'PCS',  3.00, 2.20,  4),
  ('TYP03', '2000000000305', 'Σταυρόλεξο',                  'Τύπος',               'C', 'PCS',  2.00, 1.40,  4)
) v (code, barcode, name, category, vat_code, unit, price, cost, min_stock)
join mm_category c on c.name = v.category
where not exists (select 1 from mm_item i where i.code = v.code);

insert into mm_customer (name, afm, doy, address, phone, email)
select v.name, v.afm, v.doy, v.address, v.phone, v.email from (values
  ('Καφενείο Η Πλατεία',          '999000018', 'Α΄ Πατρών', 'Πλατεία Αγίου Γεωργίου 4, Πάτρα', '2610000001', 'plateia@example.com'),
  ('Ταβέρνα Ο Γιάννης',           '999000020', 'Γ΄ Πατρών', 'Αγίου Νικολάου 18, Πάτρα',        '2610000002', 'giannis@example.com'),
  ('Φροντιστήριο Γνώση',          '999000031', 'Α΄ Πατρών', 'Μαιζώνος 51, Πάτρα',              '2610000003', null),
  ('Κατασκήνωση Τα Πεύκα',        '999000043', 'Αιγίου',    'Λόγγος Αιγιαλείας',               '2691000004', 'pefka@example.com')
) v (name, afm, doy, address, phone, email)
where not exists (select 1 from mm_customer c where c.afm = v.afm);

insert into mm_supplier (name, afm, doy, address, phone, email)
select v.name, v.afm, v.doy, v.address, v.phone, v.email from (values
  ('Αρτοποιείο Το Στάχυ',         '999000055', 'Α΄ Πατρών', 'Κορίνθου 120, Πάτρα',             '2610000011', 'stachy@example.com'),
  ('Γαλακτοκομικά Αχαΐας ΑΕ',     '999000067', 'ΦΑΕ Πατρών','ΒΙΠΕ Πατρών',                     '2610000012', 'orders@example.com'),
  ('Ποτά Δυτικής Ελλάδας ΟΕ',     '999000079', 'Β΄ Πατρών', 'Ακτή Δυμαίων 30, Πάτρα',          '2610000013', null),
  ('Πρακτορείο Τύπου Πάτρας',     '999000080', 'Α΄ Πατρών', 'Γούναρη 7, Πάτρα',                '2610000014', 'typos@example.com'),
  ('Χονδρική Τροφίμων ΑΕ',        '999000092', 'ΦΑΕ Πατρών','Νέα Εθνική Οδός, Πάτρα',          '2610000015', 'sales@example.com')
) v (name, afm, doy, address, phone, email)
where not exists (select 1 from mm_supplier s where s.afm = v.afm);

insert into mm_register (code, name)
select 'T1', 'Ταμείο 1' from dual where not exists (select 1 from mm_register where code = 'T1');

-- the first count: a move INIT for each item that has none, and the stock the same
insert into mm_stock_move (item_id, kind, qty, note)
select i.id, 'INIT', i.min_stock * 3, 'Πρώτη απογραφή'
from mm_item i
where i.min_stock > 0
  and i.serial_tracked = 'N'      -- the stock of the cards is their serials
  and not exists (select 1 from mm_stock_move m where m.item_id = i.id);

-- MM_ITEM.STOCK is reservable: only "stock = stock + n", one item at a time, by its id
begin
  for r in (select i.id, nvl(sum(m.qty), 0) - i.stock d
            from mm_item i left join mm_stock_move m on m.item_id = i.id
            group by i.id, i.stock
            having nvl(sum(m.qty), 0) <> i.stock) loop
    update mm_item set stock = stock + r.d where id = r.id;
  end loop;
end;
/

-- a reservation item: the New Year cake, and two reservations for the last day of this year
insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock)
select 'VAS01', '2000000000343', 'Βασιλόπιτα 1 kg', c.id, 'B', 'PCS', 14.00, 8.00, 0
from mm_category c
where c.name = 'Αρτοποιήματα' and not exists (select 1 from mm_item where code = 'VAS01');

declare
  r number;
begin
  for x in (select * from (values ('Μαρία Παπαδοπούλου', '6900000001', 2),
                                  ('Γιώργος Νικολάου',   '6900000002', 1)) v (name, phone, qty)
            where not exists (select 1 from mm_reservation m where m.phone = v.phone)) loop
    insert into mm_reservation (name, phone, pickup_date, notes)
    values (x.name, x.phone, add_months(trunc(sysdate, 'YYYY'), 12) - 1, 'Επίδειξη')
    returning id into r;
    insert into mm_reservation_line (reservation_id, item_id, qty, price)
    select r, id, x.qty, price from mm_item where code = 'VAS01';
  end loop;
end;
/

-- two baskets: wine and sweets (2 made before), breakfast (made at the sale)
insert into mm_category (name)
select 'Καλάθια δώρου' from dual where not exists (select 1 from mm_category where name = 'Καλάθια δώρου');

insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock)
select v.code, v.barcode, v.name, c.id, 'A', 'PCS', v.price, 0, 0
from (values
  ('KAL01', '2000000000350', 'Καλάθι κρασί και γλυκά', 19.90),
  ('KAL02', '2000000000367', 'Καλάθι πρωινού',         14.50)
) v (code, barcode, name, price)
join mm_category c on c.name = 'Καλάθια δώρου'
where not exists (select 1 from mm_item i where i.code = v.code);

declare
  n number;
  function id_of(c varchar2) return number is
    v number;
  begin
    select id into v from mm_item where code = c;
    return v;
  end;
begin
  select count(*) into n from mm_kit_component k join mm_item i on i.id = k.kit_id where i.code = 'KAL01';
  if n = 0 then
    mm_core.set_component(id_of('KAL01'), id_of('POT06'), 1);
    mm_core.set_component(id_of('KAL01'), id_of('SNK02'), 2);
    mm_core.set_component(id_of('KAL01'), id_of('SNK03'), 1);
    mm_core.assemble_kit(id_of('KAL01'), 2, 'Επίδειξη');
    mm_core.set_component(id_of('KAL02'), id_of('KAF02'), 1);
    mm_core.set_component(id_of('KAL02'), id_of('ART02'), 1);
    mm_core.set_component(id_of('KAL02'), id_of('SNK04'), 3);
  end if;
end;
/

-- three promotions until the end of this year: beers 2+1, coffees -20%, filter coffee + biscuits 5 euro
declare
  p number;
  last_ date := add_months(trunc(sysdate, 'YYYY'), 12) - 1;
  n number;
  function id_of(c varchar2) return number is
    v number;
  begin
    select id into v from mm_item where code = c;
    return v;
  end;
begin
  select count(*) into n from mm_promo where name in ('Μπίρες 2+1', 'Καφέδες -20%', 'Καφές φίλτρου + μπισκότα 5 €');
  if n = 0 then
    p := mm_core.new_promo('Μπίρες 2+1', 'NM', trunc(sysdate), last_, p_buy => 2, p_free => 1);
    mm_core.promo_item(p, id_of('POT05'));
    p := mm_core.new_promo('Καφέδες -20%', 'PCT', trunc(sysdate), last_, p_pct => 20);
    for c in (select id from mm_category where name = 'Καφές και ροφήματα') loop
      mm_core.promo_item(p, p_category_id => c.id);
    end loop;
    p := mm_core.new_promo('Καφές φίλτρου + μπισκότα 5 €', 'BUNDLE', trunc(sysdate), last_, p_price => 5);
    mm_core.promo_item(p, id_of('KAF02'), p_qty => 1);
    mm_core.promo_item(p, id_of('SNK03'), p_qty => 1);
  end if;
end;
/

-- clothes and shoes: colours, sizes, a T-shirt (black/white x S/M/L) and trainers (black x 40..44),
-- 2 of each variant
insert into mm_color (code, name)
select v.code, v.name from (values ('BLK', 'Μαύρο'), ('WHT', 'Λευκό'), ('BLU', 'Μπλε'),
                                   ('RED', 'Κόκκινο'), ('GRY', 'Γκρι')) v (code, name)
where not exists (select 1 from mm_color c where c.code = v.code);

insert into mm_size (size_group, code, sort_no)
select v.g, v.code, v.n from (values ('CLOTHES', 'XS', 1), ('CLOTHES', 'S', 2), ('CLOTHES', 'M', 3),
                                     ('CLOTHES', 'L', 4), ('CLOTHES', 'XL', 5), ('CLOTHES', 'XXL', 6),
                                     ('SHOES', '36', 36), ('SHOES', '37', 37), ('SHOES', '38', 38),
                                     ('SHOES', '39', 39), ('SHOES', '40', 40), ('SHOES', '41', 41),
                                     ('SHOES', '42', 42), ('SHOES', '43', 43), ('SHOES', '44', 44),
                                     ('SHOES', '45', 45), ('SHOES', '46', 46)) v (g, code, n)
where not exists (select 1 from mm_size z where z.size_group = v.g and z.code = v.code);

insert into mm_category (name)
select v.name from (values ('Ρούχα'), ('Παπούτσια')) v (name)
where not exists (select 1 from mm_category c where c.name = v.name);

insert into mm_item (code, name, category_id, vat_code, unit, price, cost, min_stock)
select v.code, v.name, c.id, 'A', 'PCS', v.price, v.cost, 0
from (values ('TSH01', 'Μπλουζάκι βαμβακερό', 'Ρούχα', 12.90, 5.00),
             ('SHO01', 'Αθλητικά παπούτσια', 'Παπούτσια', 49.90, 22.00)) v (code, name, cat, price, cost)
join mm_category c on c.name = v.cat
where not exists (select 1 from mm_item i where i.code = v.code);

declare
  n number;
  v number;
  function id_of(c varchar2) return number is
    x number;
  begin
    select id into x from mm_item where code = c;
    return x;
  end;
begin
  v := id_of('TSH01');                  -- (a local function may not be called inside SQL)
  select count(*) into n from mm_item where parent_id = v;
  if n = 0 then
    for c in (select id from mm_color where code in ('BLK', 'WHT') order by code) loop
      for z in (select id from mm_size where size_group = 'CLOTHES' and code in ('S', 'M', 'L') order by sort_no) loop
        v := mm_core.make_variant(id_of('TSH01'), c.id, z.id);
        mm_core.adjust_stock(v, 2, 'Επίδειξη');
      end loop;
    end loop;
    for z in (select id from mm_size where size_group = 'SHOES' and sort_no between 40 and 44 order by sort_no) loop
      select id into n from mm_color where code = 'BLK';
      v := mm_core.make_variant(id_of('SHO01'), n, z.id);
      mm_core.adjust_stock(v, 2, 'Επίδειξη');
    end loop;
  end if;
end;
/

-- wholesale prices (without VAT) for the drinks and the snacks; the others: the retail without VAT
update mm_item i set wholesale_price = round(i.price / (1 + (select v.rate from mm_vat v where v.code = i.vat_code) / 100) * 0.85, 2)
where i.wholesale_price is null and i.code in ('POT01', 'POT02', 'POT03', 'POT04', 'POT05', 'POT06',
                                               'SNK01', 'SNK02', 'SNK03', 'SNK04');

-- two invoices: a purchase of beers from a supplier, a wholesale sale to a taverna (on credit)
declare
  d number;
  l number;
  n number;
  function id_of(c varchar2) return number is
    x number;
  begin
    select id into x from mm_item where code = c;
    return x;
  end;
begin
  select count(*) into n from mm_doc where doc_type in ('TPY', 'TAG');
  if n = 0 then
    select id into n from mm_supplier where afm = '999000079';
    d := mm_core.new_doc('TAG', p_supplier_id => n, p_payment => 'CREDIT');
    l := mm_core.add_line(d, id_of('POT05'), 48, 0.80);
    l := mm_core.add_line(d, id_of('POT01'), 120, 0.18);
    n := mm_core.post_doc(d);
    select id into n from mm_customer where afm = '999000020';
    d := mm_core.new_doc('TPY', p_customer_id => n, p_payment => 'CREDIT');
    l := mm_core.add_line(d, id_of('POT05'), 24);
    l := mm_core.add_line(d, id_of('POT01'), 48);
    n := mm_core.post_doc(d);
  end if;
end;
/

-- the cards of mobile phones: items with serials, 5 cards each (made-up serials and PINs), when
-- MM_PIN works (DBMS_CRYPTO: GRANT_CRYPTO.sql)
insert into mm_category (name)
select 'Κάρτες κινητής' from dual where not exists (select 1 from mm_category where name = 'Κάρτες κινητής');

insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock, serial_tracked)
select v.code, v.barcode, v.name, c.id, 'A', 'PCS', v.price, v.cost, 2, 'Y'
from (values
  ('CRD05', '2000000000312', 'Κάρτα κινητής 5 €',  5.00,  4.75),
  ('CRD10', '2000000000329', 'Κάρτα κινητής 10 €', 10.00,  9.50),
  ('CRD20', '2000000000336', 'Κάρτα κινητής 20 €', 20.00, 19.00)
) v (code, barcode, name, price, cost)
join mm_category c on c.name = 'Κάρτες κινητής'
where not exists (select 1 from mm_item i where i.code = v.code);

-- one card of each value in a sale
update mm_item set max_per_sale = 1 where code like 'CRD%' and max_per_sale is null;

declare
  n number;
  s number;
begin
  select count(*) into n from user_objects where object_name = 'MM_PIN' and object_type = 'PACKAGE BODY'
  and status = 'VALID';
  if n = 0 then
    return;
  end if;
  for i in (select id, code from mm_item where serial_tracked = 'Y' and code like 'CRD%'
            and not exists (select 1 from mm_serial s where s.item_id = mm_item.id)) loop
    for k in 1 .. 5 loop
      s := mm_core.load_serial(i.id, 'DEMO-' || i.code || '-' || lpad(k, 4, '0'),
                               lpad(trunc(dbms_random.value(0, 1e12)), 12, '0'), 'Κάρτες επίδειξης');
    end loop;
  end loop;
end;
/

commit;
