"""test_recipes.py -- the recipes of the cafe: a coffee is a kit never assembled (MM_KIT_COMPONENT), each sale
takes its materials by FIFO; the materials of an option (MM_OPTION_COMPONENT, mm_core.option_component): more
of one (a shot of coffee) or less of one of the recipe (oat milk instead of the fresh), never below 0; a
cancel gives them back exactly; the cost of the line its materials; the REST of the page (the recipe of a
tile, its cost; the materials of an option).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

On its own items (TST..), removed at the end (test_core.env).
"""
import itertools

import oracledb
import pytest

import test_api
import test_core
from test_api import get, post

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users
SEQ = itertools.count()


def fails(db, fn, *args):
    with pytest.raises(oracledb.DatabaseError) as e:
        db.proc(fn, *args)
    db.conn.rollback()
    return str(e.value)


@pytest.fixture
def cafe(env):
    """materials (coffee kg 20 €, fresh milk L 1 €, oat L 3 €, cups 0,10 €), bought; a coffee TST..C (18 g of
    coffee, 0,1 L of milk, a cup), 3,00 €; options TST Γάλα: Βρώμης (+0,30: oat 0,15, fresh −0,15) and TST
    Έξτρα: Σφηνάκι (+0,50: coffee 0,009), on it; a Z open on TST"""
    db, ids = env
    tag = '%sR%d' % (ids['tag'], next(SEQ))          # (the items of each test of its own)
    cat = db.one('select min(id) from mm_category')[0]
    m = {}
    for key, name, unit, cost, price in (('coffee', 'Test κόκκοι', 'KG', 20, 0), ('milk', 'Test γάλα', 'L', 1, 0),
                                         ('oat', 'Test βρώμη', 'L', 3, 0), ('cup', 'Test ποτήρι', 'PCS', 0.1, 0),
                                         ('freddo', 'Test freddo', 'PCS', 0, 3)):
        v = db.cur.var(int)
        db.cur.execute("insert into mm_item (code, name, category_id, vat_code, unit, price, cost) "
                       "values (:c, :n, :cat, 'B', :u, :p, :cost) returning id into :v",
                       c=f'TST{tag}{key[:3].upper()}', n=name, cat=cat, u=unit, p=price, cost=cost, v=v)
        m[key] = v.getvalue()[0]
    d = db.fn('new_doc', int, 'DPA', p_supplier_id=ids['supplier'], p_payment='CREDIT')
    for key, q, cost in (('coffee', 2, 20), ('milk', 10, 1), ('oat', 4, 3), ('cup', 100, 0.1)):
        db.fn('add_line', int, d, m[key], q, cost)
    db.fn('post_doc', int, d)
    for key, q in (('coffee', 0.018), ('milk', 0.1), ('cup', 1)):
        db.proc('set_component', m['freddo'], m[key], q)
    g_milk = db.fn('option_group_save', int, None, 'TST Γάλα', 'O', 'N', 'Y')
    oat = db.fn('option_save', int, None, g_milk, 'Βρώμης', 0.30, 'N', 'Y')
    g_extra = db.fn('option_group_save', int, None, 'TST Έξτρα', 'M', 'N', 'Y')
    shot = db.fn('option_save', int, None, g_extra, 'Σφηνάκι', 0.50, 'N', 'Y')
    db.proc('option_component', oat, m['oat'], 0.15)
    db.proc('option_component', oat, m['milk'], -0.15)
    db.proc('option_component', shot, m['coffee'], 0.009)
    db.proc('item_option', m['freddo'], g_milk, 'Y')
    db.proc('item_option', m['freddo'], g_extra, 'Y')
    test_core.close_open_z(db, ids['reg'])
    db.fn('open_z', int, ids['reg'], 0)
    db.commit()
    yield db, ids, m, {'oat': oat, 'shot': shot, 'g_milk': g_milk, 'tag': tag}
    db.conn.rollback()
    test_core.close_open_z(db, ids['reg'])
    db.cur.execute("delete from mm_doc_line_option where option_id in (select o.id from mm_option o "
                   "join mm_option_group g on g.id = o.group_id where g.name like 'TST%')")
    db.cur.execute("delete from mm_option_group where name like 'TST%'")
    db.cur.execute("delete from mm_tile_group where name like 'TST%'")
    db.cur.execute('delete from mm_kit_component where kit_id = :k', k=m['freddo'])
    db.commit()


def stocks(db, m):
    return {k: round(db.stock(v), 3) for k, v in m.items() if k != 'freddo'}


def moves(db, d):
    db.cur.execute('select i.code, sum(m.qty) from mm_stock_move m join mm_item i on i.id = m.item_id '
                   'where m.doc_id = :d group by i.code', d=d)
    return {c[-3:]: round(float(q), 3) for c, q in db.cur}


