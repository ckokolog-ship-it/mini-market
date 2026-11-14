-- UNINSTALL.sql -- removes all the tables of the mini market and their rows, as their owner:
--
--   sqlplus mm/<password>@FREEPDB1 @UNINSTALL.sql
set feedback off
-- a form or another session that uses a table holds it a moment: wait for it up to 60 seconds
-- (else ORA-00054 at once, e.g. at "create index if not exists" of a table a form has open)
alter session set ddl_lock_timeout = 60;
prompt == drop the package and the tables of the mini market
drop package if exists mm_core;
drop package if exists mm_text;
drop package if exists mm_pin;
drop package if exists mm_ledger;
drop package if exists mm_report;
drop view if exists mm_sales_day;
drop view if exists mm_vat_day;
drop view if exists mm_min_stock;
drop view if exists mm_check;
drop view if exists mm_serial_check;
drop view if exists mm_doc_serials;
drop view if exists mm_item_avail;
drop view if exists mm_kit_avail;
drop view if exists mm_variant_grid;
drop view if exists mm_reservation_need;
drop table if exists mm_promo_item cascade constraints purge;
drop table if exists mm_promo cascade constraints purge;
drop table if exists mm_kit_component cascade constraints purge;
drop table if exists mm_ledger_row purge;
drop table if exists mm_setting purge;
drop table if exists mm_payment cascade constraints purge;
drop table if exists mm_reservation_line cascade constraints purge;
drop table if exists mm_reservation cascade constraints purge;
drop table if exists mm_pin_log cascade constraints purge;
drop table if exists mm_pin_user cascade constraints purge;
drop table if exists mm_secret cascade constraints purge;
drop table if exists mm_serial cascade constraints purge;
drop table if exists mm_count_line cascade constraints purge;
drop table if exists mm_count cascade constraints purge;
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
drop table if exists mm_color cascade constraints purge;
drop table if exists mm_size cascade constraints purge;
drop table if exists mm_vat cascade constraints purge;
prompt == MM UNINSTALL OK
exit
