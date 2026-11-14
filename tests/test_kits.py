"""test_kits.py -- baskets and sets (kits) in MM_CORE: what one has, made before (assemble_kit) or
sold before they are made (post_doc: the ready ones first, the rest from the components), the
cancel back exactly.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

As test_core.py: it commits, on its own items (TST..), and removes them at the end.
"""
import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN, close_open_z, retail  # noqa: E402

pytestmark = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')
env = test_core.env


@pytest.fixture(scope='module')
def kit(env):
    """a basket TST..K: 2 of item a, 3 of item b; the register TST with an open Z"""
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    v = db.cur.var(int)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price) "
                   "values (:c, 'Test basket', :cat, 'A', 30) returning id into :v",
                   c=f"TST{ids['tag']}K", cat=cat, v=v)
    ids['kit'] = v.getvalue()[0]
    db.proc('set_component', ids['kit'], ids['a'], 2)
    db.proc('set_component', ids['kit'], ids['b'], 3)
    db.commit()
    close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'])
    db.commit()
    return db, ids


def stocks(db, ids):
    return tuple(db.stock(ids[k]) for k in ('kit', 'a', 'b'))


def test_components_and_rules(kit):
    db, ids = kit
    assert db.one('select kit from mm_item where id = :i', i=ids['kit'])[0] == 'Y'
    db.cur.execute('select component_id, qty from mm_kit_component where kit_id = :k order by qty', k=ids['kit'])
    assert [(c, float(q)) for c, q in db.cur] == [(ids['a'], 2), (ids['b'], 3)]
    db.fails(154, 'set_component', ids['a'], ids['kit'], 1)        # a kit inside another
    db.fails(155, 'set_component', ids['kit'], ids['kit'], 1)
    db.fails(124, 'set_component', ids['kit'], ids['a'], -1)
    db.fails(156, 'assemble_kit', ids['a'], 1)                     # not a kit
    db.fails(124, 'assemble_kit', ids['kit'], 0)
    # the last component out: no more a kit
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price) values (:c, 'Test k2', :cat, 'A', 1)",
                   c=f"TST{ids['tag']}J", cat=cat)
    k2 = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}J")[0]
    db.proc('set_component', k2, ids['a'], 1)
    db.fails(154, 'set_component', ids['kit'], k2, 1)              # (rolled back: k2 is gone)
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price) values (:c, 'Test k2', :cat, 'A', 1)",
                   c=f"TST{ids['tag']}J", cat=cat)
    k2 = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}J")[0]
    db.proc('set_component', k2, ids['a'], 1)
    db.proc('set_component', k2, ids['a'], 0)
    assert db.one('select kit from mm_item where id = :i', i=k2)[0] == 'N'
    db.conn.rollback()


def test_assemble_and_take_apart(kit):
    db, ids = kit
    k, a, b = stocks(db, ids)
    db.proc('assemble_kit', ids['kit'], 2)
    db.commit()
    assert stocks(db, ids) == (k + 2, a - 4, b - 6)
    cost = db.fn('kit_cost', float, ids['kit'])
    assert float(db.one('select cost from mm_item where id = :i', i=ids['kit'])[0]) == cost
    assert db.one("select count(*) from mm_stock_move where item_id = :i and kind = 'ASM'", i=ids['kit'])[0] >= 1
    db.proc('assemble_kit', ids['kit'], -1)                         # one taken apart
    db.commit()
    assert stocks(db, ids) == (k + 1, a - 2, b - 3)
    ready, can = db.one('select ready, can_make from mm_kit_avail where kit_id = :i', i=ids['kit'])
    assert float(ready) == k + 1 and can == min(max(a - 2, 0) // 2, max(b - 3, 0) // 3)


def test_sale_takes_the_ready_first_and_cancel_gives_back_exactly(kit):
    db, ids = kit
    k, a, b = stocks(db, ids)
    if k < 1:
        db.proc('assemble_kit', ids['kit'], 1 - k)
        db.commit()
        k, a, b = stocks(db, ids)
    sold = int(k) + 2                                               # 2 more than the ready ones
    d, _ = retail(db, ids, [('kit', sold)])
    assert stocks(db, ids) == (0, a - 2 * 2, b - 2 * 3)
    db.proc('cancel_doc', d)
    db.commit()
    assert stocks(db, ids) == (k, a, b)


def test_sale_with_none_ready(kit):
    db, ids = kit
    k, a, b = stocks(db, ids)
    if k > 0:
        db.proc('assemble_kit', ids['kit'], -k)
        db.commit()
        k, a, b = stocks(db, ids)
    retail(db, ids, [('kit', 1)])
    assert stocks(db, ids) == (0, a - 2, b - 3)


def test_two_lines_of_one_kit_take_the_ready_one_once(kit):
    """the stock is reservable: post_doc does not see what its first line took"""
    db, ids = kit
    k, a, b = stocks(db, ids)
    if k != 1:
        db.proc('assemble_kit', ids['kit'], 1 - k)
        db.commit()
        k, a, b = stocks(db, ids)
    d, _ = retail(db, ids, [('kit', 1), ('kit', 1)])
    assert stocks(db, ids) == (0, a - 2, b - 3)
    db.proc('cancel_doc', d)
    db.commit()
    assert stocks(db, ids) == (1, a, b)
