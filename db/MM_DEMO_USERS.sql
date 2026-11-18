-- MM_DEMO_USERS.sql -- users of the shop in its stores, to see where each works: the central store and the
-- two branches of MM_DEMO_WAREHOUSES.sql (run it first). As the owner mm, from this folder
-- (NLS_LANG=GREEK_GREECE.AL32UTF8, as for INSTALL.sql):
--
--   sqlplus mm/<password>@FREEPDB1 @MM_DEMO_USERS.sql
--
-- It asks once for the password of all of them (it does not show and is not written anywhere: only its
-- PBKDF2 goes to MM_USER; at least 10 characters, with letters and digits); each is changed later in
-- the page Χρήστες. A user that exists already: left as it is. One more register in Ρίο (R3), so that
-- a store has two.
--
--   maria.k     Μαρία Κ.       CASHIER   K   T1     only the register T1
--   petros.k    Πέτρος Κ.      MANAGER   K   -      the registers of the central store
--   giorgos.r   Γιώργος Ρ.     CASHIER   Y1  R1     only R1
--   anna.r      Άννα Ρ.        CASHIER   Y1  R3     only R3
--   dimitra.r   Δήμητρα Ρ.     CASHIER   Y1  -      R1 or R3 (where she is needed)
--   nikos.r     Νίκος Ρ.       MANAGER   Y1  R1     the registers of Ρίο; the till opens on R1
--   eleni.a     Ελένη Α.       CASHIER   Y2  R2     only R2
--   katerina.a  Κατερίνα Α.    MANAGER   Y2  -      the registers of Αίγιο
set verify off
set feedback off
set serveroutput on
whenever sqlerror exit failure rollback
accept u_pw1 char prompt 'Password of the demo users: ' hide
accept u_pw2 char prompt 'Password again: ' hide
declare
  pw varchar2(200) := '&u_pw1';
  made pls_integer := 0;
  y1 number;

  function wh(p_code varchar2) return number is
    v number;
  begin
    select id into v from mm_warehouse where code = p_code;
    return v;
  exception
    when no_data_found then
      raise_application_error(-20001, 'no warehouse ' || p_code || ': run MM_DEMO_WAREHOUSES.sql first');
  end;

  function reg(p_code varchar2) return number is
    v number;
  begin
    if p_code is null then
      return null;
    end if;
    select id into v from mm_register where code = p_code;
    return v;
  end;

  procedure usr(p_name varchar2, p_full varchar2, p_role varchar2, p_wh varchar2, p_reg varchar2) is
    n number;
  begin
    select count(*) into n from mm_user where username = p_name;
    if n > 0 then
      return;
    end if;
    n := mm_auth.create_user(p_name, p_full, p_role, pw);
    mm_auth.set_place(p_name, wh(p_wh), reg(p_reg));
    made := made + 1;
  end;
begin
  if pw is null or pw <> '&u_pw2' then
    raise_application_error(-20001, 'the two passwords differ');
  end if;
  y1 := wh('Y1');
  insert into mm_register (code, name, warehouse_id)
  select 'R3', 'Ταμείο Ρίου 2', y1 from dual where not exists (select 1 from mm_register where code = 'R3');
  usr('maria.k', 'Μαρία Κ.', 'CASHIER', 'K', 'T1');
  usr('petros.k', 'Πέτρος Κ.', 'MANAGER', 'K', null);
  usr('giorgos.r', 'Γιώργος Ρ.', 'CASHIER', 'Y1', 'R1');
  usr('anna.r', 'Άννα Ρ.', 'CASHIER', 'Y1', 'R3');
  usr('dimitra.r', 'Δήμητρα Ρ.', 'CASHIER', 'Y1', null);
  usr('nikos.r', 'Νίκος Ρ.', 'MANAGER', 'Y1', 'R1');
  usr('eleni.a', 'Ελένη Α.', 'CASHIER', 'Y2', 'R2');
  usr('katerina.a', 'Κατερίνα Α.', 'MANAGER', 'Y2', null);
  commit;
  dbms_output.put_line('== MM_DEMO_USERS: ' || made || ' new users');
  dbms_output.put_line(rpad('user', 12) || rpad('role', 9) || rpad('store', 6) || rpad('register', 10) || 'may use');
  for u in (select u.username, u.role, w.code wh, g.code reg,
                   (select listagg(r.code, ' ') within group (order by r.code) from mm_register r
                    where r.active = 'Y' and mm_auth.may_use(u.id, r.id) = 'Y') regs
            from mm_user u
            left join mm_warehouse w on w.id = u.warehouse_id left join mm_register g on g.id = u.register_id
            order by w.code nulls first, u.role desc, u.username) loop
    dbms_output.put_line(rpad(u.username, 12) || rpad(u.role, 9) || rpad(nvl(u.wh, '-'), 6) || rpad(nvl(u.reg, '-'), 10)
      || nvl(u.regs, '-'));
  end loop;
end;
/
undefine u_pw1
undefine u_pw2
exit
