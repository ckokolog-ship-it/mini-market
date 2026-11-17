"""test_core.py -- the package MM_CORE (db/MM_CORE.sql) in a live database.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

MM_ITEM.STOCK is reservable: its change shows after COMMIT, so these tests commit. They work on
their own items (codes TST..) and their own register (TST), and remove them at the end; the
numbers of the documents they post are used up. Run them on a test schema, not on the shop's.
"""
import random
import uuid

import pytest

oracledb = pytest.importorskip('oracledb')
from test_db import DSN, afm_ok, ean_ok  # noqa: E402  (the same helpers, the same MM_DSN)

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')


def connect():
    user, rest = DSN.split('/', 1)
    pw, where = rest.rsplit('@', 1)
    return oracledb.connect(user=user, password=pw, dsn=where)


class Db:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()

    def one(self, sql, **kw):
        self.cur.execute(sql, kw)
        return self.cur.fetchone()

    def fn(self, name, rtype, *args, **kw):
        return self.cur.callfunc('mm_core.' + name, rtype, list(args), kw)

    def proc(self, name, *args, **kw):
        self.cur.callproc('mm_core.' + name, list(args), kw)

    def fails(self, code, name, *args, rtype=None, **kw):
        """The call fails with MM-<code>; the transaction is rolled back."""
        with pytest.raises(oracledb.DatabaseError) as e:
            if rtype:
                self.fn(name, rtype, *args, **kw)
            else:
                self.proc(name, *args, **kw)
        self.conn.rollback()
        assert f'MM-{code}' in str(e.value), str(e.value)

    def stock(self, item):
        return float(self.one('select stock from mm_item where id = :i', i=item)[0])

    def commit(self):
        self.conn.commit()


@pytest.fixture(scope='module')
def env():
    """Two items (VAT B 13% and A 24%), a customer, a supplier and the register TST."""
    conn = connect()
    db = Db(conn)
    cleanup(db.cur)
    tag = uuid.uuid4().hex[:6].upper()
    cat = db.one('select min(id) from mm_category')[0]
    ids = {}
    for key, vat, price, cost in (('b', 'B', 2.26, 1.00), ('a', 'A', 12.40, 6.00)):
        v = db.cur.var(int)
        db.cur.execute('insert into mm_item (code, name, category_id, vat_code, price, cost) '
                       'values (:c, :n, :cat, :vat, :p, :cost) returning id into :v',
                       c=f'TST{tag}{key.upper()}', n='Test ' + key, cat=cat, vat=vat, p=price, cost=cost, v=v)
        ids[key] = v.getvalue()[0]
    for t in ('customer', 'supplier'):
        v = db.cur.var(int)
        db.cur.execute(f"insert into mm_{t} (name) values ('Test {tag}') returning id into :v", v=v)
        ids[t] = v.getvalue()[0]
    db.cur.execute("insert into mm_register (code, name) values ('TST', 'Test')")
    ids['reg'] = db.one("select id from mm_register where code = 'TST'")[0]
    ids['tag'] = tag
    db.commit()
    yield db, ids
    # remove what the tests made (this run's and any left by a run that stopped half-way)
    conn.rollback()
    try:
        cleanup(db.cur)
        conn.commit()
    finally:
        conn.close()


TEST_ITEMS = "select id from mm_item where code like 'TST%'"
TEST_DOCS = (f"select doc_id from mm_doc_line where item_id in ({TEST_ITEMS}) union "
             "select id from mm_doc where register_id in (select id from mm_register where code = 'TST') "
             "or customer_id in (select id from mm_customer where name like 'Test %') "
             "or supplier_id in (select id from mm_supplier where name like 'Test %')")


