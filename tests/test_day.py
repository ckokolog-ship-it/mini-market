"""test_day.py -- the summary of a day (mm-api Day.java, GET /api/day): what a day at the till adds to it
(the Z of the register, the sales, the VAT, the items sold most, a scratch prize); another day, empty;
MANAGER only.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import datetime

import pytest

import test_api
import test_core
from test_api import get, post

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users


def vat13(r):
    return sum(v['net'] + v['vat'] for v in r['vat'] if v['vat_rate'] == 13)


def test_the_summary_of_a_day(api, env, users):
    db, ids = env
    today = datetime.date.today().isoformat()
    test_core.close_open_z(db, ids['reg'])
    r0 = get(api, '/api/day')
    assert r0['date'] == today
    assert set(r0) == {'date', 'zs', 'sales', 'vat', 'top', 'scratch', 'orders', 'mydata', 'min_stock', 'expiry', 'backup', 'profit',
                       'by_warehouse', 'by_user'}
    assert r0['backup']['state'] in ('OK', 'OLD', 'FAILED', 'NEVER')
    # a day at the till: a Z, 3 x b (2,26, 13%) paid by card, a prize of a scratch ticket from the drawer
    pos = '/api/pos/tst'
    z = post(api, pos + '/open', {'cash': 30}, token='CASHIER')['z']
    b = 'TST%sB' % ids['tag']
    post(api, pos + '/scan', {'code': b, 'qty': 3}, token='CASHIER')
    post(api, pos + '/pay', {'payment': 'CARD'}, token='CASHIER')
    post(api, pos + '/prize', {'amount': 2}, token='CASHIER')
    r = get(api, '/api/day?date=' + today)
    mine = [x for x in r['zs'] if x['register'] == 'TST' and x['z_no'] == z['z_no']]
    assert len(mine) == 1
    m = mine[0]
    assert (m['status'], m['docs'], m['total'], m['card'], m['cash']) == ('O', 1, 6.78, 6.78, 0)
    assert (m['money_out'], m['drawer']) == (-2, 28)
    s0, s = r0['sales'], r['sales']
    assert (s['alp_docs'] - s0['alp_docs'], round(s['alp_total'] - s0['alp_total'], 2)) == (1, 6.78)
    assert round(vat13(r) - vat13(r0), 2) == 6.78
    t = {x['code']: x for x in r['top']}
    assert len(r['top']) <= 10 and (b not in t or t[b]['qty'] >= 3)
    assert r['top'] == sorted(r['top'], key=lambda x: -x['total'])
    sc, sc0 = r['scratch'], r0['scratch']
    assert (sc['prizes'] - sc0['prizes'], round(sc['prizes_total'] - sc0['prizes_total'], 2)) == (1, 2)
    # closed: its sums are the Z's
    post(api, pos + '/close', token='CASHIER')
    m = [x for x in get(api, '/api/day')['zs'] if x['register'] == 'TST' and x['z_no'] == z['z_no']][0]
    assert (m['status'], m['total']) == ('C', 6.78) and m['closed_at'][:10] == today
    # a day long ago: nothing; a bad date; a cashier: no
    old = get(api, '/api/day?date=1990-01-01')
    assert (old['zs'], old['vat'], old['top'], old['sales']['total'], old['scratch']['tickets']) == ([], [], [], 0, 0)
    assert get(api, '/api/day?date=1990-13-01', 400)['error'] == 'bad_date'
    assert get(api, '/api/day', 403, token='CASHIER')['error'] == 'forbidden'


def test_the_charts_of_the_sales(api, env, users):
    """GET /api/chart: the days of the period (each with the day a year before), the hours, the sums;
    a receipt of today in them; the period clamped to 7..364 days; MANAGER only"""
    db, ids = env
    today = datetime.date.today()
    test_core.close_open_z(db, ids['reg'])
    r0 = get(api, '/api/chart?days=7')
    assert (r0['from'], r0['to']) == ((today - datetime.timedelta(days=6)).isoformat(), today.isoformat())
    assert [d['day'][:10] for d in r0['days']] == [(today - datetime.timedelta(days=6 - k)).isoformat() for k in range(7)]
    assert [h['hour'] for h in r0['hours']] == list(range(24))
    pos = '/api/pos/tst'
    post(api, pos + '/open', {'cash': 0}, token='CASHIER')
    post(api, pos + '/scan', {'code': 'TST%sB' % ids['tag'], 'qty': 2}, token='CASHIER')     # 4,52
    post(api, pos + '/pay', {'payment': 'CASH'}, token='CASHIER')
    hour = db.one("select to_number(to_char(max(created_at), 'HH24')) from mm_doc where register_id = :r", r=ids['reg'])[0]
    r = get(api, '/api/chart?days=7&to=' + today.isoformat())
    d0, d = r0['days'][-1], r['days'][-1]
    assert (round(d['total'] - d0['total'], 2), d['receipts'] - d0['receipts']) == (4.52, 1)
    h0, h = r0['hours'][hour], r['hours'][hour]
    assert (round(h['total'] - h0['total'], 2), h['receipts'] - h0['receipts']) == (4.52, 1)
    s0, s = r0['sums'], r['sums']
    assert round(s['total'] - s0['total'], 2) == 4.52 and s['receipts'] - s0['receipts'] == 1
    assert s['total'] == round(sum(x['total'] for x in r['days']), 2)
    assert s['last_year'] == round(sum(x['last_year'] for x in r['days']), 2)
    assert s['avg_receipt'] == round(s['receipts_total'] / s['receipts'], 2)
    post(api, pos + '/close', token='CASHIER')
    assert len(get(api, '/api/chart?days=1')['days']) == 7
    assert len(get(api, '/api/chart?days=9999')['days']) == 364
    old = get(api, '/api/chart?days=7&to=1990-01-07')
    assert old['sums']['avg_receipt'] is None and all(x['total'] == 0 for x in old['days'])
    assert get(api, '/api/chart', 403, token='CASHIER')['error'] == 'forbidden'
