-- INSTALL.sql -- the database of the mini market, as its owner, from this folder:
--
--   sqlplus mm/<password>@FREEPDB1 @INSTALL.sql            (the tables, the VAT, the kinds of documents)
--   sqlplus mm/<password>@FREEPDB1 @INSTALL.sql demo       (and the demo rows)
--
-- The files are UTF-8 (Greek): the client must read them so, before sqlplus:
--   Windows:  set NLS_LANG=GREEK_GREECE.AL32UTF8
--   Linux:    export NLS_LANG=GREEK_GREECE.AL32UTF8
-- If not, the check below stops before anything is written.
-- A second run is safe: what exists stays (UNINSTALL.sql removes everything).
-- The user mm: CREATE_USER.sql, as SYSTEM.
set define on
set verify off
set feedback off
whenever sqlerror exit failure rollback
-- a form or another session that uses a table holds it a moment: wait for it up to 60 seconds
-- (else ORA-00054 at once, e.g. at "create index if not exists" of a table a form has open)
alter session set ddl_lock_timeout = 60;

-- &1 empty when not given (else sqlplus would ask for it)
set termout off
column 1 new_value 1
select '' "1" from dual where rownum = 0;
column demo_file new_value demo_file noprint
select case when lower('&1') = 'demo' then 'MM_DEMO.sql' else 'MM_NODEMO.sql' end demo_file from dual;
set termout on
set define off

prompt == the client reads UTF-8
declare
  w varchar2(20 char) := 'Ωμέγα';
begin
  if length(w) <> 5 then
    raise_application_error(-20001, 'the files are UTF-8: set NLS_LANG=GREEK_GREECE.AL32UTF8 and run again');
  end if;
end;
/
prompt == the tables
@MM_TABLES.sql
prompt == the VAT and the kinds of documents
@MM_BASE.sql
prompt == the packages MM_PIN (the PINs of the cards), MM_CORE, MM_LEDGER (the ledgers), and MM_TEXT (the Greek of the forms)
whenever sqlerror continue
@MM_PIN.sql
@MM_CORE.sql
@MM_LEDGER.sql
@MM_TEXT.sql
whenever sqlerror exit failure rollback
-- MM_PIN needs DBMS_CRYPTO (GRANT_CRYPTO.sql, as SYS): without it only the PINs do not work
set serveroutput on
declare
  n number;
begin
  select count(*) into n from user_objects where object_name = 'MM_PIN' and status <> 'VALID';
  if n > 0 then
    dbms_output.put_line('== [!] MM_PIN is not valid: no PINs for the cards. As SYS: @GRANT_CRYPTO.sql, then INSTALL.sql again');
  end if;
end;
/
set serveroutput off
declare
  n number;
begin
  select count(*) into n from user_errors where name in ('MM_CORE', 'MM_LEDGER', 'MM_TEXT');
  if n > 0 then
    raise_application_error(-20002, 'MM_CORE/MM_LEDGER/MM_TEXT: ' || n || ' errors (show errors package body mm_core)');
  end if;
end;
/
set define on
prompt == &demo_file
@&demo_file
set define off
-- a view made before a column was added to its table (an upgrade) waits invalid until it is used:
-- compiled now, so that nothing is left invalid
begin
  dbms_utility.compile_schema(schema => user, compile_all => false);
end;
/
prompt == what is in the database
set feedback on
select 'items' what, count(*) n from mm_item
union all select 'categories', count(*) from mm_category
union all select 'customers', count(*) from mm_customer
union all select 'suppliers', count(*) from mm_supplier
union all select 'kinds of documents', count(*) from mm_doc_type
union all select 'VAT rates', count(*) from mm_vat;
prompt == MM INSTALL OK
exit
