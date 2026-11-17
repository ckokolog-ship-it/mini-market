"""test_transfer.py -- the transfer between two warehouses (Δελτίο ενδοδιακίνησης, DEN; mm_core.new_doc
with p_to_warehouse_id, add_line at cost, post_doc, cancel_doc; FIFO): bought at two costs into the main
one, sent to a branch: its lines at the cost of each layer (x at a, y at b), no VAT; posted, out of the
one and into the other with the same layers and costs; sold there at those costs; a transfer cancelled:
back in both; FIFO built again, the same; not a sale (no profit, no VAT); what is refused.

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
def branch(env):
    db, ids = env
    k = next(SEQ)
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    code = 'TST%sT%d' % (ids['tag'], k)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test μελάνι', :cat, 'A', 9.00, 1.00) returning id into :v", c=code, cat=cat, v=v)
    item = v.getvalue()[0]
    w = db.cur.var(int)
    db.cur.execute("insert into mm_warehouse (code, name) values (:c, 'Test υποκατάστημα') returning id into :v",
                   c='TST%sB%d' % (ids['tag'][:3], k), v=w)
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 0)
    db.commit()
    yield db, ids, item, w.getvalue()[0], code
    db.cur.execute('update mm_register set warehouse_id = null where id = :r', r=ids['reg'])
    db.commit()
    test_core.close_open_z(db, ids['reg'])


def buy(db, ids, item, qty, price):
    d = db.fn('new_doc', int, 'DPA', p_supplier_id=ids['supplier'], p_payment='CREDIT')
    db.fn('add_line', int, d, item, qty, price)
    db.fn('post_doc', int, d)
    db.commit()


def lines(db, d):
    db.cur.execute('select qty, price, vat, total from mm_doc_line where doc_id = :d order by line_no', d=d)
    return [tuple(float(x) for x in r) for r in db.cur]


def layers(db, item, wh):
    db.cur.execute('select qty, unit_cost, left_ from mm_fifo where item_id = :i and warehouse_id = :w order by id',
                   i=item, w=wh)
    return [tuple(float(x) for x in r) for r in db.cur]


def stock(db, item, wh):
    return float(db.one('select nvl(sum(qty), 0) from mm_stock_move where item_id = :i and warehouse_id = :w',
                        i=item, w=wh)[0])


def test_a_transfer_at_cost(branch):
    db, ids, it, w2, _ = branch
    main = db.fn('main_warehouse', int)
    buy(db, ids, it, 10, 1.00)
    buy(db, ids, it, 10, 1.20)
    # the transfer: its lines at the cost of each layer, no VAT
    d = db.fn('new_doc', int, 'DEN', p_warehouse_id=main, p_to_warehouse_id=w2)
    db.fn('add_line', int, d, it, 12)
    assert lines(db, d) == [(10, 1.0, 0, 10.0), (2, 1.2, 0, 2.4)]
    db.fn('add_line', int, d, it, 3, 99)                 # (a price given: not taken, the cost)
    assert lines(db, d)[-1] == (3, 1.2, 0, 3.6)
    # posted: its lines once more by the layers; out of the main one, into the branch at the same costs
    db.fn('post_doc', int, d)
    db.commit()
    assert lines(db, d) == [(10, 1.0, 0, 10.0), (5, 1.2, 0, 6.0)]
    assert db.one('select total, vat from mm_doc where id = :d', d=d) == (16, 0)
    assert (stock(db, it, main), stock(db, it, w2)) == (5, 15)
    assert layers(db, it, w2) == [(10, 1.0, 10), (5, 1.2, 5)]
    assert [x[2] for x in layers(db, it, main)] == [0, 5]
    # sold in the branch (its register): at the costs that came, the oldest first
    db.cur.execute('update mm_register set warehouse_id = :w where id = :r', w=w2, r=ids['reg'])
    db.commit()
    s = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_payment='CASH')
    db.fn('add_line', int, s, it, 11)
    db.fn('post_doc', int, s)
    db.commit()
    assert float(db.one('select sum(cost) from mm_move_cost where doc_id = :d', d=s)[0]) == 10 * 1.0 + 1 * 1.2
    # another one, cancelled: back in both, as they were
    before = (layers(db, it, main), layers(db, it, w2))
    d2 = db.fn('new_doc', int, 'DEN', p_warehouse_id=main, p_to_warehouse_id=w2)
    db.fn('add_line', int, d2, it, 2)
    db.fn('post_doc', int, d2)
    db.commit()
    assert (stock(db, it, main), stock(db, it, w2)) == (3, 6)
    db.proc('cancel_doc', d2)
    db.commit()
    assert (stock(db, it, main), stock(db, it, w2)) == (5, 4)
    assert [x[2] for x in layers(db, it, main)] == [x[2] for x in before[0]]
    assert sum(x[2] for x in layers(db, it, w2)) == sum(x[2] for x in before[1])
    # built again from the moves: the same; MM_CHECK
    now = (layers(db, it, main), layers(db, it, w2))
    db.proc('fifo_rebuild', it)
    db.commit()
    assert (layers(db, it, main), layers(db, it, w2)) == now
    assert db.one("select count(*) from mm_check where what in ('FIFO', 'FIFO_WH', 'WAREHOUSE', 'STOCK')")[0] == 0
    # not a sale: no VAT of the day, no cost of sales
    assert db.one("select count(*) from mm_vat_day v where exists (select 1 from mm_doc x where x.id = :d)", d=d)[0] >= 0
    assert db.one("select count(*) from mm_doc d join mm_doc_type t on t.code = d.doc_type "
                  "where d.id = :d and (t.side = 'S' or t.vat_sign <> 0 or t.partner_sign <> 0)", d=d)[0] == 0
    # refused: no warehouse to go to, the same one, a partner; a warehouse to go to on another kind
    db.fails(194, 'new_doc', 'DEN', p_warehouse_id=main, rtype=int)
    db.fails(194, 'new_doc', 'DEN', p_warehouse_id=main, p_to_warehouse_id=main, rtype=int)
    db.fails(194, 'new_doc', 'DEN', p_customer_id=ids['customer'], p_to_warehouse_id=w2, rtype=int)
    db.fails(194, 'new_doc', 'DPA', p_supplier_id=ids['supplier'], p_to_warehouse_id=w2, rtype=int)


def test_a_transfer_in_the_pages(branch, api, users):
    """the REST of the office (Docs.java): a transfer made, its lines at cost, posted; the document says
    where from and where to; a cashier: no"""
    db, ids, it, w2, code = branch
    buy(db, ids, it, 4, 1.00)
    buy(db, ids, it, 4, 1.50)
    main = db.fn('main_warehouse', int)
    d = post(api, '/api/docs', {'doc_type': 'DEN', 'warehouse_id': main, 'to_warehouse_id': w2})
    assert (d['doc_type'], d['warehouse_id'], d['to_warehouse_id']) == ('DEN', main, w2)
    d = post(api, '/api/docs/%d/lines' % d['id'], {'code': code, 'qty': 6})
    assert [(x['qty'], x['price']) for x in d['lines']] == [(4, 1.0), (2, 1.5)]
    d = post(api, '/api/docs/%d/post' % d['id'])
    assert d['status'] == 'P' and d['total'] == 7.0 and d['vat'] == 0
    assert d['warehouse'] == 'K' and d['to_warehouse'] == db.one('select code from mm_warehouse where id = :w', w=w2)[0]
    x = get(api, '/api/items/' + code)
    assert {w['code']: w['stock'] for w in x['warehouses']}['K'] == 2
    assert post(api, '/api/docs', {'doc_type': 'DEN', 'to_warehouse_id': main}, status=400)['error'] == 'MM-194'
