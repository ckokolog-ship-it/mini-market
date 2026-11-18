-- MM_AUDIT.sql -- the history of what was done (MM_AUDIT_LOG), by triggers on the tables: whatever did it (the pages,
-- the forms, SQL) is written. Run by INSTALL.sql, after the packages.
--
--   who:       CLIENT_IDENTIFIER of the session (the user of the pages, mm-api; of the forms, MM_UI), else the
--              user of the database (e.g. MM, from SQL*Plus)
--   from where: MODULE of the session (mm-api, the forms, SQL*Plus ...)
--   what:      a document posted, cancelled, a draft out; a Z opened, closed; money in and out of a
--              register; the stock corrected by hand; a count posted, cancelled; a payment, cancelled; an
--              item new, its name, prices, minimum, active; a customer, a supplier new or changed; a user new,
--              its role, active, place, password (never the password); the roles, their users, their rights;
--              the menu; the settings (no value of a key, a password, a token); a warehouse
--
-- In the transaction of what it writes: undone with it. MM_AUDIT_ALL: these and the logins (MM_AUTH_LOG).
-- Kept: mm_audit.purge(days) takes out what is older (e.g. 730: two years).

create or replace package mm_audit as
  procedure log(p_action varchar2, p_ref_type varchar2 default null, p_ref_id number default null,
                p_ref_text varchar2 default null, p_detail varchar2 default null);
  -- a change of a value for the detail: 'name: old → new' (nothing when the same)
  function diff(p_name varchar2, p_old varchar2, p_new varchar2) return varchar2;
  procedure purge(p_days number);
end mm_audit;
/

create or replace package body mm_audit as
  procedure log(p_action varchar2, p_ref_type varchar2 default null, p_ref_id number default null,
                p_ref_text varchar2 default null, p_detail varchar2 default null) is
  begin
    insert into mm_audit_log (username, source, action, ref_type, ref_id, ref_text, detail)
    values (substr(nvl(sys_context('USERENV', 'CLIENT_IDENTIFIER'), sys_context('USERENV', 'SESSION_USER')), 1, 64),
            substr(sys_context('USERENV', 'MODULE'), 1, 64), p_action, p_ref_type, p_ref_id,
            substr(p_ref_text, 1, 100), substr(p_detail, 1, 1000));
  end;

  function diff(p_name varchar2, p_old varchar2, p_new varchar2) return varchar2 is
  begin
    if p_old = p_new or p_old is null and p_new is null then
      return null;
    end if;
    return p_name || ': ' || nvl(p_old, '-') || ' → ' || nvl(p_new, '-') || '; ';
  end;

  procedure purge(p_days number) is
  begin
    if p_days is null or p_days < 30 then
      raise_application_error(-20199, 'MM-199: Το ιστορικό κρατιέται τουλάχιστον 30 ημέρες');
    end if;
    delete from mm_audit_log where at < systimestamp - numtodsinterval(p_days, 'DAY');
  end;
end mm_audit;
/

-- what was done and the logins, together (the page «Ιστορικό ενεργειών»)
create or replace view mm_audit_all as
select id, at, username, source, action, ref_type, ref_id, ref_text, detail from mm_audit_log
union all
select -l.id, cast(l.at as timestamp), l.username, l.client, 'AUTH_' || l.event, 'USER', null, l.username, null
from mm_auth_log l;

create or replace trigger mm_doc_audit
after update of status or delete on mm_doc
for each row
declare
  r varchar2(100) := :old.doc_type || ' ' || :old.doc_no;
begin
  if deleting then
    if :old.status = 'D' then
      mm_audit.log('DOC_DELETE', 'DOC', :old.id, :old.doc_type || ' (πρόχειρο)', 'σύνολο ' || :old.total);
    end if;
  elsif :old.status = 'D' and :new.status = 'P' then
    mm_audit.log('DOC_POST', 'DOC', :new.id, :new.doc_type || ' ' || :new.doc_no, 'σύνολο ' || :new.total);
  elsif :old.status = 'P' and :new.status = 'C' then
    mm_audit.log('DOC_CANCEL', 'DOC', :new.id, r, 'σύνολο ' || :new.total);
  end if;
end;
/

create or replace trigger mm_z_audit
after insert or update of status on mm_z
for each row
declare
  reg varchar2(30);
begin
  select max(code) into reg from mm_register where id = :new.register_id;
  if inserting then
    mm_audit.log('Z_OPEN', 'Z', :new.id, reg || ' Ζ ' || :new.z_no);
  elsif :old.status = 'O' and :new.status = 'C' then
    mm_audit.log('Z_CLOSE', 'Z', :new.id, reg || ' Ζ ' || :new.z_no,
                 'σύνολο ' || :new.total || ', μετρητά ' || :new.cash || ', κάρτα ' || :new.card);
  end if;
