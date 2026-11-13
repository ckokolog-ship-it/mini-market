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
  and not exists (select 1 from mm_stock_move m where m.item_id = i.id);

update mm_item i
set i.stock = (select nvl(sum(m.qty), 0) from mm_stock_move m where m.item_id = i.id)
where i.stock <> (select nvl(sum(m.qty), 0) from mm_stock_move m where m.item_id = i.id);

commit;
