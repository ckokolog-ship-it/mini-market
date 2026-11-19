"""test_options.py -- the options of an item at the till (a cafe: sugar, milk, extras): MM_OPTION_GROUP,
MM_OPTION, MM_ITEM_OPTION, MM_DOC_LINE_OPTION and MM_DOC_LINE.OPTIONS; the rules of mm_core (option_group_save,
option_save, option_delete, option_move, item_option, add_line_options; errors MM-132), the number at the
counter (counter_ticket, MM_DOC.TICKET_NO); the REST (POST /api/pos/{register}/item with options, a scan with
the defaults, the receipt and its ticket, /api/tiles/options...); the dialog in a browser (tests/tiles_check.js,
with test_tiles.py).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import oracledb
import pytest

import test_api
import test_core
from test_api import get, post

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users


def fails(db, fn, *args):
    with pytest.raises(oracledb.DatabaseError) as e:
        if fn.startswith('f:'):
            db.fn(fn[2:], int, *args)
        else:
            db.proc(fn, *args)
    db.conn.rollback()
    return str(e.value)


@pytest.fixture
def opts(env):
    """the item a of the tests with three groups of options of its own: TST Ζάχαρη (one, required, default
    Μέτριος), TST Γάλα (one: Φρέσκο 0, Βρώμης 0,30), TST Έξτρα (any: Σφηνάκι 0,50, Κανέλα 0); out at the end"""
    db, ids = env
    test_core.close_open_z(db, ids['reg'])
    g = {}
    o = {}
    g['sugar'] = db.fn('option_group_save', int, None, 'TST Ζάχαρη', 'O', 'Y', 'Y')
    o['plain'] = db.fn('option_save', int, None, g['sugar'], 'Σκέτος', 0, 'N', 'Y')
    o['medium'] = db.fn('option_save', int, None, g['sugar'], 'Μέτριος', 0, 'Y', 'Y')
    g['milk'] = db.fn('option_group_save', int, None, 'TST Γάλα', 'O', 'N', 'Y')
    o['fresh'] = db.fn('option_save', int, None, g['milk'], 'Φρέσκο', 0, 'N', 'Y')
    o['oat'] = db.fn('option_save', int, None, g['milk'], 'Βρώμης', 0.30, 'N', 'Y')
    g['extra'] = db.fn('option_group_save', int, None, 'TST Έξτρα', 'M', 'N', 'Y')
    o['shot'] = db.fn('option_save', int, None, g['extra'], 'Σφηνάκι', 0.50, 'N', 'Y')
    o['cinnamon'] = db.fn('option_save', int, None, g['extra'], 'Κανέλα', 0, 'N', 'Y')
    for k in g.values():
        db.proc('item_option', ids['a'], k, 'Y')
    db.commit()
    yield db, ids, g, o
    db.conn.rollback()
    test_core.close_open_z(db, ids['reg'])
    for (d,) in db.cur.execute("select id from mm_doc where register_id = :r and status = 'D'", r=ids['reg']).fetchall():
        db.proc('delete_doc', d)
    db.cur.execute("delete from mm_doc_line_option where option_id in (select o.id from mm_option o "
                   "join mm_option_group g on g.id = o.group_id where g.name like 'TST%')")
    db.cur.execute("delete from mm_option_group where name like 'TST%'")
    db.cur.execute("delete from mm_tile_group where name like 'TST%'")
    db.commit()


def new_receipt(db, ids):
    return db.fn('new_doc', int, 'ALP', p_register_id=ids['reg'])


def test_the_rules_of_the_options(opts):
    db, ids, g, o = opts
    for args, word in ((('', 'O', 'N', 'Y'), 'όνομα'), (('TST x', 'X', 'N', 'Y'), 'O (μία'), (('TST x', 'M', 'Y', 'Y'), 'Υποχρεωτική είναι μόνο')):
        assert 'MM-132' in (m := fails(db, 'f:option_group_save', None, *args)) and word in m, m
    for args, word in ((('', 0), 'όνομα'), (('x', -1), 'Η τιμή'), (('x', 0.123), 'δύο δεκαδικά')):
        assert word in fails(db, 'f:option_save', None, g['milk'], *args, 'N', 'Y')
    assert 'Δεν υπάρχει ομάδα επιλογών' in fails(db, 'f:option_save', None, -1, 'x', 0, 'N', 'Y')
    # one default in a group of one
    db.fn('option_save', int, o['plain'], None, 'Σκέτος', 0, 'Y', 'Y')
    assert db.one("select listagg(name, ',') within group (order by id) from mm_option where group_id = :g "
                  "and is_default = 'Y'", g=g['sugar'])[0] == 'Σκέτος'
    db.fn('option_save', int, o['medium'], None, 'Μέτριος', 0, 'Y', 'Y')
    db.commit()
    # the order
    db.proc('option_move', 'O', o['medium'], -1)
    assert [n for (n,) in db.cur.execute('select name from mm_option where group_id = :g order by sort_no', g=g['sugar'])] == ['Μέτριος', 'Σκέτος']
    db.proc('option_move', 'O', o['medium'], 1)
    assert 'G (ομάδα) ή O' in fails(db, 'option_move', 'X', o['medium'], 1)
    # an item and a group: in, out; not an item, not a group
    assert 'MM-106' in fails(db, 'item_option', -1, g['milk'], 'Y')
    assert 'Δεν υπάρχει ομάδα επιλογών' in fails(db, 'item_option', ids['a'], -1, 'Y')
    assert 'Y (ναι) ή N' in fails(db, 'item_option', ids['a'], g['milk'], 'X')
    db.proc('item_option', ids['a'], g['milk'], 'Y')                             # (twice: once)
    assert db.one('select count(*) from mm_item_option where item_id = :i', i=ids['a'])[0] == 3
    db.commit()


def test_a_line_with_its_options(opts):
    db, ids, g, o = opts
    db.fn('open_z', int, ids['reg'], 0)
    d = new_receipt(db, ids)
    price = float(db.one('select price from mm_item where id = :i', i=ids['a'])[0])
    # sugar plain, oat milk, a shot and cinnamon: the price and the extras, the text in their order
    v = db.fn('add_line_options', int, d, ids['a'], 2, '%d,%d,%d,%d' % (o['cinnamon'], o['oat'], o['plain'], o['shot']))
    p, opt, tot = db.one('select price, options, total from mm_doc_line where id = :v', v=v)
    assert float(p) == round(price + 0.80, 2) and float(tot) == round(2 * (price + 0.80), 2)
    assert opt == 'Σκέτος, Βρώμης +0,30, Σφηνάκι +0,50, Κανέλα'
    assert db.one('select count(*), sum(price) from mm_doc_line_option where line_id = :v', v=v) == (4, 0.8)
    # nothing chosen: the default of the required group (Μέτριος), nothing else
    v2 = db.fn('add_line_options', int, d, ids['a'], 1, None)
    assert db.one('select price, options from mm_doc_line where id = :v', v=v2) == (price, 'Μέτριος')
    db.commit()                                     # (each refusal below is rolled back)
    # refused: two of a group of one; an option not of the item; inactive; not a number
    assert 'μία επιλογή μόνο' in fails(db, 'f:add_line_options', d, ids['a'], 1, '%d,%d' % (o['plain'], o['medium']))
    assert 'δεν είναι για αυτό το είδος' in fails(db, 'f:add_line_options', d, ids['b'], 1, str(o['oat']))
    assert 'Δεν υπάρχει επιλογή' in fails(db, 'f:add_line_options', d, ids['a'], 1, '-5')
    assert 'χωρισμένοι με κόμμα' in fails(db, 'f:add_line_options', d, ids['a'], 1, 'x')
    # a required group without a default: chosen, or refused
    db.cur.execute("update mm_option set is_default = 'N' where group_id = :g", g=g['sugar'])
    assert 'Διάλεξε από την ομάδα «TST Ζάχαρη»' in fails(db, 'f:add_line_options', d, ids['a'], 1, None)
    # used on a line: not out (inactive instead)
    db.cur.execute("update mm_option set is_default = 'Y' where id = :o", o=o['medium'])
    db.commit()
    assert 'κάνε την ανενεργή' in fails(db, 'option_delete', o['oat'])
    assert 'κάνε την ανενεργή' in fails(db, 'option_group_delete', g['milk'])
    db.fn('option_save', int, o['oat'], None, 'Βρώμης', 0.30, 'N', 'N')
    assert 'δεν είναι για αυτό το είδος' in fails(db, 'f:add_line_options', d, ids['a'], 1, str(o['oat']))
    # posted: the number at the counter only of the items of the buttons (MM_TILE), the next of the day
    db.proc('set_payment', d, 'CASH')
    db.fn('post_doc', int, d)
    assert db.fn('counter_ticket', int, d) is None                                # (a is not a button)
    tg = db.fn('tile_group_save', int, None, 'TST Καφέδες', None, 'Y')
    db.fn('tile_add', int, tg, ids['a'])
    db.cur.execute("update mm_doc set ticket_no = null where id = :d", d=d)
    n1 = db.fn('counter_ticket', int, d)
    assert n1 >= 1 and db.fn('counter_ticket', int, d) == n1                       # once
    d2 = new_receipt(db, ids)
    db.fn('add_line_options', int, d2, ids['a'], 1, None)
    db.proc('set_payment', d2, 'CARD')
    db.fn('post_doc', int, d2)
    assert db.fn('counter_ticket', int, d2) == n1 + 1
    d3 = new_receipt(db, ids)
    assert db.fn('counter_ticket', int, d3) is None                                # a draft: none
    db.proc('delete_doc', d3)
    db.commit()
    assert db.one('select count(*) from mm_check')[0] == 0


def test_the_options_in_the_rest(api, opts, users):
    """the till: the buttons with their options; a coffee with options, a scan with the defaults; paid: its
    number at the counter, the receipt with the options and the lines to make; the page: options made,
    changed, on an item; a cashier: 403"""
    db, ids, g, o = opts
    a, b = 'TST%sA' % ids['tag'], 'TST%sB' % ids['tag']
    price = float(db.one('select price from mm_item where id = :i', i=ids['a'])[0])
    tg = db.fn('tile_group_save', int, None, 'TST Καφέδες', '#8b5a2b', 'Y')
    db.fn('tile_add', int, tg, ids['a'])
    db.fn('tile_add', int, tg, ids['b'])
    db.commit()
    t = get(api, '/api/pos/tiles', token='CASHIER')
    tiles = {x['code']: x for grp in t['groups'] for x in grp['tiles']}
    assert tiles[a]['option_groups'] == [g['sugar'], g['milk'], g['extra']] and tiles[b]['option_groups'] == []
    groups = {x['id']: x for x in t['options']}
    assert [x['name'] for x in groups[g['sugar']]['options']] == ['Σκέτος', 'Μέτριος']
    assert groups[g['sugar']]['required'] == 'Y' and groups[g['extra']]['pick'] == 'M'
    pos = '/api/pos/tst'
    post(api, pos + '/open', {'cash': 0}, token='CASHIER')
    s = post(api, pos + '/item', {'item_id': ids['a'], 'qty': 2, 'options': [o['oat'], o['shot']]}, token='CASHIER')
    s = post(api, pos + '/scan', {'code': a}, token='CASHIER')                     # the defaults
    s = post(api, pos + '/scan', {'code': b}, token='CASHIER')                     # no options
    ls = s['receipt']['lines']
    assert [(x['code'], x['qty'], x['price'], x['options']) for x in ls] == [
        (a, 2, round(price + 0.80, 2), 'Μέτριος, Βρώμης +0,30, Σφηνάκι +0,50'), (a, 1, price, 'Μέτριος'), (b, 1, 2.26, None)]
    assert post(api, pos + '/item', {'item_id': ids['a'], 'options': 'x'}, token='CASHIER', status=400)['error'] == 'bad_options'
    assert post(api, pos + '/item', {'item_id': ids['a'], 'options': [o['plain'], o['medium']]}, token='CASHIER',
                status=400)['error'] == 'MM-132'
    s = post(api, pos + '/pay', {'payment': 'CARD'}, token='CASHIER')
    p = s['paid']
    assert p['ticket_no'] >= 1 and s['last'][0]['ticket_no'] == p['ticket_no']
    r = get(api, pos + '/receipt/%d' % p['id'], token='CASHIER')
    assert r['ticket_no'] == p['ticket_no']
    assert [(x['options'], x['counter']) for x in r['lines']] == [
        ('Μέτριος, Βρώμης +0,30, Σφηνάκι +0,50', 'Y'), ('Μέτριος', 'Y'), (None, 'Y')]
    post(api, pos + '/close', token='CASHIER')
    # the page: a group of options, an option, changed, moved, on an item, out
    assert get(api, '/api/tiles', 403, token='CASHIER')['error'] == 'forbidden'
    assert post(api, '/api/tiles/options', {'name': 'TST Σιρόπι'}, token='CASHIER', status=403)['error'] == 'forbidden'
    r = post(api, '/api/tiles/options', {'name': 'TST Σιρόπι', 'pick': 'M', 'required': False})
    sg = [x for x in r['options'] if x['name'] == 'TST Σιρόπι'][0]
    assert (sg['pick'], sg['required'], sg['active'], sg['options']) == ('M', 'N', 'Y', [])
    r = post(api, '/api/tiles/options/%d/add' % sg['id'], {'name': 'Καραμέλα', 'price': 0.3})
    r = post(api, '/api/tiles/options/%d/add' % sg['id'], {'name': 'Φουντούκι', 'price': 0.3})
    sg = [x for x in r['options'] if x['id'] == sg['id']][0]
    assert [(x['name'], x['price'], x['used']) for x in sg['options']] == [('Καραμέλα', 0.3, 0), ('Φουντούκι', 0.3, 0)]
    r = post(api, '/api/tiles/option/%d' % sg['options'][0]['id'], {'name': 'Καραμέλα αλατισμένη', 'price': 0.4, 'active': False})
    r = post(api, '/api/tiles/option/%d/move' % sg['options'][0]['id'], {'dir': 1})
    sg = [x for x in r['options'] if x['id'] == sg['id']][0]
    assert [(x['name'], x['price'], x['active']) for x in sg['options']] == [('Φουντούκι', 0.3, 'Y'), ('Καραμέλα αλατισμένη', 0.4, 'N')]
    assert post(api, '/api/tiles/options/%d/add' % sg['id'], {'name': 'x', 'price': -1}, status=400)['error'] == 'MM-132'
    r = post(api, '/api/tiles/item-options', {'code': b, 'group_id': sg['id'], 'on': True})
    assert [x['option_groups'] for grp in r['groups'] for x in grp['tiles'] if x['code'] == b] == [[sg['id']]]
    r = post(api, '/api/tiles/item-options', {'code': b, 'group_id': sg['id'], 'on': False})
    assert [x['option_groups'] for grp in r['groups'] for x in grp['tiles'] if x['code'] == b] == [[]]
    assert post(api, '/api/tiles/item-options', {'code': b}, status=400)['error'] == 'missing'
    r = post(api, '/api/tiles/option/%d/delete' % sg['options'][0]['id'])
    r = post(api, '/api/tiles/options/%d/delete' % sg['id'])
    assert sg['id'] not in [x['id'] for x in r['options']]
    assert db.one('select count(*) from mm_check')[0] == 0
