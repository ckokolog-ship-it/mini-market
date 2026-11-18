"""test_sales_by.py -- the sales by store, register and cashier (MM_SALES_DOC; MM_DOC.CREATED_BY, POSTED_BY by
the trigger of MM_AUDIT): who made and posted a receipt of the till of the pages; the report by each (the costs
and the profit only with the right to the gross profit); the summary of the day; the cashier on the receipt.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_api import PW, get, post  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
api, users = test_api.api, test_api.users


def test_the_sales_by_store_register_cashier(env, api, users):
    db, ids = env
    test_core.close_open_z(db, ids['reg'])
    db.commit()
    post(api, '/api/pos/tst/open', {'cash': 0}, token='CASHIER')
    post(api, '/api/pos/tst/scan', {'code': 'TST%sA' % ids['tag'], 'qty': 2}, token='CASHIER')
    p = post(api, '/api/pos/tst/pay', {'payment': 'CARD'}, token='CASHIER')['paid']
    # who made it, who posted it: the cashier of the till
    assert db.one('select created_by, posted_by from mm_doc where id = :d', d=p['id']) == (users['CASHIER'], users['CASHIER'])
    # the receipt: its cashier
    assert get(api, '/api/pos/tst/receipt/%d' % p['id'], token='CASHIER')['cashier'] == 'Test CASHIER'
    today = datetime.date.today().isoformat()
    q = '/api/reports/sales-by?from=%s&to=%s' % (today, today)
    # by cashier: the receipt in its total; the costs (a manager: the gross profit too)
    r = get(api, q + '&by=user')
    me = [x for x in r['rows'] if x['key'] == users['CASHIER']][0]
    assert r['by'] == 'user' and me['name'] == 'Test CASHIER' and me['docs'] >= 1 and me['total'] >= p['total']
    assert me['cost'] is not None and me['profit'] == round(me['net'] - me['cost'], 2)
    assert me['avg_total'] == round(me['total'] / me['docs'], 2)
    # by register, by store: the till TST, the main store
    reg = [x for x in get(api, q + '&by=register')['rows'] if x['name'].startswith('TST ')][0]
    assert reg['total'] >= p['total']
    main = db.fn('main_warehouse', int)
    assert str(main) in [x['key'] for x in get(api, q)['rows']]                  # (by store, by default)
    assert get(api, q + '&by=x', status=400)['error'] == 'bad_by'
    # the summary of the day: by store, by cashier
    d = get(api, '/api/day?date=' + today)
    assert any(x['username'] == users['CASHIER'] and x['total'] >= p['total'] for x in d['by_user'])
    assert any(x['code'] == 'K' for x in d['by_warehouse'])
    # a role with the report but not the gross profit: no costs
    role = 'TSTS_' + ids['tag']
    name = 'tsts' + ids['tag'].lower()
    db.cur.execute('delete from mm_role where code = :r', r=role)
    if not db.one('select count(*) from mm_user where username = :u', u=name)[0]:
        db.cur.callfunc('mm_auth.create_user', int, [name, 'Test αναφορές', 'CASHIER', PW])
    db.cur.callfunc('mm_rights.create_role', int, [role, 'Test αναφορές'])
    db.cur.callproc('mm_rights.set_grant', [role, 'REP_SALES_BY', None, 'R'])
    db.cur.callproc('mm_rights.add_user_role', [name, role])
    db.commit()
    tok = post(api, '/api/auth/login', {'username': name, 'password': PW}, token=None)['token']
    rows = get(api, q + '&by=user', token=tok)['rows']
    assert rows and all(x['cost'] is None and x['profit'] is None for x in rows)
    assert get(api, q, status=403, token='CASHIER')['error'] == 'forbidden'
    db.cur.execute('delete from mm_role where code = :r', r=role)
    post(api, '/api/pos/tst/close', {}, token='CASHIER')
    db.commit()
