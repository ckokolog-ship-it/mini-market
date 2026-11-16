-- GRANT_BACKUP.sql -- once, as SYS, in the pluggable database: MM may write its backups with Data Pump
-- (backup.ps1) into DATA_PUMP_DIR, the folder of the database for them; backup.ps1 moves them from
-- there to C:\mm_backup.
--
--   Windows: C:\app\chris\product\26ai\dbhomeFree\bin\sqlplus.exe sys@localhost:1522/FREEPDB1 as sysdba @GRANT_BACKUP.sql
--   Linux:   sqlplus sys@localhost:1521/FREEPDB1 as sysdba @GRANT_BACKUP.sql
-- (it asks for the password of SYS).
grant read, write on directory data_pump_dir to mm;
select directory_path from dba_directories where directory_name = 'DATA_PUMP_DIR';
prompt == MM may use DATA_PUMP_DIR: now backup.ps1 -Install (docs\ODIGIES_VASI.md, the backup)
exit
