"""test_expiry.py -- the expiry of the goods (MM_DOC_LINE.EXPIRES, mm_core.set_expiry, the view MM_EXPIRY;
the REST of Expiry.java and the lines of Docs.java): an item received three times with dates, what is
left of each by FIFO as it is sold, taken out, received again without a date; expired and expiring in
N days; one taken out of the stock; what is refused.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import datetime

import pytest

import test_api
import test_core
from test_api import get, post

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users
TODAY = datetime.date.today()


def iso(days):
    return (TODAY + datetime.timedelta(days=days)).isoformat()


@pytest.fixture
def milk(env):
    """an item of its own (its stock 0): every receipt of it is of this test"""
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test γάλα', :cat, 'B', 1.50, 0.90) returning id into :v",
                   c='TST%sM' % ids['tag'], cat=cat, v=v)
    db.commit()
    return db, ids, v.getvalue()[0], 'TST%sM' % ids['tag']


def left(db, item):
    db.cur.execute('select to_char(expires, \'YYYY-MM-DD\'), left_ from mm_expiry where item_id = :i order by expires', i=item)
    return [(e, float(n)) for e, n in db.cur]


def test_expiry_by_fifo(api, milk, users):
    db, ids, item, code = milk
    # three receipts with dates (DPA, the web of the office): 10 expired yesterday, 5 in 3 days, 8 in 30
    docs = []
    for qty, days in ((10, -1), (5, 3), (8, 30)):
        d = post(api, '/api/docs', {'doc_type': 'DPA', 'supplier_id': ids['supplier']})['id']
        r = post(api, '/api/docs/%d/lines' % d, {'code': code, 'qty': qty, 'expires': iso(days)})
        assert r['lines'][0]['expires'][:10] == iso(days)
        post(api, '/api/docs/%d/post' % d)
        docs.append(d)
    assert left(db, item) == [(iso(-1), 10), (iso(3), 5), (iso(30), 8)]
    # 12 sold: the oldest went first
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 0)
    db.commit()
    s = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_payment='CASH')
    db.fn('add_line', int, s, item, 12)
    db.fn('post_doc', int, s)
    db.commit()
    assert left(db, item) == [(iso(3), 3), (iso(30), 8)]
    # the next 7 days (by default): the one in 3 days; 60 days: both; one taken out (2 of its 3)
    r = get(api, '/api/expiry')
    mine = [x for x in r['rows'] if x['item_id'] == item]
    assert r['days'] == 7 and [(x['days_left'], x['left_'], x['doc_id']) for x in mine] == [(3, 3, docs[1])]
    assert len([x for x in get(api, '/api/expiry?days=60')['rows'] if x['item_id'] == item]) == 2
    w = post(api, '/api/expiry/withdraw', {'line_id': mine[0]['line_id'], 'qty': 2})
    assert [x['left_'] for x in w['rows'] if x['item_id'] == item] == [1]                  # the list after it
    assert w['withdrawn'] == 2 and float(db.one('select stock from mm_item where id = :i', i=item)[0]) == 9
    assert db.one("select note from mm_stock_move where item_id = :i order by id desc fetch first 1 rows only",
                  i=item)[0] == 'Απόσυρση: λήξη %s (DPA %s)' % (
                      (TODAY + datetime.timedelta(days=3)).strftime('%d/%m/%Y'),
                      db.one('select doc_no from mm_doc where id = :d', d=docs[1])[0])
    assert left(db, item) == [(iso(3), 1), (iso(30), 8)]
    assert post(api, '/api/expiry/withdraw', {'line_id': mine[0]['line_id'], 'qty': 5}, status=400)['error'] == 'bad_number'
    # received again, no date: the newest stock is that one first
    d = post(api, '/api/docs', {'doc_type': 'DPA', 'supplier_id': ids['supplier']})['id']
    line = post(api, '/api/docs/%d/lines' % d, {'code': code, 'qty': 4})['lines'][0]['id']
    assert post(api, '/api/docs/%d/lines/%d' % (d, line), {'expires': iso(10)})['lines'][0]['expires'][:10] == iso(10)
    assert post(api, '/api/docs/%d/lines/%d' % (d, line), {'expires': ''})['lines'][0]['expires'] is None
    assert post(api, '/api/docs/%d/lines/%d' % (d, line), {'expires': '2026-13-01'}, status=400)['error'] == 'bad_date'
    post(api, '/api/docs/%d/post' % d)
    assert left(db, item) == [(iso(3), 1), (iso(30), 8)]
    # the summary of the day: expired none left, one in the next days
    e = get(api, '/api/day')['expiry']
    assert e['days'] == 7 and e['soon'] >= 1
    # refused: a date on a sale, on a posted one; the date of the shop: EXPIRY_DAYS
    t = post(api, '/api/docs', {'doc_type': 'DAP', 'customer_id': ids['customer']})['id']
    assert post(api, '/api/docs/%d/lines' % t, {'code': code, 'qty': 1, 'expires': iso(5)}, status=400)['error'] == 'MM-192'
    db.fails(102, 'set_expiry', db.one('select id from mm_doc_line where doc_id = :d', d=d)[0], TODAY)
    db.cur.execute("insert into mm_setting (name, value) values ('EXPIRY_DAYS', '40')")
    db.commit()
    try:
        assert get(api, '/api/expiry')['days'] == 40
    finally:
        db.cur.execute("delete from mm_setting where name = 'EXPIRY_DAYS'")
        db.commit()
    assert get(api, '/api/expiry', 403, token='CASHIER')['error'] == 'forbidden'
    test_core.close_open_z(db, ids['reg'])