end;
/

create or replace trigger mm_cash_move_audit
after insert on mm_cash_move
for each row
when (new.kind in ('IN', 'OUT'))
declare
  reg varchar2(30);
begin
  select max(code) into reg from mm_register where id = :new.register_id;
  mm_audit.log(case :new.kind when 'IN' then 'CASH_IN' else 'CASH_OUT' end, 'Z', :new.z_id, reg,
               :new.amount || ': ' || :new.note);
end;
/

create or replace trigger mm_stock_move_audit
after insert on mm_stock_move
for each row
when (new.kind = 'ADJ' and new.count_id is null)
declare
  c varchar2(30);
begin
  select max(code) into c from mm_item where id = :new.item_id;
  mm_audit.log('STOCK_ADJ', 'ITEM', :new.item_id, c, :new.qty || ': ' || :new.note);
end;
/

create or replace trigger mm_count_audit
after update of status on mm_count
for each row
when (old.status = 'O' and new.status in ('P', 'C'))
begin
  mm_audit.log(case :new.status when 'P' then 'COUNT_POST' else 'COUNT_CANCEL' end, 'COUNT', :new.id, :new.name);
end;
/

create or replace trigger mm_payment_audit
after insert or update of status on mm_payment
for each row
declare
  n varchar2(100);
begin
  if :new.kind = 'R' then
    select max(name) into n from mm_customer where id = :new.customer_id;
  else
    select max(name) into n from mm_supplier where id = :new.supplier_id;
  end if;
  if inserting then
    mm_audit.log(case :new.kind when 'R' then 'PAYMENT_IN' else 'PAYMENT_OUT' end, 'PAYMENT', :new.id, n,
                 :new.amount || ' ' || :new.method);
  elsif :old.status = 'P' and :new.status = 'C' then
    mm_audit.log('PAYMENT_CANCEL', 'PAYMENT', :new.id, n, to_char(:new.amount));
  end if;
end;
/

create or replace trigger mm_item_audit
after insert or update of name, price, wholesale_price, min_stock, active on mm_item
for each row
declare
  d varchar2(1000);
begin
  if inserting then
    mm_audit.log('ITEM_NEW', 'ITEM', :new.id, :new.code, :new.name || ', τιμή ' || :new.price);
  else
    d := mm_audit.diff('όνομα', :old.name, :new.name) || mm_audit.diff('τιμή', :old.price, :new.price)
         || mm_audit.diff('χονδρική', :old.wholesale_price, :new.wholesale_price)
         || mm_audit.diff('ελάχιστο', :old.min_stock, :new.min_stock) || mm_audit.diff('ενεργό', :old.active, :new.active);
    if d is not null then
      mm_audit.log('ITEM_CHANGE', 'ITEM', :new.id, :new.code, rtrim(d, '; '));
    end if;
  end if;
end;
/

create or replace trigger mm_customer_audit
after insert or update of name, afm, active on mm_customer
for each row
declare
  d varchar2(1000);
begin
  if inserting then
    mm_audit.log('CUSTOMER_NEW', 'CUSTOMER', :new.id, :new.name);
  else
    d := mm_audit.diff('επωνυμία', :old.name, :new.name) || mm_audit.diff('ΑΦΜ', :old.afm, :new.afm)
         || mm_audit.diff('ενεργός', :old.active, :new.active);
    if d is not null then
      mm_audit.log('CUSTOMER_CHANGE', 'CUSTOMER', :new.id, :new.name, rtrim(d, '; '));
    end if;
  end if;
end;
/

create or replace trigger mm_supplier_audit
after insert or update of name, afm, active on mm_supplier
for each row
declare
  d varchar2(1000);
begin
  if inserting then
    mm_audit.log('SUPPLIER_NEW', 'SUPPLIER', :new.id, :new.name);
  else
    d := mm_audit.diff('επωνυμία', :old.name, :new.name) || mm_audit.diff('ΑΦΜ', :old.afm, :new.afm)
         || mm_audit.diff('ενεργός', :old.active, :new.active);
    if d is not null then
      mm_audit.log('SUPPLIER_CHANGE', 'SUPPLIER', :new.id, :new.name, rtrim(d, '; '));
    end if;
  end if;
end;
/

create or replace trigger mm_user_audit
after insert or update of role, active, warehouse_id, register_id, pw_hash on mm_user
for each row
declare
  d varchar2(1000);