def cleanup(c):
    # (tstf...: the users of test_forms.py, which removes them itself)
    c.execute("delete from mm_auth_log where username like 'tst%' and username not like 'tstf%'")
    c.execute("delete from mm_user where username like 'tst%' and username not like 'tstf%'")   # (their sessions too)
    c.execute("delete from mm_cash_move where payment_id in (select id from mm_payment where customer_id in "
              "(select id from mm_customer where name like 'Test %') or supplier_id in "
              "(select id from mm_supplier where name like 'Test %'))")
    c.execute("delete from mm_payment where customer_id in (select id from mm_customer where name like 'Test %') "
              "or register_id in (select id from mm_register where code = 'TST') "
              "or supplier_id in (select id from mm_supplier where name like 'Test %')")
    c.execute("update mm_doc_line set promo_id = null where promo_id in (select id from mm_promo where name like 'Test %')")
    c.execute("delete from mm_promo where name like 'Test %'")
    c.execute(f'delete from mm_promo_item where item_id in ({TEST_ITEMS})')
    c.execute(f'delete from mm_pin_log where serial_id in (select id from mm_serial where item_id in ({TEST_ITEMS}))')
    c.execute(f'delete from mm_serial where item_id in ({TEST_ITEMS})')
    c.execute("delete from mm_pin_user where username like 'TST%'")
    c.execute("delete from mm_cash_move where reservation_id in (select id from mm_reservation where name like 'Test %')")
    c.execute("delete from mm_reservation where name like 'Test %'")
    c.execute(f'update mm_doc set ref_doc_id = null where ref_doc_id in ({TEST_DOCS})')
    c.execute(f'update mm_doc set invoice_id = null where invoice_id in ({TEST_DOCS})')
    # an item of the shop on a document of the tests (an order of the pages with the bread too): its
    # stock back as its moves are taken away (row by row: reservable)
    c.execute(f'select item_id, sum(qty) from mm_stock_move where doc_id in ({TEST_DOCS}) '
              f'and item_id not in ({TEST_ITEMS}) group by item_id')
    shop = c.fetchall()
    for item, qty in shop:
        c.execute('update mm_item set stock = stock - :q where id = :i', q=qty, i=item)
    # FIFO: the layers of the test items out; of an item of the shop, built again below from its moves
    c.execute(f'delete from mm_fifo_out where fifo_id in (select id from mm_fifo where item_id in ({TEST_ITEMS}))')
    c.execute(f'delete from mm_fifo where item_id in ({TEST_ITEMS})')
    c.execute(f'delete from mm_stock_move where item_id in ({TEST_ITEMS}) or doc_id in ({TEST_DOCS})')
    c.execute(f'delete from mm_count_line where item_id in ({TEST_ITEMS})')
    c.execute("delete from mm_count where name like 'TST %'")
    c.execute(f"delete from mm_cash_move where doc_id in ({TEST_DOCS}) "
              "or register_id in (select id from mm_register where code = 'TST')")
    c.execute(f"delete from mm_points where doc_id in ({TEST_DOCS}) "
              "or customer_id in (select id from mm_customer where name like 'Test %')")
    c.execute(f'delete from mm_doc where id in ({TEST_DOCS})')
    c.execute("delete from mm_z where register_id in (select id from mm_register where code = 'TST')")
    c.execute("delete from mm_register where code = 'TST'")
    # the totals of the months of the test items (row by row: MM_MONTHS.REBUILD), of its partners. A
    # row of MM_ITEM_MONTH changed by the trigger of the moves above (reservable) is deleted only after
    # that is committed (else ORA-55754)
    for item, _ in shop:
        c.callproc('mm_core.fifo_rebuild', [item])
    c.connection.commit()
    c.execute(f'begin for r in (select item_id, month from mm_item_month where item_id in ({TEST_ITEMS})) loop '
              'delete from mm_item_month where item_id = r.item_id and month = r.month; end loop; end;')
    c.execute("delete from mm_partner_month where (kind = 'C' and partner_id in "
              "(select id from mm_customer where name like 'Test %')) or (kind = 'S' and partner_id in "
              "(select id from mm_supplier where name like 'Test %'))")
    c.execute(f'delete from mm_item where id in ({TEST_ITEMS})')
    c.execute("delete from mm_customer where name like 'Test %'")
    c.execute("delete from mm_supplier where name like 'Test %'")


def close_open_z(db, reg):
    if db.fn('open_z_of', int, reg):
        db.cur.execute("delete from mm_doc where register_id = :r and status = 'D'", r=reg)
        db.fn('close_z', int, reg)
        db.commit()


