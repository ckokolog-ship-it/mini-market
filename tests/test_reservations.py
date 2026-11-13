"""test_reservations.py -- the reservations of MM_CORE (e.g. New Year cakes): the quantities reserved,
the deposit in the cash register on its day, the delivery with a receipt that takes only the rest,
the cancel with the deposit back.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: it commits, on its own items (TST..) and reservations (Test ...), and removes them.
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN, close_open_z  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env

PICKUP = datetime.date.today() + datetime.timedelta(days=10)


@pytest.fixture
def z(env):
    """a fresh Z on the register TST"""
    db, ids = env
    close_open_z(db, ids['reg'])
    zid = db.fn('open_z', int, ids['reg'])
    db.commit()
    return db, ids, zid


def avail(db, item):
    return [float(x) for x in db.one('select stock, reserved, available from mm_item_avail where item_id = :i',
                                     i=item)]


def money(db, zid):
    """cash and card that came in this Z, by kind"""
    db.cur.execute('select kind, payment, sum(amount) from mm_cash_move where z_id = :z group by kind, payment',
                   z=zid)
    return {(k, p): float(a) for k, p, a in db.cur}


def new_res(db, ids, name='Test Μαρία', qty=2):
    r = db.fn('new_reservation', int, name, '6912345678', PICKUP)
    db.proc('reserve', r, ids['b'], qty)                        # 2,26 each (VAT 13%)
    db.commit()
    return r


def test_reserved_not_moved(z):
    db, ids, _ = z
    stock, res0, _ = avail(db, ids['b'])
    r = new_res(db, ids, qty=3)
    assert avail(db, ids['b']) == [stock, res0 + 3, stock - res0 - 3]
    db.proc('reserve', r, ids['b'], 5)                          # the quantity changed
    assert avail(db, ids['b'])[1] == res0 + 5
    db.proc('reserve', r, ids['b'], 0)                          # out of the reservation
    db.commit()
    assert avail(db, ids['b'])[1] == res0
    need = db.one('select count(*) from mm_reservation_need where item_id = :i and pickup_date = :d',
                  i=ids['a'], d=PICKUP)[0]
    db.proc('reserve', r, ids['a'], 1)
    db.commit()
    assert db.one('select qty from mm_reservation_need where item_id = :i and pickup_date = :d',
                  i=ids['a'], d=PICKUP)[0] >= 1 and need >= 0


def test_rules(z):
    db, ids, _ = z
    db.fails(145, 'new_reservation', 'Test x', 'abc', PICKUP, rtype=int)
    db.fails(145, 'new_reservation', ' ', '6912345678', PICKUP, rtype=int)
    db.fails(149, 'new_reservation', 'Test x', '6912345678', datetime.date.today() - datetime.timedelta(days=1),
             rtype=int)
    r = db.fn('new_reservation', int, 'Test x', '6912345678', PICKUP)
    db.fails(124, 'reserve', r, ids['b'], -1)
    r = db.fn('new_reservation', int, 'Test x', '6912345678', PICKUP)
    db.fails(151, 'deliver', r, ids['reg'], rtype=int)          # nothing in it
    r = db.fn('new_reservation', int, 'Test x', '6912345678', PICKUP)
    db.fails(148, 'take_deposit', r, ids['reg'], 0)
    db.fails(150, 'reserve', 999999999, ids['b'], 1)


def test_deposit_then_delivery_takes_the_rest(z):
    db, ids, zid = z
    stock = avail(db, ids['b'])[0]
    r = new_res(db, ids, qty=2)                                  # 4,52
    db.proc('take_deposit', r, ids['reg'], 2, 'CARD')
    db.commit()
    assert money(db, zid)[('DEPOSIT', 'CARD')] == 2
    # another day: a new Z
    close_open_z(db, ids['reg'])
    z1 = db.one("select max(id) from mm_z where register_id = :r", r=ids['reg'])[0]
    assert float(db.one('select deposits from mm_z where id = :z', z=z1)[0]) == 2
    z2 = db.fn('open_z', int, ids['reg'])
    db.commit()
    d = db.fn('deliver', int, r, ids['reg'], 'CASH')
    db.commit()
    db.fails(146, 'reserve', r, ids['b'], 3)                     # it has a receipt waiting
    total, dep = db.one('select total, deposit from mm_doc where id = :d', d=d)
    assert (float(total), float(dep)) == (4.52, 2)
    db.fn('post_doc', int, d)
    db.commit()
    assert db.one('select status from mm_reservation where id = :r', r=r)[0] == 'D'
    assert money(db, z2) == {('SALE', 'CASH'): 2.52}             # only the rest, today
    assert avail(db, ids['b'])[0] == stock - 2                   # the stock moves at the delivery
    close_open_z(db, ids['reg'])
    zz = db.one('select total, cash, card, deposits from mm_z where id = :z', z=z2)
    assert [float(x) for x in zz] == [4.52, 2.52, 0, 0]          # the sale whole, the money of the day


def test_delivery_deleted_or_cancelled_opens_the_reservation_again(z):
    db, ids, _ = z
    r = new_res(db, ids, qty=1)
    d = db.fn('deliver', int, r, ids['reg'])
    db.proc('delete_doc', d)
    db.commit()
    assert db.one('select status, doc_id from mm_reservation where id = :r', r=r) == ('O', None)
    d = db.fn('deliver', int, r, ids['reg'])
    db.fn('post_doc', int, d)
    db.commit()
    db.proc('cancel_doc', d)
    db.commit()
    assert db.one('select status, doc_id from mm_reservation where id = :r', r=r) == ('O', None)


def test_cancel_gives_the_deposit_back(z):
    db, ids, zid = z
    r = new_res(db, ids)
    db.proc('take_deposit', r, ids['reg'], 3, 'CASH')
    db.proc('take_deposit', r, ids['reg'], 1, 'CARD')
    db.commit()
    db.fails(112, 'cancel_reservation', r, None)                 # no register: no money back
    db.proc('cancel_reservation', r, ids['reg'])
    db.commit()
    assert db.one('select status from mm_reservation where id = :r', r=r)[0] == 'C'
    m = money(db, zid)
    assert m[('DEPOSIT', 'CASH')] == 0 and m[('DEPOSIT', 'CARD')] == 0
    db.fails(146, 'take_deposit', r, ids['reg'], 1)
    # kept: no money back
    r = new_res(db, ids)
    db.proc('take_deposit', r, ids['reg'], 5)
    db.proc('cancel_reservation', r, p_refund='N')
    db.commit()
    assert money(db, zid)[('DEPOSIT', 'CASH')] == 5


def test_deposit_above_the_total(z):
    db, ids, _ = z
    r = new_res(db, ids, qty=1)                                  # 2,26
    db.proc('take_deposit', r, ids['reg'], 10)
    db.commit()
    d = db.fn('deliver', int, r, ids['reg'])
    db.fails(147, 'post_doc', d, rtype=int)


def test_no_cards_in_a_reservation(z):
    db, ids, _ = z
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, serial_tracked) "
                   "values (:c, 'Test card', :cat, 'A', 5, 'Y')", c=f"TST{ids['tag']}R", cat=cat)
    item = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}R")[0]
    r = db.fn('new_reservation', int, 'Test x', '6912345678', PICKUP)
    db.fails(152, 'reserve', r, item, 1)
