-- CREATE_MM_USER.sql -- a user of the shop (the first one: an ADMIN), as the owner mm, from this
-- folder (NLS_LANG=GREEK_GREECE.AL32UTF8, as for INSTALL.sql):
--
--   sqlplus mm/<password>@FREEPDB1 @CREATE_MM_USER.sql
--
-- It asks for the username, the name, the role (ADMIN, MANAGER, CASHIER) and the password (twice; it
-- does not show and is not written anywhere: only its PBKDF2 goes to MM_USER). The password: at least
-- 10 characters, with letters and digits.
set verify off
set feedback off
whenever sqlerror exit failure rollback
accept u_name   char prompt 'Username (latin, e.g. chris): '
accept u_full   char prompt 'Full name: '
accept u_role   char default 'ADMIN' prompt 'Role [ADMIN / MANAGER / CASHIER] (ADMIN): '
accept u_pw1    char prompt 'Password: ' hide
accept u_pw2    char prompt 'Password again: ' hide
declare
  v number;
begin
  if '&u_pw1' is null or '&u_pw1' <> '&u_pw2' then
    raise_application_error(-20001, 'the two passwords differ');
  end if;
  v := mm_auth.create_user('&u_name', '&u_full', upper('&u_role'), '&u_pw1');
  commit;
end;
/
undefine u_pw1
undefine u_pw2
prompt == the user &u_name (&u_role): ready
exit