def retail(db, ids, lines, payment='CASH'):
    """A posted retail receipt on the register TST: lines [(item, qty)]; returns (id, number)."""
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'], p_payment=payment)
    for it, q in lines:
        db.fn('add_line', int, d, ids[it], q)
    no = db.fn('post_doc', int, d)
    db.commit()
    return d, no


# -- the check digits and the amounts ----------------------------------------------------------

def test_afm_and_ean_like_python(env):
    db, _ = env
    rnd = random.Random(7)
    for _ in range(200):
        afm = '%09d' % rnd.randrange(10 ** 9)
        assert db.fn('afm_ok', str, afm) == ('Y' if afm_ok(afm) and afm != '000000000' else 'N'), afm
        for n in (8, 12, 13, 14):
            code = ''.join(rnd.choice('0123456789') for _ in range(n))
            assert db.fn('ean_ok', str, code) == ('Y' if ean_ok(code) else 'N'), code
    assert db.fn('afm_ok', str, '12345678A') == 'N'
    assert db.fn('ean_ok', str, '4006381333931') == 'Y'
    assert db.fn('ean_ok', str, '12345') == 'N'


@pytest.mark.parametrize('price,qty,disc,rate,incl,want', [
    (2.26, 1, 0, 13, 'Y', (2.00, 0.26, 2.26)),
    (12.40, 3, 0, 24, 'Y', (30.00, 7.20, 37.20)),
    (10.00, 2, 10, 24, 'N', (18.00, 4.32, 22.32)),
    (1.79, 0.5, 0, 13, 'Y', (0.80, 0.10, 0.90)),   # 0.895 -> 0.90 with VAT
    (0.33, 3, 0, 6, 'N', (0.99, 0.06, 1.05)),
])
def test_amounts(env, price, qty, disc, rate, incl, want):
    db, _ = env
    o = [db.cur.var(float) for _ in range(3)]
    db.proc('amounts', price, qty, disc, rate, incl, *o)
    assert tuple(round(x.getvalue(), 2) for x in o) == want


def test_default_price(env):
    db, ids = env
    assert db.fn('default_price', float, 'ALP', ids['b']) == 2.26
    assert db.fn('default_price', float, 'TPY', ids['b']) == 2.0       # 2.26 / 1.13
    assert db.fn('default_price', float, 'TAG', ids['b']) == 1.0       # the cost
    db.cur.execute('update mm_item set wholesale_price = 1.75 where id = :i', i=ids['b'])
    assert db.fn('default_price', float, 'TPY', ids['b']) == 1.75      # the wholesale price
    assert db.fn('default_price', float, 'ALP', ids['b']) == 2.26      # retail: as before
    db.conn.rollback()


def test_find_item(env):
    db, ids = env
    assert db.fn('find_item', int, f"tst{ids['tag']}b") == ids['b']    # the code, any case
    assert db.fn('find_item', int, '2000000000015') is not None         # a barcode of the demo
    assert db.fn('find_item', int, 'NOPE-NOPE') is None


# -- the documents -------------------------------------------------------------------------------

def test_retail_receipt(env):
    db, ids = env
    close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 50)
    db.commit()
    sb, sa = db.stock(ids['b']), db.stock(ids['a'])
    nxt = db.one("select next_no from mm_doc_type where code = 'ALP'")[0]
    d, no = retail(db, ids, [('b', 2), ('a', 1)])
    assert no == nxt
    net, vat, total, st = db.one('select net, vat, total, status from mm_doc where id = :d', d=d)
    assert (float(net), float(vat), float(total), st) == (14.0, 2.92, 16.92, 'P')
    assert db.stock(ids['b']) == sb - 2 and db.stock(ids['a']) == sa - 1
    kind, amount = db.one('select kind, amount from mm_cash_move where doc_id = :d', d=d)
    assert (kind, float(amount)) == ('SALE', 16.92)
    # a posted document does not change
    line = db.one('select min(id) from mm_doc_line where doc_id = :d', d=d)[0]
    db.fails(102, 'update_line', line, 1, 1)
    db.fails(102, 'add_line', d, ids['b'], 1, rtype=int)
    db.fails(102, 'post_doc', d, rtype=int)


