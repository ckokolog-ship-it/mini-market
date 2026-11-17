-- MM_BASE.sql -- the rows the application needs: the VAT rates and the kinds of documents.
-- Run by INSTALL.sql; merge, so a second run changes nothing (and keeps NEXT_NO).

merge into mm_vat t
using (select * from (values
         ('A', 24, 'Κανονικός 24%'),
         ('B', 13, 'Μειωμένος 13%'),
         ('C',  6, 'Υπερμειωμένος 6%'),
         ('D',  0, 'Εκτός ΦΠΑ 0%')) v (code, rate, descr)) s     -- D: gift cards, scratch tickets
on (t.code = s.code)
when matched then update set t.rate = s.rate, t.descr = s.descr
when not matched then insert (code, rate, descr) values (s.code, s.rate, s.descr);

-- side S sale, P purchase, T transfer between warehouses; stock_sign what a posted document does to the stock
-- the kinds of documents and what each does: STOCK_SIGN to the stock, PARTNER_SIGN to the balance of the
-- customer or the supplier, VAT_SIGN to the VAT; REF_TYPE: the delivery note an invoice is made from
-- (one or more of them: MM_CORE.INVOICE_FROM, ADD_NOTE). A delivery note moves the stock only, an
-- invoice the balance only (and the VAT); an invoice-delivery note both.
merge into mm_doc_type t
using (select * from (values
         --   code   name                                        side stock partner vat  incl partner ref
         ('ALP', 'Απόδειξη λιανικής πώλησης',               'S', -1,  0,  1, 'Y', 'N', null),
         ('DAP', 'Δελτίο αποστολής',                        'S', -1,  0,  0, 'N', 'Y', null),
         ('DEP', 'Δελτίο επιστροφής από πελάτη',            'S',  1,  0,  0, 'N', 'Y', null),
         ('TPY', 'Τιμολόγιο πώλησης',                       'S',  0,  1,  1, 'N', 'Y', 'DAP'),
         ('PPY', 'Πιστωτικό τιμολόγιο πώλησης',             'S',  0, -1, -1, 'N', 'Y', 'DEP'),
         ('TDA', 'Τιμολόγιο - δελτίο αποστολής',            'S', -1,  1,  1, 'N', 'Y', null),
         ('DPA', 'Δελτίο παραλαβής',                        'P',  1,  0,  0, 'N', 'Y', null),
         ('DEA', 'Δελτίο επιστροφής σε προμηθευτή',         'P', -1,  0,  0, 'N', 'Y', null),
         ('TAG', 'Τιμολόγιο αγοράς',                        'P',  0,  1,  1, 'N', 'Y', 'DPA'),
         ('PAG', 'Πιστωτικό τιμολόγιο αγοράς',              'P',  0, -1, -1, 'N', 'Y', 'DEA'),
         ('TAD', 'Τιμολόγιο - δελτίο παραλαβής',     'P',  1,  1,  1, 'N', 'Y', null),
         -- a transfer from a warehouse to another (side T): out of the one of the document, into its
         -- TO_WAREHOUSE_ID, at the costs of the layers it takes (FIFO); no partner, no VAT, no profit
         ('DEN', 'Δελτίο ενδοδιακίνησης',                   'T', -1,  0,  0, 'N', 'N', null)
       ) v (code, name, side, stock_sign, partner_sign, vat_sign, prices_incl_vat, partner_needed, ref_type)) s
on (t.code = s.code)
when matched then update set t.name = s.name, t.side = s.side, t.stock_sign = s.stock_sign,
                             t.partner_sign = s.partner_sign, t.vat_sign = s.vat_sign,
                             t.prices_incl_vat = s.prices_incl_vat, t.partner_needed = s.partner_needed,
                             t.ref_type = s.ref_type
when not matched then insert (code, name, side, stock_sign, partner_sign, vat_sign, prices_incl_vat,
                              partner_needed, ref_type)
                      values (s.code, s.name, s.side, s.stock_sign, s.partner_sign, s.vat_sign,
                              s.prices_incl_vat, s.partner_needed, s.ref_type);

-- myDATA (mm-api MyData.java): the invoices of a sale 1.1 (Τιμολόγιο Πώλησης), a credit note of a sale
-- 5.1 (Πιστωτικό Συσχετιζόμενο: of an invoice sent, its MARK) or else 5.2 (Μη Συσχετιζόμενο). The
-- retail receipts go to AADE through the cash register (ΦΗΜ) or a provider, the delivery notes and the
-- purchases are not sent by the shop
update mm_doc_type set mydata_type = case code when 'TPY' then '1.1' when 'TDA' then '1.1' when 'PPY' then '5.1' end
where decode(mydata_type, case code when 'TPY' then '1.1' when 'TDA' then '1.1' when 'PPY' then '5.1' end, 1, 0) = 0;

commit;
