"""test_reports.py -- the reports (reports/mkreports.py): their XML (ASCII, every field with its
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
BUILT = {name: mkreports.build(name, r) for name, r in mkreports.REPORTS.items()}
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
    for p in (':P_KIND', ':P_ID', ':P_FROM', ':P_TO'):
        assert p in mkreports.QUERY and p[1:] in params


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
