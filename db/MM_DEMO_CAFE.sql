-- MM_DEMO_CAFE.sql -- the cafe of the shop, to try it: 16 items without a barcode (coffees, juices, snacks and
-- sweets) with a short number (PLU 101-145), in three groups of buttons of the till (Καφέδες, Χυμοί, Σνακ και
-- γλυκά); the options (Ζάχαρη: one, required, Μέτριος by default; Γάλα: Βρώμης +0,30, Αμυγδάλου +0,30, Χωρίς
-- λακτόζη +0,20; Έξτρα: σφηνάκι +0,50, σιρόπι +0,30, σαντιγί +0,40, κανέλα) on the coffees; the materials of
-- the cafe (coffee in kg, milk in L, cups) and the recipe of each coffee and juice, the materials of the
-- options (Βρώμης: oat instead of fresh milk), and one delivery note of the materials and of the snacks from the
-- supplier «Χονδρική καφέ (επίδειξη)», so that they have stock and a cost.
--
-- Run by INSTALL.sql demo. On its own, on a database that works already (no receipts are made), as the owner,
-- from this folder (NLS_LANG=GREEK_GREECE.AL32UTF8, as for INSTALL.sql):
--
--   sqlplus mm/<password>@FREEPDB1 @MM_DEMO_CAFE.sql
--
-- Only what is missing is added: the items by code, the buttons and the options only if there are none yet,
-- the recipes and the delivery note only once.
set define off
whenever sqlerror exit failure rollback

-- the cafe of the shop (the buttons of the till, #/tiles): coffees, juices, sweets without a barcode, each with a
-- short number (PLU, typed at the till), in three groups of buttons. A category of their own (not the
-- promotion of the coffees in packs)
insert into mm_category (name)
select 'Καφέ πάγκου' from dual where not exists (select 1 from mm_category where name = 'Καφέ πάγκου');
insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock, plu)
select v.code, null, v.name, c.id, v.vat_code, 'PCS', v.price, v.cost, 0, v.plu
from (values
  ('CAF01', 'Freddo espresso',          'B', 2.50, 0.45, 101),
  ('CAF02', 'Freddo cappuccino',        'B', 3.00, 0.60, 102),
  ('CAF03', 'Espresso',                 'B', 1.60, 0.30, 103),
  ('CAF04', 'Cappuccino',               'B', 2.80, 0.55, 104),
  ('CAF05', 'Ελληνικός',                'B', 1.80, 0.25, 105),
  ('CAF06', 'Φραπέ',                    'B', 2.20, 0.30, 106),
  ('CAF07', 'Σοκολάτα ζεστή',           'B', 3.00, 0.70, 107),
  ('CAF08', 'Τσάι',                     'B', 1.80, 0.20, 108),
  ('CAF21', 'Χυμός πορτοκάλι φρέσκος',  'B', 3.50, 1.10, 121),
  ('CAF22', 'Σμούθι φράουλα',           'B', 4.00, 1.40, 122),
  ('CAF23', 'Λεμονάδα σπιτική',         'B', 2.80, 0.60, 123),
  ('CAF41', 'Τυρόπιτα',                 'B', 2.20, 0.90, 141),
  ('CAF42', 'Κρουασάν βουτύρου',        'B', 1.90, 0.70, 142),
  ('CAF43', 'Μπουγάτσα κρέμα',          'B', 2.80, 1.00, 143),
  ('CAF44', 'Κέικ σοκολάτα (κομμάτι)',  'B', 2.50, 0.80, 144),
  ('CAF45', 'Τοστ γαλοπούλα-τυρί',      'B', 2.60, 1.00, 145)
) v (code, name, vat_code, price, cost, plu)
join mm_category c on c.name = 'Καφέ πάγκου'
where not exists (select 1 from mm_item i where i.code = v.code);

declare
  g number;
  n number;
  t number;
begin
  select count(*) into n from mm_tile_group;
  if n = 0 then
    for x in (select 'Καφέδες' name, '#8b5a2b' color, 'CAF0' pfx from dual union all
              select 'Χυμοί', '#e08a00', 'CAF2' from dual union all
              select 'Σνακ και γλυκά', '#b4436c', 'CAF4' from dual) loop
      g := mm_core.tile_group_save(null, x.name, x.color, 'Y');
      for i in (select id from mm_item where code like x.pfx || '%' order by code) loop
        t := mm_core.tile_add(g, i.id);
      end loop;
    end loop;
  end if;