def test_numbers_have_no_gaps(env):
    db, ids = env
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    nos = [retail(db, ids, [('b', 1)])[1] for _ in range(3)]
    assert nos == list(range(nos[0], nos[0] + 3))


def test_rules_of_posting(env):
    db, ids = env
    close_open_z(db, ids['reg'])
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fn('add_line', int, d, ids['b'], 1)
    db.fails(112, 'post_doc', d, rtype=int)                 # no open Z
    d = db.fn('new_doc', int, 'ALP')
    db.fn('add_line', int, d, ids['b'], 1)
    db.fails(110, 'post_doc', d, rtype=int)                 # retail without a register
    d = db.fn('new_doc', int, 'TDA')
    db.fails(109, 'post_doc', d, rtype=int)                 # no lines
    d = db.fn('new_doc', int, 'TDA')
    db.fn('add_line', int, d, ids['b'], 1)
    db.fails(104, 'post_doc', d, rtype=int)                 # an invoice without a customer
    db.fails(104, 'new_doc', 'TAG', p_customer_id=ids['customer'], rtype=int)
    db.fails(105, 'new_doc', 'TAG', p_supplier_id=ids['supplier'], p_register_id=ids['reg'], rtype=int)
    db.fails(101, 'new_doc', 'XXX', rtype=int)


def test_purchase_raises_stock_and_cost(env):
    db, ids = env
    s = db.stock(ids['a'])
    d = db.fn('new_doc', int, 'TAD', p_supplier_id=ids['supplier'], p_payment='CREDIT')
    db.fn('add_line', int, d, ids['a'], 10, 5.5)
    db.fn('post_doc', int, d)
    db.commit()
    assert db.stock(ids['a']) == s + 10
    assert float(db.one('select cost from mm_item where id = :i', i=ids['a'])[0]) == 5.5
    assert float(db.one('select total from mm_doc where id = :d', d=d)[0]) == 68.2   # 55 + 24%


def test_draft_lines(env):
    db, ids = env
    d = db.fn('new_doc', int, 'TPY', p_customer_id=ids['customer'], p_payment='CREDIT')
    l1 = db.fn('add_line', int, d, ids['b'], 3)          # 3 x 2.00 + 13%
    l2 = db.fn('add_line', int, d, ids['a'], 1, 10, 50)  # 10 - 50% + 24%
    assert db.one('select total from mm_doc where id = :d', d=d)[0] == 6.78 + 6.2
    db.proc('update_line', l1, 1, 2)
    db.proc('delete_line', l2)
    assert float(db.one('select total from mm_doc where id = :d', d=d)[0]) == 2.26
    db.proc('delete_doc', d)
    assert db.one('select count(*) from mm_doc where id = :d', d=d)[0] == 0
    db.conn.rollback()


def test_cancel_while_z_open(env):
    db, ids = env
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    s = db.stock(ids['b'])
    d, _ = retail(db, ids, [('b', 4)], payment='CARD')
    assert db.stock(ids['b']) == s - 4
    db.proc('cancel_doc', d)
    db.commit()
    assert db.stock(ids['b']) == s
    assert db.one('select status from mm_doc where id = :d', d=d)[0] == 'C'
    assert float(db.one('select sum(amount) from mm_cash_move where doc_id = :d', d=d)[0]) == 0
    db.fails(113, 'cancel_doc', d)


def test_z(env):
    db, ids = env
    close_open_z(db, ids['reg'])
    z = db.fn('open_z', int, ids['reg'], 100)
    db.commit()
    db.fails(118, 'open_z', ids['reg'], rtype=int)
    retail(db, ids, [('b', 1)])                          # 2.26, 13%
    retail(db, ids, [('a', 2)], payment='CARD')          # 24.80, 24%
    gone, _ = retail(db, ids, [('a', 1)])
    db.proc('cancel_doc', gone)
    db.proc('cash_in_out', ids['reg'], -20, 'Ψωμί για το μαγαζί')
    db.commit()
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.commit()
    db.fails(120, 'close_z', ids['reg'], rtype=int)      # a draft is open
    db.proc('delete_doc', d)
    assert db.fn('close_z', int, ids['reg']) == z
    db.commit()
    docs, net, vat, total, cash, card, st = db.one(
        'select docs, net, vat, total, cash, card, status from mm_z where id = :z', z=z)
    assert (docs, float(total), float(cash), float(card), st) == (2, 27.06, 2.26, 24.8, 'C')
    assert float(net) + float(vat) == 27.06
    db.cur.execute('select vat_code, total from mm_z_vat where z_id = :z order by vat_code', z=z)
    assert [(c, float(t)) for c, t in db.cur] == [('A', 24.8), ('B', 2.26)]
    # after the Z: no cancel, a credit note instead (for invoices)
    d = db.one("select max(id) from mm_doc where z_id = :z and status = 'P'", z=z)[0]
    db.fails(114, 'cancel_doc', d)
    db.fails(112, 'cash_in_out', ids['reg'], 5, 'x')


