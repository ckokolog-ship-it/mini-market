"""test_auth.py -- the users of the shop (MM_AUTH, step 7a): the password only as PBKDF2 (the same as
Python's hashlib), the rules, login and its token, the lock after 5 wrong passwords, the end of a
session (logout, a new password, a new role, inactive, expired), an administrator always left.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: it commits, on its own users (tst...), and removes them at the end.
"""
import hashlib

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
PW = 'Kodikos-2026'


def auth(db, name, *args, rtype=None):
    if rtype:
        return db.cur.callfunc('mm_auth.' + name, rtype, list(args))
    db.cur.callproc('mm_auth.' + name, list(args))


def fails(db, code, name, *args, rtype=None):
    with pytest.raises(oracledb.DatabaseError) as e:
        auth(db, name, *args, rtype=rtype)
    db.conn.rollback()
    assert 'MM-%d' % code in str(e.value), str(e.value)


def login(db, user, pw=PW):
    tok, role, exp = db.cur.var(str), db.cur.var(str), db.cur.var(oracledb.DATETIME)
    auth(db, 'login', user, pw, 'pytest', tok, role, exp)
    db.commit()
    return tok.getvalue(), role.getvalue()


def who(db, tok):
    u, n, r = db.cur.var(int), db.cur.var(str), db.cur.var(str)
    auth(db, 'check_token', tok, u, n, r)
    return n.getvalue(), r.getvalue()


@pytest.fixture(scope='module')
def users(env):
    db, ids = env
    t = ids['tag'].lower()
    names = {'admin': 'tsta' + t, 'cashier': 'tstc' + t}
    auth(db, 'create_user', names['admin'], 'Test admin', 'ADMIN', PW, rtype=int)
    auth(db, 'create_user', names['cashier'], 'Test ταμίας', 'cashier', PW, rtype=int)
    db.commit()
    return db, names


def test_the_password_is_only_its_pbkdf2(users):
    db, names = users
    h, s, n, role = db.one('select pw_hash, pw_salt, pw_iter, role from mm_user where username = :u',
                           u=names['cashier'])
    assert role == 'CASHIER' and n >= 100000 and len(s) == 16
    assert h == hashlib.pbkdf2_hmac('sha256', PW.encode(), s, n)
    other = db.one('select pw_salt from mm_user where username = :u', u=names['admin'])[0]
    assert other != s                                                    # a salt for each one


def test_rules(users):
    db, names = users
    fails(db, 174, 'create_user', 'Χρήστος', 'x', 'CASHIER', PW, rtype=int)  # latin only
    fails(db, 174, 'create_user', 'ab', 'x', 'CASHIER', PW, rtype=int)
    fails(db, 175, 'create_user', 'tstshort', 'x', 'CASHIER', 'short1', rtype=int)
    fails(db, 175, 'create_user', 'tstnodigit', 'x', 'CASHIER', 'abcdefghijk', rtype=int)
    fails(db, 176, 'create_user', 'tstrole', 'x', 'BOSS', PW, rtype=int)
    fails(db, 182, 'create_user', names['cashier'], 'x', 'CASHIER', PW, rtype=int)
    fails(db, 180, 'set_role', 'tstnobody', 'ADMIN')


def test_login_and_its_token(users):
    db, names = users
    tok, role = login(db, names['cashier'].upper())                     # the name in any case
    assert role == 'CASHIER' and len(tok) == 64
    assert who(db, tok) == (names['cashier'], 'CASHIER')
    # only the SHA-256 of the token is kept
    th = hashlib.sha256(tok.encode()).digest()
    assert db.one('select count(*) from mm_session where token_hash = :h', h=th)[0] == 1
    assert db.one("select count(*) from mm_session where rawtohex(token_hash) = upper(:t)", t=tok)[0] == 0
    fails(db, 179, 'check_token', 'f' * 64, db.cur.var(int), db.cur.var(str), db.cur.var(str))
    fails(db, 179, 'check_token', "' or 1=1 --", db.cur.var(int), db.cur.var(str), db.cur.var(str))
    auth(db, 'logout', tok)
    db.commit()
    fails(db, 179, 'check_token', tok, db.cur.var(int), db.cur.var(str), db.cur.var(str))
    # expired
    tok, _ = login(db, names['cashier'])
    db.cur.execute('update mm_session set expires_at = sysdate - 1 / 1440 where token_hash = :h',
                   h=hashlib.sha256(tok.encode()).digest())
    db.commit()
    fails(db, 179, 'check_token', tok, db.cur.var(int), db.cur.var(str), db.cur.var(str))


def test_wrong_passwords_lock(users):
    db, names = users
    u = names['cashier']
    fails(db, 177, 'login', 'tstnobody', PW, 'pytest', db.cur.var(str), db.cur.var(str), db.cur.var(oracledb.DATETIME))
    for _ in range(5):
        fails(db, 177, 'login', u, 'Wrong-pass-1', 'pytest', db.cur.var(str), db.cur.var(str),
              db.cur.var(oracledb.DATETIME))
    # locked: even the right password, for 15 minutes; the failures stayed though each call failed
    fails(db, 178, 'login', u, PW, 'pytest', db.cur.var(str), db.cur.var(str), db.cur.var(oracledb.DATETIME))
    assert db.one('select failed from mm_user where username = :u', u=u)[0] >= 5
    assert db.one("select count(*) from mm_auth_log where username = :u and event in ('FAIL', 'LOCKED')", u=u)[0] >= 6
    auth(db, 'unlock', u)
    db.commit()
    assert login(db, u)[1] == 'CASHIER'


def test_sessions_end_with_password_role_or_inactive(users):
    db, names = users
    u = names['cashier']
    new = 'Neos-kodikos-7'
    for pw, change in ((PW, lambda: auth(db, 'set_password', u, new)),
                       (new, lambda: auth(db, 'set_role', u, 'MANAGER')),
                       (new, lambda: auth(db, 'set_active', u, 'N'))):
        tok, _ = login(db, u, pw)
        change()
        db.commit()
        fails(db, 179, 'check_token', tok, db.cur.var(int), db.cur.var(str), db.cur.var(str))
    fails(db, 177, 'login', u, new, 'pytest', db.cur.var(str), db.cur.var(str),
          db.cur.var(oracledb.DATETIME))                                   # inactive
    auth(db, 'set_active', u, 'Y')
    auth(db, 'set_role', u, 'CASHIER')
    db.commit()


def test_an_admin_always_left(users):
    db, names = users
    n = db.one("select count(*) from mm_user where role = 'ADMIN' and active = 'Y'")[0]
    if n == 1:                                                            # ours is the only one
        fails(db, 181, 'set_role', names['admin'], 'CASHIER')
        fails(db, 181, 'set_active', names['admin'], 'N')
    else:
        pytest.skip('other administrators in this database')
