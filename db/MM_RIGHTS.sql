-- MM_RIGHTS.sql -- the rights of the users: roles, the screens of the menu (a page of the web and/or a form
-- of Oracle Forms), their fields and actions, what each role may do with them. Run by INSTALL.sql, after
-- MM_AUTH.sql (the tables: MM_TABLES.sql).
--
--   MM_ROLE         the roles: CASHIER, MANAGER, ADMIN (system: as before them) and the shop's own; a role
--                   of all rights (ADMIN): everything, always
--   MM_USER_ROLE    the roles of a user (more than one: the most of each)
--   MM_OBJECT       the menu: its groups (G) and its screens (S), each with its page (route) and/or form
--   MM_OBJECT_ITEM  the fields (F) and the actions (A) of a screen
--   MM_GRANT        what a role may do: N none, R read, W write (an action: W allowed, else not)
--
-- The level of a user, for each screen, field, action (MM_USER_RIGHT): of each of its roles, the most.
-- Of a role: a screen, its grant (none: N); a field, its grant, not above its screen (none: as its
-- screen); an action, its grant when the screen is at least R (none: allowed when the screen is W).
--
--   mm_rights.lvl(user_id, 'ITEMS', 'COST')            N, R or W
--   mm_rights.can(user_id, 'DOCS', 'POST', 'W')        Y or N
--   mm_rights.need(user_id, 'ITEMS', null, 'W')        else MM-197
--   mm_rights.create_role('STORE_MGR', 'Υπεύθυνος καταστήματος'); mm_rights.copy_role('MANAGER', 'STORE_MGR')
--   mm_rights.set_grant('STORE_MGR', 'ITEMS', 'COST', 'N')        (null: the grant out)
--   mm_rights.add_user_role('nikos.r', 'STORE_MGR')
--
-- Once more (INSTALL.sql again): a screen, a field, a role, a grant that is there already stays as it is
-- (what the shop changed is kept); only what is new comes in. No commit in the package, as MM_CORE.
-- The errors: MM-197 (not allowed), MM-198 (the roles and the grants).

-- the level of each role, for each screen, field and action (as a number: 0 N, 1 R, 2 W)
create or replace view mm_role_right as
with so as (
  select r.id role_id, r.all_rights, o.id object_id, o.code object_code,
         case when r.all_rights = 'Y' then 2
              else nvl((select instr('NRW', g.lvl) - 1 from mm_grant g
                        where g.role_id = r.id and g.object_id = o.id and g.item_id is null), 0) end lv
  from mm_role r cross join mm_object o
  where r.active = 'Y' and o.kind = 'S' and o.active = 'Y')
select so.role_id, so.object_id, so.object_code, cast(null as number) item_id, cast(null as varchar2(30)) item_code,
       'S' kind, so.lv
from so
union all
select so.role_id, so.object_id, so.object_code, i.id, i.code, i.kind,
       case when so.all_rights = 'Y' then 2
            when so.lv = 0 then 0
            when i.kind = 'F' then least(so.lv, nvl(g.lv, so.lv))
            else case when nvl(g.lv, so.lv) = 2 then 2 else 0 end end
from so
join mm_object_item i on i.object_id = so.object_id
left join (select role_id, item_id, instr('NRW', lvl) - 1 lv from mm_grant where item_id is not null) g
  on g.role_id = so.role_id and g.item_id = i.id;

-- the level of each active user: of its active roles, the most
create or replace view mm_user_right as
select ur.user_id, r.object_id, r.object_code, r.item_id, r.item_code, r.kind, max(r.lv) lv,
       substr('NRW', max(r.lv) + 1, 1) lvl
from mm_user_role ur
join mm_user u on u.id = ur.user_id and u.active = 'Y'
join mm_role_right r on r.role_id = ur.role_id
group by ur.user_id, r.object_id, r.object_code, r.item_id, r.item_code, r.kind;