def balance(db, kind, pid):
    """the balance of a customer (C, + he owes) or of a supplier (S, + we owe), as its ledger"""
    b = float(db.one('select nvl(sum(debit - credit), 0) from mm_partner_event where kind = :k and partner_id = :p',
                     k=kind, p=pid)[0])
    return round(b if kind == 'C' else -b, 2)


def note(db, ids, kind, lines, partner='customer'):
    d = db.fn('new_doc', int, kind, p_payment='CREDIT', **{'p_%s_id' % partner: ids[partner]})
    for it, q in lines:
        db.fn('add_line', int, d, ids[it], q)
    db.fn('post_doc', int, d)
    return d


def total(db, d):
    return float(db.one('select total from mm_doc where id = :d', d=d)[0])


def test_notes_and_their_invoice(env):
    """a delivery note moves the stock, not the balance; its invoice the balance, not the stock; one
    invoice of many notes"""
    db, ids = env
    c = ids['customer']
    s, b0 = db.stock(ids['b']), balance(db, 'C', c)
    n1 = note(db, ids, 'DAP', [('b', 5)])
    n2 = note(db, ids, 'DAP', [('b', 2), ('a', 1)])
    db.commit()
    assert db.stock(ids['b']) == s - 7 and balance(db, 'C', c) == b0
    j = db.fn('new_doc', int, 'TPY', p_customer_id=c, p_payment='CREDIT')
    db.fn('add_line', int, j, ids['b'], 1)
    db.fails(183, 'post_doc', j, rtype=int)                           # an invoice of sale: from its notes
    i = db.fn('invoice_from', int, n1)
    db.proc('add_note', i, n2)
    t, st = db.one('select doc_type, status from mm_doc where id = :i', i=i)
    assert (t, st) == ('TPY', 'D')
    assert db.one('select count(*) from mm_doc_line where doc_id = :i', i=i)[0] == 3
    assert total(db, i) == round(total(db, n1) + total(db, n2), 2)
    db.fn('post_doc', int, i)
    db.commit()
    assert db.stock(ids['b']) == s - 7                                # the invoice: no stock
    assert balance(db, 'C', c) == round(b0 + total(db, i), 2)
    db.cur.execute('select invoice_id from mm_doc where id in (:a, :b)', a=n1, b=n2)
    assert {r[0] for r in db.cur} == {i}
    # a note into one invoice only; a note of another kind or of another customer: not into it
    j = db.fn('new_doc', int, 'TPY', p_customer_id=c, p_payment='CREDIT')
    db.commit()
    db.fails(184, 'add_note', j, n1)
    p = note(db, ids, 'DPA', [('b', 1)], 'supplier')
    db.commit()
    db.fails(184, 'add_note', j, p)
    other = db.one("select min(id) from mm_customer where id <> :c", c=c)[0]
    n3 = db.fn('new_doc', int, 'DAP', p_customer_id=other, p_payment='CREDIT')
    db.fn('add_line', int, n3, ids['b'], 1)
    db.commit()
    db.fails(184, 'add_note', j, n3)                                   # a draft note
    db.fn('post_doc', int, n3)
    db.commit()
    db.fails(184, 'add_note', j, n3)                                   # another customer
    db.proc('delete_doc', j)
    # a note in an invoice is not cancelled before its invoice; the invoice cancelled frees its notes
    db.fails(185, 'cancel_doc', n1)
    db.proc('cancel_doc', i)
    db.commit()
    assert balance(db, 'C', c) == b0 and db.stock(ids['b']) == s - 7      # (+1 of the DPA, -1 of n3)
    assert db.one('select count(invoice_id) from mm_doc where id in (:a, :b)', a=n1, b=n2)[0] == 0
    db.proc('cancel_doc', n1)
    db.commit()
    assert db.stock(ids['b']) == s - 2


