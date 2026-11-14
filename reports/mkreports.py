#!/usr/bin/env python3
"""mkreports.py -- the reports of the mini market in the XML of Oracle Reports 14 (rwconverter makes
the .rdf: build_reports.ps1 on Windows):

  MM_LEDGER_I   the ledger of an item (quantities, 3 decimals)
  MM_LEDGER_P   the ledger of a customer (P_KIND=C) or a supplier (P_KIND=S) (money, 2 decimals)

The parameters: P_KIND (I, C, S), P_ID, P_FROM and P_TO (DD/MM/YYYY). The rows: mm_ledger.report_rows
of the database (db/MM_LEDGER.sql). On every page, on top "from the carry-over" (από μεταφορά): the
totals before its first row (the first PRIOR_*, a summary reset at the page); at the bottom "to the
carry-over" (σε μεταφορά): with its last row (the last CUM_* and BALANCE). After the last row: the
totals of the period, the balance before it and at its end.

The XML is ASCII, as the forms: the Greek (the title, the headings, the words) comes from the
database when the report runs (mm_ledger.title and mm_ledger.label, in formula columns).

  python3 mkreports.py        (writes MM_LEDGER_I.xml and MM_LEDGER_P.xml here)
"""
import os
from xml.sax.saxutils import quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))

# A4 portrait, in inches; the body under the heading of the page, above its foot
PAGE_W, PAGE_H = 8.27, 11.69
LEFT = 0.4
BODY_Y, BODY_H = 1.35, 9.55
FOOT_Y = BODY_Y + BODY_H + 0.1
ROW_H = 0.17
FONT, SIZE = 'Arial', 8          # (uifont.ali of the Reports Server: Arial -> arial.ttf, with Greek)

# the columns: (item, x in the body, width, alignment); the heading of the page has the same x + LEFT
COLS = [('LDATE', 0.00, 0.72, 'start'), ('DOC_TEXT', 0.75, 0.82, 'start'), ('DESCR', 1.60, 2.55, 'start'),
        ('DEBIT', 4.18, 0.95, 'end'), ('CREDIT', 5.16, 0.95, 'end'), ('BALANCE', 6.14, 1.10, 'end')]
X = {c: (x, w, a) for c, x, w, a in COLS}

# the data of the query: (name, datatype, width)
ITEMS = [('SEQ', 'number', 22), ('LDATE', 'date', 9), ('DOC_TEXT', 'vchar2', 40), ('DESCR', 'vchar2', 300),
         ('DEBIT', 'number', 22), ('CREDIT', 'number', 22), ('BALANCE', 'number', 22),
         ('PRIOR_DEBIT', 'number', 22), ('PRIOR_CREDIT', 'number', 22), ('PRIOR_BALANCE', 'number', 22),
         ('CUM_DEBIT', 'number', 22), ('CUM_CREDIT', 'number', 22)]

# the summaries: (name, source, function, reset); a page one only in the margin
SUMMARIES = [('CS_PF_DEBIT', 'PRIOR_DEBIT', 'first', 'page'), ('CS_PF_CREDIT', 'PRIOR_CREDIT', 'first', 'page'),
             ('CS_PF_BALANCE', 'PRIOR_BALANCE', 'first', 'page'),
             ('CS_PL_DEBIT', 'CUM_DEBIT', 'last', 'page'), ('CS_PL_CREDIT', 'CUM_CREDIT', 'last', 'page'),
             ('CS_PL_BALANCE', 'BALANCE', 'last', 'page'),
             ('CS_T_DEBIT', 'DEBIT', 'sum', 'report'), ('CS_T_CREDIT', 'CREDIT', 'sum', 'report'),
             ('CS_OPEN', 'PRIOR_BALANCE', 'first', 'report'), ('CS_CLOSE', 'BALANCE', 'last', 'report')]

# the words: formula columns of the report, from the database
LABELS = ['DATE', 'DOC', 'DESCR', 'DEBIT', 'CREDIT', 'BALANCE', 'FROM_CARRY', 'TO_CARRY', 'TOTALS',
          'OPEN', 'CLOSE', 'PAGE']

QUERY = ("select seq, ldate, doc_text, descr, debit, credit, balance, prior_debit, prior_credit, "
         "prior_balance, cum_debit, cum_credit\n"
         "from table(mm_ledger.report_rows(:P_KIND, :P_ID, to_date(:P_FROM, 'DD/MM/YYYY'), "
         "to_date(:P_TO, 'DD/MM/YYYY')))\norder by seq")

