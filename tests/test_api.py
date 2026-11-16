"""test_api.py -- the REST service (api/, mm-api.jar) on a live database: it starts the jar on a
free port of this computer, with MM_DSN, and asks it as a client would: a login first (its users:
a manager and a cashier, tst...), then each call with its token; the roles; a count of the stock as
the phones of step 9 will do it.

    (cd api && mvn -q -B package)        the jar (else the tests build it, if mvn is there)
    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

Without MM_DSN, java, or the jar (and mvn), the tests are skipped.
"""
import datetime
import http.client
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import pytest

oracledb = pytest.importorskip('oracledb')
import fake_aade  # noqa: E402
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
JAR = os.path.join(ROOT, 'api', 'target', 'mm-api.jar')
pytestmark = pytest.mark.skipif(not DSN or not shutil.which('java'), reason='MM_DSN or java missing')
env = test_core.env
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
AADE = None                                  # myDATA: the little AADE of the tests (fake_aade.py)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# the pages of the app of Android in the tests (test_web.py): from another origin, as on the phone
APP_PORT = free_port()


@pytest.fixture(scope='module')
def api():
    if not os.path.exists(JAR):
        if not shutil.which('mvn'):
            pytest.skip('no api/target/mm-api.jar and no mvn')
        subprocess.run(['mvn', '-q', '-B', 'package'], cwd=os.path.join(ROOT, 'api'), check=True)
    user, rest = DSN.split('/', 1)
    pw, where = rest.rsplit('@', 1)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    global AADE
    AADE = fake_aade.Aade()                                # myDATA: a little AADE of the tests
    conf = os.path.join(tempfile.mkdtemp(prefix='mmaade-'), 'mydata.properties')
    with open(conf, 'w') as f:
        f.write('url=%s\nuser=%s\nkey=%s\n' % (AADE.url, fake_aade.USER, fake_aade.KEY))
    e = dict(os.environ, MM_DB_URL='jdbc:oracle:thin:@' + where, MM_DB_USER=user, MM_DB_PASSWORD=pw,
             MM_API_PORT=str(port), MM_API_BIND='127.0.0.1',
             MM_API_CORS='http://localhost,http://localhost:%d' % APP_PORT, MM_MYDATA_CONFIG=conf, MM_MYDATA_EVERY='2')
    p = subprocess.Popen(['java', '-jar', JAR], env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = 'http://127.0.0.1:%d' % port
    try:
        for _ in range(60):
            try:
                NO_PROXY.open(base + '/api/health', timeout=2).read()
                break
            except (urllib.error.URLError, ConnectionError):
                if p.poll() is not None:
                    pytest.fail('mm-api stopped: ' + p.stdout.read().decode(errors='replace'))
                time.sleep(0.5)
        yield base
    finally:
        p.terminate()                       # by its own handle (its PID), nothing else
        p.wait(timeout=20)
        AADE.stop()
        shutil.rmtree(os.path.dirname(conf), ignore_errors=True)


PW = 'Kodikos-2026'
TOKENS = {}


@pytest.fixture(scope='module')
def users(env, api):
    """a manager and a cashier of this run; their tokens through the login of the service"""
    db, ids = env
    t = ids['tag'].lower()
    names = {'MANAGER': 'tstm' + t, 'CASHIER': 'tstk' + t}
    for role, name in names.items():
        db.cur.callfunc('mm_auth.create_user', int, [name, 'Test ' + role, role, PW])
    db.commit()
    for role, name in names.items():
        r = post(api, '/api/auth/login', {'username': name, 'password': PW}, token=None)
        assert r['role'] == role and len(r['token']) == 64 and r['username'] == name
        TOKENS[role] = r['token']
    TOKENS[None] = TOKENS['MANAGER']
    return names


def call(base, path, method='GET', body=None, token='MANAGER', status=200):
    req = urllib.request.Request(base + path, method=method,
                                 data=None if body is None else json.dumps(body).encode())
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + TOKENS.get(token, token))
    try:
        r = NO_PROXY.open(req, timeout=30)
        code, data, ctype = r.status, r.read(), r.headers['Content-Type']
    except urllib.error.HTTPError as e:
        code, data, ctype = e.code, e.read(), e.headers['Content-Type']
    assert code == status, (method, path, code, data[:300])
    assert ctype == 'application/json; charset=utf-8'
    return json.loads(data.decode('utf-8'))


def post(base, path, body=None, token='MANAGER', status=200):
    return call(base, path, 'POST', body if body is not None else {}, token, status)


def get(base, path, status=200, token='MANAGER'):
    return call(base, path, token=token, status=status)


def test_health_needs_no_login(api):
    assert get(api, '/api/health', token=None) == {'status': 'ok', 'db': 'ok'}