-- the menu of each user: the screens it may at least read, in their groups, in order
create or replace view mm_user_menu as
select u.user_id, g.code group_code, g.name group_name, g.sort_no group_sort, o.code, o.name, o.route, o.form,
       o.sort_no, u.lvl
from mm_user_right u
join mm_object o on o.id = u.object_id
left join mm_object g on g.id = o.parent_id
where u.item_id is null and u.lv > 0 and (g.id is null or g.active = 'Y');

create or replace package mm_rights as
  function lvl(p_user_id number, p_object varchar2, p_item varchar2 default null) return varchar2;
  function can(p_user_id number, p_object varchar2, p_item varchar2 default null,
               p_level varchar2 default 'R') return varchar2;
  procedure need(p_user_id number, p_object varchar2, p_item varchar2 default null, p_level varchar2 default 'R');

  -- the roles: a new one (a code A-Z 0-9 _); its name, (not) active; out (not a system one); its grants
  -- from another one (all of them: what it had, replaced)
  function create_role(p_code varchar2, p_name varchar2, p_all_rights varchar2 default 'N') return number;
  procedure set_role(p_code varchar2, p_name varchar2, p_active varchar2 default 'Y');
  procedure drop_role(p_code varchar2);
  procedure copy_role(p_from varchar2, p_to varchar2);
  -- what a role may do with a screen (p_item null), a field or an action of it: N, R, W; null: the grant
  -- out (a screen: none; a field, an action: as its screen)
  procedure set_grant(p_role varchar2, p_object varchar2, p_item varchar2, p_level varchar2);
  -- the roles of a user
  procedure add_user_role(p_username varchar2, p_role varchar2);
  procedure drop_user_role(p_username varchar2, p_role varchar2);
  -- the menu: a group or a screen renamed, its place (its order; a screen: its group), (not) active (not
  -- the roles and the rights themselves: the way back to them)
  procedure set_object(p_code varchar2, p_name varchar2, p_sort number, p_group varchar2, p_active varchar2 default 'Y');
end mm_rights;
/

