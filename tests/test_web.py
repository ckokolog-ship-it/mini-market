"""test_web.py -- the pages of the mini market (api/src/main/resources/web) in a real browser: the jar
of test_api.py, its manager and cashier; tests/web_check.js with Playwright (Chromium).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

Without MM_DSN, java, node or Playwright, skipped. The screenshots: MM_WEB_SHOTS=<folder>.
"""
import os
import re
import shutil
import subprocess
import tempfile

import pytest

oracledb = pytest.importorskip('oracledb')
import test_api  # noqa: E402
import test_core  # noqa: E402
from test_core import DSN  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
pytestmark = pytest.mark.skipif(not DSN or not shutil.which('java') or not shutil.which('node'),
                                reason='MM_DSN, java or node missing')
env = test_core.env
api = test_api.api
users = test_api.users
XSS = '<img src=x onerror="window.__xss=1">'


def test_the_pages_in_a_browser(api, env, users):
    db, ids = env
    if subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no Playwright for node')
    db.cur.execute('update mm_item set name = :n where id = :i', n=XSS, i=ids['a'])
    for k in range(30):                                   # the ledger of the item b: two pages of 25
        db.proc('adjust_stock', ids['b'], k % 4 + 1, 'TST web %d' % k)
    db.commit()
    test_core.close_open_z(db, ids['reg'])                 # the till: the Z of TST opened in the page
    db.cur.execute("delete from mm_setting where name like 'BACKUP\\_%' escape '\\'")
    db.proc('backup_done', 'N', 'expdp: test')            # the last backup failed: a manager sees it
    db.commit()
    # an invoice sent to myDATA (the little AADE of the tests): its print, with its MARK and QR
    db.cur.execute("delete from mm_setting where name like 'MYDATA%'")
    db.cur.execute("insert into mm_setting (name, value) values ('MYDATA_AFM', '094014201')")
    db.cur.execute("update mm_customer set afm = '090000045' where id = :c", c=ids['customer'])
    sent = db.fn('new_doc', int, 'TDA', p_customer_id=ids['customer'], p_payment='CREDIT')
    db.fn('add_line', int, sent, ids['b'], 2)
    db.fn('post_doc', int, sent)
    db.commit()
    mark = test_api.post(api, '/api/docs/%d/mydata' % sent)['mydata_mark']
    labels = tempfile.mkdtemp(prefix='mmlabels-')
    e = dict(os.environ, BASE=api, MGR=users['MANAGER'], CASHIER=users['CASHIER'], PW=test_api.PW,
             ITEM='TST%sA' % ids['tag'], ITEM_B=str(ids['b']), XSS=XSS, SHOTS=os.environ.get('MM_WEB_SHOTS', ''),
             LABELS=labels, DOC_SENT=str(sent), SENT_MARK=str(mark))
    try:
        r = subprocess.run(['node', os.path.join(HERE, 'web_check.js')], env=e, capture_output=True, text=True, timeout=180)
        print(r.stdout, r.stderr)
        assert r.returncode == 0, r.stdout + r.stderr
        assert '== web OK' in r.stdout
        read_labels(labels, 'TST%sA' % ids['tag'])
    finally:
        shutil.rmtree(labels, ignore_errors=True)
        db.cur.execute("delete from mm_setting where name like 'MYDATA%'")
        db.cur.execute('update mm_customer set afm = null where id = :c', c=ids['customer'])
        db.cur.execute("delete from mm_setting where name like 'BACKUP\\_%' escape '\\'")
        db.commit()


def read_labels(folder, item):
    """the labels as they show: their barcode and their QR read back by a decoder (zxing-cpp, when there);
    the PDF of the print: one A4 page"""
    with open(os.path.join(folder, 'labels.pdf'), 'rb') as f:
        pdf = f.read()
    assert pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages') == 1
    boxes = re.findall(rb'/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]', pdf)
    assert boxes and all(abs(float(w) - 595.3) < 1 and abs(float(h) - 841.9) < 1 for w, h in boxes), boxes   # A4
    try:
        import zxingcpp
        from PIL import Image
    except ImportError:
        print('(no zxing-cpp or Pillow: the labels are not read back)')
        return
    want = [(item, 'Code128'), ('2000000000015', 'EAN13')]
    for k, (text, kind) in enumerate(want):
        found = {(x.format.name, x.text) for x in zxingcpp.read_barcodes(Image.open(os.path.join(folder, 'label%d.png' % k)))}
        assert (kind, text) in found, (k, found)
        code = item if k == 0 else 'ART01'
        assert ('QRCode', 'http://192.168.1.10:8090/web/#/item/' + code) in found, (k, found)


def y4m(path, bars, w=640, h=480, frames=12):
    """a video of the fake camera of Chromium: the bars of a barcode, black on white, in the middle"""
    import array
    y = array.array('B', [235]) * (w * h)
    mod = 4
    x0 = (w - (len(bars) + 20) * mod) // 2 + 10 * mod
    for i, b in enumerate(bars):
        if b == '1':
            for x in range(x0 + i * mod, x0 + (i + 1) * mod):
                for row in range(140, 340):
                    y[row * w + x] = 16
    uv = bytes([128]) * (w * h // 4)
    with open(path, 'wb') as f:
        f.write(b'YUV4MPEG2 W%d H%d F10:1 Ip A1:1 C420jpeg\n' % (w, h))
        for _ in range(frames):
            f.write(b'FRAME\n' + y.tobytes() + uv + uv)


def test_the_app_mode(api, env, users):
    """the pages as the app of Android runs them: another origin, the address of the shop, CORS, the
    camera (a fake one showing the barcode of the bread)"""
    db, ids = env
    if subprocess.run(['node', '-e', "require('playwright')"], capture_output=True).returncode:
        pytest.skip('no Playwright for node')
    import http.server
    import json
    import threading
    web = os.path.join(HERE, '..', 'api', 'src', 'main', 'resources', 'web')
    bars = json.loads(subprocess.check_output(['node', os.path.join(HERE, 'codes_check.mjs'),
                                               json.dumps({'ean': ['2000000000015'], 'c128': [], 'qr': []})]))
    tmp = tempfile.mkdtemp(prefix='mmapp-')
    video = os.path.join(tmp, 'bread.y4m')
    y4m(video, bars['ean'][0]['bars'])

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=web, **k)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', test_api.APP_PORT), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        e = dict(os.environ, APP='http://localhost:%d' % test_api.APP_PORT, API=api, BAD='127.0.0.1:%d' % test_api.free_port(),
                 MGR=users['MANAGER'],
                 PW=test_api.PW, VIDEO=video, SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
        r = subprocess.run(['node', os.path.join(HERE, 'app_check.js')], env=e, capture_output=True, text=True, timeout=180)
        print(r.stdout, r.stderr)
        assert r.returncode == 0, r.stdout + r.stderr
        assert '== app OK' in r.stdout
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
