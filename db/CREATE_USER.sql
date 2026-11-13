-- CREATE_USER.sql -- the owner of the mini market, once, as SYSTEM, in the pluggable database:
--
--   sqlplus system@FREEPDB1 @CREATE_USER.sql
--
-- It asks for the password of the new user (it is not written in any file of the repo).
-- Then: sqlplus mm@FREEPDB1 @INSTALL.sql demo
set verify off
accept mm_pw char prompt 'Password of the user MM: ' hide
create user mm identified by "&mm_pw"
  default tablespace users quota unlimited on users;
grant create session, create table, create view, create sequence, create procedure,
      create trigger, create type, create synonym to mm;
undefine mm_pw
prompt == user MM: OK
exit
