"""test_rights_api.py -- the rights (MM_RIGHTS) on the service and the pages: a role of the shop (only the
items, without their prices; the documents read, posted but not made; the users without the
administrators): its menu (/api/auth/rights), its calls (403), the fields it may not read (null), the
customers through the documents without their tax numbers; in a browser (rights_check.js): its menu, the
page of an item without its price, a page not allowed.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import os
import shutil
import subprocess

import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_api import PW, get, post  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
api, users = test_api.api, test_api.users


@pytest.fixture
def clerk(env, api, users):
    """a user only in a role of the shop: the items read without their prices"""
    db, ids = env
    t = ids['tag']
    role = 'TSTW_' + t
    name = 'tstw' + t.lower()
    if not db.one('select count(*) from mm_user where username = :u', u=name)[0]:
        db.cur.callfunc('mm_auth.create_user', int, [name, 'Test υπάλληλος', 'CASHIER', PW])
    db.cur.execute('delete from mm_role where code = :r', r=role)
    db.cur.callfunc('mm_rights.create_role', int, [role, 'Test υπάλληλος'])
    for g in [('ITEMS', None, 'R'), ('ITEMS', 'PRICE', 'N'), ('ITEMS', 'WHOLESALE_PRICE', 'N'), ('ITEMS', 'COST', 'N'),
              ('ITEMS', 'FIFO', 'N'), ('DOCS', None, 'R'),
              ('DOCS', 'POST', 'W'), ('USERS', None, 'W'), ('USERS', 'CREATE', 'W')]:
        db.cur.callproc('mm_rights.set_grant', [role, *g])
    db.cur.callproc('mm_rights.add_user_role', [name, role])
    db.cur.callproc('mm_rights.drop_user_role', [name, 'CASHIER'])
    db.commit()
    tok = post(api, '/api/auth/login', {'username': name, 'password': PW}, token=None)['token']
    yield db, ids, name, role, tok
    db.cur.execute('delete from mm_role where code = :r', r=role)
    db.commit()


def test_a_role_of_the_shop_on_the_service(clerk, api):
    db, ids, name, role, tok = clerk
    r = get(api, '/api/auth/rights', token=tok)
    assert [(g['code'], [s['code'] for s in g['screens']]) for g in r['menu']] == \
        [('STORE', ['ITEMS']), ('OFFICE', ['DOCS']), ('ADMIN', ['USERS'])]
    assert (r['rights']['ITEMS'], r['rights']['ITEMS.PRICE'], r['rights']['ITEMS.STOCK'], r['rights']['DOCS.CREATE'],
            r['rights']['DOCS.POST'], r['rights']['POS']) == ('R', 'N', 'R', 'N', 'W', 'N')
    # the items: without their prices (null); the cost: not as a cashier, as its screen here
    code = 'TST%sA' % ids['tag']
    x = get(api, '/api/items/' + code, token=tok)
    assert (x['price'], x['wholesale_price'], x['code']) == (None, None, code) and x['stock'] is not None
    assert all(r['price'] is None for r in get(api, '/api/items?q=' + code, token=tok)['rows'])
    assert get(api, '/api/items/' + code, token='CASHIER')['price'] is not None
    assert get(api, '/api/items/' + code, token='CASHIER')['cost'] is None              # (a cashier: not its cost)
    assert get(api, '/api/items/' + code)['cost'] is not None                          # (a manager)
    # not its screens, not its actions: 403
    for path in ('/api/pos', '/api/counts', '/api/reports/sales', '/api/day', '/api/warehouses/1', '/api/ledger/item/1'):
        assert get(api, path, status=403, token=tok)['error'] == 'forbidden', path
    assert post(api, '/api/docs', {'doc_type': 'DPA', 'supplier_id': ids['supplier']}, status=403, token=tok)['error'] == 'forbidden'
    assert post(api, '/api/counts', {'name': 'TST x'}, status=403, token=tok)['error'] == 'forbidden'
    # the documents read; the customers through them, without what its role may not read of them
    get(api, '/api/docs', token=tok)
    c = get(api, '/api/customers?q=Test', token=tok)['rows']
    assert c and all(x['afm'] is None and x['phone'] is None for x in c)
    # the warehouses as a list (for the choices), without their value
    w = get(api, '/api/warehouses', token=tok)['rows']
    assert w and all(x['value'] is None and x['items'] is None for x in w)
    # the users: a cashier made; an administrator not (only by one of all rights)
    r = post(api, '/api/users', {'username': 'tstx' + ids['tag'].lower(), 'role': 'CASHIER', 'password': PW}, token=tok)
    assert any(x['username'] == 'tstx' + ids['tag'].lower() for x in r['rows'])
    assert post(api, '/api/users', {'username': 'tsty' + ids['tag'].lower(), 'role': 'ADMIN', 'password': PW},
                status=403, token=tok)['error'] == 'forbidden'
    an = 'tstz' + ids['tag'].lower()
    if not db.one('select count(*) from mm_user where username = :u', u=an)[0]:
        db.cur.callfunc('mm_auth.create_user', int, [an, 'Test ADMIN', 'ADMIN', PW])
        db.commit()
    admin = db.one('select id from mm_user where username = :u', u=an)[0]
    assert post(api, '/api/users/%d' % admin, {'active': False}, status=403, token=tok)['error'] == 'forbidden'
    assert post(api, '/api/users/%d' % admin, {'password': 'Allos-kodikos-1'}, status=403, token=tok)['error'] == 'forbidden'
    # the right changed: at the next call (no new login)
    db.cur.callproc('mm_rights.set_grant', [role, 'POS', None, 'R'])
    db.commit()
    get(api, '/api/pos', token=tok)


def test_a_role_of_the_shop_in_a_browser(clerk, api):
    if not shutil.which('node') or subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no node or Playwright')
    db, ids, name, role, tok = clerk
    e = dict(os.environ, BASE=api, USER=name, PW=PW, ITEM='TST%sA' % ids['tag'], SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
    r = subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rights_check.js')],
                       env=e, capture_output=True, text=True, timeout=120)
    print(r.stdout, r.stderr)
    assert r.returncode == 0 and '== rights OK' in r.stdout, r.stdout + r.stderr
