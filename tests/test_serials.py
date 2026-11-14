"""test_serials.py -- the cards of mobile phones (items with serial numbers) in MM_CORE, and their
PINs (MM_PIN, encrypted). Needs EXECUTE on DBMS_CRYPTO (db/GRANT_CRYPTO.sql).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: it commits, on its own items (TST..), and removes them at the end.
"""
import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN, Db, connect, close_open_z  # noqa: E402

env = test_core.env      # the fixture of test_core.py: its items, customer, supplier, register

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')


@pytest.fixture(scope='module')
def card(env):
    """an item with serials, 10,00 with VAT 24%; the register TST with an open Z"""
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost, serial_tracked) "
                   "values (:c, 'Test card', :cat, 'A', 10, 9.5, 'Y') returning id into :v",
                   c=f"TST{ids['tag']}C", cat=cat, v=v)
    ids['card'] = v.getvalue()[0]
    db.commit()
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    return db, ids


def load(db, ids, n, prefix):
    """n cards straight to the stock; their serials"""
    out = []
    for k in range(n):
        s = f"{prefix}-{ids['tag']}-{k:03d}"
        db.fn('load_serial', int, ids['card'], s, '%012d' % (k + 4711))
        out.append(s)
    db.commit()
    return out


def status(db, serial):
    return db.one('select status from mm_serial where serial = :s', s=serial)[0]


def consistent(db, ids):
    return db.one('select count(*) from mm_serial_check where item_id = :i', i=ids['card'])[0] == 0


def test_load_and_rules(card):
    db, ids = card
    s0 = db.stock(ids['card'])
    serials = load(db, ids, 3, 'LD')
    assert db.stock(ids['card']) == s0 + 3 and consistent(db, ids)
    db.fails(136, 'load_serial', ids['card'], serials[0], '1234', rtype=int)       # twice
    db.fails(125, 'load_serial', ids['b'], 'ABCD-1', '1234', rtype=int)            # not an item with serials
    db.fails(134, 'load_serial', ids['card'], 'a b', '1234', rtype=int)            # a bad serial
    db.fails(135, 'load_serial', ids['card'], 'GOOD-1', '12ab', rtype=int)         # a bad PIN
    db.fails(133, 'adjust_stock', ids['card'], 1, 'x')                            # stock = the cards
    db.fails(131, 'scan', db.fn('start_count', int, f"TST {ids['tag']} c"), f"TST{ids['tag']}C", rtype=int)


def test_pin_encrypted_and_shown_only_to_allowed(card):
    db, ids = card
    (serial,) = load(db, ids, 1, 'PIN')
    sid, enc = db.one('select id, rawtohex(pin_enc) from mm_serial where serial = :s', s=serial)
    pin = '%012d' % 4711
    assert pin not in enc and pin.encode().hex().upper() not in enc and len(enc) == 64
    db.fails(143, 'reveal_pin', sid, 'TSTNOBODY', rtype=str)
    db.cur.execute("insert into mm_pin_user (username) values ('TSTBOSS')")
    db.commit()
    assert db.fn('reveal_pin', str, sid, 'tstboss') == pin
    db.commit()
    assert db.one("select count(*) from mm_pin_log where serial_id = :s and username = 'TSTBOSS' "
                  "and reason = 'REVEAL'", s=sid)[0] == 1
    db.fails(144, 'receipt_pin', sid, rtype=str)                                   # not sold


def test_purchase_with_serials(card):
    db, ids = card
    s0 = db.stock(ids['card'])
    d = db.fn('new_doc', int, 'TAG', p_supplier_id=ids['supplier'], p_payment='CREDIT')
    line = db.fn('add_line', int, d, ids['card'], 2)
    db.fn('add_serial', int, line, f"PU-{ids['tag']}-1", '11112222')
    db.fails(128, 'post_doc', d, rtype=int)                                        # 2 pieces, 1 serial
    d = db.fn('new_doc', int, 'TAG', p_supplier_id=ids['supplier'], p_payment='CREDIT')
    line = db.fn('add_line', int, d, ids['card'], 2)
    for k in (1, 2):
        db.fn('add_serial', int, line, f"PU-{ids['tag']}-{k}", '11112222')
    assert status(db, f"PU-{ids['tag']}-1") == 'N'
    db.fn('post_doc', int, d)
    db.commit()
    assert status(db, f"PU-{ids['tag']}-1") == 'A' and db.stock(ids['card']) == s0 + 2 and consistent(db, ids)
    # the purchase cancelled: its cards void
    db.proc('cancel_doc', d)
    db.commit()
    assert status(db, f"PU-{ids['tag']}-2") == 'X' and db.stock(ids['card']) == s0 and consistent(db, ids)


