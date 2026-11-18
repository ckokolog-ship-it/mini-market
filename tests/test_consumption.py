"""test_consumption.py -- the consumption note (Δελτίο ανάλωσης, DAN; mm_core.set_reason; MM_CONSUMPTION): goods out
of a warehouse at the costs of the layers they take (FIFO), for a reason; no sale, no VAT; cancelled: back; the
report of the consumptions; what is refused.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_api import get, post  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env
api, users = test_api.api, test_api.users


def test_a_consumption_at_cost(env, api, users):
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    code = 'TST%sU' % ids['tag']
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test χαρτί', :cat, 'A', 3.00, 1.00) returning id into :v", c=code, cat=cat, v=v)
    item = v.getvalue()[0]
    main = db.fn('main_warehouse', int)
    for qty, price in ((10, 1.00), (5, 1.50)):
        d = db.fn('new_doc', int, 'DPA', p_supplier_id=ids['supplier'], p_payment='CREDIT')
        db.fn('add_line', int, d, item, qty, price)
        db.fn('post_doc', int, d)
    db.commit()
    # 12 damaged: its lines at the cost of each layer (10 at 1.00, 2 at 1.50), no VAT
    r = post(api, '/api/docs', {'doc_type': 'DAN', 'warehouse_id': main, 'reason': 'DAMAGE'})
    assert (r['doc_type'], r['reason'], r['warehouse_id'], r['to_warehouse_id']) == ('DAN', 'DAMAGE', main, None)
    r = post(api, '/api/docs/%d/lines' % r['id'], {'code': code, 'qty': 12})
    assert [(x['qty'], x['price'], x['vat']) for x in r['lines']] == [(10, 1, 0), (2, 1.5, 0)] and r['total'] == 13
    dan = r['id']
    post(api, '/api/docs/%d/post' % dan)
    assert float(db.one('select stock from mm_item where id = :i', i=item)[0]) == 3
    db.cur.execute('select reason, qty, cost_fifo from mm_consumption where doc_id = :d and item_id = :i', d=dan, i=item)
    assert [(a, float(b), float(c)) for a, b, c in db.cur] == [('DAMAGE', 12, 13)]
    assert db.one('select count(*) from mm_sales_doc where doc_id = :d', d=dan)[0] == 0              # (no sale)
    # the report: by warehouse and reason, at cost
    today = datetime.date.today().isoformat()
    rows = get(api, '/api/reports/consumption?from=%s&to=%s&warehouse=k' % (today, today))['rows']
    assert [(x['warehouse'], x['reason'], x['qty'], x['cost'], x['docs']) for x in rows if x['code'] == code] == [('K', 'DAMAGE', 12, 13, 1)]
    assert get(api, '/api/reports/consumption', status=403, token='CASHIER')['error'] == 'forbidden'
    # cancelled: back to the layers; MM_CHECK
    post(api, '/api/docs/%d/cancel' % dan)
    assert float(db.one('select stock from mm_item where id = :i', i=item)[0]) == 15
    assert db.one('select count(*) from mm_consumption where doc_id = :d', d=dan)[0] == 0
    # no reason given: used by the shop
    d = db.fn('new_doc', int, 'DAN', p_warehouse_id=main)
    db.fn('add_line', int, d, item, 1)
    db.fn('post_doc', int, d)
    db.commit()
    assert db.one('select reason from mm_doc where id = :d', d=d) == ('USE',)
    # refused: a warehouse it goes to, a reason of another document, a reason of no one
    db.fails(194, 'new_doc', 'DAN', p_warehouse_id=main, p_to_warehouse_id=main, rtype=int)
    t = db.fn('new_doc', int, 'DAP', p_customer_id=ids['customer'], p_payment='CREDIT')
    db.fails(194, 'set_reason', t, 'USE')
    d = db.fn('new_doc', int, 'DAN', p_warehouse_id=main)
    db.fails(194, 'set_reason', d, 'LOST')
    post(api, '/api/docs/%d/reason' % d, {'reason': 'sample'})
    assert db.one('select reason from mm_doc where id = :d', d=d) == ('SAMPLE',)
    db.proc('delete_doc', d)
    db.proc('delete_doc', t)
    db.commit()
    assert db.one("select count(*) from mm_check where what in ('FIFO', 'FIFO_WH', 'STOCK')")[0] == 0
