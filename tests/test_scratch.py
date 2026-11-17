"""test_scratch.py -- the scratch tickets in packs (MM_SCRATCH_GAME, mm_core.load_pack, scratch_prize; the
REST of Scratch.java and the till): a game and its item; a pack loaded from the barcode of one of its
tickets (game 4 digits, pack 7, ticket 3): its tickets as serials, the stock; at the till a scan sells that
very ticket, a second scan says it is sold; a prize paid from the drawer; what is refused.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import pytest

import test_api
import test_core
from test_api import get, post

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users


@pytest.fixture
def scratch(env):
    db, ids = env
    tag = ids['tag']
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, serial_tracked) "
                   "values (:c, 'Test σκρατς 1 €', :cat, 'D', 1, 'Y')", c=f'TST{tag}S', cat=cat)
    item = db.one('select id from mm_item where code = :c', c=f'TST{tag}S')[0]
    game = '%04d' % (int(tag, 16) % 9000 + 1000)
    db.cur.execute('delete from mm_scratch_game where game = :g', g=game)
    db.commit()
    yield db, ids, item, game
    db.cur.execute('delete from mm_scratch_game where game = :g', g=game)
    db.commit()


def test_a_pack_loaded_and_sold_ticket_by_ticket(api, scratch, users):
    db, ids, item, game = scratch
    pack = '0004211'
    # a game and its item (an item with serials only); the size of its packs
    assert post(api, '/api/scratch/games', {'game': game, 'code': 'TST%sB' % ids['tag']},
                status=400)['error'] == 'MM-190'                                   # no serials
    r = post(api, '/api/scratch/games', {'game': game, 'code': 'TST%sS' % ids['tag'], 'pack_size': 300})
    assert [g for g in r['games'] if g['game'] == game][0]['pack_size'] == 300
    # a pack from the barcode of one of its tickets: its 300 tickets, 000 to 299, into the stock
    stock = float(db.one('select stock from mm_item where id = :i', i=item)[0])
    r = post(api, '/api/scratch/packs', {'code': game + pack + '137'})
    assert r['loaded'] == 300
    assert float(db.one('select stock from mm_item where id = :i', i=item)[0]) == stock + 300
    assert db.one("select min(serial), max(serial), count(*) from mm_serial where item_id = :i", i=item) == (
        game + pack + '000', game + pack + '299', 300)
    assert db.one('select count(*) from mm_check')[0] == 0                       # the stock is its serials
    p = [x for x in r['packs'] if (x['game'], x['pack']) == (game, pack)][0]
    assert (p['tickets'], p['sold'], p['left_']) == (300, 0, 300)
    # the same pack again, a game not declared, a wrong length: no
    assert post(api, '/api/scratch/packs', {'code': game + pack}, status=400)['error'] == 'MM-190'
    assert 'δεν έχει δηλωθεί' in post(api, '/api/scratch/packs', {'code': '0000' + pack}, status=400)['message']
    assert post(api, '/api/scratch/packs', {'code': game + '12'}, status=400)['error'] == 'MM-190'
    # a pack by game and pack (11 digits) and a count of its own
    assert post(api, '/api/scratch/packs', {'code': game + '0004212', 'count': 5})['loaded'] == 5
    # the till: a scan of a ticket sells that ticket; again: sold, where
    test_core.close_open_z(db, ids['reg'])
    pos = '/api/pos/tst'
    post(api, pos + '/open', {'cash': 20}, token='CASHIER')
    t = game + pack + '007'
    r = post(api, pos + '/scan', {'code': t}, token='CASHIER')
    assert [x for x in r['receipt']['lines'] if x['code'] == 'TST%sS' % ids['tag']][0]['serials'] == t
    paid = post(api, pos + '/pay', {'payment': 'CASH', 'given': 1}, token='CASHIER')['paid']
    e = post(api, pos + '/scan', {'code': t}, status=409, token='CASHIER')
    assert e['error'] == 'sold' and 'ΑΛΠ %s' % paid['doc_no'] in e['message']
    assert db.one('select status from mm_serial where serial = :s', s=t)[0] == 'S'
    # a prize paid from the drawer: out of it, in the page of the scratch tickets
    drawer = post(api, pos + '/prize', {'amount': 5, 'ticket': game + pack + '123'}, token='CASHIER')['z']['drawer']
    assert drawer == 20 + 1 - 5
    assert post(api, pos + '/prize', {'amount': 0}, status=400, token='CASHIER')['error'] == 'MM-190'
    r = get(api, '/api/scratch')
    p = [x for x in r['packs'] if (x['game'], x['pack']) == (game, pack)][0]
    assert (p['sold'], p['left_']) == (1, 299)
    assert r['prizes'][0]['total'] >= 5
    assert db.one("select note from mm_cash_move where kind = 'OUT' order by id desc fetch first 1 rows only")[0] == (
        'Κέρδος σκρατς ' + game + pack + '123')
    assert get(api, '/api/scratch', 403, token='CASHIER')['error'] == 'forbidden'
    post(api, pos + '/close', token='CASHIER')
