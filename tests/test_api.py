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
import time
import urllib.error
import urllib.request

import pytest

oracledb = pytest.importorskip('oracledb')
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
JAR = os.path.join(ROOT, 'api', 'target', 'mm-api.jar')
pytestmark = pytest.mark.skipif(not DSN or not shutil.which('java'), reason='MM_DSN or java missing')
env = test_core.env
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
    e = dict(os.environ, MM_DB_URL='jdbc:oracle:thin:@' + where, MM_DB_USER=user, MM_DB_PASSWORD=pw,
             MM_API_PORT=str(port), MM_API_BIND='127.0.0.1')
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
