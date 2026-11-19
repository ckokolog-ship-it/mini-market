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
-- Only what is missing is added: the items by code (a PLU taken by another item: none), the groups of buttons
-- and of options by name, the tiles and the options missing in them; the recipes and the delivery note once.
-- What the shop has made already (its own buttons and options) stays as it is.
set define off
whenever sqlerror exit failure rollback

-- the cafe of the shop (the buttons of the till, #/tiles): coffees, juices, sweets without a barcode, each with a
-- short number (PLU, typed at the till), in three groups of buttons. Four categories of their own (the options
-- are by category: sugar and a double for the coffees, not for the bougatsa; not the promotion of the coffees
-- in packs): CAF0x coffees, CAF07/08 the other hot drinks, CAF2x juices, CAF4x snacks and sweets
insert into mm_category (name)
select v.name from (values ('Καφές (πάγκος)'), ('Ροφήματα (πάγκος)'), ('Χυμοί (πάγκος)'), ('Σνακ και γλυκά (πάγκος)')) v (name)
where not exists (select 1 from mm_category c where c.name = v.name);
insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, cost, min_stock, plu)
select v.code, null, v.name, c.id, v.vat_code, 'PCS', v.price, v.cost, 0,
       case when not exists (select 1 from mm_item p where p.plu = v.plu) then v.plu end   -- (a PLU taken: none)
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
join mm_category c on c.name = case when v.code in ('CAF07', 'CAF08') then 'Ροφήματα (πάγκος)'
                                    when v.code like 'CAF0%' then 'Καφές (πάγκος)'
                                    when v.code like 'CAF2%' then 'Χυμοί (πάγκος)' else 'Σνακ και γλυκά (πάγκος)' end
where not exists (select 1 from mm_item i where i.code = v.code);
-- (the items of before, all in the one category «Καφέ πάγκου»: into the four; it out, if empty)
update mm_item i set category_id = (select c.id from mm_category c where c.name =
         case when i.code in ('CAF07', 'CAF08') then 'Ροφήματα (πάγκος)' when i.code like 'CAF0%' then 'Καφές (πάγκος)'
              when i.code like 'CAF2%' then 'Χυμοί (πάγκος)' else 'Σνακ και γλυκά (πάγκος)' end)
where i.code like 'CAF%' and i.category_id = (select min(id) from mm_category where name = 'Καφέ πάγκου');
delete from mm_category c where c.name = 'Καφέ πάγκου' and not exists (select 1 from mm_item i where i.category_id = c.id);

-- the groups of buttons, by name: one missing made; in each, the items of the cafe it does not have yet
declare
  g number;
  t number;
begin
  for x in (select 'Καφέδες' name, '#8b5a2b' color, 'CAF0' pfx from dual union all
            select 'Χυμοί', '#e08a00', 'CAF2' from dual union all
            select 'Σνακ και γλυκά', '#b4436c', 'CAF4' from dual) loop
    select min(id) into g from mm_tile_group where name = x.name;
    if g is null then
      g := mm_core.tile_group_save(null, x.name, x.color, 'Y');
    end if;
    for i in (select id from mm_item where code like x.pfx || '%' and active = 'Y'
              and not exists (select 1 from mm_tile k where k.group_id = g and k.item_id = mm_item.id) order by code) loop
      t := mm_core.tile_add(g, i.id);
    end loop;
  end loop;
end;
/

-- the options of the cafe, by category (by name: a group or an option missing made; those of the shop stay as
-- they are): Μέγεθος (μονός / διπλός +0,50, required) and Ζάχαρη (required, μέτριος) on the coffees; Γάλα and
-- Έξτρα on the coffees and the hot drinks, the shot only for the coffees
declare
  size_ number;
  sugar number;
  milk number;
  extra number;
  o number;
  coffee number;
  drinks number;
  made boolean;
  function cat(p_name varchar2) return number is
    v number;
  begin
    select min(id) into v from mm_category where name = p_name;
    return v;
  end;
  function grp(p_name varchar2, p_pick varchar2, p_required varchar2) return number is
    v number;
  begin
    select min(id) into v from mm_option_group where name = p_name;
    made := v is null;
    if v is null then                   -- (not nvl: it makes both of its arguments)
      v := mm_core.option_group_save(null, p_name, p_pick, p_required, 'Y');
    end if;
    return v;
  end;
  function opt(p_group number, p_name varchar2, p_price number, p_default varchar2) return number is
    v number;
  begin
    select min(id) into v from mm_option where group_id = p_group and name = p_name;
    if v is null then
      v := mm_core.option_save(null, p_group, p_name, p_price, p_default, 'Y');
    end if;
    return v;
  end;
  procedure on_cat(p_group number, p_cat number) is
  begin
    if p_cat is not null then
      mm_core.category_option(p_cat, p_group, 'Y');
    end if;
  end;