create or replace package body mm_rights as

  procedure fail(p_no pls_integer, p_text varchar2) is
  begin
    raise_application_error(-20100 - p_no, 'MM-' || to_char(100 + p_no) || ': ' || p_text);
  end;

  function lvl(p_user_id number, p_object varchar2, p_item varchar2 default null) return varchar2 is
    v varchar2(1);
  begin
    select max(lvl) keep (dense_rank last order by lv) into v from mm_user_right
    where user_id = p_user_id and object_code = upper(p_object)
      and (p_item is null and item_id is null or item_code = upper(p_item));
    return nvl(v, 'N');
  end;

  function can(p_user_id number, p_object varchar2, p_item varchar2 default null,
               p_level varchar2 default 'R') return varchar2 is
  begin
    return case when instr('NRW', lvl(p_user_id, p_object, p_item)) >= instr('NRW', upper(nvl(p_level, 'R')))
                then 'Y' else 'N' end;
  end;

  procedure need(p_user_id number, p_object varchar2, p_item varchar2 default null, p_level varchar2 default 'R') is
    n varchar2(200);
  begin
    if can(p_user_id, p_object, p_item, p_level) = 'N' then
      select max(o.name) || max(case when i.name is not null then ': ' || i.name end) into n
      from mm_object o left join mm_object_item i on i.object_id = o.id and i.code = upper(p_item)
      where o.code = upper(p_object);
      fail(97, 'Δεν επιτρέπεται: ' || nvl(n, upper(p_object)));
    end if;
  end;

  function role_id(p_code varchar2) return number is
    v number;
  begin
    select id into v from mm_role where code = upper(p_code);
    return v;
  exception
    when no_data_found then fail(98, 'Δεν υπάρχει ρόλος ' || p_code);
  end;

  -- the shop never stays without an active user of an active role of all rights (checked when a role of
  -- all rights is taken from a user, out, not active)
  procedure keep_an_admin(p_role_id number) is
    n number;
    a varchar2(1);
  begin
    select max(all_rights) into a from mm_role where id = p_role_id;
    if nvl(a, 'Y') = 'N' then
      return;
    end if;
    select count(*) into n from mm_user u
    join mm_user_role ur on ur.user_id = u.id
    join mm_role r on r.id = ur.role_id and r.active = 'Y' and r.all_rights = 'Y'
    where u.active = 'Y';
    if n = 0 then
      fail(98, 'Πρέπει να μείνει τουλάχιστον ένας ενεργός χρήστης με όλα τα δικαιώματα');
    end if;
  end;

  function create_role(p_code varchar2, p_name varchar2, p_all_rights varchar2 default 'N') return number is
    v number;
  begin
    if p_code is null or not regexp_like(upper(p_code), '^[A-Z][A-Z0-9_]{1,29}$') then
      fail(98, 'Κωδικός ρόλου: 2 έως 30 λατινικά γράμματα, ψηφία ή _, από γράμμα');
    end if;
    if trim(p_name) is null then
      fail(98, 'Ο ρόλος θέλει όνομα');
    end if;
    if nvl(p_all_rights, 'N') not in ('Y', 'N') then
      fail(98, 'Όλα τα δικαιώματα: Y ή N');
    end if;
    begin
      insert into mm_role (code, name, all_rights) values (upper(p_code), trim(p_name), nvl(p_all_rights, 'N'))
      returning id into v;
    exception
      when dup_val_on_index then fail(98, 'Υπάρχει ήδη ρόλος ' || upper(p_code));
    end;
    return v;
  end;

  procedure set_role(p_code varchar2, p_name varchar2, p_active varchar2 default 'Y') is
    r mm_role%rowtype;
    id_ number := role_id(p_code);
  begin
    select * into r from mm_role where id = id_;
    if nvl(p_active, 'Y') not in ('Y', 'N') then
      fail(98, 'Ενεργός: Y ή N');
    end if;
    if r.system = 'Y' and nvl(p_active, 'Y') = 'N' then
      fail(98, 'Ο ρόλος ' || r.code || ' του συστήματος μένει ενεργός');
    end if;
    update mm_role set name = nvl(trim(p_name), name), active = nvl(p_active, 'Y') where id = r.id;
    keep_an_admin(r.id);
  end;

  procedure drop_role(p_code varchar2) is
    r mm_role%rowtype;
    id_ number := role_id(p_code);
  begin
    select * into r from mm_role where id = id_;
    if r.system = 'Y' then
      fail(98, 'Ο ρόλος ' || r.code || ' του συστήματος δεν διαγράφεται');
    end if;
    delete from mm_role where id = r.id;                 -- (its grants, its users in it: with it)
    if r.all_rights = 'Y' then
      keep_an_admin(null);
    end if;
  end;

  procedure copy_role(p_from varchar2, p_to varchar2) is
    f number := role_id(p_from);
    t number := role_id(p_to);
    s varchar2(1);
  begin
    select system into s from mm_role where id = t;
    if s = 'Y' then
      fail(98, 'Ο ρόλος ' || upper(p_to) || ' του συστήματος δεν αλλάζει έτσι');
    end if;
    delete from mm_grant where role_id = t;
    insert into mm_grant (role_id, object_id, item_id, lvl)
    select t, object_id, item_id, lvl from mm_grant where role_id = f;
  end;

  procedure set_grant(p_role varchar2, p_object varchar2, p_item varchar2, p_level varchar2) is
    r number := role_id(p_role);
    o number;
    i number;
    k varchar2(1);
    a varchar2(1);
  begin
    select all_rights into a from mm_role where id = r;
    if a = 'Y' then
      fail(98, 'Ο ρόλος ' || upper(p_role) || ' έχει όλα τα δικαιώματα');
    end if;
    begin
      select id into o from mm_object where code = upper(p_object) and kind = 'S';
    exception
      when no_data_found then fail(98, 'Δεν υπάρχει οθόνη ' || p_object);
    end;
    if p_item is not null then
      begin
        select id, kind into i, k from mm_object_item where object_id = o and code = upper(p_item);
      exception
        when no_data_found then fail(98, 'Η οθόνη ' || upper(p_object) || ' δεν έχει ' || p_item);
      end;
    end if;
    if p_level is not null and upper(p_level) not in ('N', 'R', 'W')
       or k = 'A' and upper(p_level) = 'R' then
      fail(98, 'Δικαίωμα: N (κανένα), R (ανάγνωση), W (αλλαγή)' || case when k = 'A' then '; μια ενέργεια: N ή W' end);
    end if;
    if p_level is null then
      delete from mm_grant where role_id = r and object_id = o and nvl(item_id, 0) = nvl(i, 0);
    else
      merge into mm_grant g
      using (select r role_id, o object_id, i item_id from dual) x
      on (g.role_id = x.role_id and g.object_id = x.object_id and nvl(g.item_id, 0) = nvl(x.item_id, 0))
      when matched then update set g.lvl = upper(p_level)
      when not matched then insert (role_id, object_id, item_id, lvl) values (x.role_id, x.object_id, x.item_id, upper(p_level));
    end if;
  end;

  procedure add_user_role(p_username varchar2, p_role varchar2) is
    u number;
    r number := role_id(p_role);
  begin
    begin
      select id into u from mm_user where username = lower(p_username);
    exception
      when no_data_found then fail(80, 'Δεν υπάρχει χρήστης ' || p_username);
    end;
    insert into mm_user_role (user_id, role_id)
    select u, r from dual where not exists (select 1 from mm_user_role where user_id = u and role_id = r);
  end;

  procedure drop_user_role(p_username varchar2, p_role varchar2) is
    r number := role_id(p_role);
  begin
    delete from mm_user_role where role_id = r
      and user_id = (select id from mm_user where username = lower(p_username));
    keep_an_admin(r);
  end;

  procedure set_object(p_code varchar2, p_name varchar2, p_sort number, p_group varchar2, p_active varchar2 default 'Y') is
    o mm_object%rowtype;
    g number;
  begin
    begin
      select * into o from mm_object where code = upper(p_code);
    exception
      when no_data_found then fail(98, 'Δεν υπάρχει στο μενού ' || p_code);
    end;
    if trim(p_name) is null or length(trim(p_name)) > 100 then
      fail(98, 'Το όνομα στο μενού: 1 έως 100 χαρακτήρες');
    end if;
    if nvl(p_active, 'Y') not in ('Y', 'N') then
      fail(98, 'Ενεργό: Y ή N');
    end if;
    select max(parent_id) into g from mm_object where code = 'ROLES';
    if p_active = 'N' and (o.code = 'ROLES' or o.id = g) then
      fail(98, 'Οι ρόλοι και τα δικαιώματα μένουν στο μενού');
    end if;
    g := null;
    if o.kind = 'S' then
      begin
        select id into g from mm_object where code = upper(p_group) and kind = 'G';
      exception
        when no_data_found then fail(98, 'Δεν υπάρχει ομάδα του μενού ' || p_group);
      end;
    end if;
    update mm_object set name = trim(p_name), sort_no = nvl(p_sort, sort_no), parent_id = g, active = nvl(p_active, 'Y')
    where id = o.id;
  end;