end;
/

-- the options of the cafe (sugar, milk, extras), on its coffees
declare
  sugar number;
  milk number;
  extra number;
  n number;
  o number;
  function id_of(p_code varchar2) return number is
    v number;
  begin
    select id into v from mm_item where code = p_code;
    return v;
  end;
begin
  select count(*) into n from mm_option_group;
  if n = 0 then
    sugar := mm_core.option_group_save(null, 'Ζάχαρη', 'O', 'Y', 'Y');
    o := mm_core.option_save(null, sugar, 'Σκέτος', 0, 'N', 'Y');
    o := mm_core.option_save(null, sugar, 'Μέτριος', 0, 'Y', 'Y');
    o := mm_core.option_save(null, sugar, 'Γλυκός', 0, 'N', 'Y');
    o := mm_core.option_save(null, sugar, 'Με στέβια', 0, 'N', 'Y');
    milk := mm_core.option_group_save(null, 'Γάλα', 'O', 'N', 'Y');
    o := mm_core.option_save(null, milk, 'Φρέσκο', 0, 'N', 'Y');
    o := mm_core.option_save(null, milk, 'Βρώμης', 0.30, 'N', 'Y');
    o := mm_core.option_save(null, milk, 'Αμυγδάλου', 0.30, 'N', 'Y');
    o := mm_core.option_save(null, milk, 'Χωρίς λακτόζη', 0.20, 'N', 'Y');
    extra := mm_core.option_group_save(null, 'Έξτρα', 'M', 'N', 'Y');
    o := mm_core.option_save(null, extra, 'Έξτρα σφηνάκι', 0.50, 'N', 'Y');
    o := mm_core.option_save(null, extra, 'Σιρόπι καραμέλα', 0.30, 'N', 'Y');
    o := mm_core.option_save(null, extra, 'Σαντιγί', 0.40, 'N', 'Y');
    o := mm_core.option_save(null, extra, 'Κανέλα', 0, 'N', 'Y');
    for c in (select column_value code from table(sys.odcivarchar2list('CAF01', 'CAF02', 'CAF03', 'CAF04', 'CAF05', 'CAF06'))) loop
      mm_core.item_option(id_of(c.code), sugar, 'Y');
    end loop;
    for c in (select column_value code from table(sys.odcivarchar2list('CAF02', 'CAF04', 'CAF06', 'CAF07'))) loop
      mm_core.item_option(id_of(c.code), milk, 'Y');
    end loop;
    for c in (select column_value code from table(sys.odcivarchar2list('CAF01', 'CAF02', 'CAF03', 'CAF04', 'CAF06', 'CAF07'))) loop
      mm_core.item_option(id_of(c.code), extra, 'Y');
    end loop;
  end if;
end;
/

-- the recipes of the cafe: its materials (bought, so that they have stock and a cost by FIFO), each coffee a
-- kit never assembled (a sale takes its materials), the materials of the options (Βρώμης: oat milk instead of
-- the fresh one); the snacks bought ready
insert into mm_category (name)
select 'Υλικά καφέ' from dual where not exists (select 1 from mm_category where name = 'Υλικά καφέ');
insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock)
select v.code, null, v.name, c.id, v.vat_code, v.unit, 0, v.cost, v.min_stock
from (values
  ('RAW01', 'Καφές espresso (κόκκοι)',              'B', 'KG',  18.00,   2),
  ('RAW02', 'Καφές ελληνικός (για τον πάγκο)',      'B', 'KG',  12.00,   1),
  ('RAW03', 'Καφές στιγμιαίος (φραπέ)',             'B', 'KG',  20.00, 0.5),
  ('RAW04', 'Γάλα φρέσκο (για τον πάγκο)',          'B', 'L',    1.20,   6),
  ('RAW05', 'Ρόφημα βρώμης',                        'B', 'L',    2.80,   2),
  ('RAW06', 'Ρόφημα αμυγδάλου',                     'B', 'L',    3.20,   2),
  ('RAW07', 'Ποτήρι χάρτινο 12 oz με καπάκι',       'A', 'PCS',  0.08, 100),
  ('RAW08', 'Ποτήρι 14 oz με καπάκι και καλαμάκι',  'A', 'PCS',  0.10, 100),
  ('RAW09', 'Πορτοκάλια χυμού',                     'C', 'KG',   1.00,  10),
  ('RAW10', 'Σιρόπι καραμέλα',                      'A', 'L',    8.00,   1)
) v (code, name, vat_code, unit, cost, min_stock)
join mm_category c on c.name = 'Υλικά καφέ'
where not exists (select 1 from mm_item i where i.code = v.code);

