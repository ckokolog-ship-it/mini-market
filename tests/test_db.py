"""test_db.py -- the tables of the mini market (db/INSTALL.sql demo) in a live database.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

Every test works in its own transaction and rolls it back: the database stays as it was.
Without MM_DSN (or without the package oracledb) the tests are skipped.
"""
import os

import pytest

oracledb = pytest.importorskip('oracledb')

DSN = os.environ.get('MM_DSN')
pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')

TABLES = ['MM_VAT', 'MM_CATEGORY', 'MM_ITEM', 'MM_CUSTOMER', 'MM_SUPPLIER', 'MM_DOC_TYPE',
          'MM_REGISTER', 'MM_Z', 'MM_Z_VAT', 'MM_DOC', 'MM_DOC_LINE', 'MM_STOCK_MOVE', 'MM_CASH_MOVE']


def ean_ok(code):
    """EAN-8/UPC-A/EAN-13/GTIN-14: the weights 3,1,3,... from the right, without the check digit."""
    body, check = code[:-1], int(code[-1])
    s = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(body)))
    return (10 - s % 10) % 10 == check


def afm_ok(afm):
    """The Greek tax number: the first eight digits times 2^8..2^1, mod 11, mod 10."""
    s = sum(int(c) * 2 ** (8 - i) for i, c in enumerate(afm[:8]))
    return s % 11 % 10 == int(afm[8])


@pytest.fixture(scope='module')
def conn():
    user, rest = DSN.split('/', 1)
    pw, where = rest.rsplit('@', 1)
    c = oracledb.connect(user=user, password=pw, dsn=where)
    yield c
    c.rollback()
    c.close()


@pytest.fixture
def cur(conn):
    c = conn.cursor()
    yield c
    conn.rollback()


def one(cur, sql, **kw):
    cur.execute(sql, kw)
    return cur.fetchone()


def rejects(cur, sql, constraint, **kw):
    """The statement fails on the constraint (its name in the message)."""
    cur.execute('savepoint t')
    with pytest.raises(oracledb.DatabaseError) as e:
        cur.execute(sql, kw)
    cur.execute('rollback to savepoint t')
    assert constraint.upper() in str(e.value).upper(), str(e.value)


def item_id(cur, code='ART01'):
    return one(cur, 'select id from mm_item where code = :c', c=code)[0]


# -- what INSTALL.sql leaves ------------------------------------------------------------------

def test_tables(cur):
    cur.execute("select table_name from user_tables where table_name like 'MM\\_%' escape '\\'")
    assert set(TABLES) <= {r[0] for r in cur}


def test_vat_and_doc_types(cur):
    cur.execute('select code, rate from mm_vat order by code')
    assert cur.fetchall() == [('A', 24), ('B', 13), ('C', 6)]
    cur.execute('select code, side, stock_sign from mm_doc_type order by code')
    assert cur.fetchall() == [('ALP', 'S', -1), ('PAG', 'P', -1), ('PPY', 'S', 1),
                              ('TAG', 'P', 1), ('TPY', 'S', -1)]


def test_demo_rows(cur):
    assert one(cur, 'select count(*) from mm_item')[0] >= 30
    assert one(cur, 'select count(*) from mm_customer')[0] >= 4
    assert one(cur, 'select count(*) from mm_supplier')[0] >= 5
    assert one(cur, "select count(*) from mm_register where code = 'T1'")[0] == 1


def test_greek_stored_as_unicode(cur):
    name, n = one(cur, "select name, length(name) from mm_item where code = 'ART01'")
    assert name == 'Ψωμί χωριάτικο 1 kg' and n == len(name)


def test_demo_codes_valid(cur):
    cur.execute('select barcode from mm_item where barcode is not null')
    bad = [b for (b,) in cur if not ean_ok(b)]
    assert not bad
    cur.execute('select afm from mm_customer where afm is not null union all '
                'select afm from mm_supplier where afm is not null')
    bad = [a for (a,) in cur if not afm_ok(a)]
    assert not bad