def test_login_tokens_and_roles(api, users):
    # no token, a wrong one: 401
    assert get(api, '/api/items', 401, token=None)['error'] == 'auth_required'
    assert get(api, '/api/items', 401, token='f' * 64)['error'] == 'MM-179'
    assert post(api, '/api/auth/login', {'username': users['CASHIER'], 'password': 'Wrong-pass-1'},
                token=None, status=401)['error'] == 'MM-177'
    assert post(api, '/api/auth/login', {'username': 'tstnobody', 'password': PW}, token=None,
                status=401)['error'] == 'MM-177'                      # the same answer: no hint
    assert post(api, '/api/auth/login', {'username': users['CASHIER']}, token=None, status=400)['error'] == 'missing'
    assert get(api, '/api/auth/me', token='CASHIER') == {'username': users['CASHIER'], 'role': 'CASHIER'}
    # the cashier: the items and the counts, not the office
    assert get(api, '/api/items?limit=1', token='CASHIER')['rows']
    for path in ('/api/customers', '/api/ledger/item/1', '/api/reports/sales'):
        assert get(api, path, 403, token='CASHIER')['error'] == 'forbidden'
    assert post(api, '/api/counts', {'name': 'TST no'}, token='CASHIER', status=403)['error'] == 'forbidden'
    # logout: the token ends
    r = post(api, '/api/auth/login', {'username': users['CASHIER'], 'password': PW}, token=None)
    assert post(api, '/api/auth/logout', token=r['token'])['ok'] is True
    assert get(api, '/api/items', 401, token=r['token'])['error'] == 'MM-179'


def test_a_count_from_the_phones(api, env, users):
    db, ids = env
    a = 'TST%sA' % ids['tag']
    c = post(api, '/api/counts', {'name': 'TST count %s' % ids['tag']})
    assert c['status'] == 'O' and c['lines'] == []
    cid = c['id']
    # two phones of cashiers: 3 and 2 of a, then 5 of it set
    r = post(api, '/api/counts/%d/scan' % cid, {'code': a, 'qty': 3, 'device': 'phone-1'}, token='CASHIER')
    assert r['code'] == a and r['counted_qty'] == 3 and r['device'] == 'phone-1'
    r = post(api, '/api/counts/%d/scan' % cid, {'code': a, 'qty': 2}, token='CASHIER')
    assert r['counted_qty'] == 5 and r['device'] == users['CASHIER']
    r = post(api, '/api/counts/%d/scan' % cid, {'code': a, 'qty': 7, 'mode': 'set'}, token='CASHIER')
    assert r['counted_qty'] == 7
    assert post(api, '/api/counts/%d/scan' % cid, {'code': 'NOPE-1'}, token='CASHIER',
                status=400)['error'] == 'MM-123'
    assert post(api, '/api/counts/%d/scan' % cid, {'code': a, 'qty': 'x'}, token='CASHIER',
                status=400)['error'] == 'bad_number'
    assert any(x['id'] == cid for x in get(api, '/api/counts', token='CASHIER')['rows'])
    one = get(api, '/api/counts/%d' % cid, token='CASHIER')
    assert [x['code'] for x in one['lines']] == [a] and one['lines'][0]['diff'] == 7 - one['lines'][0]['system_qty']
    # posted by the manager: the stock is what was counted
    assert post(api, '/api/counts/%d/post' % cid, token='CASHIER', status=403)['error'] == 'forbidden'
    assert post(api, '/api/counts/%d/post' % cid)['status'] == 'P'
    assert db.stock(ids['a']) == 7
    assert post(api, '/api/counts/%d/scan' % cid, {'code': a}, token='CASHIER', status=400)['error'].startswith('MM-')
    assert get(api, '/api/counts/999999999', 404)['error'] == 'not_found'


def test_bad_bodies(api, users):
    host, port = api[len('http://'):].split(':')
    for body, code in ((b'not json', 'bad_json'), (b'[1, 2]', 'bad_json'), (b'x' * (64 * 1024 + 10), 'too_large')):
        c = http.client.HTTPConnection(host, int(port), timeout=10)
        c.request('POST', '/api/counts', body=body, headers={'Authorization': 'Bearer ' + TOKENS['MANAGER']})
        r = c.getresponse()
        assert json.loads(r.read())['error'] == code
        c.close()


def test_items(api, env, users):
    db, ids = env
    r = get(api, '/api/items?q=%CE%A8%CF%89%CE%BC%CE%AF&limit=5')          # «Ψωμί»
    assert r['limit'] == 5 and r['rows'] and all('Ψωμί' in x['name'] for x in r['rows'])
    assert len(get(api, '/api/items?limit=3')['rows']) == 3
    assert get(api, '/api/items?limit=100000')['limit'] == 500                      # at most 500
    code = 'TST%sA' % ids['tag']
    one = get(api, '/api/items/' + code)
    assert one['id'] == ids['a'] and one['code'] == code and one['vat_rate'] == 24
    assert one['stock'] == db.stock(ids['a']) and one['available'] == one['stock'] - one['reserved']
    bread = get(api, '/api/items/2000000000015')                                   # by its barcode
    assert bread == get(api, '/api/items/ART01')
    assert get(api, '/api/items/NOPE-1', 404)['error'] == 'not_found'


