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
    assert set(r0) == {'date', 'zs', 'sales', 'vat', 'top', 'scratch', 'orders', 'mydata', 'min_stock', 'backup'}
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