declare
  n number;
  d number;
  l number;
  s number;
  function id_of(p_code varchar2) return number is
    v number;
  begin
    select id into v from mm_item where code = p_code;
    return v;
  end;
  function opt(p_group varchar2, p_name varchar2) return number is
    v number;
  begin
    select o.id into v from mm_option o join mm_option_group g on g.id = o.group_id
    where g.name = p_group and o.name = p_name;
    return v;
  end;
begin
  d := id_of('CAF01');                -- (a function of this block: not in SQL, PLS-00231)
  select count(*) into n from mm_kit_component where kit_id = d;
  if n = 0 then
    -- bought: the materials and the snacks (a delivery note of the supplier, posted)
    select min(id) into s from mm_supplier where name = 'Χονδρική καφέ (επίδειξη)';
    if s is null then
      insert into mm_supplier (name) values ('Χονδρική καφέ (επίδειξη)') returning id into s;
    end if;
    d := mm_core.new_doc('DPA', p_supplier_id => s, p_payment => 'CREDIT', p_doc_date => trunc(sysdate) - 7);
    for x in (select 'RAW01' c, 5 q from dual union all select 'RAW02', 2 from dual union all select 'RAW03', 1 from dual
              union all select 'RAW04', 24 from dual union all select 'RAW05', 6 from dual union all select 'RAW06', 6 from dual
              union all select 'RAW07', 500 from dual union all select 'RAW08', 500 from dual union all select 'RAW09', 40 from dual
              union all select 'RAW10', 2 from dual union all select 'CAF41', 40 from dual union all select 'CAF42', 40 from dual
              union all select 'CAF43', 30 from dual union all select 'CAF44', 24 from dual union all select 'CAF45', 30 from dual) loop
      l := mm_core.add_line(d, id_of(x.c), x.q);
    end loop;
    n := mm_core.post_doc(d);
    -- the recipes
    for r in (select 'CAF01' k, 'RAW01' c, 0.018 q from dual union all select 'CAF01', 'RAW08', 1 from dual
              union all select 'CAF02', 'RAW01', 0.018 from dual union all select 'CAF02', 'RAW04', 0.1 from dual
              union all select 'CAF02', 'RAW08', 1 from dual
              union all select 'CAF03', 'RAW01', 0.009 from dual union all select 'CAF03', 'RAW07', 1 from dual
              union all select 'CAF04', 'RAW01', 0.009 from dual union all select 'CAF04', 'RAW04', 0.15 from dual
              union all select 'CAF04', 'RAW07', 1 from dual
              union all select 'CAF05', 'RAW02', 0.007 from dual union all select 'CAF05', 'RAW07', 1 from dual
              union all select 'CAF06', 'RAW03', 0.004 from dual union all select 'CAF06', 'RAW08', 1 from dual
              union all select 'CAF21', 'RAW09', 0.5 from dual union all select 'CAF21', 'RAW08', 1 from dual) loop
      mm_core.set_component(id_of(r.k), id_of(r.c), r.q);
    end loop;
    -- the materials of the options: oat or almond instead of the fresh milk, a shot more, the syrup
    mm_core.option_component(opt('Γάλα', 'Βρώμης'), id_of('RAW05'), 0.15);
    mm_core.option_component(opt('Γάλα', 'Βρώμης'), id_of('RAW04'), -0.15);
    mm_core.option_component(opt('Γάλα', 'Αμυγδάλου'), id_of('RAW06'), 0.15);
    mm_core.option_component(opt('Γάλα', 'Αμυγδάλου'), id_of('RAW04'), -0.15);
    mm_core.option_component(opt('Έξτρα', 'Έξτρα σφηνάκι'), id_of('RAW01'), 0.009);
    mm_core.option_component(opt('Έξτρα', 'Σιρόπι καραμέλα'), id_of('RAW10'), 0.02);
  end if;
end;
/

commit;
