"""test_fifo.py -- FIFO (MM_FIFO, MM_FIFO_OUT, mm_core.stock_move and fifo_rebuild, the views
MM_FIFO_VALUE and MM_MOVE_COST): an item of its own bought twice at two costs, sold (the oldest first),
the sale cancelled (its layers back), sold beyond its stock (a shortage at the cost of the item), bought
again (the shortage filled first), the receipt cancelled; a return of a customer; built again from the
moves, the same; MM_CHECK FIFO.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

Its costs: a receipt of a supplier (DPA) at the net of its line by piece; any other move in, and a
shortage, at that of the newest layer.
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
SEQ = itertools.count(1)
api, users = test_api.api, test_api.users


@pytest.fixture
def item(env):
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    code = 'TST%sF%d' % (ids['tag'], next(SEQ))
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test FIFO', :cat, 'B', 3.00, 1.00) returning id into :v",
                   c=code, cat=cat, v=v)
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 0)
    db.commit()
    yield db, ids, v.getvalue()[0], code
    test_core.close_open_z(db, ids['reg'])


def buy(db, ids, item, qty, price):
    d = db.fn('new_doc', int, 'DPA', p_supplier_id=ids['supplier'], p_payment='CREDIT')
    db.fn('add_line', int, d, item, qty, price)
    db.fn('post_doc', int, d)
    db.commit()
    return d


def sell(db, ids, item, qty):
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_payment='CASH')
    line = db.fn('add_line', int, d, item, qty)
    db.fn('post_doc', int, d)
    db.commit()
    return d, line


def layers(db, item):
    db.cur.execute('select qty, unit_cost, left_ from mm_fifo where item_id = :i order by id', i=item)
    return [tuple(float(x) for x in r) for r in db.cur]


def value(db, item):
    r = db.one('select stock, value from mm_fifo_value where item_id = :i', i=item)
    return float(r[0]), float(r[1])


def line_cost(db, line):
    return float(db.one('select nvl(sum(cost), 0) from mm_move_cost where doc_line_id = :l', l=line)[0])


def test_fifo(item):
    db, ids, it, _ = item
    # 10 at 1,00, then 10 at 1,20; 12 sold: 10 x 1,00 + 2 x 1,20
    buy(db, ids, it, 10, 1.00)
    p2 = buy(db, ids, it, 10, 1.20)
    assert layers(db, it) == [(10, 1.0, 10), (10, 1.2, 10)] and value(db, it) == (20, 22.0)
    s1, l1 = sell(db, ids, it, 12)
    assert line_cost(db, l1) == 12.40
    assert float(db.one('select sum(cost_last) from mm_move_cost where doc_line_id = :l', l=l1)[0]) == 14.40   # 12 x 1,20
    assert layers(db, it) == [(10, 1.0, 0), (10, 1.2, 8)] and value(db, it) == (8, 9.6)
    assert float(db.one('select next_cost from mm_fifo_value where item_id = :i', i=it)[0]) == 1.2
    # the sale cancelled: its layers back as they were, its cost 0
    db.proc('cancel_doc', s1)
    db.commit()
    assert layers(db, it) == [(10, 1.0, 10), (10, 1.2, 10)] and line_cost(db, l1) == 0
    # 25 sold, 20 there: the 5 more a shortage at the cost of the newest layer (1,20)
    s2, l2 = sell(db, ids, it, 25)
    assert line_cost(db, l2) == 10 * 1.0 + 10 * 1.2 + 5 * 1.2
    assert value(db, it) == (-5, -6.0)
    # 10 at 1,50: the shortage filled first, 5 left at 1,50
    p3 = buy(db, ids, it, 10, 1.50)
    assert layers(db, it)[-2:] == [(0, 1.2, 0), (5, 1.5, 5)] and value(db, it) == (5, 7.5)
    # that receipt cancelled: what is left of it out, then the shortage again
    db.proc('cancel_doc', p3)
    db.commit()
    assert value(db, it) == (-5, -6.0)
    # goods back from a customer (a return note, DEP): a layer at the cost of the item
    buy(db, ids, it, 10, 1.00)                          # (the cost of the item: 1,00 now)
    r = db.fn('new_doc', int, 'DEP', p_customer_id=ids['customer'], p_payment='CREDIT')
    lr = db.fn('add_line', int, r, it, 2)
    db.fn('post_doc', int, r)
    db.commit()
    assert line_cost(db, lr) == -2.0 and value(db, it) == (7, 7.0)
    # built again from the moves: the same layers, the same costs of the lines
    before = (layers(db, it), [line_cost(db, x) for x in (l1, l2, lr)])
    db.proc('fifo_rebuild', it)
    db.commit()
    assert (layers(db, it), [line_cost(db, x) for x in (l1, l2, lr)]) == before
    # MM_CHECK: the layers are the stock
    assert db.one("select count(*) from mm_check where what = 'FIFO'")[0] == 0
    assert p2 and s2 and r


def test_fifo_in_the_pages(item, api, users):
    """the REST: the layers of an item and the value of its stock; the gross profit of a period (its
    receipts: the net of the sales less their FIFO cost); the value of the stock; the profit of the day"""
    db, ids, it, code = item
    buy(db, ids, it, 10, 1.00)
    buy(db, ids, it, 10, 1.20)
    sell(db, ids, it, 12)                    # 12 x 3,00 with VAT 13%: net 31,86; cost 12,40
    x = get(api, '/api/items/' + code)
    assert [(f['qty'], f['unit_cost'], f['left_'], f['doc_type']) for f in x['fifo']] == [(10, 1.2, 8, 'DPA')]
    assert (x['fifo_value'], x['fifo_unit'], x['fifo_next']) == (9.6, 1.2, 1.2)
    p = [r for r in get(api, '/api/reports/profit')['rows'] if r['code'] == code][0]
    net = float(db.one("select sum(net) from mm_doc_line where item_id = :i and doc_id in "
                       "(select id from mm_doc where doc_type = 'ALP')", i=it)[0])
    assert (p['qty'], p['revenue'], p['cost'], p['profit']) == (12, net, 12.4, round(net - 12.4, 2))
    # the other way: the cost of the last purchase when it was sold (1,20 x 12); both are given
    assert (p['cost_fifo'], p['cost_last']) == (12.4, 14.4)
    r = get(api, '/api/reports/profit?method=LAST')
    p = [x for x in r['rows'] if x['code'] == code][0]
    assert (r['method'], r['default_method'], p['cost'], p['profit']) == ('LAST', 'FIFO', 14.4, round(net - 14.4, 2))
    v = [r for r in get(api, '/api/reports/stock-value')['rows'] if r['code'] == code][0]
    assert (v['stock'], v['value'], v['value_fifo'], v['value_last'], v['last_cost']) == (8, 9.6, 9.6, 9.6, 1.2)
    d = get(api, '/api/day')['profit']
    assert d['profit'] == round(d['revenue'] - d['cost'], 2) and d['cost'] >= 12.4 and d['method'] == 'FIFO'
    # the way of the shop: LAST, for all of the pages (the day, the reports), until set again
    try:
        assert post(api, '/api/reports/cost-method', {'method': 'last'})['method'] == 'LAST'
        assert get(api, '/api/reports/profit')['method'] == 'LAST' and get(api, '/api/day')['profit']['method'] == 'LAST'
        v = get(api, '/api/reports/stock-value')
        assert v['method'] == 'LAST' and all(x['value'] == x['value_last'] for x in v['rows'])
        assert post(api, '/api/reports/cost-method', {'method': 'AVG'}, status=400)['error'] == 'bad_method'
        assert post(api, '/api/reports/cost-method', {'method': 'LAST'}, status=403, token='CASHIER')['error'] == 'forbidden'
    finally:
        db.cur.execute("delete from mm_setting where name = 'COST_METHOD'")
        db.commit()
    assert get(api, '/api/reports/profit', 403, token='CASHIER')['error'] == 'forbidden'
