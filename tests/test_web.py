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
    labels = tempfile.mkdtemp(prefix='mmlabels-')
    e = dict(os.environ, BASE=api, MGR=users['MANAGER'], CASHIER=users['CASHIER'], PW=test_api.PW,
             ITEM='TST%sA' % ids['tag'], ITEM_B=str(ids['b']), XSS=XSS, SHOTS=os.environ.get('MM_WEB_SHOTS', ''),
             LABELS=labels)
    try:
        r = subprocess.run(['node', os.path.join(HERE, 'web_check.js')], env=e, capture_output=True, text=True, timeout=180)
        print(r.stdout, r.stderr)
        assert r.returncode == 0, r.stdout + r.stderr
        assert '== web OK' in r.stdout
        read_labels(labels, 'TST%sA' % ids['tag'])
    finally:
        shutil.rmtree(labels, ignore_errors=True)


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
