-- MM_CHECK.sql -- does the database add up? As the owner, at any time:
--
--   sqlplus mm/<password>@FREEPDB1 @MM_CHECK.sql
--
-- The view MM_CHECK (MM_TABLES.sql): the stock is the sum of its moves, every document the sum of
-- its lines, every closed Z the sum of its documents, of its VAT and of its money, every receipt
-- of a register paid there once, the cards in stock are their serials, the next numbers come
-- after the last ones. Each row is something that does not add up.
set feedback off
set pages 100 lines 200
column what format a8
column detail format a80
select what, id, detail from mm_check order by what, id fetch first 50 rows only;
set serveroutput on
declare
  n number;
begin
  select count(*) into n from mm_check;
  dbms_output.put_line(case when n = 0 then '== MM CHECK OK' else '== MM CHECK: ' || n || ' rows do not add up' end);
end;
/
exit
