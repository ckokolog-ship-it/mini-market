"""test_rights.py -- the rights (MM_RIGHTS): the roles of the system as the shop worked before them; the role of
the level of a user kept with it (mm_auth.create_user, set_role); a role of the shop (made, a copy of
another, its grants); a user in more than one role (the most of each); a field not above its screen; an
action on a screen read only; the menu of a user; need (MM-197); what is refused (MM-198).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
PW = 'Kodikos-2026'


def call(db, name, *args, rtype=None):
    if rtype:
        return db.cur.callfunc('mm_rights.' + name, rtype, list(args))
    db.cur.callproc('mm_rights.' + name, list(args))


def fails(db, code, name, *args, rtype=None):
    with pytest.raises(oracledb.DatabaseError) as e:
        call(db, name, *args, rtype=rtype)
    db.conn.rollback()
    assert 'MM-%d' % code in str(e.value), str(e.value)


@pytest.fixture
def people(env):
    db, ids = env
    t = ids['tag'].lower()
    names = {}
    for role in ('CASHIER', 'MANAGER', 'ADMIN'):
        n = 'tstr%s%s' % (role[0].lower(), t)
        if not db.one('select count(*) from mm_user where username = :u', u=n)[0]:
            db.cur.callfunc('mm_auth.create_user', int, [n, 'Test ' + role, role, PW])
        names[role] = n
    db.commit()
    uid = {r: db.one('select id from mm_user where username = :u', u=n)[0] for r, n in names.items()}
    role = 'TST_' + ids['tag']
    yield db, names, uid, role
    db.cur.execute("delete from mm_role where code like 'TST\\_%' escape '\\'")
    for r, n in names.items():
        db.cur.callproc('mm_auth.set_role', [n, r])
    db.commit()


def lvl(db, uid, obj, item=None):
    return call(db, 'lvl', uid, obj, item, rtype=str)


def test_the_roles_of_the_system(people):
    db, names, uid, _ = people
    assert db.one("select listagg(code, ',') within group (order by code) from mm_role where system = 'Y'")[0] == 'ADMIN,CASHIER,MANAGER'
    # each user in the role of its level
    for r, n in names.items():
        assert db.one('select r.code from mm_user_role ur join mm_role r on r.id = ur.role_id join mm_user u on u.id = ur.user_id '
                      'where u.username = :u', u=n) == (r,)
    c, m, a = uid['CASHIER'], uid['MANAGER'], uid['ADMIN']
    # a cashier: the till (not its warehouse), the items read only (no cost), the counts without their actions
    assert [lvl(db, c, *x) for x in [('POS',), ('POS', 'OPEN_Z'), ('POS', 'WAREHOUSE'), ('ITEMS',), ('ITEMS', 'PRICE'),
                                       ('ITEMS', 'COST'), ('ITEMS', 'CREATE'), ('COUNTS',), ('COUNTS', 'POST'), ('DOCS',), ('USERS',)]] \
        == ['W', 'W', 'N', 'R', 'R', 'N', 'N', 'W', 'N', 'N', 'N']
    # a manager: everything but the users and the roles; the reports read
    assert [lvl(db, m, *x) for x in [('DOCS', 'POST'), ('ITEMS', 'COST'), ('POS', 'WAREHOUSE'), ('PROFIT',), ('USERS',), ('ROLES',)]] \
        == ['W', 'W', 'W', 'R', 'N', 'N']
    # an administrator: everything, also a screen without grants
    assert [lvl(db, a, *x) for x in [('USERS', 'CREATE'), ('ROLES',), ('PROFIT',), ('ITEMS', 'COST')]] == ['W'] * 4
    assert call(db, 'can', c, 'ITEMS', 'PRICE', 'R', rtype=str) == 'Y'
    assert call(db, 'can', c, 'ITEMS', 'PRICE', 'W', rtype=str) == 'N'
    assert lvl(db, c, 'NO_SUCH') == 'N'
    # the menu of a cashier: its screens in their groups
    db.cur.execute('select group_code, code, route from mm_user_menu where user_id = :u order by group_sort, sort_no', u=c)
    assert [(g, s) for g, s, _ in db.cur] == [('SALES', 'POS'), ('SALES', 'ORDERS'), ('SALES', 'RESERVATIONS'), ('STORE', 'ITEMS'), ('STORE', 'LABELS'),
                                              ('STORE', 'COUNTS')]
    assert db.one("select route from mm_user_menu where user_id = :u and code = 'ITEMS'", u=c) == ('#/items',)
    # need: the name of what is not allowed
    with pytest.raises(oracledb.DatabaseError) as e:
        call(db, 'need', c, 'ITEMS', 'COST', 'R')
    assert 'MM-197' in str(e.value) and 'Είδη: Κόστος' in str(e.value)
    call(db, 'need', c, 'ITEMS', None, 'R')


def test_a_role_of_the_shop(people):
    db, names, uid, role = people
    c = uid['CASHIER']
    # a role of its own: a copy of the manager without the costs; the cashier in it too
    call(db, 'create_role', role, 'Test υπεύθυνος', rtype=int)
    call(db, 'copy_role', 'MANAGER', role)
    call(db, 'set_grant', role, 'ITEMS', 'COST', 'N')
    call(db, 'set_grant', role, 'ITEMS', 'FIFO', 'N')
    call(db, 'add_user_role', names['CASHIER'], role)
    db.commit()
    # the most of each role: the items now W, the cost N in both, the documents W
    assert [lvl(db, c, *x) for x in [('ITEMS',), ('ITEMS', 'PRICE'), ('ITEMS', 'COST'), ('DOCS', 'POST'), ('POS', 'WAREHOUSE')]] \
        == ['W', 'W', 'N', 'W', 'W']
    # a field not above its screen; an action on a screen read: its own grant; none: not allowed
    call(db, 'set_grant', role, 'ITEMS', None, 'R')
    call(db, 'set_grant', role, 'ITEMS', 'PRICE', 'W')
    call(db, 'set_grant', role, 'DOCS', None, 'R')
    call(db, 'set_grant', role, 'DOCS', 'POST', 'W')
    call(db, 'set_grant', role, 'DOCS', 'CANCEL', None)
    assert [lvl(db, c, *x) for x in [('ITEMS', 'PRICE'), ('DOCS', 'POST'), ('DOCS', 'CANCEL'), ('DOCS', 'COST')]] == ['R', 'W', 'N', 'R']
    # the screen out: its fields and actions too
    call(db, 'set_grant', role, 'DOCS', None, None)
    assert [lvl(db, c, *x) for x in [('DOCS',), ('DOCS', 'POST')]] == ['N', 'N']
    # its level changed (set_role): the role of the system changed, the role of the shop stays
    db.cur.callproc('mm_auth.set_role', [names['CASHIER'], 'MANAGER'])
    db.cur.execute('select r.code from mm_user_role ur join mm_role r on r.id = ur.role_id where ur.user_id = :u order by r.code', u=c)
    assert [r for (r,) in db.cur] == ['MANAGER', role]
    # the role not active: as if not there; out of the user; dropped (its grants with it)
    db.cur.callproc('mm_auth.set_role', [names['CASHIER'], 'CASHIER'])
    call(db, 'set_grant', role, 'ITEMS', None, 'W')
    assert lvl(db, c, 'ITEMS') == 'W'
    call(db, 'set_role', role, 'Test άλλο όνομα', 'N')
    assert lvl(db, c, 'ITEMS') == 'R'
    call(db, 'set_role', role, None, 'Y')
    assert db.one('select name from mm_role where code = :r', r=role) == ('Test άλλο όνομα',)
    call(db, 'drop_user_role', names['CASHIER'], role)
    assert lvl(db, c, 'ITEMS') == 'R'
    call(db, 'drop_role', role)
    assert db.one('select count(*) from mm_grant g join mm_role r on r.id = g.role_id where r.code = :r', r=role) == (0,)
    db.commit()
    # a user not active: no rights
    db.cur.callproc('mm_auth.set_active', [names['CASHIER'], 'N'])
    assert lvl(db, c, 'POS') == 'N'
    db.cur.callproc('mm_auth.set_active', [names['CASHIER'], 'Y'])
    db.commit()


def test_what_is_refused(people):
    db, names, uid, role = people
    fails(db, 198, 'create_role', 'x y', 'Test', rtype=int)
    fails(db, 198, 'create_role', 'MANAGER', 'Test', rtype=int)
    fails(db, 198, 'create_role', role, ' ', rtype=int)
    fails(db, 198, 'drop_role', 'CASHIER')
    fails(db, 198, 'set_role', 'MANAGER', None, 'N')
    fails(db, 198, 'set_grant', 'ADMIN', 'ITEMS', None, 'N')           # (all its rights, always)
    fails(db, 198, 'set_grant', 'CASHIER', 'NO_SUCH', None, 'R')
    fails(db, 198, 'set_grant', 'CASHIER', 'ITEMS', 'NO_SUCH', 'R')
    fails(db, 198, 'set_grant', 'CASHIER', 'ITEMS', 'CREATE', 'R')      # (an action: N or W)
    fails(db, 198, 'set_grant', 'CASHIER', 'ITEMS', None, 'X')
    fails(db, 198, 'set_grant', 'CASHIER', 'SALES', None, 'R')          # (a group of the menu: not a screen)
    fails(db, 198, 'copy_role', 'MANAGER', 'CASHIER')
    fails(db, 198, 'add_user_role', names['CASHIER'], 'NO_SUCH')
    fails(db, 180, 'add_user_role', 'tstnobody', 'CASHIER')
    # never without an active user of all rights: (the administrators of the database, all of them out)
    db.cur.execute("select u.username from mm_user u join mm_user_role ur on ur.user_id = u.id "
                   "join mm_role r on r.id = ur.role_id and r.all_rights = 'Y' where u.active = 'Y'")
    admins = [n for (n,) in db.cur]
    with pytest.raises(oracledb.DatabaseError) as e:
        for n in admins:
            call(db, 'drop_user_role', n, 'ADMIN')
    db.conn.rollback()
    assert 'MM-198' in str(e.value)
    assert db.one("select count(*) from mm_user_role ur join mm_role r on r.id = ur.role_id where r.code = 'ADMIN'")[0] >= len(admins)