begin
  if inserting then
    mm_audit.log('USER_NEW', 'USER', :new.id, :new.username, 'ρόλος ' || :new.role);
  else
    d := mm_audit.diff('επίπεδο', :old.role, :new.role) || mm_audit.diff('ενεργός', :old.active, :new.active)
         || mm_audit.diff('κατάστημα', :old.warehouse_id, :new.warehouse_id)
         || mm_audit.diff('ταμείο', :old.register_id, :new.register_id)
         || case when :old.pw_hash <> :new.pw_hash then 'νέος κωδικός; ' end;
    if d is not null then
      mm_audit.log('USER_CHANGE', 'USER', :new.id, :new.username, rtrim(d, '; '));
    end if;
  end if;
end;
/

-- (a role or a user out: its rows here go with it, the names may be gone already: the ids then)
create or replace trigger mm_user_role_audit
after insert or delete on mm_user_role
for each row
declare
  u varchar2(100);
  r varchar2(100);
begin
  begin
    select max(username) into u from mm_user where id = nvl(:new.user_id, :old.user_id);
    select max(code) into r from mm_role where id = nvl(:new.role_id, :old.role_id);
  exception
    when others then null;
  end;
  mm_audit.log(case when inserting then 'USER_ROLE_ADD' else 'USER_ROLE_DROP' end, 'USER',
               nvl(:new.user_id, :old.user_id), nvl(u, '#' || nvl(:new.user_id, :old.user_id)),
               'ρόλος ' || nvl(r, '#' || nvl(:new.role_id, :old.role_id)));
end;
/

create or replace trigger mm_role_audit
after insert or update or delete on mm_role
for each row
begin
  if inserting then
    mm_audit.log('ROLE_NEW', 'ROLE', :new.id, :new.code, :new.name);
  elsif deleting then
    mm_audit.log('ROLE_DROP', 'ROLE', :old.id, :old.code, :old.name);
  else
    mm_audit.log('ROLE_CHANGE', 'ROLE', :new.id, :new.code,
                 rtrim(mm_audit.diff('όνομα', :old.name, :new.name) || mm_audit.diff('ενεργός', :old.active, :new.active), '; '));
  end if;
end;
/

create or replace trigger mm_grant_audit
after insert or update or delete on mm_grant
for each row
declare
  r varchar2(100);
  o varchar2(100);
  i varchar2(100);
begin
  begin
    select max(code) into r from mm_role where id = nvl(:new.role_id, :old.role_id);
    select max(code) into o from mm_object where id = nvl(:new.object_id, :old.object_id);
    select max(code) into i from mm_object_item where id = nvl(:new.item_id, :old.item_id);
  exception
    when others then null;
  end;
  mm_audit.log('GRANT', 'ROLE', nvl(:new.role_id, :old.role_id), nvl(r, '#' || nvl(:new.role_id, :old.role_id)),
               o || case when i is not null then '.' || i end || ': ' || nvl(:old.lvl, '-') || ' → ' || nvl(:new.lvl, '-'));
end;
/

create or replace trigger mm_object_audit
after update of name, sort_no, parent_id, active on mm_object
for each row
declare
  d varchar2(1000);
begin
  d := mm_audit.diff('όνομα', :old.name, :new.name) || mm_audit.diff('σειρά', :old.sort_no, :new.sort_no)
       || mm_audit.diff('ομάδα', :old.parent_id, :new.parent_id) || mm_audit.diff('ενεργό', :old.active, :new.active);
  if d is not null then
    mm_audit.log('MENU_CHANGE', 'MENU', :new.id, :new.code, rtrim(d, '; '));
  end if;
end;
/

create or replace trigger mm_setting_audit
after insert or update on mm_setting
for each row
when (new.name not like 'BACKUP\_%' escape '\')
declare
  secret boolean := regexp_like(:new.name, 'KEY|PASS|SECRET|TOKEN|PW', 'i');
begin
  if inserting or nvl(:old.value, '~') <> nvl(:new.value, '~') then
    mm_audit.log('SETTING', 'SETTING', null, :new.name,
                 case when secret then '(αλλαγή, χωρίς την τιμή)' else nvl(:old.value, '-') || ' → ' || nvl(:new.value, '-') end);
  end if;
end;
/

create or replace trigger mm_warehouse_audit
after insert or update of name, active on mm_warehouse
for each row
begin
  if inserting then
    mm_audit.log('WAREHOUSE_NEW', 'WAREHOUSE', :new.id, :new.code, :new.name);
  else
    mm_audit.log('WAREHOUSE_CHANGE', 'WAREHOUSE', :new.id, :new.code,
                 rtrim(mm_audit.diff('όνομα', :old.name, :new.name) || mm_audit.diff('ενεργή', :old.active, :new.active), '; '));
  end if;
end;
/