def test_purchase_note_and_invoice(env):
    db, ids = env
    sp = ids['supplier']
    s, b0 = db.stock(ids['a']), balance(db, 'S', sp)
    d = db.fn('new_doc', int, 'DPA', p_supplier_id=sp, p_payment='CREDIT')
    db.fn('add_line', int, d, ids['a'], 4, 6.5)
    db.fn('post_doc', int, d)
    db.commit()
    assert db.stock(ids['a']) == s + 4 and balance(db, 'S', sp) == b0
    i = db.fn('invoice_from', int, d)
    assert db.one('select doc_type from mm_doc where id = :i', i=i)[0] == 'TAG'
    db.fn('post_doc', int, i)
    db.commit()
    assert db.stock(ids['a']) == s + 4 and balance(db, 'S', sp) == round(b0 + total(db, i), 2)
    assert float(db.one('select cost from mm_item where id = :i', i=ids['a'])[0]) == 6.5


def test_tda_both(env):
    """an invoice that is also its delivery note: the stock and the balance"""
    db, ids = env
    c = ids['customer']
    s, b0 = db.stock(ids['b']), balance(db, 'C', c)
    d = note(db, ids, 'TDA', [('b', 3)])
    db.commit()
    assert db.stock(ids['b']) == s - 3 and balance(db, 'C', c) == round(b0 + total(db, d), 2)
    db.fails(184, 'invoice_from', d, rtype=int)                       # no invoice from it


def test_credit_note(env):
    """goods back of an invoice: a return note (the stock back), then its credit note (the balance)"""
    db, ids = env
    c = ids['customer']
    n = note(db, ids, 'DAP', [('b', 5)])
    d = db.fn('invoice_from', int, n)
    db.fn('post_doc', int, d)
    db.commit()
    s, b0 = db.stock(ids['b']), balance(db, 'C', c)
    r = db.fn('credit_note', int, d)
    t, ref, st = db.one('select doc_type, ref_doc_id, status from mm_doc where id = :c', c=r)
    assert (t, ref, st) == ('DEP', d, 'D')
    assert total(db, r) == total(db, d)
    line = db.one('select id from mm_doc_line where doc_id = :r', r=r)[0]
    db.proc('update_line', line, 2, 2)                                 # 2 of the 5 back
    db.fn('post_doc', int, r)
    db.commit()
    assert db.stock(ids['b']) == s + 2 and balance(db, 'C', c) == b0
    cn = db.fn('invoice_from', int, r)
    assert db.one('select doc_type from mm_doc where id = :c', c=cn)[0] == 'PPY'
    db.fn('post_doc', int, cn)
    db.commit()
    assert db.stock(ids['b']) == s + 2 and balance(db, 'C', c) == round(b0 - total(db, cn), 2)
    db.fails(115, 'credit_note', cn, rtype=int)            # not of a credit note
    db.fails(115, 'credit_note', n, rtype=int)             # not of a note


def test_adjust_stock(env):
    db, ids = env
    s = db.stock(ids['a'])
    db.fails(116, 'adjust_stock', ids['a'], 1, None)
    db.proc('adjust_stock', ids['a'], -1.5, 'Σπασμένο')
    db.commit()
    assert db.stock(ids['a']) == s - 1.5


# -- the count of the stock (the phones) -------------------------------------------------------

