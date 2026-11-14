#!/usr/bin/env python3
"""mkforms.py -- the forms of the mini market in the XML of Oracle Forms 14 (XML2Forms makes the
.fmb, frmcmp the .fmx: build_forms.ps1 on Windows, build_forms.sh on Linux):

  MM_ITEMS      the items: a block ITEM on MM_ITEM, LOVs for the category, the VAT and the unit
  MM_CUSTOMERS  the customers: a block PARTNER on MM_CUSTOMER, a LOV for the tax office (DOY)
  MM_SUPPLIERS  the suppliers: the same on MM_SUPPLIER

Each form: a block CTL on top (Find... with a LOV of the records, All), the block of the table
below it, 15 rows. The stock is not a column of the block (MM_ITEM.STOCK is reservable): the
POST-QUERY of the package UI (MM_UI.pls) fills it, with the name of the category and the VAT rate.

The forms are ASCII: XML2Forms does not carry Greek into a form. The prompts, labels and titles
(of the window, the LOVs, their columns) and the messages are in the package MM_TEXT of the
database (../db/MM_TEXT.sql, written here too), and ui.init sets them when the form opens.

  python3 mkforms.py        (writes MM_*.xml here and ../db/MM_TEXT.sql)
"""
import hashlib
import os
import re
from xml.sax.saxutils import quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, '..', 'db')
CANVAS, WINDOW = 'CNV', 'WIN'
ROWS, ROW_H = 15, 22
TOP = 80                        # the first row of the block (the prompts above it)

GREEKLISH = dict(zip('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρσςτυφχψωάέήίόύώΆΈΉΊΌΎΏϊϋΐΰ',
                     ['A', 'V', 'G', 'D', 'E', 'Z', 'I', 'Th', 'I', 'K', 'L', 'M', 'N', 'X', 'O', 'P',
                      'R', 'S', 'T', 'Y', 'F', 'Ch', 'Ps', 'O', 'a', 'v', 'g', 'd', 'e', 'z', 'i',
                      'th', 'i', 'k', 'l', 'm', 'n', 'x', 'o', 'p', 'r', 's', 's', 't', 'y', 'f',
                      'ch', 'ps', 'o', 'a', 'e', 'i', 'i', 'o', 'y', 'o', 'A', 'E', 'I', 'I', 'O',
                      'Y', 'O', 'i', 'y', 'i', 'y']))


def greeklish(s):
    return ''.join(GREEKLISH.get(c, c) for c in s)


def nonascii(s):
    return any(ord(c) > 127 for c in s)


class Words:
    """The Greek of all the forms: a key from the md5 of the text (a new layout keeps it)."""
    def __init__(self):
        self.words = {}

    def key(self, text):
        k = 'T' + hashlib.md5(text.encode('utf-8')).hexdigest()[:8].upper()
        assert self.words.get(k, text) == text, 'two words, one key: ' + text
        self.words[k] = text
        return k


WORDS = Words()
UNITS = (('PCS', 'Τεμάχιο'), ('KG', 'Κιλό'), ('L', 'Λίτρο'))

# a column of the block: (name, prompt, width, options)
#   db=False   not a column of the table;   hidden=True  not on the canvas
#   num=True   a number;   len   the maximum length;   lov   its LOV;   display=True  read only
#   check=True a check box Y/N;   init  the initial value;   req=True  required
#   mask       the format mask of a number


def C(name, prompt, width, **o):
    return dict(name=name, prompt=prompt, width=width, **o)


FORMS = {
    'MM_ITEMS': dict(
        title='Είδη', block='ITEM', table='MM_ITEM', order='code',
        find_title='Είδη', find=('select id, code, name, barcode from mm_item order by code',
                                 [('ID', 0, 'Κωδ.', 'FIND_ID'), ('CODE', 90, 'Κωδικός', None),
                                  ('NAME', 260, 'Περιγραφή', 'FIND_TEXT'), ('BARCODE', 120, 'Barcode', None)]),
        cols=[
            C('ID', '', 0, num=True, hidden=True, query_only=True),
            C('CODE', 'Κωδικός', 90, len=20, req=True, upper=True),
            C('BARCODE', 'Barcode', 110, len=14),
            C('NAME', 'Περιγραφή', 230, len=100, req=True),
            C('CATEGORY_ID', '', 0, num=True, hidden=True, req=True),
            C('CAT_NAME', 'Κατηγορία', 150, len=60, db=False, req=True, lov='LOV_CAT'),
            C('VAT_CODE', 'ΦΠΑ', 40, len=1, req=True, upper=True, lov='LOV_VAT'),
            C('VAT_RATE', '%', 40, num=True, db=False, display=True, mask='90'),
            C('UNIT', 'Μονάδα', 60, len=3, req=True, upper=True, lov='LOV_UNIT', init='PCS'),
            C('PRICE', 'Τιμή λιαν.', 70, num=True, req=True, mask='99G990D00'),
            C('WHOLESALE_PRICE', 'Χονδρική', 70, num=True, mask='99G990D00'),
            C('COST', 'Κόστος', 70, num=True, req=True, init='0', mask='99G990D00'),
            C('MIN_STOCK', 'Ελάχιστο', 64, num=True, req=True, init='0'),
            C('STOCK', 'Απόθεμα', 70, num=True, db=False, display=True),
            C('ACTIVE', 'Ενεργό', 50, check=True, init='Y'),
        ],
        lovs=[
            ('LOV_CAT', 'Κατηγορίες', 'select id, name from mm_category order by name',
             [('ID', 0, 'Κωδ.', 'ITEM.CATEGORY_ID'), ('NAME', 220, 'Κατηγορία', 'ITEM.CAT_NAME')]),
            ('LOV_VAT', 'ΦΠΑ', 'select code, rate, descr from mm_vat order by code',
             [('CODE', 40, 'ΦΠΑ', 'ITEM.VAT_CODE'), ('RATE', 50, '%', 'ITEM.VAT_RATE'),
              ('DESCR', 180, 'Περιγραφή', None)]),
            ('LOV_UNIT', 'Μονάδες', ' union all '.join(
                "select '%s' code, mm_text.t('%s') descr, %d o from dual" % (c, WORDS.key(d), i)
                for i, (c, d) in enumerate(UNITS)) + ' order by 3',
             [('CODE', 50, 'Μονάδα', 'ITEM.UNIT'), ('DESCR', 120, 'Περιγραφή', None), ('O', 0, '#', None)]),
        ]),
}


def partner_form(table, title, one):
    return dict(
        title=title, block='PARTNER', table=table, order='name',
        find_title=title, find=('select id, name, afm, phone from %s order by name' % table.lower(),
                                [('ID', 0, 'Κωδ.', 'FIND_ID'), ('NAME', 260, one, 'FIND_TEXT'),
                                 ('AFM', 90, 'ΑΦΜ', None), ('PHONE', 100, 'Τηλέφωνο', None)]),
        cols=[
            C('ID', '', 0, num=True, hidden=True, query_only=True),
            C('NAME', 'Επωνυμία', 230, len=100, req=True),
            C('AFM', 'ΑΦΜ', 90, len=9),
            C('DOY', 'ΔΟΥ', 140, len=60, lov='LOV_DOY', free=True),
            C('ADDRESS', 'Διεύθυνση', 220, len=120),
            C('PHONE', 'Τηλέφωνο', 100, len=20),
            C('EMAIL', 'Email', 180, len=100),
            C('ACTIVE', 'Ενεργός', 54, check=True, init='Y'),
        ],
        lovs=[('LOV_DOY', 'ΔΟΥ', 'select doy from (select doy from mm_customer union '
                                 'select doy from mm_supplier) where doy is not null order by 1',
               [('DOY', 220, 'ΔΟΥ', 'PARTNER.DOY')])])


FORMS['MM_CUSTOMERS'] = partner_form('MM_CUSTOMER', 'Πελάτες', 'Πελάτης')
FORMS['MM_SUPPLIERS'] = partner_form('MM_SUPPLIER', 'Προμηθευτές', 'Προμηθευτής')

