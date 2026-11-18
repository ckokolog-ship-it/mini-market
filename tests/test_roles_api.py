"""test_roles_api.py -- the page «Ρόλοι και δικαιώματα» on the service (Roles): a role made, its rights (the
screen, a field, an action), copied from another, given to a user (its menu, its calls), renamed, not active,
out; the menu renamed, moved, a screen not active (no one sees it), the roles kept in it; only with a right
to the roles (an administrator); in a browser (roles_check.js).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import os
import shutil
import subprocess

import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_api import PW, TOKENS, get, post  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
api, users = test_api.api, test_api.users


@pytest.fixture
def admin(env, api, users):
    db, ids = env
    t = ids['tag']
    name = 'tstq' + t.lower()
    clerk = 'tstv' + t.lower()
    for n, r in ((name, 'ADMIN'), (clerk, 'CASHIER')):
        if not db.one('select count(*) from mm_user where username = :u', u=n)[0]:
            db.cur.callfunc('mm_auth.create_user', int, [n, 'Test ' + r, r, PW])
    db.commit()
    TOKENS['ROLES_ADMIN'] = post(api, '/api/auth/login', {'username': name, 'password': PW}, token=None)['token']
    role = 'TSTR_' + t
    yield db, ids, role, clerk
    db.cur.execute("delete from mm_role where code like 'TSTR\\_%' escape '\\'")
    db.cur.execute("update mm_object set name = 'Είδη', sort_no = 10, active = 'Y', "
                   "parent_id = (select id from mm_object where code = 'STORE') where code = 'ITEMS'")
    db.cur.execute("update mm_object set active = 'Y' where code = 'LABELS'")
    db.commit()


def test_the_roles_and_the_menu(admin, api):
    db, ids, role, clerk = admin
    A = 'ROLES_ADMIN'
    r = get(api, '/api/roles', token=A)
    assert [x['code'] for x in r['rows']][:3] == ['CASHIER', 'MANAGER', 'ADMIN']
    assert [x['all_rights'] for x in r['rows'] if x['code'] == 'ADMIN'] == ['Y']
    # a role: made, the rights of the cashier copied, the items without their prices, the documents posted
    post(api, '/api/roles', {'code': role.lower(), 'name': 'Test ρόλος'}, token=A)
    g = post(api, '/api/roles/%s/copy' % role, {'from': 'CASHIER'}, token=A)
    items = [s for s in g['screens'] if s['code'] == 'ITEMS'][0]
    assert (items['grant'], items['lvl'], items['group_code']) == ('R', 'R', 'STORE')
    assert [(i['code'], i['grant'], i['lvl']) for i in items['items'] if i['code'] in ('PRICE', 'COST')] == [('PRICE', None, 'R'), ('COST', 'N', 'N')]
    post(api, '/api/roles/%s/grants' % role, {'screen': 'ITEMS', 'item': 'PRICE', 'level': 'N'}, token=A)
    post(api, '/api/roles/%s/grants' % role, {'screen': 'DOCS', 'level': 'R'}, token=A)
    g = post(api, '/api/roles/%s/grants' % role, {'screen': 'DOCS', 'item': 'POST', 'level': 'W'}, token=A)
    docs = [s for s in g['screens'] if s['code'] == 'DOCS'][0]
    assert docs['lvl'] == 'R' and [(i['code'], i['lvl']) for i in docs['items'] if i['code'] in ('POST', 'CREATE')] == [('CREATE', 'N'), ('POST', 'W')]
    g = post(api, '/api/roles/%s/grants' % role, {'screen': 'ITEMS', 'item': 'PRICE', 'level': None}, token=A)
    assert [i['grant'] for s in g['screens'] if s['code'] == 'ITEMS' for i in s['items'] if i['code'] == 'PRICE'] == [None]
    post(api, '/api/roles/%s/grants' % role, {'screen': 'ITEMS', 'item': 'PRICE', 'level': 'N'}, token=A)
    # given to the clerk, instead of its cashier: its menu and its calls
    uid = db.one('select id from mm_user where username = :u', u=clerk)[0]
    r = post(api, '/api/users/%d/roles' % uid, {'roles': [role]}, token=A)
    assert [x['roles'] for x in r['rows'] if x['id'] == uid] == [role]
    tok = post(api, '/api/auth/login', {'username': clerk, 'password': PW}, token=None)['token']
    m = get(api, '/api/auth/rights', token=tok)
    assert [s['code'] for g_ in m['menu'] for s in g_['screens']] == ['POS', 'ORDERS', 'ITEMS', 'LABELS', 'COUNTS', 'DOCS']
    assert get(api, '/api/items/TST%sA' % ids['tag'], token=tok)['price'] is None
    # the menu: the items renamed, first in the office; the labels not active: no one sees them
    post(api, '/api/menu/ITEMS', {'name': 'Τα είδη', 'sort_no': 1, 'group': 'OFFICE'}, token=A)
    r = post(api, '/api/menu/LABELS', {'name': 'Ετικέτες', 'sort_no': 50, 'group': 'STORE', 'active': False}, token=A)
    assert sorted((x['code'], x['group_code'], x['active']) for x in r['rows'] if x['code'] in ('ITEMS', 'LABELS')) == \
        [('ITEMS', 'OFFICE', 'Y'), ('LABELS', 'STORE', 'N')]
    m = get(api, '/api/auth/rights', token=tok)
    assert [(g_['code'], [s['code'] for s in g_['screens']]) for g_ in m['menu']] == \
        [('SALES', ['POS', 'ORDERS']), ('STORE', ['COUNTS']), ('OFFICE', ['ITEMS', 'DOCS'])]
    assert [s['name'] for g_ in m['menu'] for s in g_['screens'] if s['code'] == 'ITEMS'] == ['Τα είδη']
    assert 'LABELS' not in get(api, '/api/auth/rights', token=A)['rights']
    # what is refused: the roles out of the menu, a role of the system out, a role of no one, a role of another
    for path, body in (('/api/menu/ROLES', {'name': 'x', 'group': 'ADMIN', 'active': False}),
                       ('/api/menu/ADMIN', {'name': 'x', 'active': False}),
                       ('/api/menu/ITEMS', {'name': 'x', 'group': 'NO_SUCH'}),
                       ('/api/roles/CASHIER/delete', {}), ('/api/roles/ADMIN/grants', {'screen': 'ITEMS', 'level': 'N'}),
                       ('/api/roles', {'code': 'CASHIER', 'name': 'x'})):
        assert post(api, path, body, status=400, token=A)['error'] == 'MM-198', path
    assert post(api, '/api/users/%d/roles' % uid, {'roles': ['NO_SUCH']}, status=400, token=A)['error'] == 'MM-198'
    assert get(api, '/api/roles/NO_SUCH/grants', status=404, token=A)['error'] == 'not_found'
    # only with a right to the roles: not a manager (not even the roles of a user)
    assert get(api, '/api/roles', status=403)['error'] == 'forbidden'
    assert post(api, '/api/roles', {'code': 'TSTR_X', 'name': 'x'}, status=403)['error'] == 'forbidden'
    assert post(api, '/api/users/%d/roles' % uid, {'roles': ['ADMIN']}, status=403)['error'] == 'forbidden'
    # renamed, not active (the clerk: no rights of it), out
    r = post(api, '/api/roles/' + role, {'name': 'Test άλλο', 'active': False}, token=A)
    assert [(x['name'], x['active'], x['users']) for x in r['rows'] if x['code'] == role] == [('Test άλλο', 'N', 1)]
    assert get(api, '/api/auth/rights', token=tok)['menu'] == []
    r = post(api, '/api/roles/%s/delete' % role, {}, token=A)
    assert role not in [x['code'] for x in r['rows']]
    assert [x['roles'] for x in get(api, '/api/users', token=A)['rows'] if x['id'] == uid] == [None]


def test_the_roles_in_a_browser(admin, api):
    if not shutil.which('node') or subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no node or Playwright')
    db, ids, role, clerk = admin
    e = dict(os.environ, BASE=api, ADMIN='tstq' + ids['tag'].lower(), USER=clerk, PW=PW, ROLE=role,
             SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
    r = subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'roles_check.js')],
                       env=e, capture_output=True, text=True, timeout=120)
    print(r.stdout, r.stderr)
    assert r.returncode == 0 and '== roles OK' in r.stdout, r.stdout + r.stderr
    assert db.one("select g.lvl from mm_grant g join mm_role r on r.id = g.role_id join mm_object o on o.id = g.object_id "
                  "where r.code = :r and o.code = 'DOCS' and g.item_id is null", r=role) == ('R',)
    assert db.one("select count(*) from mm_user_role ur join mm_role r on r.id = ur.role_id join mm_user u on u.id = ur.user_id "
                  "where r.code = :r and u.username = :u", r=role, u=clerk) == (1,)
