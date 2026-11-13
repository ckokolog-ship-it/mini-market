-- UNINSTALL.sql -- removes all the tables of the mini market and their rows, as their owner:
--
--   sqlplus mm/<password>@FREEPDB1 @UNINSTALL.sql
set feedback off
prompt == drop the tables of the mini market
drop table if exists mm_cash_move cascade constraints purge;
drop table if exists mm_stock_move cascade constraints purge;
drop table if exists mm_doc_line cascade constraints purge;
drop table if exists mm_doc cascade constraints purge;
drop table if exists mm_z_vat cascade constraints purge;
drop table if exists mm_z cascade constraints purge;
drop table if exists mm_register cascade constraints purge;
drop table if exists mm_doc_type cascade constraints purge;
drop table if exists mm_supplier cascade constraints purge;
drop table if exists mm_customer cascade constraints purge;
drop table if exists mm_item cascade constraints purge;
drop table if exists mm_category cascade constraints purge;
drop table if exists mm_vat cascade constraints purge;
prompt == MM UNINSTALL OK
exit