def test_stock_is_sum_of_moves(cur):
    n = one(cur, '''select count(*) from mm_item i
                    where i.stock <> (select nvl(sum(m.qty), 0) from mm_stock_move m
                                      where m.item_id = i.id)''')[0]
    assert n == 0


def test_check_digit_helpers():
    assert ean_ok('4006381333931') and not ean_ok('4006381333932')
    assert ean_ok('96385074') and afm_ok('999000018') and not afm_ok('999000019')


# -- the constraints ---------------------------------------------------------------------------

def test_item_constraints(cur):
    cat = one(cur, 'select min(id) from mm_category')[0]
    ins = ('insert into mm_item (code, barcode, name, category_id, vat_code, unit, price) '
           'values (:code, :bc, :name, :cat, :vat, :unit, :price)')
    ok = dict(code='T-X', bc=None, name='x', cat=cat, vat='A', unit='PCS', price=1)
    rejects(cur, ins, 'MM_ITEM_CODE_UK', **{**ok, 'code': 'ART01'})
    rejects(cur, ins, 'MM_ITEM_BARCODE_UK', **{**ok, 'bc': '2000000000015'})
    rejects(cur, ins, 'MM_ITEM_BARCODE_CK', **{**ok, 'bc': '12345'})
    rejects(cur, ins, 'MM_ITEM_VAT_FK', **{**ok, 'vat': 'Z'})
    rejects(cur, ins, 'MM_ITEM_UNIT_CK', **{**ok, 'unit': 'BOX'})
    rejects(cur, ins, 'MM_ITEM_PRICE_CK', **{**ok, 'price': -1})
    cur.execute(ins, ok)  # the good one goes in


def test_partner_constraints(cur):
    for t in ('customer', 'supplier'):
        ins = f'insert into mm_{t} (name, afm, email) values (:n, :afm, :em)'
        rejects(cur, ins, f'MM_{t.upper()}_AFM_CK', n='x', afm='12345678A', em=None)
        rejects(cur, ins, f'MM_{t.upper()}_AFM_UK', n='x', afm='999000018' if t == 'customer' else '999000055', em=None)
        rejects(cur, ins, f'MM_{t.upper()}_EMAIL_CK', n='x', afm=None, em='not-an-email')


def test_doc_constraints(cur):
    cust = one(cur, 'select min(id) from mm_customer')[0]
    sup = one(cur, 'select min(id) from mm_supplier')[0]
    ins = ('insert into mm_doc (doc_type, doc_no, status, customer_id, supplier_id, net, vat, total) '
           'values (:t, :no, :st, :c, :s, :net, :vat, :tot)')
    ok = dict(t='TPY', no=None, st='D', c=cust, s=None, net=10, vat=2.4, tot=12.4)
    rejects(cur, ins, 'MM_DOC_TOTAL_CK', **{**ok, 'tot': 12})
    rejects(cur, ins, 'MM_DOC_PARTNER_CK', **{**ok, 's': sup})
    rejects(cur, ins, 'MM_DOC_NO_CK', **{**ok, 'st': 'P'})
    rejects(cur, ins, 'MM_DOC_STATUS_CK', **{**ok, 'st': 'X', 'no': 900009})
    # drafts: many without a number; posted: a number once for each kind
    cur.execute(ins, ok)
    cur.execute(ins, ok)
    cur.execute(ins, {**ok, 'no': 900001, 'st': 'P'})
    rejects(cur, ins, 'MM_DOC_NO_UK', **{**ok, 'no': 900001, 'st': 'P'})
    cur.execute(ins, {**ok, 't': 'PPY', 'no': 900001, 'st': 'P'})  # the same number, another kind