end mm_rights;
/

-- the roles of the system, the menu, the fields and the actions of each screen, what the roles of the
-- system may do (as the shop worked before the rights: a cashier the till, the orders, the items without
-- their costs, the labels, the counts without starting or closing one; a manager everything but the
-- users and the roles; an administrator everything). What is there already: as it is.
declare
  procedure role_(p_code varchar2, p_name varchar2, p_all varchar2) is
  begin
    insert into mm_role (code, name, all_rights, system)
    select p_code, p_name, p_all, 'Y' from dual where not exists (select 1 from mm_role where code = p_code);
  end;

  procedure grp(p_code varchar2, p_name varchar2, p_sort number) is
  begin
    insert into mm_object (code, kind, name, sort_no)
    select p_code, 'G', p_name, p_sort from dual where not exists (select 1 from mm_object where code = p_code);
  end;

  -- a screen; its fields (F) and actions (A): 'F:CODE:Name;A:CODE:Name;...'
  procedure scr(p_code varchar2, p_group varchar2, p_name varchar2, p_route varchar2, p_form varchar2,
                p_sort number, p_items varchar2 default null) is
    o number;
    s varchar2(200);
  begin
    insert into mm_object (code, kind, parent_id, name, route, form, sort_no)
    select p_code, 'S', (select id from mm_object where code = p_group), p_name, p_route, p_form, p_sort
    from dual where not exists (select 1 from mm_object where code = p_code);
    select id into o from mm_object where code = p_code;
    for k in 1 .. nvl(regexp_count(p_items, '[^;]+'), 0) loop
      s := regexp_substr(p_items, '[^;]+', 1, k);
      insert into mm_object_item (object_id, kind, code, name, sort_no)
      select o, regexp_substr(s, '[^:]+', 1, 1), regexp_substr(s, '[^:]+', 1, 2), regexp_substr(s, '[^:]+', 1, 3), k * 10
      from dual where not exists (select 1 from mm_object_item where object_id = o and code = regexp_substr(s, '[^:]+', 1, 2));
    end loop;
  end;

  -- a grant of a role of the system, when it has none there yet: 'SCREEN:LEVEL' or 'SCREEN.ITEM:LEVEL'
  procedure grants(p_role varchar2, p_list varchar2) is
    s varchar2(100);
    r number;
    o number;
    i number;
  begin
    select id into r from mm_role where code = p_role;
    for k in 1 .. regexp_count(p_list, '[^;]+') loop
      s := regexp_substr(p_list, '[^;]+', 1, k);
      select id into o from mm_object where code = regexp_substr(s, '[^.:]+', 1, 1);
      i := null;
      if instr(s, '.') > 0 then
        select id into i from mm_object_item where object_id = o and code = regexp_substr(s, '[^.:]+', 1, 2);
      end if;
      insert into mm_grant (role_id, object_id, item_id, lvl)
      select r, o, i, regexp_substr(s, '[^:]+', 1, 2) from dual
      where not exists (select 1 from mm_grant where role_id = r and object_id = o and nvl(item_id, 0) = nvl(i, 0));
    end loop;
  end;