def test_partners_and_ledgers(api, env, users):
    db, ids = env
    db.fn('receive', int, ids['customer'], 12.5, 'BANK', datetime.date(2001, 1, 2))
    db.commit()
    c = get(api, '/api/customers/%d' % ids['customer'])
    assert c['name'].startswith('Test ')
    led = get(api, '/api/ledger/customer/%d?from=1900-01-01' % ids['customer'])
    assert led['close'] == c['balance'] and led['title'].startswith('Καρτέλα πελάτη: Test')
    assert led['rows'][0]['kind'] == 'O' and led['open'] == 0
    assert 12.5 in [x['credit'] for x in led['rows']]
    assert abs(led['close'] - (led['open'] + led['debit'] - led['credit'])) < 0.005
    s = get(api, '/api/suppliers?q=Test')['rows']
    assert any(x['id'] == ids['supplier'] for x in s)
    # an item: its ledger from the beginning ends at its stock
    it = get(api, '/api/ledger/item/%d?from=1900-01-01' % ids['a'])
    assert it['close'] == db.stock(ids['a'])
    e = get(api, '/api/ledger/item/%d?from=2026-02-01&to=2026-01-01' % ids['a'], 400)
    assert e['error'] == 'MM-172' and 'διάστημα' in e['message']
    assert get(api, '/api/ledger/shop/1', 404)['error'] == 'not_found'
    assert get(api, '/api/customers/abc', 404)['error'] == 'not_found'
    assert get(api, '/api/ledger/item/1?from=2026-13-01', 400)['error'] == 'bad_date'


def test_reports(api, env, users):
    db, _ = env
    r = get(api, '/api/reports/sales?from=1900-01-01&to=2100-01-01')
    total = db.one('select nvl(sum(total), 0) from mm_sales_day')[0]
    assert abs(sum(x['total'] for x in r['rows']) - float(total)) < 0.005
    v = get(api, '/api/reports/vat?from=1900-01-01&to=2100-01-01')
    assert abs(sum(x['s_net'] + x['s_vat'] for x in v['rows']) - float(total)) < 0.005
    m = get(api, '/api/reports/min-stock')
    assert len(m['rows']) == db.one('select count(*) from mm_min_stock')[0]
    assert get(api, '/api/reports/nothing', 404)['error'] == 'not_found'


def test_only_get_and_no_tricks(api):
    host, port = api[len('http://'):].split(':')
    for method, path, status in (('PUT', '/api/health', 405), ('DELETE', '/api/items/ART01', 405),
                                 ('GET', '/api/health/../items', 400), ('GET', '/api/%2e%2e/x', 400)):
        c = http.client.HTTPConnection(host, int(port), timeout=10)
        c.request(method, path)
        r = c.getresponse()
        assert r.status == status, (method, path, r.status)
        r.read()
        c.close()


def test_pages(api, env, users):
    """a list a page at a time, with its total; a ledger a page at a time, its carry-over from page to
    page (the "to" of one is the "from" of the next), the pages together are the whole of it"""
    db, ids = env
    r = get(api, '/api/items?limit=5&offset=0')
    assert r['total'] >= len(r['rows']) == 5 and r['offset'] == 0
    r2 = get(api, '/api/items?limit=5&offset=5')
    assert r2['total'] == r['total'] and not {x['id'] for x in r['rows']} & {x['id'] for x in r2['rows']}
    assert get(api, '/api/customers?limit=2')['total'] >= 1
    for k in range(23):                                                  # 23 moves of the item b
        db.proc('adjust_stock', ids['b'], k % 3 + 1 if k % 4 else -1, 'TST page %d' % k)
    db.commit()
    whole = get(api, '/api/ledger/item/%d?from=1900-01-01' % ids['b'])
    moves = whole['rows'][1:]
    pages, offset = [], 0
    while True:
        p = get(api, '/api/ledger/item/%d?from=1900-01-01&limit=10&offset=%d' % (ids['b'], offset))
        assert p['total'] == len(moves) and p['limit'] == 10 and p['offset'] == offset
        pages.append(p)
        offset += 10
        if offset >= p['total']:
            break
    assert [x['seq'] for p in pages for x in p['rows']] == [x['seq'] for x in moves]
    assert pages[0]['carry_in'] == {'debit': 0, 'credit': 0, 'balance': whole['open']}
    for a, b in zip(pages, pages[1:]):
        assert a['carry_out'] == b['carry_in']
        assert a['carry_out']['balance'] == a['rows'][-1]['balance']
    last = pages[-1]['carry_out']
    assert (last['debit'], last['credit'], last['balance']) == (whole['debit'], whole['credit'], whole['close'])
    # past the end: the last page; a page of nothing: the carry-over only
    assert get(api, '/api/ledger/item/%d?from=1900-01-01&limit=10&offset=9999' % ids['b'])['offset'] == (len(moves) - 1) // 10 * 10
    none = get(api, '/api/ledger/item/%d?from=1990-01-01&to=1990-12-31&limit=10' % ids['b'])
    assert none['total'] == 0 and none['rows'] == [] and none['carry_in'] == none['carry_out']


