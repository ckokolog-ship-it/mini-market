"""test_audit.py -- the history of what was done (MM_AUDIT_LOG, its triggers; MM_AUDIT_ALL with the logins): who
(the user of the pages: mm-api tells the database; else the user of the database), from where, what, of what;
undone with what failed; a value of a secret setting not written; the page «Ιστορικό ενεργειών» (AUDIT: an
administrator; filters, pages); purge; in a browser (audit_check.js).

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
    name = 'tsth' + ids['tag'].lower()
    if not db.one('select count(*) from mm_user where username = :u', u=name)[0]:
        db.cur.callfunc('mm_auth.create_user', int, [name, 'Test ADMIN', 'ADMIN', PW])
        db.commit()
    TOKENS['AUDIT_ADMIN'] = post(api, '/api/auth/login', {'username': name, 'password': PW}, token=None)['token']
    yield db, ids, name


def last(db, action, ref_id=None):
    db.cur.execute('select username, source, ref_type, ref_id, ref_text, detail from mm_audit_log where action = :a '
                   'and (:r is null or ref_id = :r) order by id desc fetch first 1 row only', a=action, r=ref_id)
    return db.cur.fetchone()


def test_what_was_done(admin, api, users):
    db, ids, name = admin
    # through the pages: who (the manager of the tests) and from where (mm-api)
    k = post(api, '/api/counts', {'name': 'TST audit'})
    post(api, '/api/counts/%d/cancel' % k['id'])
    assert last(db, 'COUNT_CANCEL', k['id']) == (users['MANAGER'], 'mm-api', 'COUNT', k['id'], 'TST audit', None)
    # through SQL: the user of the database; an item: its prices, before and after
    db.cur.execute('update mm_item set price = price + 1, min_stock = 2 where id = :i', i=ids['a'])
    db.commit()
    u, src, t, rid, code, d = last(db, 'ITEM_CHANGE', ids['a'])
    assert (u, t, rid, code) == ('MM', 'ITEM', ids['a'], 'TST%sA' % ids['tag']) and 'τιμή:' in d and 'ελάχιστο: 0 → 2' in d
    db.cur.execute('update mm_item set price = price - 1, min_stock = 0 where id = :i', i=ids['a'])
    # a sale posted at the till of the pages: the cashier
    test_core.close_open_z(db, ids['reg'])
    db.commit()
    post(api, '/api/pos/tst/open', {'cash': 0}, token='CASHIER')
    assert last(db, 'Z_OPEN')[0] == users['CASHIER']
    post(api, '/api/pos/tst/scan', {'code': 'TST%sA' % ids['tag']}, token='CASHIER')
    p = post(api, '/api/pos/tst/pay', {'payment': 'CARD'}, token='CASHIER')['paid']
    assert last(db, 'DOC_POST', p['id'])[:3] == (users['CASHIER'], 'mm-api', 'DOC')
    post(api, '/api/pos/tst/cash', {'amount': -5, 'note': 'TST καφές'}, token='CASHIER')
    assert last(db, 'CASH_OUT')[5] == '-5: TST καφές'
    post(api, '/api/pos/tst/close', {}, token='CASHIER')
    assert last(db, 'Z_CLOSE')[0] == users['CASHIER'] and 'σύνολο' in last(db, 'Z_CLOSE')[5]
    # what failed: nothing of it (its transaction undone)
    n = db.one('select count(*) from mm_audit_log')[0]
    post(api, '/api/counts/%d/cancel' % k['id'], status=400)                 # (cancelled already)
    assert db.one('select count(*) from mm_audit_log')[0] == n
    # the rights and the users; a secret setting: not its value
    role = 'TSTA_' + ids['tag']
    db.cur.execute('delete from mm_role where code = :r', r=role)
    db.cur.callfunc('mm_rights.create_role', int, [role, 'Test ιστορικό'])
    db.cur.callproc('mm_rights.set_grant', [role, 'ITEMS', None, 'R'])
    db.cur.callproc('mm_rights.set_grant', [role, 'ITEMS', None, 'W'])
    assert last(db, 'GRANT')[4:] == (role, 'ITEMS: R → W')
    db.cur.execute('delete from mm_role where code = :r', r=role)
    assert last(db, 'ROLE_DROP')[4] == role
    db.cur.execute("merge into mm_setting s using (select 'TST_API_KEY' name from dual) v on (s.name = v.name) "
                   "when matched then update set value = 'x1' when not matched then insert (name, value) values (v.name, 'x1')")
    assert last(db, 'SETTING')[4:] == ('TST_API_KEY', '(αλλαγή, χωρίς την τιμή)')
    db.cur.execute("delete from mm_setting where name = 'TST_API_KEY'")
    db.commit()
    # the identifier of a call is not left on the connection: SQL of the tests after it is MM
    db.cur.execute('update mm_item set min_stock = 1 where id = :i', i=ids['b'])
    assert last(db, 'ITEM_CHANGE', ids['b'])[0] == 'MM'
    db.cur.execute('update mm_item set min_stock = 0 where id = :i', i=ids['b'])
    db.commit()


def test_the_page_of_the_history(admin, api, users):
    db, ids, name = admin
    k = post(api, '/api/counts', {'name': 'TST audit page'})
    post(api, '/api/counts/%d/cancel' % k['id'])
    A = 'AUDIT_ADMIN'
    r = get(api, '/api/audit?action=count_&user=%s' % users['MANAGER'], token=A)
    assert r['rows'][0]['action'] == 'COUNT_CANCEL' and r['rows'][0]['ref_text'] == 'TST audit page'
    assert all(x['username'] == users['MANAGER'] and x['action'].startswith('COUNT_') for x in r['rows'])
    assert users['MANAGER'] in [u['username'] for u in r['users']]
    r = get(api, '/api/audit?action=AUTH_LOGIN&user=%s' % name, token=A)        # (the logins too)
    assert r['total'] >= 1 and r['rows'][0]['ref_text'] == name
    post(api, '/api/counts/%d/cancel' % post(api, '/api/counts', {'name': 'TST audit page 2'})['id'])
    r = get(api, '/api/audit?q=audit%20page&limit=1', token=A)
    assert r['limit'] == 1 and r['total'] >= 2 and len(r['rows']) == 1
    assert get(api, '/api/audit?from=2000-01-01&to=2000-01-02', token=A)['rows'] == []
    # only an administrator (AUDIT): not a manager
    assert get(api, '/api/audit', status=403)['error'] == 'forbidden'
    # purge: at least 30 days kept
    with pytest.raises(oracledb.DatabaseError) as e:
        db.cur.callproc('mm_audit.purge', [7])
    assert 'MM-199' in str(e.value)
    db.cur.callproc('mm_audit.purge', [36500])
    db.conn.rollback()


def test_the_history_in_a_browser(admin, api):
    if not shutil.which('node') or subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no node or Playwright')
    db, ids, name = admin
    e = dict(os.environ, BASE=api, ADMIN=name, PW=PW, SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
    r = subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit_check.js')],
                       env=e, capture_output=True, text=True, timeout=120)
    print(r.stdout, r.stderr)
    assert r.returncode == 0 and '== audit OK' in r.stdout, r.stdout + r.stderr
