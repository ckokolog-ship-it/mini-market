"""test_places.py -- where a user works (mm_auth.set_place, may_use; MM_USER.WAREHOUSE_ID, REGISTER_ID): its
store and its register; the till of the pages only on the registers it may use (a cashier with a register:
only that one; with a store: the registers of it; a manager: of its store; an administrator: all); the
users in the pages (ADMIN): one made, changed (its place, role, active, password).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import itertools
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
SEQ = itertools.count(1)


@pytest.fixture
def store(env, api, users):
    """a store (a warehouse) with two registers; an administrator of this run"""
    db, ids = env
    t = ids['tag']
    k0 = next(SEQ)
    w = db.cur.var(int)
    db.cur.execute("insert into mm_warehouse (code, name) values (:c, 'Test κατάστημα') returning id into :v",
                   c='TST%sP%d' % (t[:4], k0), v=w)
    regs = []
    for k in (1, 2):
        r = db.cur.var(int)
        db.cur.execute("insert into mm_register (code, name, warehouse_id) values (:c, 'Test ταμείο', :w) returning id into :v",
                       c='TP%s%d%d' % (t[:4], k0, k), w=w.getvalue()[0], v=r)
        regs.append((r.getvalue()[0], 'TP%s%d%d' % (t[:4], k0, k)))
    admin = 'tsta' + t.lower()
    if not db.one('select count(*) from mm_user where username = :u', u=admin)[0]:
        db.cur.callfunc('mm_auth.create_user', int, [admin, 'Test ADMIN', 'ADMIN', PW])
    db.commit()
    TOKENS['ADMIN'] = post(api, '/api/auth/login', {'username': admin, 'password': PW}, token=None)['token']
    yield db, ids, w.getvalue()[0], regs
    db.cur.execute("update mm_user set warehouse_id = null, register_id = null where username like 'tst%'")
    db.cur.execute('delete from mm_register where id in (:a, :b)', a=regs[0][0], b=regs[1][0])
    db.commit()


def login(api, name, pw=PW):
    return post(api, '/api/auth/login', {'username': name, 'password': pw}, token=None)


def codes(api, token):
    return [(r['code'], r['mine']) for r in get(api, '/api/pos', token=token)['rows']]


def test_where_a_user_works(store, api):
    db, ids, w, regs = store
    (r1, c1), (r2, c2) = regs
    name = 'tstc' + ids['tag'].lower()
    # made by the administrator: a cashier of the store, on its first register
    r = post(api, '/api/users', {'username': name, 'full_name': 'Test ταμίας', 'role': 'CASHIER', 'password': PW,
                                 'warehouse_id': w, 'register_id': r1}, token='ADMIN')
    u = [x for x in r['rows'] if x['username'] == name][0]
    assert (u['role'], u['active'], u['warehouse_id'], u['register'], u['locked']) == ('CASHIER', 'Y', w, c1, 'N')
    assert 'pw_hash' not in u
    s = login(api, name)
    assert (s['warehouse_id'], s['register']) == (w, c1)
    tok = s['token']
    assert get(api, '/api/auth/me', token=tok)['register'] == c1
    # the till: only its register; another one refused
    assert codes(api, tok) == [(c1, 'Y')]
    assert get(api, '/api/pos/' + c1, token=tok)['code'] == c1
    assert get(api, '/api/pos/' + c2, status=403, token=tok)['error'] == 'not_your_register'
    assert post(api, '/api/pos/tst/open', {'cash': 0}, status=403, token=tok)['error'] == 'not_your_register'
    # no register: the registers of its store
    post(api, '/api/users/%d' % u['id'], {'warehouse_id': w, 'register_id': None}, token='ADMIN')
    assert codes(api, tok) == [(c1, 'N'), (c2, 'N')]
    # a register alone: its store too; a register of another store refused
    r = post(api, '/api/users/%d' % u['id'], {'warehouse_id': None, 'register_id': r2}, token='ADMIN')
    assert [(x['warehouse_id'], x['register']) for x in r['rows'] if x['id'] == u['id']] == [(w, c2)]
    main = db.fn('main_warehouse', int)
    assert post(api, '/api/users/%d' % u['id'], {'warehouse_id': main, 'register_id': r2}, status=400,
                token='ADMIN')['error'] == 'MM-196'
    # a manager of the store: all its registers (its own one first in the till: mine)
    post(api, '/api/users/%d' % u['id'], {'role': 'MANAGER'}, token='ADMIN')     # (its sessions ended)
    get(api, '/api/pos', status=401, token=tok)
    tok = login(api, name)['token']
    assert codes(api, tok) == [(c1, 'N'), (c2, 'Y')]
    # everywhere: no place; the users without one (the tests) everywhere as before
    post(api, '/api/users/%d' % u['id'], {'warehouse_id': None, 'register_id': None}, token='ADMIN')
    assert {c1, c2, 'TST'} <= {c for c, _ in codes(api, tok)}
    assert 'TST' in [c for c, _ in codes(api, 'CASHIER')]
    # the administrator of a store: everywhere all the same
    assert db.cur.callfunc('mm_auth.may_use', str, [db.one("select id from mm_user where username = :u",
                                                          u='tsta' + ids['tag'].lower())[0], r1]) == 'Y'
    # a new password, not active; only an administrator
    post(api, '/api/users/%d' % u['id'], {'password': 'Allos-kodikos-77', 'active': False}, token='ADMIN')
    assert login_fails(api, name, 'Allos-kodikos-77')
    post(api, '/api/users/%d' % u['id'], {'active': True}, token='ADMIN')
    assert login(api, name, 'Allos-kodikos-77')['role'] == 'MANAGER'
    assert get(api, '/api/users', status=403, token='MANAGER')['error'] == 'forbidden'
    assert post(api, '/api/users', {'username': 'tstx', 'role': 'CASHIER', 'password': PW}, status=403)['error'] == 'forbidden'
    assert post(api, '/api/users', {'username': name, 'role': 'CASHIER', 'password': PW}, status=400,
                token='ADMIN')['error'] == 'MM-182'
    assert db.one("select count(*) from mm_auth_log where username = :u and event = 'PLACE'", u=name)[0] == 4


def login_fails(api, name, pw):
    return post(api, '/api/auth/login', {'username': name, 'password': pw}, token=None, status=401)['error'] == 'MM-177'


def test_where_a_user_works_in_a_browser(store, api):
    """the page Χρήστες of an administrator: a cashier moved to the other register of its store; the till of
    the cashier: only that register (places_check.js)"""
    if not shutil.which('node') or subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no node or Playwright')
    db, ids, w, regs = store
    (r1, c1), (r2, c2) = regs
    name = 'tstd' + ids['tag'].lower()
    post(api, '/api/users', {'username': name, 'role': 'CASHIER', 'password': PW, 'warehouse_id': w, 'register_id': r1},
         token='ADMIN')
    e = dict(os.environ, BASE=api, ADMIN='tsta' + ids['tag'].lower(), USER=name, PW=PW, REG1=c1, REG2=c2,
             SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
    r = subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'places_check.js')],
                       env=e, capture_output=True, text=True, timeout=120)
    print(r.stdout, r.stderr)
    assert r.returncode == 0 and '== places OK' in r.stdout, r.stdout + r.stderr
    assert db.one('select register_id from mm_user where username = :u', u=name)[0] == r2