def test_the_till(api, env, users):
    """the till of the pages, as a cashier: a Z opened, items scanned (by code and by barcode), a line
    changed and out, paid by cash with what was given (not enough: nothing posted), money out of the
    drawer, a receipt voided, the Z closed"""
    db, ids = env
    test_core.close_open_z(db, ids['reg'])
    pos = '/api/pos/tst'
    assert 'TST' in [r['code'] for r in get(api, '/api/pos', token='CASHIER')['rows']]
    assert get(api, '/api/pos/nothere', 404, token='CASHIER')['error'] == 'not_found'
    s = get(api, pos, token='CASHIER')
    assert s['code'] == 'TST' and s['z'] is None and s['receipt'] is None and s['last'] == []
    a, b = 'TST%sA' % ids['tag'], 'TST%sB' % ids['tag']
    assert post(api, pos + '/scan', {'code': b}, token='CASHIER', status=409)['error'] == 'z_closed'
    s = post(api, pos + '/open', {'cash': 50}, token='CASHIER')
    assert s['z']['docs'] == 0 and s['z']['drawer'] == 50
    s = post(api, pos + '/scan', {'code': b, 'qty': 2}, token='CASHIER')               # 2 x 2,26
    s = post(api, pos + '/scan', {'code': a.lower()}, token='CASHIER')                 # 12,40
    r = s['receipt']
    assert [(x['code'], x['qty']) for x in r['lines']] == [(b, 2), (a, 1)] and r['total'] == 16.92
    assert post(api, pos + '/scan', {'code': 'TSTNOTHING'}, token='CASHIER', status=404)['error'] == 'not_found'
    lb, la = r['lines'][0]['id'], r['lines'][1]['id']
    s = post(api, pos + '/lines/%d' % lb, {'qty': 3}, token='CASHIER')
    assert s['receipt']['total'] == 19.18
    s = post(api, pos + '/lines/%d' % la, {'qty': 0}, token='CASHIER')                 # out
    assert [x['code'] for x in s['receipt']['lines']] == [b] and s['receipt']['total'] == 6.78
    assert post(api, pos + '/lines/1', {'qty': 1}, token='CASHIER', status=404)['error'] == 'not_found'
    assert post(api, pos + '/lines/%d' % lb, {'qty': -1}, token='CASHIER', status=400)['error'] == 'bad_number'
    assert post(api, pos + '/pay', {'payment': 'GOLD'}, token='CASHIER', status=400)['error'] == 'bad_payment'
    assert post(api, pos + '/pay', {'payment': 'CASH', 'given': 5}, token='CASHIER', status=400)['error'] == 'not_enough'
    assert get(api, pos, token='CASHIER')['receipt']['total'] == 6.78                    # still the draft
    s = post(api, pos + '/pay', {'payment': 'CASH', 'given': 10}, token='CASHIER')
    p = s['paid']
    assert (p['total'], p['change'], p['payment']) == (6.78, 3.22, 'CASH') and p['doc_no'] > 0
    assert s['receipt'] is None and s['last'][0]['doc_no'] == p['doc_no'] and s['z']['docs'] == 1
    assert (s['z']['cash'], s['z']['drawer']) == (6.78, 56.78)
    assert post(api, pos + '/pay', {'payment': 'CARD'}, token='CASHIER', status=409)['error'] == 'no_receipt'
    s = post(api, pos + '/cash', {'amount': -6.78, 'note': 'TST out'}, token='CASHIER')
    assert s['z']['drawer'] == 50
    assert post(api, pos + '/cash', {'amount': 5}, token='CASHIER', status=400)['error'] == 'MM-119'
    # a card: no change; a draft voided; the Z closed with its totals
    post(api, pos + '/scan', {'code': b}, token='CASHIER')
    s = post(api, pos + '/pay', {'payment': 'card', 'given': 100}, token='CASHIER')
    assert s['paid']['change'] is None and s['z']['card'] == 2.26
    post(api, pos + '/scan', {'code': b}, token='CASHIER')
    s = post(api, pos + '/void', token='CASHIER')
    assert s['receipt'] is None
    s = post(api, pos + '/close', token='CASHIER')
    c = s['closed']
    assert (c['docs'], c['total'], c['cash'], c['card']) == (2, 9.04, 6.78, 2.26) and s['z'] is None
    assert sum(v['total'] for v in c['vat_rows']) == 9.04