def test_sale_takes_the_oldest_and_cancel_gives_back(card):
    db, ids = card
    serials = load(db, ids, 3, 'SL')
    oldest = db.one("select serial from mm_serial where item_id = :i and status = 'A' order by id "
                    "fetch first 1 row only", i=ids['card'])[0]
    s0 = db.stock(ids['card'])
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fails(127, 'add_line', d, ids['card'], 1, rtype=int)                       # not with add_line
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    a = db.fn('sell_serial', int, d, ids['card'])
    b = db.fn('sell_serial', int, d, p_serial=serials[2])                          # a card scanned
    assert db.one('select serial from mm_serial where id = :a', a=a)[0] == oldest
    qty, total = db.one('select qty, total from mm_doc_line where doc_id = :d', d=d)
    assert (float(qty), float(total)) == (2, 20.0)
    line = db.one('select id from mm_doc_line where doc_id = :d', d=d)[0]
    db.fails(126, 'update_line', line, 3, 10)                                      # the qty is the cards
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    a = db.fn('sell_serial', int, d, ids['card'])
    b = db.fn('sell_serial', int, d, ids['card'])
    db.proc('release_serial', b)
    assert float(db.one('select qty from mm_doc_line where doc_id = :d', d=d)[0]) == 1
    db.fn('post_doc', int, d)
    db.commit()
    assert db.one('select status from mm_serial where id = :a', a=a)[0] == 'S'
    assert db.one('select status from mm_serial where id = :b', b=b)[0] == 'A'
    assert db.stock(ids['card']) == s0 - 1 and consistent(db, ids)
    assert db.fn('receipt_pin', str, a) is not None                                # sold today
    db.commit()
    db.proc('cancel_doc', d)
    db.commit()
    assert db.one('select status from mm_serial where id = :a', a=a)[0] == 'A'
    assert db.stock(ids['card']) == s0 and consistent(db, ids)
    db.fails(144, 'receipt_pin', a, rtype=str)
    # an invoice with cards: no credit note (cancel it instead)
    t = db.fn('new_doc', int, 'TPY', p_customer_id=ids['customer'], p_payment='CREDIT')
    db.fn('sell_serial', int, t, ids['card'])
    db.fn('post_doc', int, t)
    db.commit()
    db.fails(129, 'credit_note', t, rtype=int)
    db.proc('cancel_doc', t)
    db.commit()
    assert consistent(db, ids)


def test_a_draft_deleted_gives_the_cards_back(card):
    db, ids = card
    load(db, ids, 1, 'DR')
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    a = db.fn('sell_serial', int, d, ids['card'])
    db.commit()
    assert db.one('select status from mm_serial where id = :a', a=a)[0] == 'R'
    db.proc('delete_doc', d)
    db.commit()
    assert db.one('select status, out_line_id from mm_serial where id = :a', a=a) == ('A', None)


def test_no_card_left(card):
    db, ids = card
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fails(140, 'sell_serial', d, p_serial='NO-SUCH-CARD', rtype=int)
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])      # (fails rolled the first back)
    db.fails(139, 'sell_serial', d, rtype=int)


def test_two_tills_never_take_the_same_card(card):
    db, ids = card
    load(db, ids, 2, 'TW')
    other = connect()
    other.call_timeout = 3000        # SKIP LOCKED: the second does not wait for the first
    o = Db(other)
    try:
        d1 = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
        d2 = o.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
        a = db.fn('sell_serial', int, d1, ids['card'])
        b = o.fn('sell_serial', int, d2, ids['card'])
        assert a != b
    finally:
        db.conn.rollback()
        other.rollback()
        other.close()
    close_open_z(db, ids['reg'])


def test_one_card_of_each_in_a_sale(card):
    """MAX_PER_SALE = 1 (the cards of the demo): a second card of the same value in a sale is refused"""
    db, ids = card
    load(db, ids, 2, 'MX')
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
    db.cur.execute('update mm_item set max_per_sale = 1 where id = :i', i=ids['card'])
    db.commit()
    try:
        d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
        db.fn('sell_serial', int, d, ids['card'])
        db.commit()
        db.fails(157, 'sell_serial', d, ids['card'], rtype=int)
        db.fn('post_doc', int, d)                                  # one: fine
        db.commit()
    finally:
        db.cur.execute('update mm_item set max_per_sale = null where id = :i', i=ids['card'])
        db.commit()


def test_invoice_with_many_cards_and_their_serials(card):
    """an invoice of sale to a reseller: no limit, many cards on one line (sell_serials), and the
    serials under the line (MM_DOC_SERIALS); not enough cards: none taken"""
    db, ids = card
    serials = load(db, ids, 4, 'IV')
    db.cur.execute('update mm_item set max_per_sale = 1 where id = :i', i=ids['card'])
    db.commit()
    try:
        d = db.fn('new_doc', int, 'TPY', p_customer_id=ids['customer'], p_payment='CREDIT')
        avail = db.one("select count(*) from mm_serial where item_id = :i and status = 'A'", i=ids['card'])[0]
        db.fails(140, 'sell_serials', d, ids['card'], avail + 1, rtype=int)      # all or none
        d = db.fn('new_doc', int, 'TPY', p_customer_id=ids['customer'], p_payment='CREDIT')
        assert db.fn('sell_serials', int, d, ids['card'], 3) == 3
        db.fn('post_doc', int, d)
        db.commit()
        db.cur.execute('select line_no, serial from mm_doc_serials where doc_id = :d order by serial', d=d)
        rows = db.cur.fetchall()
        assert len(rows) == 3 and {r[0] for r in rows} == {1}                  # 3 serials, one line
        assert float(db.one('select qty from mm_doc_line where doc_id = :d', d=d)[0]) == 3
        assert all(s in serials or s.startswith(('LD-', 'PIN-', 'SL-', 'DR-', 'TW-', 'MX-'))
                   for _, s in rows)
    finally:
        db.cur.execute('update mm_item set max_per_sale = null where id = :i', i=ids['card'])
        db.commit()
