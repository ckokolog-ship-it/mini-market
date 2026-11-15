"""test_web.py -- the pages of the mini market (api/src/main/resources/web) in a real browser: the jar
of test_api.py, its manager and cashier; tests/web_check.js with Playwright (Chromium).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests

Without MM_DSN, java, node or Playwright, skipped. The screenshots: MM_WEB_SHOTS=<folder>.
"""
import os
import shutil
import subprocess

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
    e = dict(os.environ, BASE=api, MGR=users['MANAGER'], CASHIER=users['CASHIER'], PW=test_api.PW,
             ITEM='TST%sA' % ids['tag'], ITEM_B=str(ids['b']), XSS=XSS, SHOTS=os.environ.get('MM_WEB_SHOTS', ''))
    r = subprocess.run(['node', os.path.join(HERE, 'web_check.js')], env=e, capture_output=True, text=True, timeout=180)
    print(r.stdout, r.stderr)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '== web OK' in r.stdout
