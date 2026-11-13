-- GRANT_CRYPTO.sql -- once, as SYS, in the pluggable database: MM may encrypt the PINs of the cards
-- (MM_PIN.sql). SYSTEM cannot give it: DBMS_CRYPTO belongs to SYS.
--
--   Windows: C:\app\chris\product\26ai\dbhomeFree\bin\sqlplus.exe sys@localhost:1522/FREEPDB1 as sysdba @GRANT_CRYPTO.sql
--   Linux:   sqlplus sys@localhost:1521/FREEPDB1 as sysdba @GRANT_CRYPTO.sql
-- (it asks for the password of SYS). Then INSTALL.sql again.
grant execute on sys.dbms_crypto to mm;
prompt == MM may use DBMS_CRYPTO: now INSTALL.sql again
exit
