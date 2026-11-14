#!/usr/bin/env python3
"""mkreports.py -- the reports of the mini market in the XML of Oracle Reports 14 (rwconverter makes
the .rdf: build_reports.ps1 on Windows):

  MM_LEDGER_I   the ledger of an item (quantities, 3 decimals)
  MM_LEDGER_P   the ledger of a customer (P_KIND=C) or a supplier (P_KIND=S) (money, 2 decimals)
  MM_SALES      the sales of each day, by month (P_FROM, P_TO)
  MM_VAT        the VAT of the sales and of the purchases, by month and rate (P_FROM, P_TO)
  MM_MIN_STOCK  the items under their minimum stock, by category

The parameters: P_KIND (I, C, S), P_ID, P_FROM and P_TO (DD/MM/YYYY). The rows: mm_ledger.report_rows
of the database (db/MM_LEDGER.sql). On every page, on top "from the carry-over" (από μεταφορά): the
totals before its first row (the first PRIOR_*, a summary reset at the page); at the bottom "to the
carry-over" (σε μεταφορά): with its last row (the last CUM_* and BALANCE). After the last row: the
totals of the period, the balance before it and at its end.

The XML is ASCII, as the forms: the Greek (the title, the headings, the words) comes from the
database when the report runs (mm_ledger.title and mm_ledger.label, in formula columns).

  python3 mkreports.py        (writes MM_*.xml here)
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
            '        ' + geo(0, 0, 7.30, ROW_H * 6),
            '        <generalLayout verticalElasticity="variable"/>',
            '        <repeatingFrame name="R_ROWS" source="G_ROWS" printDirection="down" minWidowRecords="1" '
            'columnMode="no">',
            '          ' + geo(0, 0, 7.30, ROW_H),
            '          <generalLayout verticalElasticity="expand"/>']
    for c, x, w, a in COLS:
        m = 'DD/MM/YYYY' if c == 'LDATE' else mask if a == 'end' else None
        out.append(field('F_' + c, c, x, 0, w, align=a, mask=m, pad='          '))
    out.append('        </repeatingFrame>')
    # the totals after the last row: a frame of their own under the rows, pushed down with them as
    # one (fields alone at the bottom edge of M_ROWS stayed where they were drawn, on the 5th row)
    y = ROW_H * 1.5
    out += ['        <frame name="M_TOTALS">',
            '          ' + geo(0, y, 7.30, ROW_H * 3.8)]
    x, w, _ = X['DESCR']
    rows = [('F_OPEN', formula_name('OPEN'), [('F_OPEN_B', 'CS_OPEN', 'BALANCE')]),
            ('F_TOTALS', formula_name('TOTALS'), [('F_T_DEBIT', 'CS_T_DEBIT', 'DEBIT'), ('F_T_CREDIT', 'CS_T_CREDIT', 'CREDIT')]),
            ('F_CLOSE', formula_name('CLOSE'), [('F_CLOSE_B', 'CS_CLOSE', 'BALANCE')])]
    for k, (fname, label, vals) in enumerate(rows):
        yy = y + ROW_H * 0.2 + k * ROW_H * 1.2
        out.append(field(fname, label, x, yy, w, align='end', bold=True, pad='          '))
        for vn, src, col in vals:
            cx, cw, _ = X[col]
            out.append(field(vn, src, cx, yy, cw, align='end', mask=mask, bold=True, pad='          '))
    out += ['        </frame>', '      </frame>', '    </body>', '    <margin>']
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


# -- the tables: sales, VAT, minimum stock --------------------------------------------------------
# A query of a view of db/MM_REPORT.sql; its rows under a break (a month, a category) with the
# subtotals of the break after them, the grand totals at the end. The headings, the title, the
# period and the words of the totals from mm_report (the Greek).
#   items    (name, datatype, width) of the query; brk: the items of the break group (the first is
#            the order, the second shown)
#   cols     (item, x, width, alignment, mask): the columns of the rows; their heading mm_report.label(item)
#   sums     (item, function): subtotal and grand total under that column
#   words    the keys of the label of a subtotal and of the grand total
DAY_MASK, MONEY, COUNT = 'DD/MM/YYYY', 'NNNGNNNGNN0D00', 'NNNGNNNGNN0'
PERIOD = [('P_FROM', 'character', 10), ('P_TO', 'character', 10)]
BETWEEN = "between to_date(:P_FROM, 'DD/MM/YYYY') and to_date(:P_TO, 'DD/MM/YYYY')"
TABLES = {
    'MM_SALES': dict(
        title='SALES', params=PERIOD,
        query=("select to_char(day, 'YYYY-MM') month_key, to_char(day, 'MM/YYYY') month_text, day, alp_docs, "
               "alp_total, tpy_total, ppy_total, total\nfrom mm_sales_day\nwhere day " + BETWEEN + "\norder by day"),
        items=[('MONTH_KEY', 'vchar2', 7), ('MONTH_TEXT', 'vchar2', 7), ('DAY', 'date', 9), ('ALP_DOCS', 'number', 22),
               ('ALP_TOTAL', 'number', 22), ('TPY_TOTAL', 'number', 22), ('PPY_TOTAL', 'number', 22),
               ('TOTAL', 'number', 22)],
        brk=['MONTH_KEY', 'MONTH_TEXT'],
        cols=[('DAY', 0.00, 0.90, 'start', DAY_MASK), ('ALP_DOCS', 1.00, 0.80, 'end', COUNT),
              ('ALP_TOTAL', 1.90, 1.25, 'end', MONEY), ('TPY_TOTAL', 3.25, 1.25, 'end', MONEY),
              ('PPY_TOTAL', 4.60, 1.25, 'end', MONEY), ('TOTAL', 5.95, 1.30, 'end', MONEY)],
        sums=[('ALP_DOCS', 'sum'), ('ALP_TOTAL', 'sum'), ('TPY_TOTAL', 'sum'), ('PPY_TOTAL', 'sum'), ('TOTAL', 'sum')],
        words=('SUBTOTAL', 'GRAND')),
    'MM_VAT': dict(
        title='VAT', params=PERIOD,
        query=("select to_char(day, 'YYYY-MM') month_key, to_char(day, 'MM/YYYY') month_text, "
               "vat_code || ' ' || vat_rate || '%' vat_text, sum(s_net) s_net, sum(s_vat) s_vat, sum(p_net) p_net, "
               "sum(p_vat) p_vat, sum(s_vat) - sum(p_vat) payable\nfrom mm_vat_day\nwhere day " + BETWEEN +
               "\ngroup by to_char(day, 'YYYY-MM'), to_char(day, 'MM/YYYY'), vat_code, vat_rate\norder by 1, 3"),
        items=[('MONTH_KEY', 'vchar2', 7), ('MONTH_TEXT', 'vchar2', 7), ('VAT_TEXT', 'vchar2', 10),
               ('S_NET', 'number', 22), ('S_VAT', 'number', 22), ('P_NET', 'number', 22), ('P_VAT', 'number', 22),
               ('PAYABLE', 'number', 22)],
        brk=['MONTH_KEY', 'MONTH_TEXT'],
        cols=[('VAT_TEXT', 0.00, 0.80, 'start', None), ('S_NET', 0.90, 1.20, 'end', MONEY),
              ('S_VAT', 2.20, 1.15, 'end', MONEY), ('P_NET', 3.45, 1.20, 'end', MONEY),
              ('P_VAT', 4.75, 1.15, 'end', MONEY), ('PAYABLE', 6.00, 1.25, 'end', MONEY)],
        sums=[('S_NET', 'sum'), ('S_VAT', 'sum'), ('P_NET', 'sum'), ('P_VAT', 'sum'), ('PAYABLE', 'sum')],
        words=('SUBTOTAL', 'GRAND')),
    'MM_MIN_STOCK': dict(
        title='MIN_STOCK', params=[],
        query=("select category, code, name, unit, mm_report.qty(stock) stock, mm_report.qty(min_stock) min_stock, "
               "mm_report.qty(missing) missing, supplier\nfrom mm_min_stock\norder by category, code"),
        items=[('CATEGORY', 'vchar2', 60), ('CODE', 'vchar2', 20), ('NAME', 'vchar2', 100), ('UNIT', 'vchar2', 3),
               ('STOCK', 'vchar2', 30), ('MIN_STOCK', 'vchar2', 30), ('MISSING', 'vchar2', 30),
               ('SUPPLIER', 'vchar2', 100)],
        brk=['CATEGORY'],
        cols=[('CODE', 0.00, 0.70, 'start', None), ('NAME', 0.75, 2.15, 'start', None), ('UNIT', 2.95, 0.40, 'start', None),
              ('STOCK', 3.40, 0.70, 'end', None), ('MIN_STOCK', 4.15, 0.70, 'end', None),
              ('MISSING', 4.90, 0.70, 'end', None), ('SUPPLIER', 5.70, 1.60, 'start', None)],
        sums=[('CODE', 'count')],
        words=('SUBTOTAL_CAT', 'GRAND_CAT')),
}


def build_table(name, t):
    """a report of rows under a break, with subtotals and grand totals"""
    brk = t['brk']
    shown = brk[-1]
    out = ['<?xml version="1.0" encoding="UTF-8" ?>',
           '<report name="%s" DTDVersion="9.0.2.0.10" unitOfMeasurement="inch">' % name.lower(),
           '  <data>']
    for p, dt, w in t['params']:
        out.append('    <userParameter %s/>' % attrs(dict(name=p, datatype=dt, width=w)))
    out += ['    <dataSource name="Q_ROWS">', '      <select>', '      <![CDATA[%s]]>' % t['query'], '      </select>']
    order = {n: i for i, (n, _, _) in enumerate(t['items'], 1)}

    def item(n, dt, w, pad):
        return [pad + '<dataItem %s>' % attrs(dict(name=n, datatype=dt, columnOrder=10 + order[n], width=w,
                                                   defaultLabel=n.title())),
                pad + '  <dataDescriptor %s/>' % attrs(dict(expression=n.lower(), descriptiveExpression=n,
                                                            order=order[n], width=w)),
                pad + '</dataItem>']
    out.append('      <group name="G_BRK">')
    for n, dt, w in t['items']:
        if n in brk:
            out += item(n, dt, w, '        ')
    # the subtotals: in the break group, reset at it
    for n, fn in t['sums']:
        out.append('        <summary %s/>' % attrs(dict(name='CS_S_' + n, source=n, function=fn, width=22, precision=14,
                                                        scale=2, reset='G_BRK', compute='report')))
    out += ['      </group>', '      <group name="G_ROWS">']
    for n, dt, w in t['items']:
        if n not in brk:
            out += item(n, dt, w, '        ')
    out += ['      </group>', '    </dataSource>']
    for n, fn in t['sums']:
        out.append('    <summary %s/>' % attrs(dict(name='CS_G_' + n, source=n, function=fn, width=22, precision=14,
                                                    scale=2, reset='report', compute='report')))
    words = ['TITLE', 'PERIOD', 'PAGE', t['words'][0], t['words'][1]] + [c[0] for c in t['cols']]
    for w in words:
        out.append('    <formula %s/>' % attrs(dict(name='CF_' + w, source='cf_%sformula' % w.lower(),
                                                    datatype='character', width=200)))
    out.append('  </data>')

    cols = {c[0]: c for c in t['cols']}
    # the word of a total: on the left of the first column with a total (from the left edge), or on
    # its right if there is no room (the number of the items, under the first column)
    _, fx, fw, _, _ = cols[t['sums'][0][0]]
    lx, lw, la = (0.0, fx - 0.05, 'start') if fx >= 0.85 else (fx + fw + 0.05, 2.2, 'start')

    def total_row(prefix, word, y, pad):
        res = [field('F_%s_L' % prefix, 'CF_' + word, lx, y, lw, align=la, bold=True, pad=pad)]
        for n, fn in t['sums']:
            _, x, w, a, mask = cols[n]
            res.append(field('F_%s_%s' % (prefix, n), 'CS_%s_%s' % (prefix, n), x, y, w, align='end',
                             mask=COUNT if fn == 'count' else mask, bold=True, pad=pad))
        return res

    out += ['  <layout>',
            '  <section name="main" width="%.5f" height="%.5f">' % (PAGE_W, PAGE_H),
            '    <body width="%.5f" height="%.5f">' % (PAGE_W - 2 * LEFT, BODY_H),
            '      <location x="%.5f" y="%.5f"/>' % (LEFT, 1.15),
            '      <frame name="M_ALL">',
            '        ' + geo(0, 0, 7.30, ROW_H * 9),
            '        <generalLayout verticalElasticity="variable"/>',
            '        <repeatingFrame name="R_BRK" source="G_BRK" printDirection="down" minWidowRecords="1" '
            'columnMode="no">',
            '          ' + geo(0, 0, 7.30, ROW_H * 4.6),
            '          <generalLayout verticalElasticity="expand"/>',
            field('F_BRK', shown, 0, 0, 3.0, bold=True, size=9, pad='          '),
            '          <repeatingFrame name="R_ROWS" source="G_ROWS" printDirection="down" minWidowRecords="1" '
            'columnMode="no">',
            '            ' + geo(0, ROW_H * 1.3, 7.30, ROW_H),
            '            <generalLayout verticalElasticity="expand"/>']
    for n, x, w, a, mask in t['cols']:
        out.append(field('F_' + n, n, x, ROW_H * 1.3, w, align=a, mask=mask, pad='              '))
    out += ['          </repeatingFrame>',
            '          <frame name="M_SUB">',
            '            ' + geo(0, ROW_H * 2.6, 7.30, ROW_H * 1.6)]
    out += total_row('S', t['words'][0], ROW_H * 2.8, '            ')
    out += ['          </frame>',
            '        </repeatingFrame>',
            '        <frame name="M_GRAND">',
            '          ' + geo(0, ROW_H * 5.2, 7.30, ROW_H * 1.6)]
    out += total_row('G', t['words'][1], ROW_H * 5.4, '          ')
    out += ['        </frame>', '      </frame>', '    </body>', '    <margin>']
    out.append(field('F_TITLE', 'CF_TITLE', LEFT, 0.30, 5.6, h=0.24, bold=True, size=12))
    out.append(field('F_PERIOD', 'CF_PERIOD', LEFT, 0.58, 5.0, h=0.2, size=9))
    out.append(field('F_L_PAGE', 'CF_PAGE', LEFT + 5.9, 0.30, 0.6, h=0.2, align='end', size=9))
    out.append(field('F_PAGE', 'PageNumber', LEFT + 6.55, 0.30, 0.6, h=0.2, size=9))
    for n, x, w, a, _ in t['cols']:
        out.append(field('F_H_' + n, 'CF_' + n, LEFT + x, 0.88, w, align=a, bold=True))
    out += ['    </margin>', '  </section>', '  </layout>', '  <programUnits>']
    p = ', '.join(':' + n for n, _, _ in t['params'])
    for w in words:
        body = ("return mm_report.title('%s');" % t['title'] if w == 'TITLE' else
                'return mm_report.period(%s);' % p if w == 'PERIOD' else
                "return mm_report.label('%s');" % w)
        out += ['    <function name="cf_%sformula" returnType="character">' % w.lower(),
                '      <textSource>',
                '      <![CDATA[function cf_%sformula return Char is\nbegin\n  %s\nend;]]>' % (w.lower(), body),
                '      </textSource>',
                '    </function>']
    out += ['  </programUnits>',
            '  <reportPrivate defaultReportType="groupAbove" versionFlags2="0" templateName=""/>',
            '</report>']
    xml = '\n'.join(out) + '\n'
    assert all(ord(c) < 128 for c in xml), name
    return xml


def build_all():
    made = {name: build(name, r) for name, r in REPORTS.items()}
    made.update({name: build_table(name, t) for name, t in TABLES.items()})
    return made


def main():
    made = build_all()
    for name, xml in made.items():
        open(os.path.join(HERE, name + '.xml'), 'w', encoding='ascii', newline='\n').write(xml)
    print(', '.join(made))
    return made


if __name__ == '__main__':
    main()
