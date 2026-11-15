"""test_api.py -- the REST service (api/, mm-api.jar) on a live database: it starts the jar on a
free port of this computer, with MM_DSN, and asks it as a client would.

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


def get(base, path, status=200):
    try:
        r = NO_PROXY.open(base + path, timeout=30)
        code, body, ctype = r.status, r.read(), r.headers['Content-Type']
    except urllib.error.HTTPError as e:
        code, body, ctype = e.code, e.read(), e.headers['Content-Type']
    assert code == status, (path, code, body[:300])
    assert ctype == 'application/json; charset=utf-8'
    return json.loads(body.decode('utf-8'))


def test_health(api):
    assert get(api, '/api/health') == {'status': 'ok', 'db': 'ok'}


def test_items(api, env):
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


def test_partners_and_ledgers(api, env):
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


def test_reports(api, env):
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
    for method, path, status in (('POST', '/api/health', 405), ('DELETE', '/api/items/ART01', 405),
                                 ('GET', '/api/health/../items', 400), ('GET', '/api/%2e%2e/x', 400)):
        c = http.client.HTTPConnection(host, int(port), timeout=10)
        c.request(method, path)
        r = c.getresponse()
        assert r.status == status, (method, path, r.status)
        r.read()
        c.close()