def test_a_coffee_takes_its_materials(cafe):
    db, ids, m, o = cafe
    before = stocks(db, m)
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fn('add_line_options', int, d, m['freddo'], 2, None)                          # 2 plain
    db.fn('add_line_options', int, d, m['freddo'], 1, '%d,%d' % (o['oat'], o['shot']))   # 1 oat, a shot
    db.proc('set_payment', d, 'CARD')
    db.fn('post_doc', int, d)
    db.commit()
    # 3 coffees: 3×18 g + 9 g; milk 2×0,1 + (0,1 − 0,15 → 0); oat 0,15; 3 cups; no stock of the coffee itself
    assert moves(db, d) == {'COF': -0.063, 'MIL': -0.2, 'OAT': -0.15, 'CUP': -3.0}
    after = stocks(db, m)
    assert {k: round(before[k] - after[k], 3) for k in before} == {'coffee': 0.063, 'milk': 0.2, 'oat': 0.15, 'cup': 3}
    assert db.stock(m['freddo']) == 0
    # the cost of each line: its materials by FIFO
    db.cur.execute('select l.qty, l.options, sum(f.cost) from mm_doc_line l join mm_fifo_out f on f.doc_line_id = l.id '
                   'where l.doc_id = :d group by l.line_no, l.qty, l.options order by l.line_no', d=d)
    rows = [(float(q), opt, round(float(c), 2)) for q, opt, c in db.cur]
    assert rows == [(2, None, round(2 * (0.018 * 20 + 0.1 * 1 + 0.1), 2)),
                    (1, 'Βρώμης +0,30, Σφηνάκι +0,50', round(0.027 * 20 + 0.15 * 3 + 0.1, 2))]
    assert db.one('select count(*) from mm_check')[0] == 0
    # cancelled: all of it back
    db.proc('cancel_doc', d)
    db.commit()
    assert stocks(db, m) == before
    assert db.one('select count(*) from mm_check')[0] == 0


def test_an_item_of_its_own_with_the_materials_of_its_options(cafe):
    """not a kit (bought ready, e.g. a croissant): its own stock, and the materials of its options (more only)"""
    db, ids, m, o = cafe
    db.proc('set_component', m['freddo'], m['coffee'], 0)
    db.proc('set_component', m['freddo'], m['milk'], 0)
    db.proc('set_component', m['freddo'], m['cup'], 0)
    assert db.one('select kit from mm_item where id = :i', i=m['freddo'])[0] == 'N'
    d = db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])
    db.fn('add_line_options', int, d, m['freddo'], 2, '%d,%d' % (o['oat'], o['shot']))
    db.proc('set_payment', d, 'CASH')
    db.fn('post_doc', int, d)
    db.commit()
    assert moves(db, d) == {'FRE': -2.0, 'OAT': -0.3, 'COF': -0.018}             # (no "less milk": not a recipe)
    assert db.one('select count(*) from mm_check')[0] == 0


def test_the_rules_of_the_materials(cafe):
    db, ids, m, o = cafe
    assert 'MM-106' in fails(db, 'option_component', o['oat'], -1, 1)
    assert 'Δεν υπάρχει επιλογή' in fails(db, 'option_component', -1, m['milk'], 1)
    assert '3 δεκαδικά' in fails(db, 'option_component', o['oat'], m['milk'], 0.0001)
    assert 'δεν γίνεται υλικό' in fails(db, 'option_component', o['oat'], m['freddo'], 1)    # a kit
    db.proc('option_component', o['oat'], m['cup'], 1)
    db.proc('option_component', o['oat'], m['cup'], 0)                                     # out
    assert db.one('select count(*) from mm_option_component where option_id = :o', o=o['oat'])[0] == 2
    db.commit()


def test_the_recipes_in_the_rest(api, cafe, users):
    db, ids, m, o = cafe
    tag = o['tag']
    tg = db.fn('tile_group_save', int, None, 'TST Καφέδες', None, 'Y')
    db.fn('tile_add', int, tg, m['freddo'])
    db.commit()
    code = f'TST{tag}FRE'

    def tile(r):
        return [t for g in r['groups'] for t in g['tiles'] if t['code'] == code][0]

    t = tile(get(api, '/api/tiles'))
    assert sorted((x['code'][-3:], x['qty']) for x in t['recipe']) == [('COF', 0.018), ('CUP', 1), ('MIL', 0.1)]
    assert t['recipe_cost'] == round(0.018 * 20 + 0.1 + 0.1, 2)
    r = post(api, '/api/tiles/recipe', {'code': code, 'component': f'TST{tag}CUP', 'qty': 2})
    assert [x['qty'] for x in tile(r)['recipe'] if x['code'].endswith('CUP')] == [2]
    r = post(api, '/api/tiles/recipe', {'code': code, 'component': f'TST{tag}CUP', 'qty': 0})
    assert [x for x in tile(r)['recipe'] if x['code'].endswith('CUP')] == []
    assert post(api, '/api/tiles/recipe', {'code': code, 'component': code, 'qty': 1}, status=400)['error'] == 'MM-155'
    assert post(api, '/api/tiles/recipe', {'code': code, 'component': f'TST{tag}CUP'}, status=400)['error'] == 'missing'
    assert post(api, '/api/tiles/recipe', {'code': code, 'component': 'TSTNOTHING', 'qty': 1}, status=404)['error'] == 'not_found'
    opt = [x for g in r['options'] for x in g['options'] if x['id'] == o['oat']][0]
    assert sorted((x['code'][-3:], x['qty']) for x in opt['components']) == [('MIL', -0.15), ('OAT', 0.15)]
    r = post(api, '/api/tiles/option/%d/component' % o['oat'], {'component': f'TST{tag}CUP', 'qty': 1})
    opt = [x for g in r['options'] for x in g['options'] if x['id'] == o['oat']][0]
    assert ('CUP', 1) in [(x['code'][-3:], x['qty']) for x in opt['components']]
    assert post(api, '/api/tiles/recipe', {'code': code, 'component': f'TST{tag}CUP', 'qty': 1},
                token='CASHIER', status=403)['error'] == 'forbidden'
