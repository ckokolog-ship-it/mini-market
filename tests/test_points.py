"""test_points.py -- the points of the retail customers (MM_POINTS; mm_core.new_card, card_customer,
set_doc_customer, use_points, post_doc, cancel_doc): a card (EAN-13 2990...), a receipt of a customer
gives points by its total, points used as the discount of a receipt (its VAT right), a receipt cancelled
gives them back; what is refused. The settings POINTS_PER_EURO, POINT_VALUE, POINTS_MIN.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

The items of test_core.py: a 12,40 (VAT 24%), b 2,26 (VAT 13%).
"""
import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_api import get, post  # noqa: E402
from test_core import DSN  # noqa: E402
from test_db import ean_ok  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
api, users = test_api.api, test_api.users
NAMES = ('POINTS_PER_EURO', 'POINT_VALUE', 'POINTS_MIN')


@pytest.fixture
def points(env):
    db, ids = env
    db.cur.execute("select name, value from mm_setting where name in ('POINTS_PER_EURO', 'POINT_VALUE', 'POINTS_MIN')")
    kept = list(db.cur)
    db.cur.execute("delete from mm_setting where name in ('POINTS_PER_EURO', 'POINT_VALUE', 'POINTS_MIN')")
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 50)
    db.commit()
    yield db, ids
    db.conn.rollback()
    db.cur.execute("delete from mm_setting where name in ('POINTS_PER_EURO', 'POINT_VALUE', 'POINTS_MIN')")
    for n, v in kept:
        db.cur.execute('insert into mm_setting (name, value) values (:n, :v)', n=n, v=v)
    db.commit()
    test_core.close_open_z(db, ids['reg'])


def setting(db, name, value):
    db.cur.execute('delete from mm_setting where name = :n', n=name)
    db.cur.execute('insert into mm_setting (name, value) values (:n, :v)', n=name, v=value)
    db.commit()


def has(db, ids):
    return db.one('select points from mm_customer where id = :c', c=ids['customer'])[0]


def receipt(db, ids, lines, customer=True, use=0, post=True):
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_payment='CASH')
    for it, q in lines:
        db.fn('add_line', int, d, ids[it], q)
    if customer:
        db.proc('set_doc_customer', d, ids['customer'])
    if use:
        db.proc('use_points', d, use)
    if post:
        db.fn('post_doc', int, d)
    db.commit()
    return d


def test_points_earned_used_and_back(points):
    db, ids = points
    c = ids['customer']
    # the card: EAN-13 2990 + its id; the same again; its customer
    card = db.fn('new_card', str, c)
    assert len(card) == 13 and card.startswith('2990') and ean_ok(card) and int(card[4:12]) == c
    assert db.fn('new_card', str, c) == card
    assert db.fn('card_customer', int, card) == c and db.fn('card_customer', int, '2990999999999') is None
    # 1 point a euro (by default): 2 x 12,40 = 24,80 -> 24; 10 x 12,40 -> 124; a receipt with no customer: none
    p0 = has(db, ids)
    receipt(db, ids, [('a', 2)])
    assert has(db, ids) == p0 + 24
    receipt(db, ids, [('a', 10)])
    receipt(db, ids, [('a', 1)], customer=False)
    assert has(db, ids) == p0 + 148
    # used: less than POINTS_MIN, more than it has, more than the receipt (POINT_VALUE 1: 100 € > 12,40): no
    d = receipt(db, ids, [('a', 1)], post=False)
    db.fails(191, 'use_points', d, 50)
    db.fails(191, 'use_points', d, p0 + 149)
    db.fails(191, 'use_points', d, 10.5)
    setting(db, 'POINT_VALUE', '1')
    db.fails(191, 'use_points', d, 100)
    setting(db, 'POINT_VALUE', '0.01')
    # 100 points = 1 € off 12,40 + 2,26 (spread by value, the VAT of each rate); paid 13,66 -> 13 more
    db.fn('add_line', int, d, ids['b'], 1)
    db.proc('use_points', d, 100)
    db.commit()
    assert db.one('select total, disc_amount, disc_reason, points_used from mm_doc where id = :d', d=d) == (
        13.66, 1, 'Πόντοι 100', 100)
    assert db.one('select sum(doc_disc) from mm_doc_line where doc_id = :d', d=d)[0] == 1
    db.fn('post_doc', int, d)
    db.commit()
    assert has(db, ids) == p0 + 148 - 100 + 13
    assert db.one("select listagg(points, ',') within group (order by id) from mm_points where doc_id = :d",
                  d=d)[0] == '-100,13'
    # cancelled: its points back, both ways
    db.proc('cancel_doc', d)
    db.commit()
    assert has(db, ids) == p0 + 148
    # a draft: its customer out, its points with it; a discount by hand instead of the points
    e = receipt(db, ids, [('a', 1)], use=100, post=False)
    db.proc('set_doc_customer', e, None)
    assert db.one('select customer_id, points_used, disc_amount from mm_doc where id = :d', d=e) == (None, 0, 0)
    db.proc('set_doc_customer', e, c)
    db.proc('use_points', e, 100)
    db.proc('set_doc_discount', e, 10, 0, 'Test')
    assert db.one('select points_used from mm_doc where id = :d', d=e)[0] == 0
    db.proc('use_points', e, 0)
    db.fn('post_doc', int, e)
    db.commit()
    assert has(db, ids) == p0 + 148 + 11                                     # 12,40 - 10% = 11,16
    # no points (POINTS_PER_EURO 0); not a receipt; MM_CHECK: the points are their moves
    setting(db, 'POINTS_PER_EURO', '0')
    receipt(db, ids, [('a', 3)])
    assert has(db, ids) == p0 + 159
    t = db.fn('new_doc', int, 'TPY', p_customer_id=c, p_payment='CREDIT')
    db.fails(191, 'set_doc_customer', t, c)
    assert db.one("select count(*) from mm_check where what = 'POINTS'")[0] == 0