begin
  coffee := cat('Καφές (πάγκος)');
  drinks := cat('Ροφήματα (πάγκος)');
  size_ := grp('Μέγεθος', 'O', 'Y');
  if made then                          -- (new: the first of the groups)
    for k in 1 .. 20 loop
      mm_core.option_move('G', size_, -1);
    end loop;
  end if;
  o := opt(size_, 'Μονός', 0, 'Y');
  o := opt(size_, 'Διπλός', 0.50, 'N');
  sugar := grp('Ζάχαρη', 'O', 'Y');
  o := opt(sugar, 'Σκέτος', 0, 'N');
  o := opt(sugar, 'Μέτριος', 0, 'Y');
  o := opt(sugar, 'Γλυκός', 0, 'N');
  o := opt(sugar, 'Με στέβια', 0, 'N');
  milk := grp('Γάλα', 'O', 'N');
  o := opt(milk, 'Φρέσκο', 0, 'N');
  o := opt(milk, 'Βρώμης', 0.30, 'N');
  o := opt(milk, 'Αμυγδάλου', 0.30, 'N');
  o := opt(milk, 'Χωρίς λακτόζη', 0.20, 'N');
  extra := grp('Έξτρα', 'M', 'N');
  o := opt(extra, 'Έξτρα σφηνάκι', 0.50, 'N');
  if coffee is not null then
    mm_core.option_category(o, coffee, 'Y');      -- (not for the chocolate, not for the tea)
  end if;
  o := opt(extra, 'Σιρόπι καραμέλα', 0.30, 'N');
  o := opt(extra, 'Σαντιγί', 0.40, 'N');
  o := opt(extra, 'Κανέλα', 0, 'N');
  on_cat(size_, coffee);
  on_cat(sugar, coffee);
  on_cat(milk, coffee);
  on_cat(milk, drinks);
  on_cat(extra, coffee);
  on_cat(extra, drinks);
  -- (the groups of the coffees of before, item by item: now of their categories)
  delete from mm_item_option where included = 'Y' and group_id in (size_, sugar, milk, extra)
  and item_id in (select id from mm_item where code like 'CAF%');
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
  function opt(p_group varchar2, p_name varchar2) return number is      -- (none: null)
    v number;
  begin
    select min(o.id) into v from mm_option o join mm_option_group g on g.id = o.group_id
    where g.name = p_group and o.name = p_name;
    return v;
  end;
  procedure material(p_option number, p_code varchar2, p_qty number) is
  begin
    if p_option is not null then
      mm_core.option_component(p_option, id_of(p_code), p_qty);
    end if;
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
    material(opt('Γάλα', 'Βρώμης'), 'RAW05', 0.15);
    material(opt('Γάλα', 'Βρώμης'), 'RAW04', -0.15);
    material(opt('Γάλα', 'Αμυγδάλου'), 'RAW06', 0.15);
    material(opt('Γάλα', 'Αμυγδάλου'), 'RAW04', -0.15);
    material(opt('Έξτρα', 'Έξτρα σφηνάκι'), 'RAW01', 0.009);
    material(opt('Έξτρα', 'Σιρόπι καραμέλα'), 'RAW10', 0.02);
  end if;
end;
/

-- a double: a dose more of the coffee of each recipe (freddo 18 g, espresso 9 g, ελληνικός 7 g, φραπέ 4 g),
-- every time (a database with the recipes of before too)
declare
  d number;
  v number;
begin
  select min(o.id) into d from mm_option o join mm_option_group g on g.id = o.group_id
  where g.name = 'Μέγεθος' and o.name = 'Διπλός';
  if d is not null then
    for x in (select id from mm_item where code in ('RAW01', 'RAW02', 'RAW03')) loop
      select count(*) into v from mm_option_component where option_id = d and component_id = x.id;
      if v = 0 then
        mm_core.option_component(d, x.id, 1, 'Y');
      end if;
    end loop;
  end if;
end;
/

commit;
