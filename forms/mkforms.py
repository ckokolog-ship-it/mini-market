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
            C('VAT_RATE', '%', 40, num=True, db=False, display=True),
            C('UNIT', 'Μονάδα', 60, len=3, req=True, upper=True, lov='LOV_UNIT', init='PCS'),
            C('PRICE', 'Τιμή λιαν.', 70, num=True, req=True),
            C('COST', 'Κόστος', 70, num=True, req=True, init='0'),
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
    body = body.replace('NULL; -- TEXTS', ('\n' + ' ' * 4).join(texts))
    return spec, body


def build(name, f):
    texts = ["SET_WINDOW_PROPERTY('%s', TITLE, tx('%s'));" % (WINDOW, WORDS.key(f['title']))]
    blk, out_items, ctl = f['block'], [], []

    def say(item, prop, text):
        if nonascii(text):
            texts.append("SET_ITEM_PROPERTY('%s', %s, tx('%s'));" % (item, prop, WORDS.key(text)))

    # the block of the table
    x = 10
    for c in f['cols']:
        a = dict(Name=c['name'])
        if c.get('hidden'):
            a.update(ItemType='Text Item', Visible='false')
        else:
            a.update(ItemType='Check Box' if c.get('check') else
                     'Display Item' if c.get('display') else 'Text Item',
                     CanvasName=CANVAS, XPosition=x, YPosition=TOP, Width=c['width'], Height=ROW_H,
                     Prompt=ascii_text(c['prompt']), PromptAttachmentEdge='Top', PromptAttachmentOffset=2)
            x += c['width'] + 4
            say('%s.%s' % (blk, c['name']), 'PROMPT_TEXT', c['prompt'])
        if c.get('check'):
            a.update(CheckedValue='Y', UncheckedValue='N', CheckBoxOtherValues='Not Allowed',
                     Label='', DataType='Char', MaximumLength=1)
        else:
            a.update(DataType='Number' if c.get('num') else 'Char',
                     MaximumLength=c.get('len', 14 if c.get('num') else 30))
        if c.get('num') and not c.get('hidden'):
            a['Justification'] = 'Right'
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
    width = x + 6

    # the block CTL: Find... (its LOV returns FIND_ID and FIND_TEXT), All
    ctl.append(dict(Name='FIND', ItemType='Push Button', CanvasName=CANVAS, XPosition=10, YPosition=10,
                    Width=110, Height=26, Label='Vres...'))
    say('CTL.FIND', 'LABEL', 'Βρες...')
    ctl.append(dict(Name='FIND_TEXT', ItemType='Display Item', CanvasName=CANVAS, XPosition=126,
                    YPosition=12, Width=300, Height=ROW_H, DatabaseItem='false', DataType='Char',
                    MaximumLength=100))
    ctl.append(dict(Name='ALL', ItemType='Push Button', CanvasName=CANVAS, XPosition=432, YPosition=10,
                    Width=110, Height=26, Label='Ola'))
    say('CTL.ALL', 'LABEL', 'Όλα')
    ctl.append(dict(Name='FIND_ID', ItemType='Text Item', Visible='false', DatabaseItem='false',
                    DataType='Number', MaximumLength=20))

    # the record groups and the LOVs: FIND first
    lovs = [('LOV_FIND', f['find_title'], f['find'][0],
             [(n, w, t, 'CTL.' + r if r else None) for n, w, t, r in f['find'][1]])] + f['lovs']
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

    spec, body = program(name, f, texts)
    height = TOP + ROWS * ROW_H + 40
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<Module version="141200000" xmlns="http://xmlns.oracle.com/Forms">',
           '  <FormModule Name="%s" Title=%s ConsoleWindow="%s" MenuModule="DEFAULT&amp;SMARTBAR">'
           % (name, quoteattr(greeklish(f['title'])), WINDOW),
           '    <Coordinate CharacterCellWidth="7" CharacterCellHeight="14" CoordinateSystem="Real" '
           'RealUnit="Pixel" DefaultFontScaling="true"/>',
           '    <Block Name="%s" QueryDataSourceName="%s" DMLDataName="%s" OrderByClause="%s" '
           'RecordsDisplayCount="%d">' % (blk, f['table'], f['table'], f['order'], ROWS)]
    out += ['      <Item %s/>' % attrs(a) for a in out_items]
    out += [trigger('POST-QUERY', 'ui.post_query(:SYSTEM.TRIGGER_BLOCK);', '      '),
            trigger('WHEN-VALIDATE-ITEM', 'ui.validate(:SYSTEM.TRIGGER_ITEM);', '      '),
            '    </Block>',
            '    <Block Name="CTL" DatabaseBlock="false" RecordsDisplayCount="1">']
    out += ['      <Item %s/>' % attrs(a) for a in ctl]
    out += [trigger('WHEN-BUTTON-PRESSED', 'ui.press(:SYSTEM.TRIGGER_ITEM);', '      '),
            '    </Block>',
            '    <Canvas Name="%s" WindowName="%s" Width="%d" Height="%d"/>' % (CANVAS, WINDOW, width, height)]
    out += groups + lovx
    out += ['    <ProgramUnit Name="UI" ProgramUnitType="Package Spec" ProgramUnitText=%s/>' % quoteattr(spec),
            '    <ProgramUnit Name="UI" ProgramUnitType="Package Body" ProgramUnitText=%s/>' % quoteattr(body),
            trigger('WHEN-NEW-FORM-INSTANCE', 'ui.init;', '    '),
            trigger('ON-ERROR', 'ui.on_error(ERROR_CODE, ERROR_TYPE, ERROR_TEXT, DBMS_ERROR_TEXT);', '    '),
            trigger('WHEN-WINDOW-CLOSED', 'exit_form;', '    '),
            '    <Window Name="%s" Title=%s XPosition="0" YPosition="0" Width="%d" Height="%d"/>'
            % (WINDOW, quoteattr(greeklish(f['title'])), width, height),
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
    open(os.path.join(DB, 'MM_TEXT.sql'), 'w', encoding='utf-8', newline='\n').write(text_sql())
    print('%s; MM_TEXT.sql: %d words' % (', '.join(made), len(WORDS.words)))
    return made


if __name__ == '__main__':
    main()