REPORTS = {
    'MM_LEDGER_I': dict(kind='I', mask='NNNGNNNGNN0D000'),
    'MM_LEDGER_P': dict(kind='C', mask='NNNGNNNGNN0D00'),
}


def attrs(d):
    return ' '.join('%s=%s' % (k, quoteattr(str(v))) for k, v in d.items())


def geo(x, y, w, h):
    return '<geometryInfo x="%.5f" y="%.5f" width="%.5f" height="%.5f"/>' % (x, y, w, h)


def field(name, source, x, y, w, h=ROW_H, align='start', mask=None, bold=False, size=SIZE, pad='        '):
    a = dict(name=name, source=source, minWidowLines=1, spacing=0, alignment=align)
    if mask:
        a['formatMask'] = mask
    return '\n'.join([
        pad + '<field %s>' % attrs(a),
        pad + '  <font face="%s" size="%d"%s/>' % (FONT, size, ' bold="yes"' if bold else ''),
        pad + '  ' + geo(x, y, w, h),
        pad + '</field>'])


def formula_name(label):
    return 'CF_L_' + label


def build(name, r):
    mask = r['mask']
    out = ['<?xml version="1.0" encoding="UTF-8" ?>',
           '<report name="%s" DTDVersion="9.0.2.0.10" unitOfMeasurement="inch">' % name.lower(),
           '  <data>']
    for p, dt, w, init in (('P_KIND', 'character', 1, r['kind']), ('P_ID', 'number', 10, None),
                           ('P_FROM', 'character', 10, None), ('P_TO', 'character', 10, None)):
        a = dict(name=p, datatype=dt, width=w)
        if init:
            a['initialValue'] = init
        out.append('    <userParameter %s/>' % attrs(a))
    out += ['    <dataSource name="Q_ROWS">',
            '      <select>',
            '      <![CDATA[%s]]>' % QUERY,
            '      </select>',
            '      <group name="G_ROWS">']
    for i, (n, dt, w) in enumerate(ITEMS, 1):
        out += ['        <dataItem %s>' % attrs(dict(name=n, datatype=dt, columnOrder=10 + i, width=w,
                                                       defaultLabel=n.title())),
                '          <dataDescriptor %s/>' % attrs(dict(expression=n.lower(), descriptiveExpression=n,
                                                                order=i, width=w)),
                '        </dataItem>']
    out += ['      </group>', '    </dataSource>']
    for n, src, fn, reset in SUMMARIES:
        out.append('    <summary %s/>' % attrs(dict(name=n, source=src, function=fn, width=22, precision=12,
                                                    scale=3, reset=reset, compute='report')))
    out.append('    <formula %s/>' % attrs(dict(name='CF_TITLE', source='cf_titleformula', datatype='character',
                                                width=300)))
    out.append('    <formula %s/>' % attrs(dict(name='CF_PERIOD', source='cf_periodformula', datatype='character',
                                                width=100)))
    for lb in LABELS:
        out.append('    <formula %s/>' % attrs(dict(name=formula_name(lb), source=formula_name(lb).lower() + 'formula',
                                                    datatype='character', width=100)))
    out.append('  </data>')

    # the layout: the rows and after them the totals, in the body; the heading and the foot of each
    # page (with the carry-over) in the margin
    out += ['  <layout>',
            '  <section name="main" width="%.5f" height="%.5f">' % (PAGE_W, PAGE_H),
            '    <body width="%.5f" height="%.5f">' % (PAGE_W - 2 * LEFT, BODY_H),
            '      <location x="%.5f" y="%.5f"/>' % (LEFT, BODY_Y),
            '      <frame name="M_ROWS">',
            '        ' + geo(0, 0, 7.30, ROW_H * 5),
            '        <generalLayout verticalElasticity="variable"/>',
            '        <repeatingFrame name="R_ROWS" source="G_ROWS" printDirection="down" minWidowRecords="1" '
            'columnMode="no">',
            '          ' + geo(0, 0, 7.30, ROW_H),
            '          <generalLayout verticalElasticity="expand"/>']
    for c, x, w, a in COLS:
        m = 'DD/MM/YYYY' if c == 'LDATE' else mask if a == 'end' else None
        out.append(field('F_' + c, c, x, 0, w, align=a, mask=m, pad='          '))
    out.append('        </repeatingFrame>')
    # the totals after the last row
    y = ROW_H * 1.6
    x, w, _ = X['DESCR']
    rows = [('F_TOTALS', formula_name('TOTALS'), [('F_T_DEBIT', 'CS_T_DEBIT', 'DEBIT'), ('F_T_CREDIT', 'CS_T_CREDIT', 'CREDIT')]),
            ('F_OPEN', formula_name('OPEN'), [('F_OPEN_B', 'CS_OPEN', 'BALANCE')]),
            ('F_CLOSE', formula_name('CLOSE'), [('F_CLOSE_B', 'CS_CLOSE', 'BALANCE')])]
    for k, (fname, label, vals) in enumerate(rows):
        yy = y + k * ROW_H * 1.2
        out.append(field(fname, label, x, yy, w, align='end', bold=True))
        for vn, src, col in vals:
            cx, cw, _ = X[col]
            out.append(field(vn, src, cx, yy, cw, align='end', mask=mask, bold=True))
    out += ['      </frame>', '    </body>', '    <margin>']
    # the heading: the title, the period, the page; the headings of the columns; from the carry-over
    out.append(field('F_TITLE', 'CF_TITLE', LEFT, 0.30, 5.6, h=0.24, bold=True, size=12))
    out.append(field('F_PERIOD', 'CF_PERIOD', LEFT, 0.58, 5.0, h=0.2, size=9))
    out.append(field('F_L_PAGE', formula_name('PAGE'), LEFT + 5.9, 0.30, 0.6, h=0.2, align='end', size=9))
    out.append(field('F_PAGE', 'PageNumber', LEFT + 6.55, 0.30, 0.6, h=0.2, size=9))
    for c, lb in (('LDATE', 'DATE'), ('DOC_TEXT', 'DOC'), ('DESCR', 'DESCR'), ('DEBIT', 'DEBIT'),
                  ('CREDIT', 'CREDIT'), ('BALANCE', 'BALANCE')):
        x, w, a = X[c]
        out.append(field('F_H_' + c, formula_name(lb), LEFT + x, 0.88, w, align=a, bold=True))
    for fname, label, vals, yy in (
            ('F_FROM', 'FROM_CARRY', [('F_PF_DEBIT', 'CS_PF_DEBIT', 'DEBIT'), ('F_PF_CREDIT', 'CS_PF_CREDIT', 'CREDIT'),
                                      ('F_PF_BALANCE', 'CS_PF_BALANCE', 'BALANCE')], 1.10),
            ('F_TO', 'TO_CARRY', [('F_PL_DEBIT', 'CS_PL_DEBIT', 'DEBIT'), ('F_PL_CREDIT', 'CS_PL_CREDIT', 'CREDIT'),
                                  ('F_PL_BALANCE', 'CS_PL_BALANCE', 'BALANCE')], FOOT_Y)):
        x, w, _ = X['DESCR']
        out.append(field(fname, formula_name(label), LEFT + x, yy, w, align='end', bold=True))
        for vn, src, col in vals:
            cx, cw, _ = X[col]
            out.append(field(vn, src, LEFT + cx, yy, cw, align='end', mask=mask, bold=True))
    out += ['    </margin>', '  </section>', '  </layout>', '  <programUnits>']

    def fn(n, body):
        out.extend(['    <function name="%s" returnType="character">' % n,
                    '      <textSource>',
                    '      <![CDATA[function %s return Char is\nbegin\n  %s\nend;]]>' % (n, body),
                    '      </textSource>',
                    '    </function>'])
    fn('cf_titleformula', 'return mm_ledger.title(:P_KIND, :P_ID);')
    fn('cf_periodformula', "return mm_ledger.label('PERIOD') || ': ' || :P_FROM || ' - ' || :P_TO;")
    for lb in LABELS:
        fn(formula_name(lb).lower() + 'formula', "return mm_ledger.label('%s', :P_KIND);" % lb)
    out += ['  </programUnits>',
            '  <reportPrivate defaultReportType="tabular" versionFlags2="0" templateName=""/>',
            '</report>']
    xml = '\n'.join(out) + '\n'
    assert all(ord(c) < 128 for c in xml), name
    return xml


def main():
    made = {}
    for name, r in REPORTS.items():
        made[name] = build(name, r)
        open(os.path.join(HERE, name + '.xml'), 'w', encoding='ascii', newline='\n').write(made[name])
    print(', '.join(made))
    return made


if __name__ == '__main__':
    main()
