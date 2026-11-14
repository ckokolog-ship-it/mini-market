"""test_reports.py -- the reports (reports/mkreports.py): the ledgers, sales, VAT, minimum stock; their XML (ASCII, every field with its
source, every formula with its function, the summaries of a page only in the margin), and with
MM_DSN their query and their words in the database, and the carry-over from page to page.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import importlib.util
import os
import xml.etree.ElementTree as ET

import pytest

import test_core
from test_core import DSN

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
spec = importlib.util.spec_from_file_location('mkreports', os.path.join(ROOT, 'reports', 'mkreports.py'))
mkreports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mkreports)
BUILT = mkreports.build_all()
needs_db = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env


@pytest.mark.parametrize('name', sorted(BUILT))
def test_xml(name):
    xml = BUILT[name]
    assert all(ord(c) < 128 for c in xml)
    assert open(os.path.join(ROOT, 'reports', name + '.xml'), encoding='ascii').read() == xml, \
        'reports/%s.xml is old: python3 mkreports.py' % name
    root = ET.fromstring(xml)
    data = root.find('data')
    columns = {e.get('name') for e in data.iter('dataItem')} | {e.get('name') for e in data.iter('summary')} \
        | {e.get('name') for e in data.iter('formula')}
    params = {e.get('name') for e in data.iter('userParameter')}
    functions = {f.get('name') for f in root.find('programUnits').iter('function')}
    for f in data.iter('formula'):
        assert f.get('source') in functions, f.get('name')
    for s in data.iter('summary'):
        assert s.get('source') in columns, s.get('name')
    body = root.find('layout/section/body')
    margin = root.find('layout/section/margin')
    page = {s.get('name') for s in data.iter('summary') if s.get('reset') == 'page'}
    for part in (body, margin):
        for fl in part.iter('field'):
            assert fl.get('source') in columns | {'PageNumber'}, fl.get('name')
            if fl.get('source') in page:
                assert part is margin, fl.get('name') + ': a summary of the page outside the margin'
    names = [e.get('name') for e in root.iter() if e.get('name')]
    assert len(names) == len(set(names))
    query = root.find('data/dataSource/select').text
    for p in params:
        assert ':' + p in query, p


@needs_db
def test_query_words_and_carry_over(env):
    """the query of the reports, as the Reports Server runs it, and what each page would show"""
    db, ids = env
    q = mkreports.QUERY.replace(':P_KIND', ':k').replace(':P_ID', ':i').replace(':P_FROM', ':f').replace(':P_TO', ':t')
    # 25 receipts of 1 from the customer: 25 rows; pages of 10 rows
    for k in range(25):
        db.fn('receive', int, ids['customer'], 1 + k, 'BANK')
    db.commit()
    import datetime
    today = datetime.date.today().strftime('%d/%m/%Y')
    db.cur.execute(q, k='C', i=ids['customer'], f='01/01/2000', t=today)
    cols = [d[0] for d in db.cur.description]
    rows = [dict(zip(cols, r)) for r in db.cur]
    assert cols[:7] == ['SEQ', 'LDATE', 'DOC_TEXT', 'DESCR', 'DEBIT', 'CREDIT', 'BALANCE']
    assert len(rows) >= 25
    for a, b in zip(rows, rows[1:]):
        # the "from the carry-over" of a page = the "to the carry-over" of the one before
        assert b['PRIOR_BALANCE'] == a['BALANCE']
        assert b['PRIOR_DEBIT'] == a['CUM_DEBIT'] and b['PRIOR_CREDIT'] == a['CUM_CREDIT']
    last = rows[-1]
    assert last['CUM_CREDIT'] == sum(r['CREDIT'] or 0 for r in rows)
    assert last['BALANCE'] == rows[0]['PRIOR_BALANCE'] + last['CUM_DEBIT'] - last['CUM_CREDIT']
    # no move in the period: one row, the carry-over
    db.cur.execute(q, k='I', i=ids['b'], f='01/01/1990', t='31/12/1990')
    assert len(db.cur.fetchall()) == 1
    # the words: Greek from the database, none left as its key
    for lb in mkreports.LABELS + ['PERIOD']:
        for k in 'ICS':
            w = db.cur.callfunc('mm_ledger.label', str, [lb, k])
            assert w != lb and any(ord(c) > 127 for c in w), lb
    assert db.cur.callfunc('mm_ledger.title', str, ['C', ids['customer']]).startswith('Καρτέλα πελάτη: Test')


def run_query(db, name, **binds):
    q = ET.fromstring(BUILT[name]).find('data/dataSource/select').text
    for k, v in binds.items():
        q = q.replace(':' + k, ':' + k.lower())
    db.cur.execute(q, {k.lower(): v for k, v in binds.items()})
    cols = [d[0] for d in db.cur.description]
    return [dict(zip(cols, r)) for r in db.cur]


@needs_db
def test_sales_vat_and_min_stock(env):
    db, ids = env
    import datetime
    today = datetime.date.today().strftime('%d/%m/%Y')
    # the break group first: its items lead the query, sorted
    for name in ('MM_SALES', 'MM_VAT'):
        rows = run_query(db, name, P_FROM='01/01/2000', P_TO=today)
        keys = [r['MONTH_KEY'] for r in rows]
        assert keys == sorted(keys)
    # the sales are the VAT of the sales with their net: the same money two ways
    a = db.one('select nvl(sum(total), 0) from mm_sales_day')[0]
    b = db.one('select nvl(sum(s_net + s_vat), 0) from mm_vat_day')[0]
    assert a == b
    # a receipt today: in the sales of today, and its VAT
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'])
    before = db.one('select nvl(max(total), 0), nvl(max(alp_docs), 0) from mm_sales_day where day = trunc(sysdate)')
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fn('add_line', int, d, ids['a'], 2)
    db.fn('post_doc', int, d)
    db.commit()
    total = db.one('select total from mm_doc where id = :d', d=d)[0]
    after = db.one('select total, alp_docs from mm_sales_day where day = trunc(sysdate)')
    assert after == (before[0] + total, before[1] + 1)
    db.proc('cancel_doc', d)                       # cancelled: no sale
    db.commit()
    assert db.one('select nvl(max(total), 0) from mm_sales_day where day = trunc(sysdate)')[0] == before[0]
    # an item under its minimum: in the report, with what is missing and its supplier
    db.cur.execute('update mm_item set min_stock = stock + 5 where id = :i', i=ids['b'])
    db.commit()
    rows = [r for r in run_query(db, 'MM_MIN_STOCK') if r['CODE'] == 'TST%sB' % ids['tag']]
    assert len(rows) == 1 and rows[0]['MISSING'] == '5'
    db.cur.execute('update mm_item set min_stock = 0 where id = :i', i=ids['b'])
    db.commit()
    assert db.cur.callfunc('mm_report.qty', str, [0.215]) in ('0,215', '0.215')
    for k in ('SALES', 'VAT', 'MIN_STOCK'):
        assert any(ord(c) > 127 for c in db.cur.callfunc('mm_report.title', str, [k]))
    for name, t in mkreports.TABLES.items():
        for w in [c[0] for c in t['cols']] + list(t['words']) + ['PAGE']:
            assert any(ord(c) > 127 for c in db.cur.callfunc('mm_report.label', str, [w])), (name, w)