begin
  role_('CASHIER', 'Ταμίας', 'N');
  role_('MANAGER', 'Προϊστάμενος', 'N');
  role_('ADMIN', 'Διαχειριστής', 'Y');

  grp('SALES', 'Πωλήσεις', 10);
  grp('STORE', 'Αποθήκη', 20);
  grp('OFFICE', 'Γραφείο', 30);
  grp('REPORTS', 'Αναφορές', 40);
  grp('ADMIN', 'Διαχείριση', 50);

  scr('POS', 'SALES', 'Ταμείο', '#/pos', 'MM_POS', 10,
      'A:OPEN_Z:Άνοιγμα Ζ;A:CLOSE_Z:Κλείσιμο Ζ;A:CASH:Μετρητά μέσα και έξω;A:VOID:Ακύρωση απόδειξης;A:PRIZE:Κέρδος σκρατς;'
      || 'A:WAREHOUSE:Αποθήκη του ταμείου;A:SETTINGS:Κεφαλίδα και υποσέλιδο αποδείξεων');
  scr('ORDERS', 'SALES', 'Παραγγελίες', '#/orders', null, 20, 'A:CONFIRM:Επιβεβαίωση;A:CANCEL:Ακύρωση;A:NOTE:Δελτίο αποστολής');
  scr('RESERVATIONS', 'SALES', 'Κρατήσεις', null, 'MM_RESERVATIONS', 30, 'A:CREATE:Νέα;A:DELIVER:Παράδοση;A:CANCEL:Ακύρωση');
  scr('PROMOS', 'SALES', 'Προσφορές', null, 'MM_PROMOS', 40, 'A:CREATE:Νέα;A:ACTIVE:Ενεργή ή όχι');

  scr('ITEMS', 'STORE', 'Είδη', '#/items', 'MM_ITEMS', 10,
      'F:PRICE:Τιμή λιανικής;F:WHOLESALE_PRICE:Χονδρική;F:COST:Κόστος;F:FIFO:Κόστος FIFO και στρώσεις;F:STOCK:Απόθεμα;'
      || 'F:MIN_STOCK:Ελάχιστο;A:CREATE:Νέο;A:DELETE:Διαγραφή');
  scr('VARIANTS', 'STORE', 'Ρούχα και παπούτσια', null, 'MM_VARIANTS', 20, 'A:CREATE:Νέο');
  scr('KITS', 'STORE', 'Καλάθια και σετ', null, 'MM_KITS', 30, 'A:ASSEMBLE:Συναρμολόγηση');
  scr('CARDS', 'STORE', 'Κάρτες κινητής', null, 'MM_CARDS', 40, 'F:PIN:PIN;A:LOAD:Φόρτωση');
  scr('LABELS', 'STORE', 'Ετικέτες', '#/labels', null, 50);
  scr('COUNTS', 'STORE', 'Απογραφή', '#/counts', null, 60, 'A:CREATE:Νέα;A:POST:Καταχώριση;A:CANCEL:Ακύρωση');
  scr('SCRATCH', 'STORE', 'Σκρατς', '#/scratch', null, 70, 'A:LOAD:Φόρτωση πακέτου;A:RETURN:Επιστροφή πακέτου;A:GAME:Εκδόσεις');
  scr('EXPIRY', 'STORE', 'Λήξεις', '#/expiry', null, 80, 'A:WITHDRAW:Απόσυρση');
  scr('WAREHOUSES', 'STORE', 'Αποθήκες', '#/warehouses', null, 90,
      'F:VALUE:Αξία;A:CREATE:Νέα;A:MIN:Ελάχιστο υποκαταστήματος;A:TRANSFER:Δελτίο από το κεντρικό');

  scr('DOCS', 'OFFICE', 'Τιμολόγια και δελτία', '#/docs', 'MM_INVOICES', 10,
      'F:COST:Κόστος;A:CREATE:Νέο;A:POST:Καταχώριση;A:CANCEL:Ακύρωση;A:MYDATA:myDATA');
  scr('PAYMENTS', 'OFFICE', 'Εισπράξεις και πληρωμές', '#/payments', 'MM_PAYMENTS', 20, 'A:CREATE:Νέα;A:CANCEL:Ακύρωση');
  scr('CUSTOMERS', 'OFFICE', 'Πελάτες', '#/partners/customers', 'MM_CUSTOMERS', 30,
      'F:AFM:ΑΦΜ;F:CONTACT:Τηλέφωνο, email, διεύθυνση;F:BALANCE:Υπόλοιπο;F:POINTS:Πόντοι;A:CREATE:Νέος;A:CARD:Κάρτα πόντων');
  scr('SUPPLIERS', 'OFFICE', 'Προμηθευτές', '#/partners/suppliers', 'MM_SUPPLIERS', 40,
      'F:AFM:ΑΦΜ;F:CONTACT:Τηλέφωνο, email, διεύθυνση;F:BALANCE:Υπόλοιπο;A:CREATE:Νέος');
  scr('LEDGERS', 'OFFICE', 'Καρτέλες', null, 'MM_LEDGER', 50);

  scr('DAY', 'REPORTS', 'Σύνοψη ημέρας', '#/day', null, 10);
  scr('CHART', 'REPORTS', 'Γράφημα πωλήσεων', '#/chart', null, 20);
  scr('REP_SALES', 'REPORTS', 'Πωλήσεις', '#/reports/sales', null, 30);
  scr('REP_VAT', 'REPORTS', 'ΦΠΑ', '#/reports/vat', null, 40);
  scr('REP_SALES_BY', 'REPORTS', 'Πωλήσεις ανά κατάστημα και ταμία', '#/reports/sales-by', null, 35);
  scr('REP_MIN_STOCK', 'REPORTS', 'Ελάχιστο απόθεμα', '#/reports/min-stock', null, 50, 'A:ORDER:Παραγγελίες σε προμηθευτές');
  scr('TRIAL_ITEMS', 'REPORTS', 'Ισοζύγιο ειδών', '#/reports/trial-items', null, 60);
  scr('TRIAL_CUSTOMERS', 'REPORTS', 'Ισοζύγιο πελατών', '#/reports/trial-customers', null, 70);
  scr('TRIAL_SUPPLIERS', 'REPORTS', 'Ισοζύγιο προμηθευτών', '#/reports/trial-suppliers', null, 80);
  scr('PROFIT', 'REPORTS', 'Μικτό κέρδος', '#/reports/profit', null, 90);
  scr('STOCK_VALUE', 'REPORTS', 'Αξία αποθήκης', '#/reports/stock-value', null, 100, 'A:COST_METHOD:Τρόπος κοστολόγησης');
  scr('REPORTS_PDF', 'REPORTS', 'Αναφορές PDF', null, 'MM_REPORTS', 110);

  scr('USERS', 'ADMIN', 'Χρήστες', '#/users', 'MM_USERS', 10, 'A:CREATE:Νέος;A:PASSWORD:Κωδικός;A:PLACE:Κατάστημα και ταμείο');
  scr('ROLES', 'ADMIN', 'Ρόλοι και δικαιώματα', '#/roles', null, 20);
  scr('AUDIT', 'ADMIN', 'Ιστορικό ενεργειών', '#/audit', null, 30);

  grants('CASHIER', 'POS:W;POS.WAREHOUSE:N;POS.SETTINGS:N;ORDERS:W;ORDERS.NOTE:N;RESERVATIONS:W;ITEMS:R;ITEMS.COST:N;ITEMS.FIFO:N;'
                    || 'LABELS:W;COUNTS:W;COUNTS.CREATE:N;COUNTS.POST:N;COUNTS.CANCEL:N');
  grants('MANAGER', 'REP_SALES_BY:R;POS:W;ORDERS:W;RESERVATIONS:W;PROMOS:W;ITEMS:W;VARIANTS:W;KITS:W;CARDS:W;LABELS:W;COUNTS:W;'
                    || 'SCRATCH:W;EXPIRY:W;WAREHOUSES:W;DOCS:W;PAYMENTS:W;CUSTOMERS:W;SUPPLIERS:W;LEDGERS:W;'
                    || 'DAY:R;CHART:R;REP_SALES:R;REP_VAT:R;REP_MIN_STOCK:W;TRIAL_ITEMS:R;TRIAL_CUSTOMERS:R;'
                    || 'TRIAL_SUPPLIERS:R;PROFIT:R;STOCK_VALUE:W;REPORTS_PDF:R');

  -- the users in the role of their level (MM_USER.ROLE), once: those that have no role yet
  insert into mm_user_role (user_id, role_id)
  select u.id, r.id from mm_user u join mm_role r on r.code = u.role
  where not exists (select 1 from mm_user_role x where x.user_id = u.id);
  commit;
end;
/
