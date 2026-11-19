"""test_tiles.py -- the buttons of the till (a cafe: coffees, juices, sweets without a barcode): MM_TILE_GROUP,
MM_TILE and MM_ITEM.PLU, the rules of mm_core (tile_group_save, tile_add, tile_move, tile_delete, set_plu,
find_item by PLU; errors MM-132), the REST of Tiles.java (the page Κουμπιά ταμείου, the rights of TILES) and
of the till (GET /api/pos/tiles, POST /api/pos/{register}/item): a receipt from the buttons, posted, the
database still adding up (MM_CHECK); the pages in a browser (tests/tiles_check.js).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import os
import shutil
import subprocess

import oracledb
import pytest

import test_api
import test_core
from test_api import get, post

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users
HERE = os.path.dirname(os.path.abspath(__file__))


def fails(db, fn, *args):
    with pytest.raises(oracledb.DatabaseError) as e:
        if fn.startswith('f:'):
            db.fn(fn[2:], int, *args)
        else:
            db.proc(fn, *args)
    db.conn.rollback()
    return str(e.value)


@pytest.fixture
def tst_groups(env):
    """the groups of buttons of a test: out at its end (their tiles with them)"""
    db, ids = env
    yield db, ids
    db.conn.rollback()
    db.cur.execute("delete from mm_tile_group where name like 'TST%'")
    db.cur.execute("update mm_item set plu = null where code like 'TST%'")
    db.commit()


def order(db, group):
    db.cur.execute('select i.code from mm_tile t join mm_item i on i.id = t.item_id where t.group_id = :g '
                   'order by t.sort_no', g=group)
    return [c for (c,) in db.cur]


def test_the_rules_of_the_buttons(tst_groups):
    db, ids = tst_groups
    a, b = 'TST%sA' % ids['tag'], 'TST%sB' % ids['tag']
    g = db.fn('tile_group_save', int, None, 'TST Καφέδες', '#8b5a2b', 'Y')
    h = db.fn('tile_group_save', int, None, 'TST Χυμοί', None, None)
    db.cur.execute("select name, color, active, sort_no from mm_tile_group where id = :h", h=h)
    name, color, active, sort_h = db.cur.fetchone()
    assert (name, color, active) == ('TST Χυμοί', '#6b7280', 'Y')                 # a gray, active
    assert sort_h > db.one('select sort_no from mm_tile_group where id = :g', g=g)[0]   # at the end
    assert db.fn('tile_group_save', int, h, 'TST Χυμοί φρέσκοι', '#E08A00', 'N') == h
    assert db.one('select name, color, active from mm_tile_group where id = :h', h=h) == ('TST Χυμοί φρέσκοι', '#E08A00', 'N')
    db.commit()
    for args, word in ((('', '#000000', 'Y'), 'όνομα'), (('TST', 'red', 'Y'), 'χρώμα'), (('TST', None, 'X'), 'Ενεργή')):
        assert 'MM-132' in (m := fails(db, 'f:tile_group_save', None, *args)) and word in m, m
    # the tiles: at the end of their group; once in a group; an item, not a model, not inactive
    ta = db.fn('tile_add', int, g, ids['a'])
    tb = db.fn('tile_add', int, g, ids['b'])
    db.fn('tile_add', int, h, ids['a'])                                           # (in two groups: allowed)
    db.commit()
    assert order(db, g) == [a, b]
    assert 'ήδη σε αυτή την ομάδα' in fails(db, 'f:tile_add', g, ids['a'])
    assert 'MM-106' in fails(db, 'f:tile_add', g, -1)
    assert 'Δεν υπάρχει ομάδα' in fails(db, 'f:tile_add', -1, ids['a'])
    model = db.one("select min(id) from mm_item where is_model = 'Y'")[0]
    if model:
        assert 'μοντέλο' in fails(db, 'f:tile_add', g, model)
    db.cur.execute("update mm_item set active = 'N' where id = :i", i=ids['b'])
    assert 'ενεργό' in fails(db, 'f:tile_add', h, ids['b'])
    # the order: a tile after, before; at the ends nothing; the groups too
    db.proc('tile_move', 'T', ta, 1)
    assert order(db, g) == [b, a]
    db.proc('tile_move', 'T', ta, 1)                                              # the last: stays
    assert order(db, g) == [b, a]
    db.proc('tile_move', 'T', ta, -1)
    assert order(db, g) == [a, b]
    db.cur.execute("select id from mm_tile_group order by sort_no, id")
    before = [x for (x,) in db.cur]
    db.proc('tile_move', 'G', h, -1)
    db.cur.execute("select id from mm_tile_group order by sort_no, id")
    after = [x for (x,) in db.cur]
    k = before.index(h)
    assert after[k - 1] == h and after[k] == before[k - 1]
    assert 'G (ομάδα) ή T' in fails(db, 'tile_move', 'X', g, 1)
    assert 'Δεν υπάρχει κουμπί' in fails(db, 'tile_move', 'T', -1, 1)
    # a tile out (the item stays); a group out with its tiles
    db.proc('tile_delete', tb)
    assert order(db, g) == [a]
    db.commit()
    assert 'Δεν υπάρχει κουμπί' in fails(db, 'tile_delete', tb)
    db.proc('tile_group_delete', h)
    assert db.one('select count(*) from mm_tile where group_id = :h', h=h)[0] == 0
    assert db.one('select count(*) from mm_item where id = :i', i=ids['a'])[0] == 1
    db.commit()


def test_the_short_numbers(tst_groups):
    """PLU: 1 to 99999, once; not the code or the barcode of another; the till finds an item by it, after
    its barcode and its code"""
    db, ids = tst_groups
    free = db.one('select nvl(max(plu), 0) + 1 from mm_item')[0]
    db.proc('set_plu', ids['a'], free)
    db.commit()
    assert db.fn('find_item', int, str(free)) == ids['a']
    assert db.fn('find_item', int, ' %d ' % free) == ids['a']
    assert 'είναι ήδη άλλου είδους' in fails(db, 'set_plu', ids['b'], free)
    db.proc('set_plu', ids['a'], free)                                            # (its own again: fine)
    for bad in (0, 100000, 1.5):
        assert '1 ως 99999' in fails(db, 'set_plu', ids['b'], bad)
    # a number that is the code of another item: refused (the scan finds that one first; a barcode is an
    # EAN of 8 or 13 digits, never a PLU of up to 5)
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, cost) "
                   "values (:c, 'Test με αριθμό για κωδικό', :cat, 'B', 1, 0)", c=str(free + 1), cat=cat)
    assert 'είναι ήδη άλλου είδους' in fails(db, 'set_plu', ids['a'], free + 1)    # (rolled back: the item too)
    assert db.one('select count(*) from mm_item where code = :c', c=str(free + 1))[0] == 0
    assert 'MM-106' in fails(db, 'set_plu', -1, free + 2)
    db.proc('set_plu', ids['a'], None)
    db.commit()
    assert db.fn('find_item', int, str(free)) is None
    assert db.one('select plu from mm_item where id = :i', i=ids['a'])[0] is None


def test_the_buttons_in_the_rest_and_the_till(api, tst_groups, users):
    """the page (a manager; a cashier: 403), its groups and tiles; the till of a cashier: the buttons, an
    item by its button and by its PLU, ×2, paid; the database adds up; «Συχνά» the most sold of the week"""
    db, ids = tst_groups
    a, b = 'TST%sA' % ids['tag'], 'TST%sB' % ids['tag']
    page = get(api, '/api/tiles')
    assert 'Καφέδες' in [g['name'] for g in page['groups']]                       # (the demo)
    assert get(api, '/api/tiles', 403, token='CASHIER')['error'] == 'forbidden'
    assert post(api, '/api/tiles/groups', {'name': 'TST x'}, token='CASHIER', status=403)['error'] == 'forbidden'
    r = post(api, '/api/tiles/groups', {'name': 'TST Γλυκά', 'color': '#b4436c'})
    g = [x for x in r['groups'] if x['name'] == 'TST Γλυκά'][0]
    assert (g['color'], g['active'], g['tiles']) == ('#b4436c', 'Y', [])
    assert post(api, '/api/tiles/groups', {'name': ''}, status=400)['error'] == 'MM-132'
    r = post(api, '/api/tiles/groups/%d/tiles' % g['id'], {'code': a.lower()})
    r = post(api, '/api/tiles/groups/%d/tiles' % g['id'], {'code': b})
    g = [x for x in r['groups'] if x['id'] == g['id']][0]
    assert [t['code'] for t in g['tiles']] == [a, b]
    assert post(api, '/api/tiles/groups/%d/tiles' % g['id'], {'code': 'TSTNOTHING'}, status=404)['error'] == 'not_found'
    r = post(api, '/api/tiles/%d/move' % g['tiles'][0]['id'], {'dir': 1})
    assert [t['code'] for t in [x for x in r['groups'] if x['id'] == g['id']][0]['tiles']] == [b, a]
    assert post(api, '/api/tiles/%d/move' % g['tiles'][0]['id'], {'dir': 2}, status=400)['error'] == 'bad_dir'
    free = db.one('select nvl(max(plu), 0) + 1 from mm_item')[0]
    r = post(api, '/api/tiles/plu', {'code': a, 'plu': free})
    assert [t['plu'] for x in r['groups'] if x['id'] == g['id'] for t in x['tiles'] if t['code'] == a] == [free]
    assert post(api, '/api/tiles/plu', {'code': b, 'plu': free}, status=400)['error'] == 'MM-132'
    # the till of the cashier: the buttons (the active groups only)
    t = get(api, '/api/pos/tiles', token='CASHIER')
    assert [x['code'] for x in [x for x in t['groups'] if x['id'] == g['id']][0]['tiles']] == [b, a]
    post(api, '/api/tiles/groups/%d' % g['id'], {'name': 'TST Γλυκά', 'active': 'N'})
    assert g['id'] not in [x['id'] for x in get(api, '/api/pos/tiles', token='CASHIER')['groups']]
    post(api, '/api/tiles/groups/%d' % g['id'], {'name': 'TST Γλυκά', 'active': 'Y'})
    # a receipt from the buttons: b by its button ×2, a by its PLU (typed in the scan)
    test_core.close_open_z(db, ids['reg'])
    pos = '/api/pos/tst'
    post(api, pos + '/open', {'cash': 0}, token='CASHIER')
    s = post(api, pos + '/item', {'item_id': ids['b'], 'qty': 2}, token='CASHIER')
    s = post(api, pos + '/scan', {'code': str(free)}, token='CASHIER')
    assert [(x['code'], x['qty']) for x in s['receipt']['lines']] == [(b, 2), (a, 1)]
    assert post(api, pos + '/item', {'item_id': -1}, token='CASHIER', status=404)['error'] == 'not_found'
    assert post(api, pos + '/item', {}, token='CASHIER', status=404)['error'] == 'not_found'
    s = post(api, pos + '/pay', {'payment': 'CARD'}, token='CASHIER')
    assert s['paid']['total'] == round(2 * 2.26 + 12.40, 2)
    assert db.one('select count(*) from mm_check')[0] == 0
    freq = get(api, '/api/pos/tiles', token='CASHIER')['frequent']
    assert {a, b} <= {x['code'] for x in freq}
    post(api, pos + '/close', token='CASHIER')
    r = post(api, '/api/tiles/groups/%d/delete' % g['id'])
    assert g['id'] not in [x['id'] for x in r['groups']]


@pytest.mark.skipif(not shutil.which('node'), reason='no node')
def test_the_buttons_in_a_browser(api, tst_groups, users):
    """tests/tiles_check.js: the page of a manager (a group, a tile, its PLU), the till of a cashier (a press
    of a tile, ×2, the tabs)"""
    db, ids = tst_groups
    if subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no Playwright for node')
    test_core.close_open_z(db, ids['reg'])
    db.commit()
    free = db.one('select nvl(max(plu), 0) + 1 from mm_item')[0]
    e = dict(os.environ, BASE=api, MGR=users['MANAGER'], CASHIER=users['CASHIER'], PW=test_api.PW,
             ITEM='TST%sA' % ids['tag'], ITEM_B='TST%sB' % ids['tag'], PLU=str(free),
             SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
    r = subprocess.run(['node', os.path.join(HERE, 'tiles_check.js')], env=e, capture_output=True, text=True, timeout=180)
    print(r.stdout, r.stderr)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '== tiles OK' in r.stdout
    test_core.close_open_z(db, ids['reg'])
    db.commit()