# the cards of mobile phones: the items with serials (master), their cards (detail), the load of a
# card (serial, PIN: dots on the screen), and the PIN of a card for a user who may see it
FORMS['MM_CARDS'] = dict(
    title='Κάρτες κινητής',
    blocks=[
        dict(name='CARD', table='MM_ITEM', order='code', top=80, rows=4, read_only=True,
             where="serial_tracked = 'Y'",
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('CODE', 'Κωδικός', 90, len=20),
                   C('NAME', 'Περιγραφή', 260, len=100),
                   C('PRICE', 'Τιμή', 70, num=True, mask='99G990D00'),
                   C('MAX_PER_SALE', 'Μέγ./απόδ.', 70, num=True),
                   C('STOCK', 'Διαθέσιμες', 80, num=True, db=False, display=True)]),
        dict(name='SER', table='MM_SERIAL', order='id desc', top=250, rows=10, read_only=True,
             where='item_id = :CARD.ID',
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('SERIAL', 'Serial', 200, len=40),
                   C('STATUS', 'Κατ.', 40, len=1),
                   C('CREATED_AT', 'Φόρτωση', 90, date=True),
                   C('SOLD_AT', 'Πώληση', 90, date=True),
                   C('PIN_SHOW', 'PIN', 160, len=40, db=False, display=True)])],
    ctl=[('NEW_SERIAL', 'text', 10, 200, 200, 'Νέο serial', {'len': 40}),
         ('NEW_PIN', 'secret', 216, 200, 140, 'PIN', {'len': 20}),
         ('LOAD', 'button', 362, 198, 120, 'Φόρτωσε', {}),
         ('USERNAME', 'text', 560, 200, 120, 'Χρήστης', {'len': 60, 'upper': True}),
         ('PIN', 'button', 686, 198, 120, 'Δείξε PIN', {})],
    find_title='Κάρτες κινητής',
    find=("select id, code, name from mm_item where serial_tracked = 'Y' order by code",
          [('ID', 0, 'Κωδ.', 'FIND_ID'), ('CODE', 90, 'Κωδικός', None), ('NAME', 260, 'Περιγραφή', 'FIND_TEXT')]),
    lovs=[])

# the reservations: the reservations (master), their items (detail); a new reservation, an item and
# its quantity (0: out), the deposit, the delivery (a retail receipt, posted), the cancel
FORMS['MM_RESERVATIONS'] = dict(
    title='Κρατήσεις',
    blocks=[
        dict(name='RES', table='MM_RESERVATION', order='pickup_date, id', top=80, rows=6, read_only=True,
             cols=[C('ID', 'Αρ.', 50, num=True),
                   C('NAME', 'Όνομα', 200, len=100),
                   C('PHONE', 'Τηλέφωνο', 100, len=20),
                   C('PICKUP_DATE', 'Παραλαβή', 90, date=True),
                   C('STATUS', 'Κατ.', 40, len=1),
                   C('DEPOSIT', 'Προκαταβολή', 90, num=True, mask='99G990D00')]),
        dict(name='RL', table='MM_RESERVATION_LINE', order='id', top=330, rows=6, read_only=True,
             where='reservation_id = :RES.ID',
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('ITEM_ID', '', 0, num=True, hidden=True),
                   C('ITEM_TEXT', 'Είδος', 300, len=200, db=False, display=True),
                   C('QTY', 'Ποσότητα', 80, num=True),
                   C('PRICE', 'Τιμή', 80, num=True, mask='99G990D00')])],
    ctl=[('R_NAME', 'text', 10, 260, 200, 'Όνομα', {'len': 100}),
         ('R_PHONE', 'text', 216, 260, 110, 'Τηλέφωνο', {'len': 20}),
         ('R_DATE', 'date', 332, 260, 90, 'Παραλαβή', {}),
         ('NEWRES', 'button', 428, 258, 140, 'Νέα κράτηση', {}),
         ('ITEM_TEXT', 'text', 600, 330, 260, 'Είδος (λίστα)', {'len': 200, 'lov': 'LOV_ITEMR'}),
         ('ITEM_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('QTY', 'text', 866, 330, 60, 'Ποσότητα', {'num': True, 'init': '1'}),
         ('RESERVE', 'button', 932, 328, 120, 'Βάλε / άλλαξε', {}),
         ('AMOUNT', 'text', 600, 420, 80, 'Ποσό', {'num': True}),
         ('PAY', 'text', 686, 420, 60, 'Πληρωμή', {'len': 4, 'upper': True, 'init': 'CASH', 'lov': 'LOV_PAY'}),
         ('REG_CODE', 'text', 752, 420, 50, 'Ταμείο', {'len': 10, 'upper': True, 'init': 'T1'}),
         ('DEPOSIT', 'button', 808, 418, 120, 'Προκαταβολή', {}),
         ('DELIVER', 'button', 600, 460, 160, 'Παράδοση (απόδειξη)', {}),
         ('CANCELRES', 'button', 766, 460, 160, 'Ακύρωση κράτησης', {})],
    find_title='Κρατήσεις',
    find=("select id, name, phone, to_char(pickup_date, 'dd/mm/yyyy') pickup from mm_reservation "
          "order by pickup_date desc, id desc",
          [('ID', 50, 'Αρ.', 'FIND_ID'), ('NAME', 200, 'Όνομα', 'FIND_TEXT'), ('PHONE', 100, 'Τηλέφωνο', None),
           ('PICKUP', 90, 'Παραλαβή', None)]),
    lovs=[('LOV_ITEMR', 'Είδη', "select id, code || ' ' || name text from mm_item where active = 'Y' "
                               "and is_model = 'N' and serial_tracked = 'N' order by code",
           [('ID', 0, 'Κωδ.', 'CTL.ITEM_ID'), ('TEXT', 320, 'Είδος', 'CTL.ITEM_TEXT')]),
          ('LOV_PAY', 'Πληρωμή', ' union all '.join(
              "select '%s' code, mm_text.t('%s') descr from dual" % (c, WORDS.key(d))
              for c, d in (('CASH', 'Μετρητά'), ('CARD', 'Κάρτα'))),
           [('CODE', 60, 'Πληρωμή', 'CTL.PAY'), ('DESCR', 120, 'Περιγραφή', None)])])


ITEMS_PLAIN = ("select id, code || ' ' || name text from mm_item where active = 'Y' and kit = 'N' "
               "and is_model = 'N' and serial_tracked = 'N' order by code")

