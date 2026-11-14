"""test_payments.py -- receipts from customers and payments to suppliers (MM_CORE.RECEIVE, PAY,
CANCEL_PAYMENT): the rules, the move of the register (CASH/CARD with a register), the cancel.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: on its customer, supplier and register; it commits and removes them at the end.
"""
import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN, close_open_z  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env


def test_receive_and_pay(env):
    db, ids = env
    r = db.fn('receive', int, ids['customer'], 50, 'BANK', p_notes='Test')
    p = db.fn('pay', int, ids['supplier'], 20.5)
    db.commit()
    assert db.one('select kind, amount, method, status from mm_payment where id = :r', r=r) == ('R', 50, 'BANK', 'P')
    assert db.one('select kind, method, supplier_id from mm_payment where id = :p', p=p) == ('P', 'BANK', ids['supplier'])
    assert db.one('select count(*) from mm_cash_move where payment_id in (:r, :p)', r=r, p=p)[0] == 0   # no register
    db.fails(167, 'receive', ids['customer'], 0, rtype=int)
    db.fails(168, 'receive', ids['customer'], 5, 'GOLD', rtype=int)
    db.fails(169, 'receive', None, 5, rtype=int)
    db.fails(169, 'pay', None, 5, rtype=int)


def test_with_the_register_and_cancel(env):
    db, ids = env
    close_open_z(db, ids['reg'])
    db.fails(112, 'receive', ids['customer'], 10, 'CASH', p_register_id=ids['reg'], rtype=int)   # no Z
    z = db.fn('open_z', int, ids['reg'])
    db.commit()
    r = db.fn('receive', int, ids['customer'], 10, 'CASH', p_register_id=ids['reg'])
    p = db.fn('pay', int, ids['supplier'], 4, 'CASH', p_register_id=ids['reg'])
    b = db.fn('receive', int, ids['customer'], 7, 'BANK', p_register_id=ids['reg'])   # a transfer: no drawer
    db.commit()
    db.cur.execute('select kind, amount from mm_cash_move where z_id = :z order by id', z=z)
    assert [(k, float(a)) for k, a in db.cur] == [('IN', 10), ('OUT', -4)]
    assert db.one('select register_id from mm_payment where id = :b', b=b)[0] is None
    db.proc('cancel_payment', r)
    db.commit()
    assert db.one('select status from mm_payment where id = :r', r=r)[0] == 'C'
    assert float(db.one('select sum(amount) from mm_cash_move where payment_id = :r', r=r)[0]) == 0
    db.fails(170, 'cancel_payment', r)                                  # twice
    db.fn('close_z', int, ids['reg'])
    db.commit()
    db.fails(114, 'cancel_payment', p)                                  # its Z is closed
