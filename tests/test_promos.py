"""test_promos.py -- the promotions of MM_CORE.REPRICE on a draft sale, at each change: % off, buy N
get M free (the cheapest pieces), a bundle for a price, one promotion a line (bundle, then N+M, then
the best %), and the discount of the whole document spread by value (the VAT of each rate right).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

The items of test_core.py: a 12,40 (VAT 24%), b 2,26 (VAT 13%), prices with VAT on a receipt.
Its promotions are named Test ..., and go after each test.
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env

TODAY = datetime.date.today()
WEEK = TODAY + datetime.timedelta(days=7)


@pytest.fixture
def pr(env):
    db, ids = env
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    yield db, ids
    db.conn.rollback()
    db.cur.execute("delete from mm_doc where register_id = :r and status = 'D'", r=ids['reg'])
    db.cur.execute("delete from mm_doc where status = 'D' and customer_id = :c", c=ids['customer'])
    db.cur.execute("update mm_doc_line set promo_id = null where promo_id in (select id from mm_promo where name like 'Test %')")
    db.cur.execute("delete from mm_promo where name like 'Test %'")
    db.commit()


def promo(db, name, kind, items=(), cats=(), **kw):
    p = db.fn('new_promo', int, 'Test ' + name, kind, kw.pop('frm', TODAY), kw.pop('to', WEEK), **kw)
    for it, q in items:
        db.proc('promo_item', p, it, p_qty=q)
    for c in cats:
        db.proc('promo_item', p, p_category_id=c)
    db.commit()
    return p


def receipt(db, ids, lines, kind='ALP'):
    if kind == 'ALP':
        d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    else:
        d = db.fn('new_doc', int, kind, p_customer_id=ids['customer'], p_payment='CREDIT')
    for it, q in lines:
        db.fn('add_line', int, d, ids[it], q)
    return d


def lines(db, d):
    db.cur.execute('select l.qty, l.promo_disc, l.doc_disc, l.net, l.vat, l.total, p.name '
                   'from mm_doc_line l left join mm_promo p on p.id = l.promo_id '
                   'where l.doc_id = :d order by l.line_no', d=d)
    return [(float(q), float(pd), float(dd), float(n), float(v), float(t), nm) for q, pd, dd, n, v, t, nm in db.cur]


def total(db, d):
    return float(db.one('select total from mm_doc where id = :d', d=d)[0])


def test_pct_on_item_and_category_best_wins(pr):
    db, ids = pr
    cat = db.one('select category_id from mm_item where id = :i', i=ids['a'])[0]
    promo(db, 'a 10%', 'PCT', items=[(ids['a'], 1)], p_pct=10)
    promo(db, 'cat 25%', 'PCT', cats=[cat], p_pct=25)
    d = receipt(db, ids, [('a', 1)])
    (q, pd, dd, n, v, t, nm), = lines(db, d)
    assert (pd, t, nm) == (3.10, 9.30, 'Test cat 25%')                 # 12,40 - 25%
    assert round(n + v, 2) == t and n == round(9.30 / 1.24, 2)


def test_buy_two_get_one_free_cheapest(pr):
    db, ids = pr
    promo(db, '2+1', 'NM', items=[(ids['a'], 1), (ids['b'], 1)], p_buy=2, p_free=1)
    d = receipt(db, ids, [('b', 2)])
    assert lines(db, d)[0][1] == 0                                     # 2: nothing yet
    db.fn('add_line', int, d, ids['a'], 1)                             # 3 pieces: the cheapest free
    ls = lines(db, d)
    assert ls[0][1] == 2.26 and ls[0][6] == 'Test 2+1' and ls[1][1] == 0
    assert total(db, d) == 2.26 + 12.40
    d = receipt(db, ids, [('b', 6)])                                   # 6: 2 free
    assert lines(db, d)[0][1] == 4.52


def test_bundle_for_a_price(pr):
    db, ids = pr
    promo(db, 'bundle', 'BUNDLE', items=[(ids['a'], 1), (ids['b'], 2)], p_price=14)
    d = receipt(db, ids, [('a', 1), ('b', 1)])
    assert total(db, d) == 12.40 + 2.26                                # not all of it there
    db.fn('add_line', int, d, ids['b'], 1)
    assert total(db, d) == 14.00                                       # 16,92 for 14,00
    ls = lines(db, d)
    assert round(sum(x[1] for x in ls), 2) == 2.92
    assert all(round(x[3] + x[4], 2) == x[5] for x in ls)                        # net + VAT on each line
    d = receipt(db, ids, [('a', 2), ('b', 4)])                         # twice
    assert total(db, d) == 28.00


def test_one_promotion_a_line(pr):
    db, ids = pr
    promo(db, 'bundle', 'BUNDLE', items=[(ids['a'], 1), (ids['b'], 1)], p_price=13)
    promo(db, 'a 50%', 'PCT', items=[(ids['a'], 1)], p_pct=50)
    d = receipt(db, ids, [('a', 1), ('b', 1)])
    assert total(db, d) == 13.00                                       # the bundle, not also 50%
    assert {x[6] for x in lines(db, d) if x[1] > 0} == {'Test bundle'}


def test_dates_and_inactive(pr):
    db, ids = pr
    promo(db, 'old', 'PCT', items=[(ids['a'], 1)], p_pct=50, frm=TODAY - datetime.timedelta(days=30),
          to=TODAY - datetime.timedelta(days=1))
    p = promo(db, 'off', 'PCT', items=[(ids['a'], 1)], p_pct=50)
    db.cur.execute("update mm_promo set active = 'N' where id = :p", p=p)
    db.commit()
    d = receipt(db, ids, [('a', 1)])
    assert total(db, d) == 12.40


def test_discount_of_the_document(pr):
    db, ids = pr
    d = receipt(db, ids, [('a', 1), ('b', 1)])                         # 14,66
    db.fails(159, 'set_doc_discount', d, 10, 0, None)                  # no reason
    d = receipt(db, ids, [('a', 1), ('b', 1)])
    db.proc('set_doc_discount', d, 10, 0, 'Πελάτης της γειτονιάς')
    assert total(db, d) == round(14.66 - 1.47, 2)
    ls = lines(db, d)
    assert round(sum(x[2] for x in ls), 2) == 1.47 and all(round(x[3] + x[4], 2) == x[5] for x in ls)
    db.proc('set_doc_discount', d, 0, 100, 'Δώρο')                     # more than all: all
    assert total(db, d) == 0
    db.proc('set_doc_discount', d, 0, 0)                               # back
    assert total(db, d) == 14.66


def test_invoice_without_vat_in_the_prices(pr):
    db, ids = pr
    promo(db, 'b 50%', 'PCT', items=[(ids['b'], 1)], p_pct=50)
    d = receipt(db, ids, [('b', 2)], kind='TPY')                       # 2 x 2,00 net
    (q, pd, dd, n, v, t, nm), = lines(db, d)
    assert (pd, n, v, t) == (2.00, 2.00, 0.26, 2.26)


def test_posted_with_the_promotion_and_z(pr):
    db, ids = pr
    promo(db, 'b 50%', 'PCT', items=[(ids['b'], 1)], p_pct=50)
    d = receipt(db, ids, [('b', 2)])
    db.fn('post_doc', int, d)
    db.commit()
    assert total(db, d) == 2.26
    amount = float(db.one("select amount from mm_cash_move where doc_id = :d and kind = 'SALE'", d=d)[0])
    assert amount == 2.26
    # posted: a new promotion does not change it
    promo(db, 'b 90%', 'PCT', items=[(ids['b'], 1)], p_pct=90)
    db.proc('recalc', d)
    assert total(db, d) == 2.26


def test_promotion_rules(pr):
    db, ids = pr
    db.fails(158, 'new_promo', 'Test x', 'PCT', TODAY, WEEK, p_pct=0, rtype=int)
    db.fails(158, 'new_promo', 'Test x', 'NM', TODAY, WEEK, p_buy=2, rtype=int)
    db.fails(158, 'new_promo', 'Test x', 'PCT', WEEK, TODAY, p_pct=10, rtype=int)
    p = promo(db, 'b', 'BUNDLE', p_price=1)
    cat = db.one('select min(id) from mm_category')[0]
    db.fails(160, 'promo_item', p, p_category_id=cat)                  # a bundle: items only
    db.fails(160, 'promo_item', p, ids['a'], cat)
