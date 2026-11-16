"""test_ledger.py -- the ledgers (MM_LEDGER): an item, a customer, a supplier for a period: the
carry-over, the moves with the running balance, the totals, the balance at the end.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: on its items, customer, supplier and register; it commits and removes them at the
end. The dates are of 2001 (no other row of the database is there).
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN, close_open_z  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env


def D(m, d):
    return datetime.datetime(2001, m, d)


def rows(db, sql, **kw):
    db.cur.execute(sql + ' order by seq', kw)
    return [(k, None if a is None else float(a), None if b is None else float(b), float(c))
            for k, a, b, c in db.cur]


def item_rows(db, item, f, t):
    return rows(db, 'select kind, debit, credit, balance from table(mm_ledger.item_rows(:i, :f, :t))',
                i=item, f=f, t=t)


def partner_rows(db, kind, pid, f, t):
    return rows(db, 'select kind, debit, credit, balance from table(mm_ledger.partner_rows(:k, :p, :f, :t))',
                k=kind, p=pid, f=f, t=t)


def fill(db, what, pid, f, t):
    out = [db.cur.var(float) for _ in range(4)]
    db.cur.callproc('mm_ledger.fill', [what, pid, f, t] + out)
    return tuple(round(v.getvalue(), 2) for v in out)


def doc(db, ids, kind, partner, payment, day, lines):
    k = {'customer': 'p_customer_id', 'supplier': 'p_supplier_id'}[partner]
    d = db.fn('new_doc', int, kind, **{k: ids[partner]}, p_payment=payment, p_doc_date=day)
    for it, q in lines:
        db.fn('add_line', int, d, ids[it], q)
    db.fn('post_doc', int, d)
    db.commit()
    return d, float(db.one('select total from mm_doc where id = :d', d=d)[0])


@pytest.fixture(scope='module')
def item(env):
    """item b: 10 in on 10/1/2001, 3 out on 5/2/2001 (the moves moved to those days)"""
    db, ids = env
    d, _ = doc(db, ids, 'TAD', 'supplier', 'CREDIT', D(1, 10), [('b', 10)])
    db.cur.execute('update mm_stock_move set move_at = :t where doc_id = :d', t=D(1, 10) + datetime.timedelta(hours=8), d=d)
    close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'])
    r = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_doc_date=D(2, 5))
    db.fn('add_line', int, r, ids['b'], 3)
    db.fn('post_doc', int, r)
    db.cur.execute('update mm_stock_move set move_at = :t where doc_id = :d', t=D(2, 5) + datetime.timedelta(hours=12), d=r)
    db.commit()
    return db, ids


def test_item_ledger(item):
    db, ids = item
    assert item_rows(db, ids['b'], D(1, 1), D(2, 28)) == [('O', None, None, 0), ('M', 10, None, 10), ('M', None, 3, 7)]
    assert item_rows(db, ids['b'], D(2, 1), D(2, 28)) == [('O', None, None, 10), ('M', None, 3, 7)]   # from the carry-over
    assert item_rows(db, ids['b'], D(1, 10), D(1, 10)) == [('O', None, None, 0), ('M', 10, None, 10)]  # the whole last day
    assert item_rows(db, ids['b'], D(3, 1), D(3, 31)) == [('O', None, None, 7)]
    assert fill(db, 'I', ids['b'], D(2, 1), D(2, 28)) == (10, 0, 3, 7)
    db.cur.execute('select kind, doc_text, descr from mm_ledger_row order by seq')
    k, text, descr = db.cur.fetchall()[1]
    assert k == 'M' and text.startswith('ALP ') and descr


def test_customer_ledger(item):
    db, ids = item
    c = ids['customer']
    i1, t1 = doc(db, ids, 'TDA', 'customer', 'CREDIT', D(4, 10), [('a', 2), ('b', 1)])
    _, t2 = doc(db, ids, 'TDA', 'customer', 'CASH', D(4, 25), [('a', 1)])          # paid at once
    r = db.fn('receive', int, c, 5, 'BANK', D(4, 10))       # the same day as the invoice: after it
    x = db.fn('receive', int, c, 1, 'BANK', D(4, 12))
    db.proc('cancel_payment', x)                              # cancelled: not in the ledger
    back = db.fn('credit_note', int, i1)                      # the goods back: a note, not in the ledger
    db.fn('post_doc', int, back)
    cn = db.fn('invoice_from', int, back, D(4, 30))           # its credit note
    db.fn('post_doc', int, cn)
    db.commit()
    t3 = float(db.one('select total from mm_doc where id = :c', c=cn)[0])
    assert r
    b1 = round(t1, 2)
    assert partner_rows(db, 'C', c, D(4, 1), D(4, 30)) == [
        ('O', None, None, 0), ('M', t1, None, b1), ('M', None, 5, round(b1 - 5, 2)),
        ('M', t2, None, round(b1 - 5 + t2, 2)), ('M', None, t2, round(b1 - 5, 2)),
        ('M', None, t3, round(b1 - 5 - t3, 2))]
    assert partner_rows(db, 'C', c, D(4, 26), D(5, 31)) == [('O', None, None, round(b1 - 5, 2)),
                                                            ('M', None, t3, round(b1 - 5 - t3, 2))]
    assert fill(db, 'C', c, D(4, 1), D(4, 30)) == (0, round(t1 + t2, 2), round(5 + t2 + t3, 2), round(b1 - 5 - t3, 2))


def test_supplier_ledger(item):
    db, ids = item
    s = ids['supplier']
    _, t0 = doc(db, ids, 'TAD', 'supplier', 'CREDIT', D(6, 1), [('a', 4)])
    db.fn('pay', int, s, 10, 'BANK', D(6, 2))
    db.commit()
    # the TAD of the fixture (10/1) before the period: the carry-over is what we owe for it
    _, before = db.one("select count(*), sum(total) from mm_doc where supplier_id = :s and doc_date < :f "
                       "and status = 'P'", s=s, f=D(6, 1))
    before = float(before)
    assert partner_rows(db, 'S', s, D(6, 1), D(6, 30)) == [
        ('O', None, None, before), ('M', None, t0, round(before + t0, 2)), ('M', 10, None, round(before + t0 - 10, 2))]
    assert fill(db, 'S', s, D(6, 1), D(6, 30)) == (before, 10, t0, round(before + t0 - 10, 2))


def test_ledger_rules(env):
    db, ids = env
    for call in (lambda: item_rows(db, None, D(1, 1), D(1, 2)),
                 lambda: partner_rows(db, 'C', ids['customer'], D(2, 1), D(1, 1))):
        with pytest.raises(oracledb.DatabaseError) as e:
            call()
        db.conn.rollback()
        assert 'MM-171' in str(e.value) or 'MM-172' in str(e.value)
    with pytest.raises(oracledb.DatabaseError) as e:
        fill(db, 'X', ids['customer'], D(1, 1), D(1, 2))
    db.conn.rollback()
    assert 'MM-173' in str(e.value)


def trial(db, what, f, t, all_='Y'):
    db.cur.execute('select id, open_bal, debit, credit, close_bal from table(mm_ledger.trial_rows(:w, :f, :t, :a))',
                   w=what, f=f, t=t, a=all_)
    return {i: tuple(round(float(v), 2) for v in x) for i, *x in db.cur}


def test_trial_balance_is_the_ledgers(item):
    """the trial balances (ισοζύγια): every item, customer and supplier the totals of its own ledger
    (fill), for periods that start and end inside a month, across months, and over all the data"""
    db, ids = item
    doc(db, ids, 'TDA', 'customer', 'CREDIT', D(7, 20), [('b', 2)])          # a customer in July
    doc(db, ids, 'TAD', 'supplier', 'CASH', D(8, 3), [('b', 4)])            # a supplier paid at once (August)
    today = datetime.datetime.combine(datetime.date.today(), datetime.time())
    periods = [(D(1, 5), D(2, 10)), (D(1, 1), D(1, 31)), (D(2, 6), D(6, 30)), (D(7, 20), D(7, 20)), (D(7, 21), D(8, 3)),
               (datetime.datetime(2000, 1, 1), today), (today - datetime.timedelta(days=40), today)]
    for what in 'ICS':
        for f, t in periods:
            tb = trial(db, what, f, t)
            assert tb, (what, f)
            for pid, x in tb.items():
                assert x == fill(db, what, pid, f, t), (what, pid, f, t)
            some = trial(db, what, f, t, 'N')                                  # only those with something
            assert set(some) == {i for i, x in tb.items() if any(x)}
    assert trial(db, 'I', D(1, 5), D(2, 10))[ids['b']] == (0, 10, 3, 7)
    for args, code in ((('X', D(1, 1), D(1, 2)), 'MM-173'), (('C', D(2, 1), D(1, 1)), 'MM-172')):
        with pytest.raises(oracledb.DatabaseError) as e:
            trial(db, *args)
        db.conn.rollback()
        assert code in str(e.value)
