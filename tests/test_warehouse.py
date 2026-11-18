"""test_warehouse.py -- the warehouses (MM_WAREHOUSE; the warehouse of each move, layer of FIFO, document,
register; mm_core.new_doc, stock_move, main_warehouse; the view MM_WAREHOUSE_STOCK; MM_CHECK FIFO_WH):
the main one; a second one; a receipt into each, a sale from each (its register): the stock and the
layers of each apart; FIFO built again, the same; what is refused.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import itertools

import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_api import get, post  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
api, users = test_api.api, test_api.users
SEQ = itertools.count(1)


@pytest.fixture
def two(env):
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    k = next(SEQ)
    code = 'TST%sW%d' % (ids['tag'], k)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test αποθήκες', :cat, 'B', 3.00, 1.00) returning id into :v",
                   c=code, cat=cat, v=v)
    item = v.getvalue()[0]
    w = db.cur.var(int)
    db.cur.execute("insert into mm_warehouse (code, name) values (:c, 'Test υποκατάστημα') returning id into :v",
                   c='TST%s%d' % (ids['tag'][:4], k), v=w)
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 0)
    db.commit()
    yield db, ids, item, w.getvalue()[0], code
    db.cur.execute('update mm_register set warehouse_id = null where id = :r', r=ids['reg'])
    db.commit()
    test_core.close_open_z(db, ids['reg'])


def buy(db, ids, item, qty, price, wh=None):
    d = db.fn('new_doc', int, 'DPA', p_supplier_id=ids['supplier'], p_payment='CREDIT', p_warehouse_id=wh)
    db.fn('add_line', int, d, item, qty, price)
    db.fn('post_doc', int, d)
    db.commit()
    return d


def sell(db, ids, item, qty):
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_payment='CASH')
    db.fn('add_line', int, d, item, qty)
    db.fn('post_doc', int, d)
    db.commit()
    return d


def stock(db, item):
    db.cur.execute('select warehouse_id, stock from mm_warehouse_stock where item_id = :i order by warehouse_id', i=item)
    return {w: float(q) for w, q in db.cur}


def layers(db, item, wh):
    db.cur.execute('select qty, unit_cost, left_ from mm_fifo where item_id = :i and warehouse_id = :w order by id',
                   i=item, w=wh)
    return [tuple(float(x) for x in r) for r in db.cur]


def cost(db, d):
    return float(db.one('select sum(cost) from mm_move_cost where doc_id = :d', d=d)[0])


def test_two_warehouses(two):
    db, ids, it, w2, _ = two
    main = db.fn('main_warehouse', int)
    assert db.one('select code, main from mm_warehouse where id = :w', w=main) == ('K', 'Y')
    # a receipt into each: the stock and the layers of each apart, the stock of the item both
    d1 = buy(db, ids, it, 10, 1.00)
    d2 = buy(db, ids, it, 5, 1.50, w2)
    assert db.one('select warehouse_id from mm_doc where id = :d', d=d1)[0] == main
    assert stock(db, it) == {main: 10, w2: 5}
    assert float(db.one('select stock from mm_item where id = :i', i=it)[0]) == 15
    assert layers(db, it, w2) == [(5, 1.5, 5)] and d2
    # a sale of the register (its warehouse: none, the main one): 12 there, 10: 2 short; the branch untouched
    s1 = sell(db, ids, it, 12)
    assert stock(db, it) == {main: -2, w2: 5} and layers(db, it, w2) == [(5, 1.5, 5)]
    assert cost(db, s1) == 10 * 1.0 + 2 * 1.5            # (the shortage: at the newest layer of the item)
    # the register in the branch: its sale from there
    db.cur.execute('update mm_register set warehouse_id = :w where id = :r', w=w2, r=ids['reg'])
    db.commit()
    s2 = sell(db, ids, it, 3)
    assert db.one('select warehouse_id from mm_doc where id = :d', d=s2)[0] == w2
    assert stock(db, it) == {main: -2, w2: 2} and cost(db, s2) == 4.5
    # FIFO built again from the moves: the same in each; MM_CHECK
    before = (layers(db, it, main), layers(db, it, w2))
    db.proc('fifo_rebuild', it)
    db.commit()
    assert (layers(db, it, main), layers(db, it, w2)) == before
    assert db.one("select count(*) from mm_check where what in ('FIFO', 'FIFO_WH', 'WAREHOUSE')")[0] == 0
    # a warehouse not active: no document of it
    db.cur.execute("update mm_warehouse set active = 'N' where id = :w", w=w2)
    db.commit()
    db.fails(193, 'new_doc', 'DPA', p_supplier_id=ids['supplier'], p_payment='CREDIT', p_warehouse_id=w2, rtype=int)
    db.cur.execute("update mm_warehouse set active = 'Y' where id = :w", w=w2)
    db.commit()


def test_the_stock_of_each_warehouse_in_the_pages(two, api, users):
    db, ids, it, w2, code = two
    buy(db, ids, it, 4, 1.00)
    buy(db, ids, it, 6, 1.20, w2)
    x = get(api, '/api/items/' + code)
    wcode = db.one('select code from mm_warehouse where id = :w', w=w2)[0]
    assert [(w['code'], w['stock']) for w in x['warehouses'] if w['code'] in ('K', wcode)] == [('K', 4), (wcode, 6)]
    r = get(api, '/api/warehouses')
    assert [w['code'] for w in r['rows']][0] == 'K' and r['rows'][0]['main'] == 'Y'


def test_the_warehouses_in_the_pages(two, api, users):
    """the pages of the warehouses: one made, renamed, not active (not the main one); the register in a
    branch (its sales from there; a manager); a count of a branch (its stock there, its move there); the
    value of the stock of one warehouse"""
    db, ids, it, w2, code = two
    tag = 'TST%sN' % ids['tag'][:4]
    r = post(api, '/api/warehouses', {'code': tag.lower(), 'name': 'Test νέα'})
    new = [w for w in r['rows'] if w['code'] == tag][0]
    assert (new['main'], new['active'], new['items'], new['value']) == ('N', 'Y', 0, 0)
    k = [w for w in r['rows'] if w['main'] == 'Y'][0]                 # (a register of no warehouse: the main one's)
    assert k['registers'] == db.one("select count(*) from mm_register where active = 'Y' and "
                                    "nvl(warehouse_id, :m) = :m", m=k['id'])[0] > 0
    assert post(api, '/api/warehouses', {'code': tag, 'name': 'x'}, status=400)['error'] == 'bad_warehouse'
    assert post(api, '/api/warehouses', {'code': 'a b', 'name': 'x'}, status=400)['error'] == 'bad_warehouse'
    r = post(api, '/api/warehouses/%d' % new['id'], {'name': 'Test άλλο', 'active': False})
    assert [(w['name'], w['active']) for w in r['rows'] if w['id'] == new['id']] == [('Test άλλο', 'N')]
    main = db.fn('main_warehouse', int)
    assert post(api, '/api/warehouses/%d' % main, {'active': False}, status=400)['error'] == 'bad_warehouse'
    assert post(api, '/api/warehouses', {'code': 'Q', 'name': 'x'}, status=403, token='CASHIER')['error'] == 'forbidden'
    # the register: in the branch; a receipt of it from there
    buy(db, ids, it, 6, 1.20, w2)
    s = post(api, '/api/pos/tst/warehouse', {'warehouse_id': w2})
    wcode = db.one('select code from mm_warehouse where id = :w', w=w2)[0]
    assert (s['warehouse_id'], s['warehouse']) == (w2, wcode)
    assert post(api, '/api/pos/tst/warehouse', {'warehouse_id': new['id']}, status=400)['error'] == 'bad_warehouse'
    assert post(api, '/api/pos/tst/warehouse', {'warehouse_id': w2}, status=403, token='CASHIER')['error'] == 'forbidden'
    post(api, '/api/pos/tst/scan', {'code': code, 'qty': 2}, token='CASHIER')
    p = post(api, '/api/pos/tst/pay', {'payment': 'CARD'}, token='CASHIER')['paid']
    assert db.one('select warehouse_id from mm_doc where id = :d', d=p['id'])[0] == w2
    assert stock(db, it) == {w2: 4}
    # a count of the branch: what the system has there (4), counted 3: one less there
    k = post(api, '/api/counts', {'name': 'TST count branch', 'warehouse_id': w2})
    assert (k['warehouse_id'], k['warehouse']) == (w2, wcode)
    line = post(api, '/api/counts/%d/scan' % k['id'], {'code': code, 'qty': 3})
    assert (line['system_qty'], line['counted_qty']) == (4, 3)
    post(api, '/api/counts/%d/post' % k['id'])
    assert stock(db, it) == {w2: 3}
    # the value of the stock of the branch: by FIFO, by the last cost
    v = get(api, '/api/reports/stock-value?warehouse=' + wcode)
    x = [r for r in v['rows'] if r['code'] == code][0]
    assert (v['warehouse'], x['stock'], x['value_fifo']) == (wcode, 3, 3.6)
    assert not [r for r in get(api, '/api/reports/stock-value?warehouse=K')['rows'] if r['code'] == code]
    assert db.one("select count(*) from mm_check where what in ('FIFO', 'FIFO_WH', 'STOCK')")[0] == 0


def test_the_minimum_of_a_branch(two, api, users):
    """the minimum stock of an item in a branch (MM_WAREHOUSE_MIN; the main one: MM_ITEM.MIN_STOCK):
    the items under it; what is missing, a draft DEN from the central store (whole pieces, not more than
    it has; the same draft again); posted, none missing; 0: none; what is refused"""
    db, ids, it, w2, code = two
    main = db.fn('main_warehouse', int)
    buy(db, ids, it, 10, 1.00)
    r = post(api, '/api/warehouses/%d/min' % w2, {'code': code, 'min': 4.5})
    x = [y for y in r['rows'] if y['code'] == code][0]
    assert (x['stock'], x['min_stock'], x['missing'], x['central']) == (0, 4.5, 4.5, 10) and r['drafts'] == []
    assert [w['under_min'] for w in get(api, '/api/warehouses')['rows'] if w['id'] == w2] == [1]
    assert [w['min_stock'] for w in get(api, '/api/items/' + code)['warehouses'] if w['id'] == w2] == [4.5]
    # what is missing: 5 (whole pieces), a draft DEN from the central store; again: nothing more
    r = post(api, '/api/warehouses/%d/transfer' % w2, {})
    assert r['lines'] == 1 and len(r['drafts']) == 1 and r['drafts'][0]['lines'] == 1
    d = r['drafts'][0]['id']
    assert db.one('select doc_type, status, warehouse_id, to_warehouse_id from mm_doc where id = :d', d=d) == ('DEN', 'D', main, w2)
    assert float(db.one('select sum(qty) from mm_doc_line where doc_id = :d', d=d)[0]) == 5
    r = post(api, '/api/warehouses/%d/transfer' % w2, {})
    assert r['lines'] == 0 and [y['id'] for y in r['drafts']] == [d]
    db.fn('post_doc', int, d)
    db.commit()
    assert stock(db, it) == {main: 5, w2: 5}
    r = get(api, '/api/warehouses/%d' % w2)
    assert [(y['stock'], y['missing']) for y in r['rows'] if y['code'] == code] == [(5, 0)] and r['drafts'] == []
    # more missing than the central store has: what it has
    post(api, '/api/warehouses/%d/min' % w2, {'code': code, 'min': 20})
    r = post(api, '/api/warehouses/%d/transfer' % w2, {})
    d = r['drafts'][0]['id']
    assert float(db.one('select sum(qty) from mm_doc_line where doc_id = :d', d=d)[0]) == 5
    db.proc('delete_doc', d)
    db.commit()
    # the main one: the minimum of the item; 0: none; refused: below 0, the main one as a branch, a cashier
    post(api, '/api/warehouses/%d/min' % main, {'code': code, 'min': 3})
    assert float(db.one('select min_stock from mm_item where id = :i', i=it)[0]) == 3
    assert post(api, '/api/warehouses/%d/min' % w2, {'code': code, 'min': 0})['rows'] == []
    assert post(api, '/api/warehouses/%d/min' % w2, {'code': code, 'min': -1}, status=400)['error'] == 'MM-195'
    assert post(api, '/api/warehouses/%d/transfer' % main, {}, status=400)['error'] == 'MM-195'
    assert post(api, '/api/warehouses/%d/min' % w2, {'code': 'NOSUCH', 'min': 1}, status=404)['error'] == 'not_found'
    assert get(api, '/api/warehouses/%d' % w2, status=403, token='CASHIER')['error'] == 'forbidden'
    db.cur.execute('update mm_item set min_stock = 0 where id = :i', i=it)
    db.commit()
    assert db.one('select count(*) from mm_check')[0] == 0
