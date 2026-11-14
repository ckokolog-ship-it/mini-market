-- SET_REPORTS_URL.sql -- where the forms open the reports: the rwservlet of the Reports Server, with
-- the key of cgicmd.dat (mm: userid=/@MM_DB, no password in the address), and the format.
--   sqlplus mm/<password>@FREEPDB1 @SET_REPORTS_URL.sql http://192.168.178.165:9012 HTML
--   sqlplus mm/<password>@FREEPDB1 @SET_REPORTS_URL.sql http://forms1.home.lan:9012 PDF
-- The format: PDF or HTML (on Windows the Greek of the PDF is still open: HTML).
-- The key: reports_server.cmd -Alias MM_DB -Key mm of PROPOApplication (retro\oracle\windows).
set verify off
merge into mm_setting s
using (select 'REPORTS_URL' name, '&1/reports/rwservlet?mm' value from dual
       union all select 'REPORTS_FORMAT', upper('&2') from dual) v
on (s.name = v.name)
when matched then update set s.value = v.value
when not matched then insert (name, value) values (v.name, v.value);
commit;
select name, value from mm_setting order by name;
exit
