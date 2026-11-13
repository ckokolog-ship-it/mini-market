-- MM_BASE.sql -- the rows the application needs: the VAT rates and the kinds of documents.
-- Run by INSTALL.sql; merge, so a second run changes nothing (and keeps NEXT_NO).

merge into mm_vat t
using (select * from (values
         ('A', 24, 'Κανονικός 24%'),
         ('B', 13, 'Μειωμένος 13%'),
         ('C',  6, 'Υπερμειωμένος 6%')) v (code, rate, descr)) s
on (t.code = s.code)
when matched then update set t.rate = s.rate, t.descr = s.descr
when not matched then insert (code, rate, descr) values (s.code, s.rate, s.descr);

-- side S sale, P purchase; stock_sign what a posted document does to the stock
merge into mm_doc_type t
using (select * from (values
         ('ALP', 'Απόδειξη λιανικής πώλησης', 'S', -1, 'Y', 'N'),
         ('TPY', 'Τιμολόγιο πώλησης',         'S', -1, 'N', 'Y'),
         ('PPY', 'Πιστωτικό πώλησης',         'S',  1, 'N', 'Y'),
         ('TAG', 'Τιμολόγιο αγοράς',          'P',  1, 'N', 'Y'),
         ('PAG', 'Πιστωτικό αγοράς',          'P', -1, 'N', 'Y')
       ) v (code, name, side, stock_sign, prices_incl_vat, partner_needed)) s
on (t.code = s.code)
when matched then update set t.name = s.name, t.side = s.side, t.stock_sign = s.stock_sign,
                             t.prices_incl_vat = s.prices_incl_vat, t.partner_needed = s.partner_needed
when not matched then insert (code, name, side, stock_sign, prices_incl_vat, partner_needed)
                      values (s.code, s.name, s.side, s.stock_sign, s.prices_incl_vat, s.partner_needed);

commit;