def test_points_at_the_till(points, api, users):
    """the REST of the till (Pos.java): a new customer with a card into the receipt, its points by its
    total; the next receipt: the customer by phone, by a scan of its card, points used, out again"""
    db, ids = points
    pos = '/api/pos/tst'
    s = get(api, pos, token='CASHIER')
    assert s['points'] == {'per_euro': 1, 'value': 0.01, 'min': 100}
    phone = '69%08d' % (ids['customer'] % 10 ** 8)
    s = post(api, pos + '/customer/new', {'name': 'Test card %s' % ids['tag'], 'phone': phone}, token='CASHIER')
    cu = s['receipt']['customer']
    assert len(cu['card']) == 13 and cu['card'].startswith('2990') and cu['points'] == 0
    s = post(api, pos + '/scan', {'code': 'TST%sA' % ids['tag'], 'qty': 10}, token='CASHIER')
    assert s['receipt']['customer']['earn'] == 124
    paid = post(api, pos + '/pay', {'payment': 'CASH', 'given': 200}, token='CASHIER')['paid']
    r = get(api, pos + '/receipt/%d' % paid['id'], token='CASHIER')
    assert (r['customer'], r['card'], r['points_earned'], r['points']) == ('Test card %s' % ids['tag'], cu['card'], 124, 124)
    # the next one: by phone, by a scan of the card (the same), 100 points used = 1 €
    s = post(api, pos + '/customer', {'code': phone[:2] + ' ' + phone[2:]}, token='CASHIER')
    assert s['receipt']['customer']['id'] == cu['id'] and s['receipt']['lines'] == []
    post(api, pos + '/scan', {'code': 'TST%sA' % ids['tag']}, token='CASHIER')
    s = post(api, pos + '/scan', {'code': cu['card']}, token='CASHIER')
    assert s['receipt']['customer']['id'] == cu['id'] and len(s['receipt']['lines']) == 1
    s = post(api, pos + '/points', {'points': 100}, token='CASHIER')
    assert (s['receipt']['total'], s['receipt']['points_used'], s['receipt']['disc_reason']) == (11.40, 100, 'Πόντοι 100')
    assert post(api, pos + '/points', {'points': 50}, status=400, token='CASHIER')['error'] == 'MM-191'
    assert post(api, pos + '/points', {'points': 500}, status=400, token='CASHIER')['error'] == 'MM-191'
    s = post(api, pos + '/customer', {'code': ''}, token='CASHIER')                  # out: no points
    assert (s['receipt']['customer'], s['receipt']['total'], s['receipt']['points_used']) == (None, 12.40, 0)
    e = post(api, pos + '/customer', {'code': '2990999999999'}, status=404, token='CASHIER')
    assert e['error'] == 'not_found'
    post(api, pos + '/void', token='CASHIER')
    # the customer: its card, its points and their moves; a card for one without (MANAGER)
    c = get(api, '/api/customers/%d' % cu['id'])
    assert (c['card'], c['points'], [m['points'] for m in c['point_moves']]) == (cu['card'], 124, [124])
    c = post(api, '/api/customers/%d/card' % ids['customer'])
    assert c['card'].startswith('2990') and c['points'] == has(db, ids)
    assert post(api, '/api/customers/%d/card' % ids['customer'], status=403, token='CASHIER')['error'] == 'forbidden'