def test_orders_to_the_till(api, env, users):
    """an order written by a cashier (a phone), items by scan (one more of it, a quantity set, out),
    picked, ready; at the till all of it into the receipt at once, paid: done. Another one for a
    customer on credit: a delivery note (a manager)"""
    db, ids = env
    test_core.close_open_z(db, ids['reg'])
    a, b = 'TST%sA' % ids['tag'], 'TST%sB' % ids['tag']
    o = post(api, '/api/orders', {'name': 'Test παραγγελία', 'phone': '6912345678', 'notes': 'στις 6'}, token='CASHIER')
    oid = o['id']
    assert (o['status'], o['created_by'], o['lines'], o['ready_at']) == ('O', users['CASHIER'], [], None)
    assert o['pickup_date'] == datetime.date.today().isoformat()
    assert post(api, '/api/orders', {'name': 'Test x', 'phone': 'abc'}, token='CASHIER', status=400)['error'] == 'MM-145'
    path = '/api/orders/%d' % oid
    post(api, path + '/lines', {'code': b}, token='CASHIER')
    o = post(api, path + '/lines', {'code': b}, token='CASHIER')                   # one more of it
    o = post(api, path + '/lines', {'code': a.lower(), 'qty': 2, 'mode': 'SET'}, token='CASHIER')
    assert [(x['code'], x['qty']) for x in o['lines']] == [(a, 2), (b, 2)] and o['total'] == 29.32
    assert post(api, path + '/lines', {'code': 'TSTNOTHING'}, token='CASHIER', status=404)['error'] == 'not_found'
    assert any(x['id'] == oid for x in get(api, '/api/orders', token='CASHIER')['rows'])
    o = post(api, path + '/pick', {'item_id': ids['a'], 'qty': 2}, token='CASHIER')
    assert [x['picked'] for x in o['lines']] == [2, 0]
    assert post(api, path + '/pick', {'item_id': ids['b'], 'qty': 9}, token='CASHIER', status=400)['error'] == 'MM-186'
    o = post(api, path + '/ready', {'ready': True}, token='CASHIER')
    assert o['ready_at'] and [x['picked'] for x in o['lines']] == [2, 2]
    o = post(api, path + '/lines', {'code': b, 'qty': 3, 'mode': 'SET'}, token='CASHIER')   # changed: not ready
    assert o['ready_at'] is None
    # at the till: the Z closed, then a receipt open with lines: not; then all of it at once
    pos = '/api/pos/tst'
    assert post(api, pos + '/order', {'id': oid}, token='CASHIER', status=409)['error'] == 'z_closed'
    post(api, pos + '/open', {'cash': 0}, token='CASHIER')
    post(api, pos + '/scan', {'code': b}, token='CASHIER')
    assert post(api, pos + '/order', {'id': oid}, token='CASHIER', status=409)['error'] == 'receipt_open'
    post(api, pos + '/void', token='CASHIER')
    s = post(api, pos + '/order', {'id': oid}, token='CASHIER')
    r = s['receipt']
    assert r['order_id'] == oid and sorted((x['code'], x['qty']) for x in r['lines']) == [(a, 2), (b, 3)]
    assert r['total'] == 31.58 and r['due'] == 31.58
    assert post(api, path + '/lines', {'code': b}, token='CASHIER', status=400)['error'] == 'MM-146'   # at the till now
    s = post(api, pos + '/pay', {'payment': 'CASH', 'given': 40}, token='CASHIER')
    assert s['paid']['change'] == 8.42
    o = get(api, path, token='CASHIER')
    assert o['status'] == 'D' and o['doc_text'].startswith('ALP ')
    assert all(x['id'] != oid for x in get(api, '/api/orders', token='CASHIER')['rows'])          # open only
    assert any(x['id'] == oid for x in get(api, '/api/orders?status=all', token='CASHIER')['rows'])
    # a deposit: the till takes only the rest
    o2 = post(api, '/api/orders', {'name': 'Test προκαταβολή', 'phone': '6912345678'}, token='CASHIER')
    post(api, '/api/orders/%d/lines' % o2['id'], {'code': b}, token='CASHIER')
    db.proc('take_deposit', o2['id'], ids['reg'], 1)
    db.commit()
    s = post(api, pos + '/order', {'id': o2['id']}, token='CASHIER')
    assert (s['receipt']['total'], s['receipt']['due']) == (2.26, 1.26)
    s = post(api, pos + '/pay', {'payment': 'CASH', 'given': 2}, token='CASHIER')
    assert (s['paid']['due'], s['paid']['change']) == (1.26, 0.74)
    post(api, pos + '/close', token='CASHIER')
    # a customer on credit: a delivery note, by a manager; cancelled orders
    o3 = post(api, '/api/orders', {'name': 'Test χονδρική', 'phone': '2610000000', 'customer_id': ids['customer']})
    post(api, '/api/orders/%d/lines' % o3['id'], {'code': b, 'qty': 6})
    assert post(api, '/api/orders/%d/note' % o3['id'], token='CASHIER', status=403)['error'] == 'forbidden'
    o3 = post(api, '/api/orders/%d/note' % o3['id'])
    assert o3['status'] == 'D' and o3['doc_text'].startswith('DAP ') and o3['customer']
    o4 = post(api, '/api/orders', {'name': 'Test ακύρωση', 'phone': '6912345678'}, token='CASHIER')
    assert post(api, '/api/orders/%d/cancel' % o4['id'], token='CASHIER')['status'] == 'C'
    assert get(api, '/api/orders/999999999', 404, token='CASHIER')['error'] == 'not_found'


def test_cors_for_the_app(api, users):
    """the app of Android (its pages from http://localhost of the phone) may call the service: the question
    before a call (OPTIONS) and the answers carry its origin; another origin gets nothing of it"""
    def ask(method, origin, path='/api/items?limit=1', token='CASHIER'):
        req = urllib.request.Request(api + path, method=method)
        req.add_header('Origin', origin)
        if method == 'OPTIONS':
            req.add_header('Access-Control-Request-Method', 'GET')
            req.add_header('Access-Control-Request-Headers', 'authorization')
        elif token:
            req.add_header('Authorization', 'Bearer ' + TOKENS[token])
        try:
            r = NO_PROXY.open(req, timeout=30)
        except urllib.error.HTTPError as e:
            r = e
        return r.status, r.headers
    st, h = ask('OPTIONS', 'http://localhost')
    assert st == 204 and h['Access-Control-Allow-Origin'] == 'http://localhost'
    assert 'Authorization' in h['Access-Control-Allow-Headers'] and 'POST' in h['Access-Control-Allow-Methods']
    st, h = ask('GET', 'http://localhost')
    assert st == 200 and h['Access-Control-Allow-Origin'] == 'http://localhost' and h['Vary'] == 'Origin'
    for bad in ('http://evil.example', 'http://localhost.evil.example', 'null'):
        st, h = ask('GET', bad)
        assert h['Access-Control-Allow-Origin'] is None, bad
        st, h = ask('OPTIONS', bad)
        assert st == 405 and h['Access-Control-Allow-Origin'] is None, bad     # GET or POST only


