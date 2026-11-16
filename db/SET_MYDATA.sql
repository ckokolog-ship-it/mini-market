-- SET_MYDATA.sql -- the shop for myDATA of AADE (mm-api MyData.java): its ΑΦΜ, its branch (0: the seat),
-- whether a posted invoice is sent by itself, the cause of exemption of a line of 0% VAT (table 8.3 of
-- the documentation of AADE, docs/mydata; ask the accountant).
--   sqlplus mm@localhost:1522/FREEPDB1 @SET_MYDATA.sql 123456789 0 Y
--   (ΑΦΜ, branch, auto Y/N; the cause of 0%: a 4th argument, e.g. 1, else none)
-- The account at AADE (user, key) is not here: the file mydata.properties of the service (ODIGIES_REST.md).
set verify off
column 4 new_value 4
select '' "4" from dual where 1 = 0;
merge into mm_setting s
using (select 'MYDATA_AFM' name, '&1' value from dual
       union all select 'MYDATA_BRANCH', nvl('&2', '0') from dual
       union all select 'MYDATA_AUTO', upper(nvl('&3', 'N')) from dual
       union all select 'MYDATA_VAT_EXEMPTION', '&4' from dual) v
on (s.name = v.name)
when matched then update set s.value = v.value
when not matched then insert (name, value) values (v.name, v.value);
delete from mm_setting where name = 'MYDATA_VAT_EXEMPTION' and value is null;
commit;
select name, value from mm_setting where name like 'MYDATA%' order by name;
exit