def test_doc_line_constraints(cur):
    d = cur.var(int)
    cur.execute("insert into mm_doc (doc_type) values ('ALP') returning id into :d", d=d)
    doc = d.getvalue()[0]
    ins = ('insert into mm_doc_line (doc_id, line_no, item_id, qty, price, discount, vat_code, '
           'vat_rate, net, vat, total) values (:doc, :ln, :it, :q, :p, :dsc, :vc, 13, :net, :vat, :tot)')
    ok = dict(doc=doc, ln=1, it=item_id(cur), q=2, p=2.10, dsc=0, vc='B', net=3.72, vat=0.48, tot=4.2)
    rejects(cur, ins, 'MM_DOC_LINE_QTY_CK', **{**ok, 'q': 0})
    rejects(cur, ins, 'MM_DOC_LINE_DISC_CK', **{**ok, 'dsc': 101})
    rejects(cur, ins, 'MM_DOC_LINE_TOTAL_CK', **{**ok, 'tot': 4.21})
    cur.execute(ins, ok)
    rejects(cur, ins, 'MM_DOC_LINE_NO_UK', **ok)
    # the lines go with their document
    cur.execute('delete from mm_doc where id = :d', d=doc)
    assert one(cur, 'select count(*) from mm_doc_line where doc_id = :d', d=doc)[0] == 0


def test_stock_move_constraints(cur):
    ins = 'insert into mm_stock_move (item_id, kind, qty) values (:it, :k, :q)'
    it = item_id(cur)
    rejects(cur, ins, 'MM_STOCK_MOVE_QTY_CK', it=it, k='ADJ', q=0)
    rejects(cur, ins, 'MM_STOCK_MOVE_KIND_CK', it=it, k='XXX', q=1)
    rejects(cur, ins, 'MM_STOCK_MOVE_DOC_CK', it=it, k='DOC', q=1)  # DOC without a document
    cur.execute(ins, dict(it=it, k='ADJ', q=-1.5))


def test_one_open_z_for_each_register(cur):
    reg = one(cur, "select id from mm_register where code = 'T1'")[0]
    cur.execute('delete from mm_z where register_id = :r and status = :s', r=reg, s='O')
    ins = 'insert into mm_z (register_id, z_no) values (:r, :n)'
    cur.execute(ins, r=reg, n=900001)
    rejects(cur, ins, 'MM_Z_OPEN_UK', r=reg, n=900002)
    rejects(cur, "update mm_z set status = 'C' where register_id = :r and z_no = 900001",
            'MM_Z_CLOSED_CK', r=reg)  # closed without CLOSED_AT
    cur.execute("update mm_z set status = 'C', closed_at = sysdate + 1/24 "
                'where register_id = :r and z_no = 900001', r=reg)
    cur.execute(ins, r=reg, n=900002)  # now the next one can open


# -- MM_ITEM.STOCK: lock-free reservations ------------------------------------------------------

def test_stock_reservable_rules(cur):
    assert one(cur, "select reservable_column from user_tab_cols "
                    "where table_name = 'MM_ITEM' and column_name = 'STOCK'")[0] == 'YES'
    it = item_id(cur)
    rejects(cur, 'update mm_item set stock = stock - 1, price = price where id = :i', 'ORA-55735', i=it)
    rejects(cur, 'update mm_item set stock = 5 where id = :i', 'ORA-55746', i=it)
    rejects(cur, "update mm_item set stock = stock - 1 where code = 'ART01'", 'ORA-55732')
    cur.execute('update mm_item set stock = stock - 1 where id = :i', i=it)


def test_two_tills_do_not_wait(conn):
    """Two sessions take 1 of the same item; the second does not wait for the first to commit."""
    user, rest = DSN.split('/', 1)
    pw, where = rest.rsplit('@', 1)
    other = oracledb.connect(user=user, password=pw, dsn=where)
    other.call_timeout = 3000  # a row lock would wait here until the timeout
    a, b = conn.cursor(), other.cursor()
    it = item_id(a, 'POT01')
    before = one(a, 'select stock from mm_item where id = :i', i=it)[0]
    try:
        a.execute('update mm_item set stock = stock - 1 where id = :i', i=it)
        b.execute('update mm_item set stock = stock - 1 where id = :i', i=it)
        other.commit()
        conn.commit()
        assert one(a, 'select stock from mm_item where id = :i', i=it)[0] == before - 2
    finally:
        a.execute('update mm_item set stock = stock + 2 where id = :i', i=it)
        conn.commit()
        other.close()