def test_count(env):
    db, ids = env
    b_code = f"TST{ids['tag']}B"
    s = db.stock(ids['b'])
    cnt = db.fn('start_count', int, f"TST {ids['tag']}")
    db.commit()
    assert db.fn('scan', int, cnt, b_code, 2, p_device='phone1') == ids['b']
    db.fn('scan', int, cnt, b_code, 3, p_device='phone2')            # ADD: 5
    db.commit()
    db.fails(123, 'scan', cnt, 'NOPE-NOPE', rtype=int)
    db.fails(124, 'scan', cnt, b_code, -1, rtype=int)
    q, sysq = db.one('select counted_qty, system_qty from mm_count_line where count_id = :c', c=cnt)
    assert (float(q), float(sysq)) == (5, s)
    # a sale after the scan: it stays sold, the count fixes only what was on the shelf
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    retail(db, ids, [('b', 1)])
    db.proc('post_count', cnt)
    db.commit()
    assert db.stock(ids['b']) == 5 - 1
    assert db.one("select count(*) from mm_stock_move where count_id = :c and kind = 'ADJ'", c=cnt)[0] == 1
    db.fails(121, 'scan', cnt, b_code, rtype=int)                    # posted
    db.fails(121, 'post_count', cnt)


def test_count_set_and_cancel(env):
    db, ids = env
    s = db.stock(ids['a'])
    cnt = db.fn('start_count', int, f"TST {ids['tag']} 2")
    db.fn('scan', int, cnt, f"TST{ids['tag']}A", 7)
    db.fn('scan', int, cnt, f"TST{ids['tag']}A", 2, p_mode='SET')
    assert float(db.one('select counted_qty from mm_count_line where count_id = :c', c=cnt)[0]) == 2
    db.proc('cancel_count', cnt)
    db.commit()
    assert db.stock(ids['a']) == s
    db.fails(121, 'scan', cnt, f"TST{ids['tag']}A", rtype=int)


def test_two_phones_scan_without_waiting(env):
    """Two phones scan different items of the same count at the same time."""
    db, ids = env
    cnt = db.fn('start_count', int, f"TST {ids['tag']} 3")
    db.commit()
    other = connect()
    other.call_timeout = 3000
    try:
        db.fn('scan', int, cnt, f"TST{ids['tag']}A", 1)
        o = Db(other)
        o.fn('scan', int, cnt, f"TST{ids['tag']}B", 1)
        other.commit()
        db.commit()
        assert db.one('select count(*) from mm_count_line where count_id = :c', c=cnt)[0] == 2
    finally:
        db.proc('cancel_count', cnt)
        db.commit()
        other.close()


def test_max_per_sale(env):
    """at most MAX_PER_SALE of an item in a retail receipt; invoices and purchases have no limit"""
    db, ids = env
    db.cur.execute('update mm_item set max_per_sale = 2 where id = :i', i=ids['b'])
    db.commit()
    try:
        if not db.fn('open_z_of', int, ids['reg']):
            db.fn('open_z', int, ids['reg'])
        d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
        line = db.fn('add_line', int, d, ids['b'], 2)
        db.commit()
        db.fails(157, 'add_line', d, ids['b'], 1, rtype=int)
        db.fails(157, 'update_line', line, 3, 2.26)
        db.fn('post_doc', int, d)
        db.commit()
        i = db.fn('new_doc', int, 'TDA', p_customer_id=ids['customer'], p_payment='CREDIT')
        db.fn('add_line', int, i, ids['b'], 10)                      # an invoice: no limit
        p = db.fn('new_doc', int, 'TAD', p_supplier_id=ids['supplier'], p_payment='CREDIT')
        db.fn('add_line', int, p, ids['b'], 10)                      # a purchase: no limit
        db.conn.rollback()
    finally:
        db.cur.execute('update mm_item set max_per_sale = null where id = :i', i=ids['b'])
        db.commit()


def test_set_payment(env):
    db, ids = env
    d = db.fn('new_doc', int, 'TPY', p_customer_id=ids['customer'])
    db.proc('set_payment', d, 'CREDIT')
    assert db.one('select payment from mm_doc where id = :d', d=d)[0] == 'CREDIT'
    db.conn.rollback()
    close_open_z(db, ids['reg'])
    r = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.commit()
    db.fails(111, 'set_payment', r, 'CREDIT')                         # retail: cash or card
    db.fails(111, 'set_payment', r, 'GOLD')
    db.proc('set_payment', r, 'CARD')
    assert db.one('select payment from mm_doc where id = :d', d=r)[0] == 'CARD'
    db.proc('delete_doc', r)
    db.commit()