def test_the_office(api, env, users):
    """the documents of the office through the service, as a manager: two delivery notes, the invoice of
    both, goods back (a return note, its credit note), a receipt of money and its cancel; a cashier: no"""
    db, ids = env
    c, b, a = ids['customer'], 'TST%sB' % ids['tag'], 'TST%sA' % ids['tag']
    assert get(api, '/api/docs', 403, token='CASHIER')['error'] == 'forbidden'
    assert post(api, '/api/payments', {'kind': 'R'}, token='CASHIER', status=403)['error'] == 'forbidden'
    types = {t['code']: t for t in get(api, '/api/doc-types')['rows']}
    assert types['TPY']['ref_type'] == 'DAP' and types['DAP']['partner_sign'] == 0
    assert post(api, '/api/docs', {'doc_type': 'ALP'}, status=400)['error'] == 'bad_type'
    n1 = post(api, '/api/docs', {'doc_type': 'DAP', 'customer_id': c})
    assert (n1['status'], n1['payment'], n1['partner']) == ('D', 'CREDIT', db.one('select name from mm_customer where id = :c', c=c)[0])
    n1 = post(api, '/api/docs/%d/lines' % n1['id'], {'code': b, 'qty': 3, 'price': 2})
    n1 = post(api, '/api/docs/%d/lines' % n1['id'], {'code': a, 'qty': 1})
    line = n1['lines'][1]['id']
    n1 = post(api, '/api/docs/%d/lines/%d' % (n1['id'], line), {'qty': 2, 'discount': 10})
    assert [(x['code'], x['qty'], x['discount']) for x in n1['lines']] == [(b, 3, 0), (a, 2, 10)]
    assert post(api, '/api/docs/%d/lines/1' % n1['id'], {'qty': 1}, status=404)['error'] == 'not_found'
    n1 = post(api, '/api/docs/%d/post' % n1['id'])
    assert n1['status'] == 'P' and n1['doc_no'] > 0 and n1['invoice_text'] is None and n1['ref_text'] is None
    assert post(api, '/api/docs/%d/lines' % n1['id'], {'code': b}, status=409)['error'] == 'not_draft'
    n2 = post(api, '/api/docs', {'doc_type': 'DAP', 'customer_id': c})
    post(api, '/api/docs/%d/lines' % n2['id'], {'code': b, 'qty': 1})
    n2 = post(api, '/api/docs/%d/post' % n2['id'])
    notes = get(api, '/api/docs/notes?type=DAP&customer_id=%d' % c)['rows']
    assert {n1['id'], n2['id']} <= {x['id'] for x in notes}
    inv = post(api, '/api/docs', {'from_note': n1['id']})
    assert (inv['doc_type'], inv['status']) == ('TPY', 'D')
    inv = post(api, '/api/docs/%d/notes' % inv['id'], {'note_id': n2['id']})
    assert [x['id'] for x in inv['notes_in']] == [n1['id'], n2['id']] and len(inv['lines']) == 3
    assert inv['total'] == round(n1['total'] + n2['total'], 2)
    assert post(api, '/api/docs/%d/post' % inv['id'])['status'] == 'P'
    assert get(api, '/api/docs/%d' % n1['id'])['invoice_text'].startswith('TPY ')
    assert post(api, '/api/docs/%d/cancel' % n1['id'], status=400)['error'] == 'MM-185'
    # goods back: a return note (a third of one line), posted; its credit note from it
    back = post(api, '/api/docs/%d/credit' % inv['id'])
    assert (back['doc_type'], back['ref_doc_id']) == ('DEP', inv['id'])
    for x in back['lines'][1:]:
        back = post(api, '/api/docs/%d/lines/%d' % (back['id'], x['id']), {'qty': 0})
    back = post(api, '/api/docs/%d/lines/%d' % (back['id'], back['lines'][0]['id']), {'qty': 1})
    post(api, '/api/docs/%d/post' % back['id'])
    cn = post(api, '/api/docs', {'from_note': back['id']})
    cn = post(api, '/api/docs/%d/post' % cn['id'])
    assert cn['doc_type'] == 'PPY' and cn['status'] == 'P'
    lst = get(api, '/api/docs?type=TPY&limit=5')
    assert lst['rows'][0]['doc_type'] == 'TPY' and lst['total'] >= 1
    # a draft deleted
    d = post(api, '/api/docs', {'doc_type': 'TDA', 'customer_id': c})
    assert post(api, '/api/docs/%d/delete' % d['id'])['ok'] is True
    assert get(api, '/api/docs/%d' % d['id'], 404)['error'] == 'not_found'
    # the money: a receipt, listed, cancelled; a payment to the supplier
    r = post(api, '/api/payments', {'kind': 'R', 'partner_id': c, 'amount': 5, 'method': 'BANK', 'notes': 'TST web'})
    assert (r['kind'], r['amount'], r['method'], r['status']) == ('R', 5, 'BANK', 'P')
    assert any(x['id'] == r['id'] for x in get(api, '/api/payments?kind=R')['rows'])
    assert post(api, '/api/payments/%d/cancel' % r['id'])['status'] == 'C'
    pp = post(api, '/api/payments', {'kind': 'P', 'partner_id': ids['supplier'], 'amount': 7})
    assert (pp['kind'], pp['method']) == ('P', 'BANK')
    assert post(api, '/api/payments', {'kind': 'X', 'partner_id': c, 'amount': 1}, status=400)['error'] == 'bad_kind'