# baskets and sets: the baskets (ready, can make, cost) and what one has; a component in (0: out),
# a new basket from an item, assemble N (negative: take apart)
FORMS['MM_KITS'] = dict(
    title='Καλάθια και σετ',
    blocks=[
        dict(name='KIT', table='MM_ITEM', order='code', top=80, rows=5, read_only=True, where="kit = 'Y'",
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('CODE', 'Κωδικός', 90, len=20),
                   C('NAME', 'Περιγραφή', 260, len=100),
                   C('PRICE', 'Τιμή', 70, num=True, mask='99G990D00'),
                   C('COST', 'Κόστος', 70, num=True, mask='99G990D00'),
                   C('STOCK', 'Έτοιμα', 70, num=True, db=False, display=True),
                   C('CAN_MAKE', 'Φτιάχνονται', 80, num=True, db=False, display=True)]),
        dict(name='KC', table='MM_KIT_COMPONENT', order='component_id', top=320, rows=8, read_only=True,
             where='kit_id = :KIT.ID',
             cols=[C('KIT_ID', '', 0, num=True, hidden=True),
                   C('COMPONENT_ID', '', 0, num=True, hidden=True),
                   C('COMP_TEXT', 'Είδος', 300, len=200, db=False, display=True),
                   C('QTY', 'Ποσότητα', 80, num=True),
                   C('COMP_STOCK', 'Απόθεμα', 80, num=True, db=False, display=True)])],
    ctl=[('NEWKIT_TEXT', 'text', 10, 250, 300, 'Νέο καλάθι από είδος (λίστα)', {'len': 200, 'lov': 'LOV_NEWKIT'}),
         ('NEWKIT_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('COMP_TEXT', 'text', 520, 320, 260, 'Είδος του καλαθιού (λίστα)', {'len': 200, 'lov': 'LOV_COMP'}),
         ('COMP_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('COMP_QTY', 'text', 786, 320, 60, 'Ποσότητα', {'num': True, 'init': '1'}),
         ('ADDCOMP', 'button', 852, 318, 120, 'Βάλε / άλλαξε', {}),
         ('ASM_QTY', 'text', 520, 400, 60, 'Πόσα', {'num': True, 'init': '1'}),
         ('ASSEMBLE', 'button', 586, 398, 200, 'Συναρμολόγησε (-: λύσε)', {})],
    find_title='Καλάθια και σετ',
    find=("select id, code, name from mm_item where kit = 'Y' order by code",
          [('ID', 0, 'Κωδ.', 'FIND_ID'), ('CODE', 90, 'Κωδικός', None), ('NAME', 260, 'Περιγραφή', 'FIND_TEXT')]),
    lovs=[('LOV_NEWKIT', 'Είδη', ITEMS_PLAIN,
           [('ID', 0, 'Κωδ.', 'CTL.NEWKIT_ID'), ('TEXT', 320, 'Είδος', 'CTL.NEWKIT_TEXT')]),
          ('LOV_COMP', 'Είδη', ITEMS_PLAIN,
           [('ID', 0, 'Κωδ.', 'CTL.COMP_ID'), ('TEXT', 320, 'Είδος', 'CTL.COMP_TEXT')])])

# promotions: the promotions and their items or categories; new, an item/category in (0: out), on/off
FORMS['MM_PROMOS'] = dict(
    title='Προσφορές',
    blocks=[
        dict(name='PROMO', table='MM_PROMO', order='date_from desc, id desc', top=80, rows=6, read_only=True,
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('NAME', 'Όνομα', 230, len=100),
                   C('KIND', 'Είδος', 60, len=6),
                   C('DATE_FROM', 'Από', 90, date=True),
                   C('DATE_TO', 'Έως', 90, date=True),
                   C('ACTIVE', 'Ενεργή', 50, len=1),
                   C('PCT', '%', 50, num=True),
                   C('BUY_QTY', 'N', 40, num=True),
                   C('FREE_QTY', 'M', 40, num=True),
                   C('BUNDLE_PRICE', 'Τιμή πακέτου', 90, num=True, mask='99G990D00')]),
        dict(name='PI', table='MM_PROMO_ITEM', order='id', top=400, rows=6, read_only=True,
             where='promo_id = :PROMO.ID',
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('ITEM_ID', '', 0, num=True, hidden=True),
                   C('CATEGORY_ID', '', 0, num=True, hidden=True),
                   C('TEXT', 'Είδος ή κατηγορία', 320, len=200, db=False, display=True),
                   C('QTY', 'Ποσότητα', 80, num=True)])],
    ctl=[('P_NAME', 'text', 10, 260, 220, 'Όνομα', {'len': 100}),
         ('P_KIND', 'text', 236, 260, 70, 'Είδος (λίστα)', {'len': 6, 'upper': True, 'lov': 'LOV_PKIND'}),
         ('P_FROM', 'date', 312, 260, 90, 'Από', {}),
         ('P_TO', 'date', 408, 260, 90, 'Έως', {}),
         ('P_PCT', 'text', 504, 260, 50, '%', {'num': True}),
         ('P_BUY', 'text', 560, 260, 40, 'N', {'num': True}),
         ('P_FREE', 'text', 606, 260, 40, 'M', {'num': True}),
         ('P_PRICE', 'text', 652, 260, 80, 'Τιμή πακέτου', {'num': True}),
         ('NEWPROMO', 'button', 738, 258, 140, 'Νέα προσφορά', {}),
         ('TOGGLE', 'button', 884, 258, 160, 'Ενεργή / ανενεργή', {}),
         ('PI_ITEM_TEXT', 'text', 520, 400, 260, 'Είδος (λίστα)', {'len': 200, 'lov': 'LOV_PITEM'}),
         ('PI_ITEM_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('PI_CAT_TEXT', 'text', 520, 446, 260, 'ή κατηγορία (λίστα)', {'len': 100, 'lov': 'LOV_PCAT'}),
         ('PI_CAT_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('PI_QTY', 'text', 786, 400, 60, 'Ποσότητα', {'num': True, 'init': '1'}),
         ('ADDPI', 'button', 852, 398, 120, 'Βάλε / βγάλε', {})],
    find_title='Προσφορές',
    find=("select id, name, kind from mm_promo order by date_from desc, id desc",
          [('ID', 0, 'Κωδ.', 'FIND_ID'), ('NAME', 260, 'Όνομα', 'FIND_TEXT'), ('KIND', 60, 'Είδος', None)]),
    lovs=[('LOV_PKIND', 'Είδος προσφοράς', ' union all '.join(
              "select '%s' code, mm_text.t('%s') descr from dual" % (c, WORDS.key(d))
              for c, d in (('PCT', 'Έκπτωση %'), ('NM', 'Αγοράζεις N, παίρνεις M δώρο'),
                           ('BUNDLE', 'Πακέτο σε τιμή'))),
           [('CODE', 70, 'Είδος', 'CTL.P_KIND'), ('DESCR', 240, 'Περιγραφή', None)]),
          ('LOV_PITEM', 'Είδη', "select id, code || ' ' || name text from mm_item where active = 'Y' "
                                "and serial_tracked = 'N' and parent_id is null order by code",
           [('ID', 0, 'Κωδ.', 'CTL.PI_ITEM_ID'), ('TEXT', 320, 'Είδος', 'CTL.PI_ITEM_TEXT')]),
          ('LOV_PCAT', 'Κατηγορίες', 'select id, name from mm_category order by name',
           [('ID', 0, 'Κωδ.', 'CTL.PI_CAT_ID'), ('NAME', 220, 'Κατηγορία', 'CTL.PI_CAT_TEXT')])])

# clothes and shoes: the models and their variants (colour, size, stock, available); a new variant (of
# the model, or of an item that becomes a model), one price for the model and its variants
FORMS['MM_VARIANTS'] = dict(
    title='Ρούχα και παπούτσια',
    blocks=[
        dict(name='MODEL', table='MM_ITEM', order='code', top=80, rows=5, read_only=True, where="is_model = 'Y'",
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('CODE', 'Κωδικός', 90, len=20),
                   C('NAME', 'Μοντέλο', 260, len=100),
                   C('PRICE', 'Τιμή', 70, num=True, mask='99G990D00')]),
        dict(name='VG', table='MM_ITEM', order='color_id, (select z.sort_no from mm_size z where z.id = size_id)',
             top=330, rows=10, read_only=True, where='parent_id = :MODEL.ID',
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('CODE', 'Κωδικός', 130, len=20),
                   C('BARCODE', 'Barcode', 110, len=14),
                   C('COLOR_TEXT', 'Χρώμα', 90, len=40, db=False, display=True),
                   C('SIZE_TEXT', 'Μέγεθος', 60, len=10, db=False, display=True),
                   C('PRICE', 'Τιμή', 70, num=True, mask='99G990D00'),
                   C('STOCK', 'Απόθεμα', 70, num=True, db=False, display=True),
                   C('AVAIL', 'Διαθέσιμα', 70, num=True, db=False, display=True)])],
    ctl=[('NEWMODEL_TEXT', 'text', 10, 250, 300, 'Νέο μοντέλο από είδος (λίστα)', {'len': 200, 'lov': 'LOV_NEWMODEL'}),
         ('NEWMODEL_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('M_PRICE', 'text', 400, 250, 70, 'Τιμή', {'num': True}),
         ('MPRICE', 'button', 476, 248, 160, 'Τιμή σε όλες', {}),
         ('V_COLOR_TEXT', 'text', 660, 330, 120, 'Χρώμα (λίστα)', {'len': 40, 'lov': 'LOV_COLOR'}),
         ('V_COLOR_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('V_SIZE_TEXT', 'text', 786, 330, 110, 'Μέγεθος (λίστα)', {'len': 40, 'lov': 'LOV_SIZE'}),
         ('V_SIZE_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('V_BARCODE', 'text', 660, 376, 140, 'Barcode', {'len': 14}),
         ('NEWVAR', 'button', 806, 374, 160, 'Νέα παραλλαγή', {})],
    find_title='Μοντέλα',
    find=("select id, code, name from mm_item where is_model = 'Y' order by code",
          [('ID', 0, 'Κωδ.', 'FIND_ID'), ('CODE', 90, 'Κωδικός', None), ('NAME', 260, 'Μοντέλο', 'FIND_TEXT')]),
    lovs=[('LOV_NEWMODEL', 'Είδη', "select id, code || ' ' || name text from mm_item where is_model = 'N' "
                                   "and parent_id is null and kit = 'N' and serial_tracked = 'N' order by code",
           [('ID', 0, 'Κωδ.', 'CTL.NEWMODEL_ID'), ('TEXT', 320, 'Είδος', 'CTL.NEWMODEL_TEXT')]),
          ('LOV_COLOR', 'Χρώματα', 'select id, name from mm_color order by name',
           [('ID', 0, 'Κωδ.', 'CTL.V_COLOR_ID'), ('NAME', 160, 'Χρώμα', 'CTL.V_COLOR_TEXT')]),
          ('LOV_SIZE', 'Μεγέθη', "select id, size_group || ' ' || code text from mm_size order by size_group, sort_no",
           [('ID', 0, 'Κωδ.', 'CTL.V_SIZE_ID'), ('TEXT', 160, 'Μέγεθος', 'CTL.V_SIZE_TEXT')])])



# invoicing (wholesale): invoices of sale and of purchase and their credit notes (master), their
# lines (detail); new, a line (the cards of mobile phones: with their serials), delete a line, post,
# cancel, a credit note, delete a draft
FORMS['MM_INVOICES'] = dict(
    title='Τιμολόγια',
    blocks=[
        dict(name='DOC', table='MM_DOC', order='doc_date desc, id desc', top=80, rows=6, read_only=True,
             where="doc_type in ('TPY', 'PPY', 'TAG', 'PAG')",
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('DOC_TYPE', 'Είδος', 50, len=3),
                   C('DOC_NO', 'Αριθμός', 70, num=True),
                   C('DOC_DATE', 'Ημερομηνία', 90, date=True),
                   C('STATUS', 'Κατ.', 40, len=1),
                   C('CUSTOMER_ID', '', 0, num=True, hidden=True),
                   C('SUPPLIER_ID', '', 0, num=True, hidden=True),
                   C('PARTNER_TEXT', 'Πελάτης / προμηθευτής', 220, len=100, db=False, display=True),
                   C('PAYMENT', 'Πληρωμή', 70, len=6),
                   C('NET', 'Καθαρό', 80, num=True, mask='99G990D00'),
                   C('VAT', 'ΦΠΑ', 70, num=True, mask='99G990D00'),
                   C('TOTAL', 'Σύνολο', 80, num=True, mask='99G990D00')]),
        dict(name='DL', table='MM_DOC_LINE', order='line_no', top=330, rows=8, read_only=True,
             where='doc_id = :DOC.ID',
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('ITEM_ID', '', 0, num=True, hidden=True),
                   C('ITEM_TEXT', 'Είδος', 260, len=200, db=False, display=True),
                   C('QTY', 'Ποσότητα', 70, num=True),
                   C('PRICE', 'Τιμή', 80, num=True, mask='9G990D0000'),
                   C('DISCOUNT', 'Έκπτ. %', 50, num=True),
                   C('PROMO_DISC', 'Προσφορά', 70, num=True, mask='99G990D00'),
                   C('NET', 'Καθαρό', 80, num=True, mask='99G990D00'),
                   C('VAT', 'ΦΠΑ', 70, num=True, mask='99G990D00'),
                   C('TOTAL', 'Σύνολο', 80, num=True, mask='99G990D00')]),
        dict(name='DS', table='MM_SERIAL', order='id', top=540, rows=5, read_only=True,
             where='(out_line_id = :DL.ID or in_line_id = :DL.ID)',
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('SERIAL', 'Serial της γραμμής', 220, len=40),
                   C('STATUS', 'Κατ.', 40, len=1)])],
    ctl=[('D_TYPE', 'text', 10, 260, 60, 'Είδος (λίστα)', {'len': 3, 'upper': True, 'init': 'TPY', 'lov': 'LOV_DTYPE'}),
         ('CUST_TEXT', 'text', 76, 260, 200, 'Πελάτης (λίστα)', {'len': 100, 'lov': 'LOV_CUST'}),
         ('CUST_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('SUPP_TEXT', 'text', 282, 260, 200, 'ή προμηθευτής (λίστα)', {'len': 100, 'lov': 'LOV_SUPP'}),
         ('SUPP_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('D_PAY', 'text', 488, 260, 70, 'Πληρωμή', {'len': 6, 'upper': True, 'init': 'CREDIT', 'lov': 'LOV_PAY'}),
         ('D_DATE', 'date', 564, 260, 90, 'Ημερομηνία', {}),
         ('NEWDOC', 'button', 660, 258, 120, 'Νέο', {}),
         ('POSTDOC', 'button', 830, 80, 160, 'Καταχώριση', {}),
         ('CANCELDOC', 'button', 830, 112, 160, 'Ακύρωση', {}),
         ('CREDIT', 'button', 830, 144, 160, 'Πιστωτικό', {}),
         ('DELDOC', 'button', 830, 176, 160, 'Σβήσε πρόχειρο', {}),
         ('L_ITEM_TEXT', 'text', 910, 330, 220, 'Είδος (λίστα)', {'len': 200, 'lov': 'LOV_ITEMI'}),
         ('L_ITEM_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('L_QTY', 'text', 910, 376, 60, 'Ποσότητα', {'num': True, 'init': '1'}),
         ('L_PRICE', 'text', 976, 376, 80, 'Τιμή', {'num': True}),
         ('L_DISC', 'text', 1062, 376, 50, 'Έκπτ. %', {'num': True}),
         ('ADDLINE', 'button', 910, 410, 220, 'Βάλε γραμμή', {}),
         ('DELLINE', 'button', 910, 444, 220, 'Σβήσε τη γραμμή', {}),
         ('S_SERIAL', 'text', 300, 540, 200, 'Serial (σάρωση)', {'len': 40}),
         ('S_PIN', 'secret', 506, 540, 120, 'PIN (αγορά)', {'len': 20}),
         ('ADDSER', 'button', 632, 538, 140, 'Βάλε serial', {}),
         ('DELSER', 'button', 632, 572, 140, 'Βγάλε serial', {})],
    find_title='Τιμολόγια',
    find=("select d.id, d.doc_type || ' ' || d.doc_no || ' ' || to_char(d.doc_date, 'dd/mm/yyyy') text, "
          "nvl(c.name, s.name) partner from mm_doc d left join mm_customer c on c.id = d.customer_id "
          "left join mm_supplier s on s.id = d.supplier_id where d.doc_type in ('TPY', 'PPY', 'TAG', 'PAG') "
          "order by d.doc_date desc, d.id desc",
          [('ID', 0, 'Κωδ.', 'FIND_ID'), ('TEXT', 180, 'Παραστατικό', 'FIND_TEXT'), ('PARTNER', 220, 'Πελάτης / προμηθευτής', None)]),
    lovs=[('LOV_DTYPE', 'Είδος παραστατικού', "select code, name from mm_doc_type "
                                             "where code in ('TPY', 'PPY', 'TAG', 'PAG') order by code",
           [('CODE', 50, 'Είδος', 'CTL.D_TYPE'), ('NAME', 220, 'Περιγραφή', None)]),
          ('LOV_CUST', 'Πελάτες', "select id, name from mm_customer where active = 'Y' order by name",
           [('ID', 0, 'Κωδ.', 'CTL.CUST_ID'), ('NAME', 260, 'Πελάτης', 'CTL.CUST_TEXT')]),
          ('LOV_SUPP', 'Προμηθευτές', "select id, name from mm_supplier where active = 'Y' order by name",
           [('ID', 0, 'Κωδ.', 'CTL.SUPP_ID'), ('NAME', 260, 'Προμηθευτής', 'CTL.SUPP_TEXT')]),
          ('LOV_PAY', 'Πληρωμή', ' union all '.join(
              "select '%s' code, mm_text.t('%s') descr from dual" % (c, WORDS.key(d))
              for c, d in (('CREDIT', 'Πίστωση'), ('CASH', 'Μετρητά'), ('CARD', 'Κάρτα'))),
           [('CODE', 70, 'Πληρωμή', 'CTL.D_PAY'), ('DESCR', 120, 'Περιγραφή', None)]),
          ('LOV_ITEMI', 'Είδη', "select id, code || ' ' || name text from mm_item where active = 'Y' "
                                "and is_model = 'N' order by code",
           [('ID', 0, 'Κωδ.', 'CTL.L_ITEM_ID'), ('TEXT', 320, 'Είδος', 'CTL.L_ITEM_TEXT')])])


# receipts from customers and payments to suppliers: the list; a new one (with a register: a move of
# its open Z too), cancel
FORMS['MM_PAYMENTS'] = dict(
    title='Εισπράξεις και πληρωμές',
    blocks=[
        dict(name='PAY', table='MM_PAYMENT', order='pay_date desc, id desc', top=80, rows=10, read_only=True,
             cols=[C('ID', '', 0, num=True, hidden=True),
                   C('KIND', 'Είδος', 40, len=1),
                   C('PAY_DATE', 'Ημερομηνία', 90, date=True),
                   C('CUSTOMER_ID', '', 0, num=True, hidden=True),
                   C('SUPPLIER_ID', '', 0, num=True, hidden=True),
                   C('PARTNER_TEXT', 'Πελάτης / προμηθευτής', 240, len=100, db=False, display=True),
                   C('METHOD', 'Τρόπος', 60, len=6),
                   C('AMOUNT', 'Ποσό', 90, num=True, mask='99G999G990D00'),
                   C('STATUS', 'Κατ.', 40, len=1),
                   C('NOTES', 'Σημειώσεις', 240, len=400)])],
    ctl=[('P_KIND', 'text', 10, 340, 50, 'Είδος (λίστα)', {'len': 1, 'upper': True, 'init': 'R', 'lov': 'LOV_PKINDP'}),
         ('CUST_TEXT', 'text', 66, 340, 200, 'Πελάτης (λίστα)', {'len': 100, 'lov': 'LOV_CUST'}),
         ('CUST_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('SUPP_TEXT', 'text', 272, 340, 200, 'ή προμηθευτής (λίστα)', {'len': 100, 'lov': 'LOV_SUPP'}),
         ('SUPP_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('P_AMOUNT', 'text', 478, 340, 80, 'Ποσό', {'num': True}),
         ('P_METHOD', 'text', 564, 340, 60, 'Τρόπος (λίστα)', {'len': 6, 'upper': True, 'init': 'CASH', 'lov': 'LOV_METHOD'}),
         ('P_DATE', 'date', 630, 340, 90, 'Ημερομηνία', {}),
         ('REG_CODE', 'text', 726, 340, 50, 'Ταμείο', {'len': 10, 'upper': True}),
         ('P_NOTES', 'text', 10, 386, 466, 'Σημειώσεις', {'len': 400}),
         ('NEWPAY', 'button', 482, 384, 160, 'Καταχώριση', {}),
         ('CANCELPAY', 'button', 648, 384, 160, 'Ακύρωση', {})],
    find_title='Εισπράξεις και πληρωμές',
    find=("select p.id, p.kind || ' ' || to_char(p.pay_date, 'dd/mm/yyyy') || ' ' || to_char(p.amount, 'fm999990.00') text, "
          "nvl(c.name, s.name) partner from mm_payment p left join mm_customer c on c.id = p.customer_id "
          "left join mm_supplier s on s.id = p.supplier_id order by p.pay_date desc, p.id desc",
          [('ID', 0, 'Κωδ.', 'FIND_ID'), ('TEXT', 180, 'Κίνηση', 'FIND_TEXT'), ('PARTNER', 220, 'Πελάτης / προμηθευτής', None)]),
    lovs=[('LOV_PKINDP', 'Είδος', ' union all '.join(
              "select '%s' code, mm_text.t('%s') descr from dual" % (c, WORDS.key(d))
              for c, d in (('R', 'Είσπραξη από πελάτη'), ('P', 'Πληρωμή σε προμηθευτή'))),
           [('CODE', 40, 'Είδος', 'CTL.P_KIND'), ('DESCR', 220, 'Περιγραφή', None)]),
          ('LOV_CUST', 'Πελάτες', "select id, name from mm_customer where active = 'Y' order by name",
           [('ID', 0, 'Κωδ.', 'CTL.CUST_ID'), ('NAME', 260, 'Πελάτης', 'CTL.CUST_TEXT')]),
          ('LOV_SUPP', 'Προμηθευτές', "select id, name from mm_supplier where active = 'Y' order by name",
           [('ID', 0, 'Κωδ.', 'CTL.SUPP_ID'), ('NAME', 260, 'Προμηθευτής', 'CTL.SUPP_TEXT')]),
          ('LOV_METHOD', 'Τρόπος', ' union all '.join(
              "select '%s' code, mm_text.t('%s') descr from dual" % (c, WORDS.key(d))
              for c, d in (('CASH', 'Μετρητά'), ('CARD', 'Κάρτα'), ('BANK', 'Έμβασμα'))),
           [('CODE', 60, 'Τρόπος', 'CTL.P_METHOD'), ('DESCR', 120, 'Περιγραφή', None)])])

# the ledgers (MM_LEDGER in the database): of an item, a customer or a supplier for a period; the
# rows in MM_LEDGER_ROW (a temporary table of the session): the carry-over first, then the moves with
# the running balance; under them the carry-over, the totals of the period and the balance at its end
MONEY = '999G999G990D00'
FORMS['MM_LEDGER'] = dict(
    title='Καρτέλες',
    blocks=[
        dict(name='LED', table='MM_LEDGER_ROW', order='seq', top=170, rows=15, read_only=True,
             cols=[C('SEQ', '', 0, num=True, hidden=True),
                   C('KIND', '', 0, len=1, hidden=True),
                   C('LDATE', 'Ημερομηνία', 90, date=True),
                   C('DOC_TEXT', 'Παραστατικό', 110, len=40),
                   C('PARTNER', 'Πελάτης / προμηθευτής / ταμείο', 200, len=100),
                   C('DESCR', 'Περιγραφή', 260, len=200),
                   C('DEBIT', 'Χρέωση', 90, num=True, mask=MONEY),
                   C('CREDIT', 'Πίστωση', 90, num=True, mask=MONEY),
                   C('BALANCE', 'Υπόλοιπο', 100, num=True, mask=MONEY)])],
    ctl=[('L_FROM', 'date', 10, 24, 90, 'Από', {'year_start': True}),
         ('L_TO', 'date', 106, 24, 90, 'Έως', {}),
         ('ITEM_TEXT', 'text', 206, 24, 260, 'Είδος (λίστα)', {'len': 200, 'lov': 'LOV_LITEM'}),
         ('ITEM_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('SHOWITEM', 'button', 472, 22, 170, 'Καρτέλα είδους', {}),
         ('CUST_TEXT', 'text', 206, 70, 260, 'Πελάτης (λίστα)', {'len': 100, 'lov': 'LOV_CUST'}),
         ('CUST_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('SHOWCUST', 'button', 472, 68, 170, 'Καρτέλα πελάτη', {}),
         ('SUPP_TEXT', 'text', 206, 116, 260, 'Προμηθευτής (λίστα)', {'len': 100, 'lov': 'LOV_SUPP'}),
         ('SUPP_ID', 'hidden', 0, 0, 0, '', {'num': True}),
         ('SHOWSUPP', 'button', 472, 114, 170, 'Καρτέλα προμηθευτή', {}),
         ('L_TITLE', 'display', 660, 24, 314, 'Καρτέλα', {'len': 200}),
         ('PRINTLED', 'button', 660, 68, 170, 'Εκτύπωση', {}),
         ('O_OPEN', 'display', 548, 520, 130, 'Από μεταφορά', {'num': True}),
         ('O_DEBIT', 'display', 686, 520, 90, 'Σύνολο', {'num': True}),
         ('O_CREDIT', 'display', 780, 520, 90, 'Σύνολο', {'num': True}),
         ('O_CLOSE', 'display', 874, 520, 100, 'Γενικό υπόλοιπο', {'num': True})],
    lovs=[('LOV_LITEM', 'Είδη', "select id, code || ' ' || name text from mm_item where is_model = 'N' order by code",
           [('ID', 0, 'Κωδ.', 'CTL.ITEM_ID'), ('TEXT', 320, 'Είδος', 'CTL.ITEM_TEXT')]),
          ('LOV_CUST', 'Πελάτες', "select id, name from mm_customer order by name",
           [('ID', 0, 'Κωδ.', 'CTL.CUST_ID'), ('NAME', 260, 'Πελάτης', 'CTL.CUST_TEXT')]),
          ('LOV_SUPP', 'Προμηθευτές', "select id, name from mm_supplier order by name",
           [('ID', 0, 'Κωδ.', 'CTL.SUPP_ID'), ('NAME', 260, 'Προμηθευτής', 'CTL.SUPP_TEXT')])])

# the reports (reports/mkreports.py) in the browser, through the Reports Server (MM_SETTING): the
# period, a button for each
FORMS['MM_REPORTS'] = dict(
    title='Αναφορές',
    blocks=[],
    ctl=[('R_FROM', 'date', 20, 30, 90, 'Από', {'year_start': True}),
         ('R_TO', 'date', 116, 30, 90, 'Έως', {}),
         ('RPT_SALES', 'button', 20, 76, 300, 'Πωλήσεις ανά ημέρα (μήνες)', {}),
         ('RPT_VAT', 'button', 20, 110, 300, 'ΦΠΑ πωλήσεων και αγορών', {}),
         ('RPT_MIN', 'button', 20, 144, 300, 'Ελάχιστο απόθεμα (σήμερα)', {}),
         ('GO_MM_LEDGER', 'button', 20, 192, 300, 'Καρτέλες (είδους, πελάτη, προμηθευτή)', {})])

# the menu: a button for each form (CALL_FORM: closing it comes back here), and the exit
MENU_FORMS = [('MM_ITEMS', 'Είδη'), ('MM_CUSTOMERS', 'Πελάτες'), ('MM_SUPPLIERS', 'Προμηθευτές'),
              ('MM_CARDS', 'Κάρτες κινητής'), ('MM_RESERVATIONS', 'Κρατήσεις'), ('MM_KITS', 'Καλάθια και σετ'),
              ('MM_PROMOS', 'Προσφορές'), ('MM_VARIANTS', 'Ρούχα και παπούτσια'), ('MM_INVOICES', 'Τιμολόγια'),
              ('MM_PAYMENTS', 'Εισπράξεις και πληρωμές'), ('MM_LEDGER', 'Καρτέλες'), ('MM_REPORTS', 'Αναφορές')]
FORMS['MM_MAIN'] = dict(
    title='Mini market',
    blocks=[],
    ctl=[('GO_' + f, 'button', 20 + (i % 2) * 230, 20 + (i // 2) * 44, 220, t, {})
         for i, (f, t) in enumerate(MENU_FORMS)] +
        [('EXIT', 'button', 135, 20 + (len(MENU_FORMS) + 1) // 2 * 44 + 16, 220, 'Έξοδος', {})])


# the bar of pull-down menus of all the forms (the menu module MM_MENU, in place of DEFAULT&SMARTBAR):
# (menu, label, [(item, label, PL/SQL)]); a form opens in the place of the one on the screen (NEW_FORM:
# unsaved changes are asked first). Its Greek: ui.init of each form (SET_MENU_ITEM_PROPERTY).
MENU_MODULE = 'MM_MENU'
MENU_BAR = [
    ('FILE', 'Αρχείο', [('MAIN', 'Αρχικό μενού', "new_form('MM_MAIN');"),
                        ('EXIT', 'Έξοδος', "do_key('EXIT_FORM');")]),
    ('REC', 'Εγγραφές', [('SAVE', 'Αποθήκευση (F10)', "do_key('COMMIT_FORM');"),
                         ('ENTERQ', 'Αναζήτηση (F7)', "do_key('ENTER_QUERY');"),
                         ('EXECQ', 'Εκτέλεση αναζήτησης (F8)', "do_key('EXECUTE_QUERY');"),
                         ('NEWREC', 'Νέα εγγραφή', "do_key('CREATE_RECORD');"),
                         ('DELREC', 'Διαγραφή εγγραφής', "do_key('DELETE_RECORD');"),
                         ('LOV', 'Λίστα τιμών (Ctrl+L)', "do_key('LIST_VALUES');")]),
    ('STOCK', 'Αποθήκη', [('ITEMS', 'Είδη', "new_form('MM_ITEMS');"),
                          ('VARIANTS', 'Ρούχα και παπούτσια', "new_form('MM_VARIANTS');"),
                          ('KITS', 'Καλάθια και σετ', "new_form('MM_KITS');"),
                          ('CARDS', 'Κάρτες κινητής', "new_form('MM_CARDS');"),
                          ('ILEDGER', 'Καρτέλα είδους', "new_form('MM_LEDGER');")]),
    ('SALES', 'Πωλήσεις', [('INVOICES', 'Τιμολόγια πώλησης', "new_form('MM_INVOICES');"),
                           ('RECEIPTS', 'Εισπράξεις', "new_form('MM_PAYMENTS');"),
                           ('CUSTOMERS', 'Πελάτες', "new_form('MM_CUSTOMERS');"),
                           ('RESERV', 'Κρατήσεις', "new_form('MM_RESERVATIONS');"),
                           ('PROMOS', 'Προσφορές', "new_form('MM_PROMOS');"),
                           ('CLEDGER', 'Καρτέλα πελάτη', "new_form('MM_LEDGER');")]),
    ('BUY', 'Αγορές', [('PINVOICES', 'Τιμολόγια αγοράς', "new_form('MM_INVOICES');"),
                       ('PAYMENTS', 'Πληρωμές', "new_form('MM_PAYMENTS');"),
                       ('SUPPLIERS', 'Προμηθευτές', "new_form('MM_SUPPLIERS');"),
                       ('SLEDGER', 'Καρτέλα προμηθευτή', "new_form('MM_LEDGER');")]),
    ('REPORTS', 'Αναφορές', [('REPORTSF', 'Πωλήσεις, ΦΠΑ, ελάχιστο απόθεμα', "new_form('MM_REPORTS');"),
                             ('LEDGERS', 'Καρτέλες', "new_form('MM_LEDGER');")]),
]


def menu_texts():
    """the Greek labels of the bar, for ui.init of every form"""
    out = []
    for m, label, items in MENU_BAR:
        out.append("SET_MENU_ITEM_PROPERTY('MAIN_MENU.%s', LABEL, tx('%s'));" % (m, WORDS.key(label)))
        for i, il, _ in items:
            out.append("SET_MENU_ITEM_PROPERTY('%s_MENU.%s', LABEL, tx('%s'));" % (m, i, WORDS.key(il)))
    return out


def menu_xml():
    """the menu module MM_MENU (XML2Forms makes MM_MENU.mmb, frmcmp module_type=menu MM_MENU.mmx)"""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<Module version="141200000" xmlns="http://xmlns.oracle.com/Forms">',
           '  <MenuModule Name="%s" MainMenu="MAIN_MENU">' % MENU_MODULE,
           '    <Menu Name="MAIN_MENU">']
    for m, label, _ in MENU_BAR:
        out.append('      <MenuItem %s/>' % attrs(dict(Name=m, Label=ascii_text(label), CommandType='Menu',
                                                         SubMenuName=m + '_MENU')))
    out.append('    </Menu>')
    for m, _, items in MENU_BAR:
        out.append('    <Menu Name="%s_MENU">' % m)
        for i, il, code in items:
            out.append('      <MenuItem %s/>' % attrs(dict(Name=i, Label=ascii_text(il), CommandType='PL/SQL',
                                                             MenuItemCode=code)))
        out.append('    </Menu>')
    out += ['  </MenuModule>', '</Module>']
    xml = '\n'.join(out) + '\n'
    assert all(ord(c) < 128 for c in xml)
    return xml


# the toolbar of all the forms: a horizontal toolbar canvas TBC with the buttons of the block TB; they
# do not take the cursor (MouseNavigate false), so they act on the block where it is (ui.tool)
TOOLBAR = [('T_SAVE', 'Αποθήκευση', 100), ('T_ENTERQ', 'Αναζήτηση', 90), ('T_EXECQ', 'Εκτέλεση', 80),
           ('T_NEW', 'Νέα', 60), ('T_DEL', 'Διαγραφή', 80), ('T_LOV', 'Λίστα', 60), ('T_PREV', '<', 34), ('T_NEXT', '>', 34),
           ('T_MAIN', 'Μενού', 70), ('T_EXIT', 'Έξοδος', 70)]
TB_CANVAS, TB_H = 'TBC', 34


def toolbar_items(say):
    out, x = [], 4
    for name, label, w in TOOLBAR:
        out.append(dict(Name=name, ItemType='Push Button', CanvasName=TB_CANVAS, XPosition=x, YPosition=4,
                        Width=w, Height=26, Label=ascii_text(label), MouseNavigate='false',
                        KeyboardNavigable='false'))
        say('TB.' + name, 'LABEL', label)
        x += w + 4
    return out, x + 4


def attrs(a):
    return ' '.join('%s=%s' % (k, quoteattr(str(v))) for k, v in a.items())


def trigger(name, text, ind):
    return '%s<Trigger Name=%s TriggerText=%s/>' % (ind, quoteattr(name), quoteattr(text))


def ascii_text(s):
    return greeklish(s) if nonascii(s) else s


def program(name, f, texts):
    """the package UI of MM_UI.pls for this form: its Greek strings as tx('T...'), its block, the
    texts of ui.init"""
    src = open(os.path.join(HERE, 'MM_UI.pls'), encoding='utf-8').read()
    spec, body = src.split('\n-- BODY\n')
    spec = '\n'.join(l for l in spec.split('\n') if not l.startswith('--')).strip()
    out = []
    for line in body.strip().split('\n'):
        code, sep, rest = line.partition('--')
        code = re.sub(r"'([^']*)'", lambda m: "tx('%s')" % WORDS.key(m.group(1)) if nonascii(m.group(1))
                      else m.group(0), code)
        out.append(code.rstrip() if not sep else code + sep + greeklish(rest))
    body = '\n'.join(out)
    body = body.replace("c_block CONSTANT VARCHAR2(30) := 'BLOCK'; -- BLOCK",
                        "c_block CONSTANT VARCHAR2(30) := '%s';" % f['block'])
    body = body.replace("c_where CONSTANT VARCHAR2(400) := ''; -- WHERE",
                        "c_where CONSTANT VARCHAR2(400) := '%s';" % f.get('where', '').replace("'", "''"))
    body = body.replace("c_detail CONSTANT VARCHAR2(30) := ''; -- DETAIL",
                        "c_detail CONSTANT VARCHAR2(30) := '%s';" % f.get('detail', ''))
    body = body.replace("c_detail2 CONSTANT VARCHAR2(30) := ''; -- DETAIL2",
                        "c_detail2 CONSTANT VARCHAR2(30) := '%s';" % f.get('detail2', ''))
    body = body.replace('NULL; -- TEXTS', ('\n' + ' ' * 4).join(texts))
    return spec, body


def block_items(blk, cols, top, say, x0=10):
    """the items of a block of a table, side by side from x0 on the row top; its width"""
    out_items = []
    x = x0
    for c in cols:
        a = dict(Name=c['name'])
        if c.get('hidden'):
            a.update(ItemType='Text Item', Visible='false')
        else:
            a.update(ItemType='Check Box' if c.get('check') else
                     'Display Item' if c.get('display') else 'Text Item',
                     CanvasName=CANVAS, XPosition=x, YPosition=top, Width=c['width'], Height=ROW_H,
                     Prompt=ascii_text(c['prompt']), PromptAttachmentEdge='Top', PromptAttachmentOffset=2)
            x += c['width'] + 4
            say('%s.%s' % (blk, c['name']), 'PROMPT_TEXT', c['prompt'])
        if c.get('check'):
            a.update(CheckedValue='Y', UncheckedValue='N', CheckBoxOtherValues='Not Allowed',
                     Label='', DataType='Char', MaximumLength=1)
        else:
            a.update(DataType='Number' if c.get('num') else 'Date' if c.get('date') else 'Char',
                     MaximumLength=c.get('len', 14 if c.get('num') else 10 if c.get('date') else 30))
        if c.get('num') and not c.get('hidden'):
            a['Justification'] = 'Right'
        if c.get('mask'):
            a['FormatMask'] = c['mask']      # 0,45 not ,45; 4,60 not 4,6 (D and G: the NLS of the runtime)
        if c.get('date'):
            a['FormatMask'] = 'DD/MM/YYYY'
        if c.get('db', True):
            a['ColumnName'] = c['name']
        else:
            a['DatabaseItem'] = 'false'
        if c.get('req'):
            a['Required'] = 'true'
        if c.get('upper'):
            a['CaseRestriction'] = 'Upper'
        if 'init' in c:
            a['InitializeValue'] = c['init']
        if c.get('query_only'):
            a.update(InsertAllowed='false', UpdateAllowed='false')
        if c.get('lov'):
            a['LovName'] = c['lov']
            a['ValidateFromList'] = 'false' if c.get('free') else 'true'
        out_items.append(a)
    return out_items, x


def lov_xml(lovs, texts):
    """the record groups and the LOVs; their Greek titles to ui.init"""
    groups, lovx = [], []
    for lov, title, query, cols in lovs:
        rg = 'RG' + lov[3:]
        groups.append('    <RecordGroup Name="%s" RecordGroupType="Query" RecordGroupQuery=%s>' % (rg, quoteattr(query)))
        for cn, w, t, r in cols:
            # ColumnDataType: "Number"; a column of characters is the default ("Char" is not a
            # value of the schema of XML2Forms 14.1.2: XML-24523)
            num = cn in ('ID', 'RATE', 'O')
            groups.append('      <RecordGroupColumn Name="%s"%s MaximumLength="%d"/>'
                          % (cn, ' ColumnDataType="Number"' if num else '', 40 if num else 400))
        groups.append('    </RecordGroup>')
        lw = sum(w for _, w, _, _ in cols) + 40
        lovx.append('    <LOV Name="%s" RecordGroupName="%s" Title=%s Width="%d" Height="300" '
                    'AutoColumnWidth="false" AutoPosition="true" AutoRefresh="true" FilterBeforeDisplay="false">'
                    % (lov, rg, quoteattr(ascii_text(title)), max(lw, 220)))
        if nonascii(title):
            texts.append("SET_LOV_PROPERTY('%s', TITLE, tx('%s'));" % (lov, WORDS.key(title)))
        for i, (cn, w, t, r) in enumerate(cols, 1):
            m = dict(Name=cn, Title=ascii_text(t), DisplayWidth=w)
            if r:
                m['ReturnItem'] = r
            lovx.append('      <LOVColumnMapping %s/>' % attrs(m))
            if nonascii(t):
                texts.append("SET_LOV_COLUMN_PROPERTY('%s', %d, TITLE, tx('%s'));" % (lov, i, WORDS.key(t)))
        lovx.append('    </LOV>')
    return groups, lovx


def ctl_item(c, say):
    """an item of the block CTL: (name, kind, x, y, width, text, options)
       kind: button (its label), text / date / secret (a prompt on its left), display, hidden"""
    name, kind, x, y, w, text, o = c
    a = dict(Name=name)
    if kind == 'button':
        a.update(ItemType='Push Button', CanvasName=CANVAS, XPosition=x, YPosition=y, Width=w, Height=26,
                 Label=ascii_text(text))
        say('CTL.' + name, 'LABEL', text)
        return a
    if kind == 'hidden':
        a.update(ItemType='Text Item', Visible='false', DatabaseItem='false',
                 DataType='Number' if o.get('num') else 'Char', MaximumLength=o.get('len', 40))
        return a
    # a date: text DD/MM/YYYY (ui.day reads it so on every runtime; ui.init puts today in it)
    a.update(ItemType='Display Item' if kind == 'display' else 'Text Item', CanvasName=CANVAS,
             XPosition=x, YPosition=y, Width=w, Height=ROW_H, DatabaseItem='false',
             DataType='Number' if o.get('num') else 'Char',
             MaximumLength=o.get('len', 14 if o.get('num') else 10 if kind == 'date' else 100))
    if text:
        a.update(Prompt=ascii_text(text), PromptAttachmentEdge='Top', PromptAttachmentOffset=2)
        say('CTL.' + name, 'PROMPT_TEXT', text)
    if kind == 'secret':
        a['ConcealData'] = 'true'          # a PIN typed: dots on the screen
    if o.get('num'):
        a['Justification'] = 'Right'
    if o.get('upper'):
        a['CaseRestriction'] = 'Upper'
    if 'init' in o:
        a['InitializeValue'] = o['init']
    if o.get('lov'):
        a['LovName'] = o['lov']
        a['ValidateFromList'] = 'false'
    return a


FIND_CTL = [('FIND', 'button', 10, 10, 110, 'Βρες...', {}),
            ('FIND_TEXT', 'display', 126, 12, 300, '', {}),
            ('ALL', 'button', 432, 10, 110, 'Όλα', {}),
            ('FIND_ID', 'hidden', 0, 0, 0, '', {'num': True, 'len': 20})]


def build(name, f):
    """a form: f['blocks'] (the first the master; a detail with 'where' on the master), or one block
    (f['block'], f['table'], f['cols']); the block CTL (Find..., All, and f['ctl']); the LOVs"""
    texts = ["SET_WINDOW_PROPERTY('%s', TITLE, tx('%s'));" % (WINDOW, WORDS.key(f['title']))] + menu_texts()

    def say(item, prop, text):
        if nonascii(text):
            texts.append("SET_ITEM_PROPERTY('%s', %s, tx('%s'));" % (item, prop, WORDS.key(text)))

    # no block of a table (the menu): f['blocks'] = []
    blocks = f['blocks'] if 'blocks' in f else [dict(name=f['block'], table=f['table'], order=f['order'],
                                                     cols=f['cols'], top=TOP, rows=ROWS)]
    width, height, out_blocks = 0, 0, []
    for b in blocks:
        items, w = block_items(b['name'], b['cols'], b['top'], say)
        width = max(width, w + 6)
        height = max(height, b['top'] + b['rows'] * ROW_H + 40)
        out_blocks.append((b, items))
    ctl = [ctl_item(c, say) for c in (FIND_CTL if 'find' in f else []) + f.get('ctl', [])]
    tb, tbw = toolbar_items(say)           # (before program(): its labels go to ui.init)
    width = max(width, tbw)
    for c in f.get('ctl', []):
        if c[1] == 'date':
            # (year_start: the 1st of January, e.g. the start of a ledger)
            texts.append("COPY(to_char(%s, 'DD/MM/YYYY'), 'CTL.%s');"
                         % ("trunc(sysdate, 'YYYY')" if c[6].get('year_start') else 'sysdate', c[0]))
        elif 'init' in c[6]:
            # (the initial value of an item of CTL did not show on the web: put by ui.init too)
            texts.append("COPY('%s', 'CTL.%s');" % (c[6]['init'], c[0]))
    for c in f.get('ctl', []):
        if c[1] != 'hidden':
            width = max(width, c[2] + c[4] + 10)
            height = max(height, c[3] + 40)

    lovs = ([('LOV_FIND', f['find_title'], f['find'][0],
              [(n, w, t, 'CTL.' + r if r else None) for n, w, t, r in f['find'][1]])] if 'find' in f else []) \
        + f.get('lovs', [])
    groups, lovx = lov_xml(lovs, texts)

    master = blocks[0] if blocks else dict(name='')
    detail = blocks[1]['name'] if len(blocks) > 1 else ''
    detail2 = blocks[2]['name'] if len(blocks) > 2 else ''
    spec, body = program(name, dict(block=master['name'], where=master.get('where', ''), detail=detail,
                                    detail2=detail2), texts)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<Module version="141200000" xmlns="http://xmlns.oracle.com/Forms">',
           '  <FormModule Name="%s" Title=%s ConsoleWindow="%s" MenuModule="%s">'
           % (name, quoteattr(greeklish(f['title'])), WINDOW, MENU_MODULE),
           '    <Coordinate CharacterCellWidth="7" CharacterCellHeight="14" CoordinateSystem="Real" '
           'RealUnit="Pixel" DefaultFontScaling="true"/>']
    for b, items in out_blocks:
        extra = ''
        if b.get('where'):
            extra += ' WhereClause=%s' % quoteattr(b['where'])
        if b.get('read_only'):
            extra += ' InsertAllowed="false" UpdateAllowed="false" DeleteAllowed="false"'
        out.append('    <Block Name="%s" QueryDataSourceName="%s" DMLDataName="%s" OrderByClause="%s" '
                   'RecordsDisplayCount="%d"%s>' % (b['name'], b['table'], b['table'], b['order'], b['rows'], extra))
        out += ['      <Item %s/>' % attrs(a) for a in items]
        out += [trigger('POST-QUERY', 'ui.post_query(:SYSTEM.TRIGGER_BLOCK);', '      '),
                trigger('WHEN-VALIDATE-ITEM', 'ui.validate(:SYSTEM.TRIGGER_ITEM);', '      ')]
        if (b is master and detail) or (detail2 and b['name'] == detail):
            out.append(trigger('WHEN-NEW-RECORD-INSTANCE', 'ui.master(:SYSTEM.TRIGGER_BLOCK);', '      '))
        out.append('    </Block>')
    out.append('    <Block Name="CTL" DatabaseBlock="false" RecordsDisplayCount="1">')
    out += ['      <Item %s/>' % attrs(a) for a in ctl]
    out += [trigger('WHEN-BUTTON-PRESSED', 'ui.press(:SYSTEM.TRIGGER_ITEM);', '      '),
            '    </Block>']
    out.append('    <Block Name="TB" DatabaseBlock="false" RecordsDisplayCount="1">')
    out += ['      <Item %s/>' % attrs(a) for a in tb]
    out += [trigger('WHEN-BUTTON-PRESSED', 'ui.tool(:SYSTEM.TRIGGER_ITEM);', '      '),
            '    </Block>',
            '    <Canvas Name="%s" WindowName="%s" Width="%d" Height="%d"/>' % (CANVAS, WINDOW, width, height),
            '    <Canvas Name="%s" WindowName="%s" CanvasType="Horizontal Toolbar" Width="%d" Height="%d"/>'
            % (TB_CANVAS, WINDOW, width, TB_H)]
    out += groups + lovx
    out += ['    <ProgramUnit Name="UI" ProgramUnitType="Package Spec" ProgramUnitText=%s/>' % quoteattr(spec),
            '    <ProgramUnit Name="UI" ProgramUnitType="Package Body" ProgramUnitText=%s/>' % quoteattr(body),
            trigger('WHEN-NEW-FORM-INSTANCE', 'ui.init;', '    '),
            trigger('ON-ERROR', 'ui.on_error(ERROR_CODE, ERROR_TYPE, ERROR_TEXT, DBMS_ERROR_TEXT);', '    '),
            trigger('WHEN-WINDOW-CLOSED', 'exit_form;', '    '),
            trigger('WHEN-MOUSE-DOUBLECLICK', 'ui.dblclick(:SYSTEM.TRIGGER_ITEM);', '    '),
            '    <Window Name="%s" Title=%s XPosition="0" YPosition="0" Width="%d" Height="%d" '
            'HorizontalToolbarCanvasName="%s"/>'
            % (WINDOW, quoteattr(greeklish(f['title'])), width, height + TB_H, TB_CANVAS),
            '  </FormModule>',
            '</Module>']
    xml = '\n'.join(out) + '\n'
    bad = sorted({c for c in xml if ord(c) > 127})
    if bad:
        raise SystemExit('%s.xml: not ASCII: %r' % (name, ''.join(bad)))
    return xml, spec, body


def text_sql():
    sql = ['-- MM_TEXT.sql -- made by forms/mkforms.py: the Greek of the forms (prompts, labels, titles,',
           '-- messages), which the forms ask for when they open (XML2Forms does not carry Greek into a',
           '-- form). UTF-8: run by INSTALL.sql, or by the build scripts with NLS_LANG ...AL32UTF8.',
           'create or replace package mm_text as',
           '  function t(p_key varchar2) return varchar2;',
           'end mm_text;', '/', '',
           'create or replace package body mm_text as',
           '  function t(p_key varchar2) return varchar2 is',
           '  begin',
           '    return case p_key']
    for k in sorted(WORDS.words):
        sql.append("      when '%s' then '%s'" % (k, WORDS.words[k].replace("'", "''")))
    sql += ['      else p_key', '    end;', '  end;', 'end mm_text;', '/', '']
    return '\n'.join(sql)


def main():
    made = {}
    for name, f in FORMS.items():
        made[name] = build(name, f)
    for name, (xml, _, _) in made.items():
        open(os.path.join(HERE, name + '.xml'), 'w', encoding='ascii', newline='\n').write(xml)
    open(os.path.join(HERE, MENU_MODULE + '.xml'), 'w', encoding='ascii', newline='\n').write(menu_xml())
    open(os.path.join(DB, 'MM_TEXT.sql'), 'w', encoding='utf-8', newline='\n').write(text_sql())
    print('%s, %s (menu); MM_TEXT.sql: %d words' % (', '.join(made), MENU_MODULE, len(WORDS.words)))
    return made


if __name__ == '__main__':
    main()
