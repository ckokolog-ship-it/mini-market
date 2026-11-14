"""test_variants.py -- clothes and shoes: a model and its variants (a colour and/or a size), each an
item of its own; the model is not sold, counted, reserved or put in a basket; its price goes to its
variants; a promotion on the model holds for its variants.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

Uses the colours and sizes of the demo (db/INSTALL.sql demo). Its items are TST.., removed at the end.
"""
import datetime

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env


@pytest.fixture(scope='module')
def model(env):
    """a model TST..T at 20,00 (VAT 24%), its variants black/white x M/L"""
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test shirt', :cat, 'A', 20, 8) returning id into :v",
                   c=f"TST{ids['tag']}T", cat=cat, v=v)
    ids['model'] = v.getvalue()[0]
    color = {c: db.one('select id from mm_color where code = :c', c=c)[0] for c in ('BLK', 'WHT')}
    size = {z: db.one("select id from mm_size where size_group = 'CLOTHES' and code = :z", z=z)[0]
            for z in ('M', 'L')}
    ids['var'] = {}
    for c in color:
        for z in size:
            ids['var'][c + z] = db.fn('make_variant', int, ids['model'], color[c], size[z])
    ids['color'], ids['size'] = color, size
    db.commit()
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    return db, ids


def test_variants_are_items(model):
    db, ids = model
    assert db.one('select is_model, barcode from mm_item where id = :i', i=ids['model']) == ('Y', None)
    code, name, price, parent = db.one('select code, name, price, parent_id from mm_item where id = :i',
                                       i=ids['var']['BLKM'])
    assert code == f"TST{ids['tag']}T-BLK-M" and name == 'Test shirt Μαύρο M'
    assert (float(price), parent) == (20, ids['model'])
    db.cur.execute('select count(*) from mm_variant_grid where model_id = :m', m=ids['model'])
    assert db.cur.fetchone()[0] == 4


def test_rules(model):
    db, ids = model
    db.fails(165, 'make_variant', ids['model'], ids['color']['BLK'], ids['size']['M'], rtype=int)   # twice
    db.fails(164, 'make_variant', ids['model'], rtype=int)                                          # neither
    db.fails(163, 'make_variant', ids['var']['BLKM'], ids['color']['WHT'], rtype=int)               # a variant
    db.proc('adjust_stock', ids['a'], 1, 'Test')                                                   # a move
    db.commit()
    db.fails(162, 'make_variant', ids['a'], ids['color']['BLK'], rtype=int)                         # has moves
    db.fails(166, 'model_price', ids['a'], 1)


def test_the_model_is_not_sold_counted_reserved_or_in_a_basket(model):
    db, ids = model
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fails(161, 'add_line', d, ids['model'], 1, rtype=int)
    db.fails(161, 'adjust_stock', ids['model'], 1, 'x')
    r = db.fn('new_reservation', int, 'Test v', '6912345678', datetime.date.today())
    db.fails(161, 'reserve', r, ids['model'], 1)
    db.fails(161, 'set_component', ids['a'], ids['model'], 1)
    c = db.fn('start_count', int, f"TST {ids['tag']} v")
    db.fails(161, 'scan', c, f"TST{ids['tag']}T", rtype=int)


def test_a_variant_is_sold_with_its_own_stock(model):
    db, ids = model
    db.proc('adjust_stock', ids['var']['WHTL'], 3, 'Test')
    db.commit()
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fn('add_line', int, d, ids['var']['WHTL'], 1)
    db.fn('post_doc', int, d)
    db.commit()
    assert db.stock(ids['var']['WHTL']) == 2 and db.stock(ids['var']['WHTM']) == 0
    assert db.stock(ids['model']) == 0


def test_model_price_and_promotion_on_the_model(model):
    db, ids = model
    db.proc('model_price', ids['model'], 25)
    db.commit()
    db.cur.execute('select count(*) from mm_item where parent_id = :m and price = 25', m=ids['model'])
    assert db.cur.fetchone()[0] == 4
    today = datetime.date.today()
    p = db.fn('new_promo', int, 'Test shirts -40%', 'PCT', today, today, p_pct=40)
    db.proc('promo_item', p, ids['model'])
    db.commit()
    try:
        d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
        db.fn('add_line', int, d, ids['var']['BLKL'], 1)
        assert float(db.one('select total from mm_doc where id = :d', d=d)[0]) == 15.00     # 25 - 40%
        db.conn.rollback()
    finally:
        db.cur.execute("delete from mm_promo where name = 'Test shirts -40%'")
        db.commit()