def test_the_shop_of_the_customers(api, env, users):
    """the page of the customers, no login: the items (no cost, no stock, no cards), an order of a name and
    a phone (its token, not its number), at most 3 open a phone, its status, the confirm of the shop, a
    cancel only before it"""
    db, ids = env
    a, b = 'TST%sA' % ids['tag'], 'TST%sB' % ids['tag']
    info = get(api, '/api/shop/info', token=None)
    assert info['name']
    cats = get(api, '/api/shop/categories', token=None)['rows']
    assert cats and all(c['items'] > 0 for c in cats)
    r = get(api, '/api/shop/items?q=%s' % b, token=None)
    assert [x['code'] for x in r['rows']] == [b]
    x = r['rows'][0]
    assert set(x) == {'code', 'name', 'category', 'unit', 'price', 'available'} and x['available'] in ('Y', 'N')
    assert get(api, '/api/shop/items?q=CRD05', token=None)['total'] == 0                  # no card with a PIN
    phone = '69%08d' % (int(ids['tag'], 16) % 10 ** 8)
    order = {'name': 'Test πελάτης', 'phone': phone, 'notes': 'στις 6', 'lines': [{'code': a, 'qty': 1}, {'code': b, 'qty': 2}, {'code': b, 'qty': 1}]}
    o = post(api, '/api/shop/orders', order, token=None)
    assert len(o['token']) == 48 and o['state'] == 'sent' and o['pickup_date'] == datetime.date.today().isoformat()
    assert sorted((y['code'], y['qty']) for y in o['lines']) == [(a, 1), (b, 3)] and o['total'] == 19.18
    bell = get(api, '/api/orders/new', token='CASHIER')
    assert bell['count'] >= 1 and bell['last_id'] == o['id'] and bell['last_name'] == 'Test πελάτης'
    assert get(api, '/api/orders/new', 401, token=None)['error'] == 'auth_required'
    staff = get(api, '/api/orders/%d' % o['id'], token='CASHIER')
    assert (staff['source'], staff['confirmed_at'], staff['created_by']) == ('O', None, 'online')
    # wrong: no lines, a bad phone, an item not there, too many; a token wrong
    assert post(api, '/api/shop/orders', {**order, 'lines': []}, token=None, status=400)['error'] == 'bad_lines'
    assert post(api, '/api/shop/orders', {**order, 'phone': 'abc'}, token=None, status=400)['error'] == 'MM-145'
    assert post(api, '/api/shop/orders', {**order, 'lines': [{'code': 'CRD05', 'qty': 1}]}, token=None, status=404)['error'] == 'not_found'
    assert post(api, '/api/shop/orders', {**order, 'lines': [{'code': a, 'qty': 500}]}, token=None, status=400)['error'] == 'bad_number'
    assert get(api, '/api/shop/orders/%s' % ('0' * 48), 404, token=None)['error'] == 'not_found'
    assert get(api, '/api/shop/orders/%d' % o['id'], 404, token=None)['error'] == 'not_found'        # not by its number
    o2 = post(api, '/api/shop/orders', order, token=None)
    o3 = post(api, '/api/shop/orders', order, token=None)
    assert post(api, '/api/shop/orders', order, token=None, status=400)['error'] == 'MM-188'         # 3 open a phone
    assert post(api, '/api/shop/orders/%s/cancel' % o3['token'], token=None)['state'] == 'cancelled'
    # the shop confirms (a call): the customer sees it, cannot cancel it any more; ready
    n = get(api, '/api/orders/new', token='CASHIER')['count']
    s = post(api, '/api/orders/%d/confirm' % o['id'], token='CASHIER')
    assert s['confirmed_at'] is not None
    assert get(api, '/api/orders/new', token='CASHIER')['count'] == n - 1                # confirmed: no bell
    assert get(api, '/api/shop/orders/%s' % o['token'], token=None)['state'] == 'confirmed'
    assert post(api, '/api/shop/orders/%s/cancel' % o['token'], token=None, status=400)['error'] == 'MM-188'
    post(api, '/api/orders/%d/ready' % o['id'], {'ready': True}, token='CASHIER')
    assert get(api, '/api/shop/orders/%s' % o['token'], token=None)['state'] == 'ready'
    post(api, '/api/orders/%d/cancel' % o2['id'], token='CASHIER')
    assert get(api, '/api/shop/orders/%s' % o2['token'], token=None)['state'] == 'cancelled'
    # the page itself, no login
    r = NO_PROXY.open(api + '/shop/', timeout=30)
    assert r.status == 200 and b'shop.js' in r.read() and 'script-src' in r.headers['Content-Security-Policy']


