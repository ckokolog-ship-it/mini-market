"""test_months.py -- the totals of the months (MM_MONTHS): kept by the triggers through every change (a
document posted, cancelled, its date moved; a payment cancelled; a move moved or deleted), the same as
MM_MONTHS.REBUILD from all the moves, and what the ledgers take from them (their carry-over) the same as
from every move one by one. Two tills on the same item do not wait for each other (reservable).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: it commits, on its own items, customer, supplier, register; removes them at the end.
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN, connect  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env


def D(y, m, d):
    return datetime.datetime(y, m, d)


def nothing_off(db):
    """MM_CHECK: the totals of the months are their moves"""
    db.cur.execute("select what, detail from mm_check where what in ('ITEM_MONTH', 'PARTNER_MONTH')")
    rows = db.cur.fetchall()
    assert rows == [], rows


def month(db, sql, **kw):
    r = db.one(sql, **kw)
    return tuple(float(x or 0) for x in r) if r else (0.0, 0.0)


def item_month(db, item, m):
    return month(db, 'select qty_in + 0, qty_out + 0 from mm_item_month where item_id = :i and month = :m', i=item, m=m)


def partner_month(db, kind, pid, m):
    return month(db, 'select debit, credit from mm_partner_month where kind = :k and partner_id = :p and month = :m',
                 k=kind, p=pid, m=m)


def test_documents_and_payments(env):
    db, ids = env
    s = ids['supplier']
    d = db.fn('new_doc', int, 'TAG', p_supplier_id=s, p_payment='CREDIT', p_doc_date=D(2002, 3, 10))
    db.fn('add_line', int, d, ids['a'], 4)
    assert partner_month(db, 'S', s, D(2002, 3, 1)) == (0, 0)              # a draft: nothing yet
    db.fn('post_doc', int, d)
    db.commit()
    total = float(db.one('select total from mm_doc where id = :d', d=d)[0])
    assert partner_month(db, 'S', s, D(2002, 3, 1)) == (0, total)          # a purchase: credit
    nothing_off(db)
    # its date moved to another month: from March to May
    db.cur.execute('update mm_doc set doc_date = :t where id = :d', t=D(2002, 5, 2), d=d)
    db.commit()
    assert partner_month(db, 'S', s, D(2002, 3, 1)) == (0, 0) and partner_month(db, 'S', s, D(2002, 5, 1)) == (0, total)
    # a payment, then cancelled
    p = db.fn('pay', int, s, 10, 'BANK', D(2002, 5, 20))
    db.commit()
    assert partner_month(db, 'S', s, D(2002, 5, 1)) == (10, total)
    db.proc('cancel_payment', p)
    db.commit()
    assert partner_month(db, 'S', s, D(2002, 5, 1)) == (0, total)
    # a sale paid at once: debit and credit, the balance the same
    c = ids['customer']
    v = db.fn('new_doc', int, 'TPY', p_customer_id=c, p_payment='CASH', p_doc_date=D(2002, 6, 1))
    db.fn('add_line', int, v, ids['b'], 1)
    db.fn('post_doc', int, v)
    db.commit()
    t2 = float(db.one('select total from mm_doc where id = :d', d=v)[0])
    assert partner_month(db, 'C', c, D(2002, 6, 1)) == (t2, t2)
    nothing_off(db)


def test_moves_moved_cancelled_deleted(env):
    db, ids = env
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'])
    r = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fn('add_line', int, r, ids['b'], 2)
    db.fn('post_doc', int, r)
    db.commit()
    now = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    before = item_month(db, ids['b'], now)
    assert before[1] >= 2
    db.proc('cancel_doc', r)                          # the moves back: an "in" of 2 this month
    db.commit()
    after = item_month(db, ids['b'], now)
    assert after == (before[0] + 2, before[1])
    # a move to another month (as MM_DEMO_BIG does), then deleted
    db.proc('adjust_stock', ids['b'], 5, 'TST month')
    db.commit()
    mid = db.one("select max(id) from mm_stock_move where item_id = :i and note = 'TST month'", i=ids['b'])[0]
    db.cur.execute('update mm_stock_move set move_at = :t where id = :m', t=D(2003, 2, 14), m=mid)
    db.commit()
    assert item_month(db, ids['b'], D(2003, 2, 1)) == (5, 0)
    assert item_month(db, ids['b'], now)[0] == after[0]                   # not this month any more
    nothing_off(db)
    db.cur.execute('delete from mm_stock_move where id = :m', m=mid)
    db.cur.execute('update mm_item set stock = stock - 5 where id = :i', i=ids['b'])
    db.commit()
    assert item_month(db, ids['b'], D(2003, 2, 1)) == (0, 0)
    nothing_off(db)


def test_the_carry_over_as_every_move(env):
    """what a ledger takes from the totals of the months is what every move before it adds to"""
    db, ids = env
    for k in range(6):                                # moves over some months of 2004
        db.proc('adjust_stock', ids['a'], k + 1, 'TST carry %d' % k)
        db.commit()
        mid = db.one("select max(id) from mm_stock_move where item_id = :i", i=ids['a'])[0]
        db.cur.execute('update mm_stock_move set move_at = :t where id = :m', t=D(2004, k + 1, 10 + k), m=mid)
        db.commit()
    for frm in (D(2004, 1, 1), D(2004, 3, 12), D(2004, 3, 13), D(2004, 7, 1), D(2026, 1, 1)):
        opening = float(db.one("select balance from table(mm_ledger.item_rows(:i, :f, :f)) where kind = 'O'",
                               i=ids['a'], f=frm)[0])
        every = float(db.one('select nvl(sum(qty), 0) from mm_stock_move where item_id = :i and move_at < :f',
                             i=ids['a'], f=frm)[0])
        assert opening == every, frm
    for kind, pid in (('C', ids['customer']), ('S', ids['supplier'])):
        sign = 1 if kind == 'C' else -1
        for frm in (D(2002, 4, 1), D(2002, 5, 21), D(2002, 6, 2), D(2026, 1, 1)):
            opening = float(db.one("select balance from table(mm_ledger.partner_rows(:k, :p, :f, :f)) where kind = 'O'",
                                   k=kind, p=pid, f=frm)[0])
            every = float(db.one('select nvl(sum(debit - credit), 0) from mm_partner_event '
                                 'where kind = :k and partner_id = :p and ldate < :f', k=kind, p=pid, f=frm)[0])
            assert opening == sign * every, (kind, frm)


def test_rebuild_is_what_the_triggers_kept(env):
    db, ids = env
    q = ('select item_id, month, qty_in + 0, qty_out + 0 from mm_item_month '
         'where qty_in + 0 <> 0 or qty_out + 0 <> 0 order by 1, 2')
    qp = 'select kind, partner_id, month, debit, credit from mm_partner_month where debit <> 0 or credit <> 0 order by 1, 2, 3'
    db.cur.execute(q)
    items = db.cur.fetchall()
    db.cur.execute(qp)
    partners = db.cur.fetchall()
    db.cur.callproc('mm_months.rebuild')
    db.cur.execute(q)
    assert db.cur.fetchall() == items
    db.cur.execute(qp)
    assert db.cur.fetchall() == partners
    db.conn.rollback()


def test_two_tills_do_not_wait(env):
    """two sessions that move the same item in the same month: neither waits (reservable)"""
    db, ids = env
    db.proc('adjust_stock', ids['b'], 1, 'TST till 0')          # the row of this month exists
    db.commit()
    a, b = connect(), connect()
    try:
        b.call_timeout = 5000
        a.cursor().callproc('mm_core.adjust_stock', [ids['b'], 1, 'TST till A'])     # not committed
        b.cursor().callproc('mm_core.adjust_stock', [ids['b'], 1, 'TST till B'])     # no wait for A
    finally:
        a.rollback()
        b.rollback()
        a.close()
        b.close()