def test_the_receipt_to_print(api, env, users):
    """a receipt as printed: the header and the footer of the shop (a manager sets them), its lines, its
    VAT, the PIN of its card sold today (the print in MM_PIN_LOG, by the user of the login)"""
    db, ids = env
    test_core.close_open_z(db, ids['reg'])
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, serial_tracked) "
                   "values (:c, 'Test card print', :cat, 'D', 15, 'Y')", c='TST%sP' % ids['tag'], cat=cat)
    card = db.one('select id from mm_item where code = :c', c='TST%sP' % ids['tag'])[0]
    db.fn('load_serial', int, card, 'PRT-%s-1' % ids['tag'], '123412341234')
    db.commit()
    assert post(api, '/api/pos/settings', {'header': 'x'}, token='CASHIER', status=403)['error'] == 'forbidden'
    s = post(api, '/api/pos/settings', {'header': 'MINI MARKET TEST\nΑΦΜ 999999999', 'footer': 'Ευχαριστούμε!'})
    assert s == {'header': 'MINI MARKET TEST\nΑΦΜ 999999999', 'footer': 'Ευχαριστούμε!'}
    assert post(api, '/api/pos/settings', {'header': 'x' * 401}, status=400)['error'] == 'too_long'
    pos = '/api/pos/tst'
    post(api, pos + '/open', {'cash': 0}, token='CASHIER')
    post(api, pos + '/scan', {'code': 'TST%sB' % ids['tag'], 'qty': 2}, token='CASHIER')
    post(api, pos + '/scan', {'code': 'TST%sP' % ids['tag']}, token='CASHIER')
    paid = post(api, pos + '/pay', {'payment': 'CASH', 'given': 20}, token='CASHIER')['paid']
    r = get(api, '%s/receipt/%d' % (pos, paid['id']), token='CASHIER')
    assert (r['doc_no'], r['total'], r['register'], r['status']) == (paid['doc_no'], 19.52, 'TST', 'P')
    assert r['header'].startswith('MINI MARKET TEST') and r['footer'] == 'Ευχαριστούμε!'
    assert [x['qty'] for x in r['lines']] == [2, 1]
    assert {v['vat_code']: v['total'] for v in r['vat_rows']} == {'B': 4.52, 'D': 15}
    assert [(c['serial'], c['pin']) for c in r['cards']] == [('PRT-%s-1' % ids['tag'], '123412341234')]
    assert db.one("select username, reason from mm_pin_log where serial_id = (select id from mm_serial where serial = :s) "
                  "order by id desc fetch first 1 rows only", s='PRT-%s-1' % ids['tag']) == (users['CASHIER'].upper(), 'RECEIPT')
    assert get(api, '%s/receipt/%d' % (pos, 999999999), 404, token='CASHIER')['error'] == 'not_found'
    assert get(api, '/api/pos/t1/receipt/%d' % paid['id'], 404, token='CASHIER')['error'] == 'not_found'   # another register
    post(api, pos + '/close', token='CASHIER')
    assert post(api, '/api/pos/settings', {'header': None, 'footer': None}) == {'header': None, 'footer': None}


def test_the_state_of_the_backup(api, env, users):
    """backup.ps1 tells the database (mm_core.backup_done); /api/backup: NEVER, OK, OLD (more than 2 days),
    FAILED (the last try after the last good one); a manager only"""
    db, ids = env
    db.cur.execute("select name, value from mm_setting where name like 'BACKUP\\_%' escape '\\'")
    kept = list(db.cur)
    try:
        db.cur.execute("delete from mm_setting where name like 'BACKUP\\_%' escape '\\'")
        db.commit()
        assert get(api, '/api/backup')['state'] == 'NEVER'
        db.proc('backup_done', 'Y', 'mm_20261116_2315.dmp')
        db.commit()
        r = get(api, '/api/backup')
        assert (r['state'], r['ok_file'], r['days']) == ('OK', 'mm_20261116_2315.dmp', 0)
        db.cur.execute("update mm_setting set value = to_char(sysdate - 3, 'YYYY-MM-DD HH24:MI:SS') where name = 'BACKUP_OK_AT'")
        db.commit()
        assert get(api, '/api/backup')['state'] == 'OLD'
        db.proc('backup_done', 'N', "expdp failed: ORA-39002 'x'")
        db.commit()
        r = get(api, '/api/backup')
        assert (r['state'], r['error']) == ('FAILED', "expdp failed: ORA-39002 'x'")
        db.proc('backup_done', 'Y', 'mm_next.dmp')                     # a good one after it: OK again
        db.commit()
        assert get(api, '/api/backup')['state'] == 'OK'
        assert get(api, '/api/backup', 403, token='CASHIER')['error'] == 'forbidden'
    finally:
        db.cur.execute("delete from mm_setting where name like 'BACKUP\\_%' escape '\\'")
        for name, value in kept:
            db.cur.execute('insert into mm_setting (name, value) values (:n, :v)', n=name, v=value)
        db.commit()
