"""test_codes.py -- the barcodes and the QR codes of the labels (api/src/main/resources/web/codes.js),
drawn as pictures and read back by a decoder (zxing-cpp): EAN-13 (and its check digit), Code 128 B,
QR of every version 1 to 10 (latin, Greek: UTF-8). No database.

    pip install zxing-cpp pillow        (else skipped)
"""
import json
import os
import shutil
import subprocess

import pytest

zxingcpp = pytest.importorskip('zxingcpp')
Image = pytest.importorskip('PIL.Image')
pytestmark = pytest.mark.skipif(not shutil.which('node'), reason='node missing')
HERE = os.path.dirname(os.path.abspath(__file__))

EAN = ['2000000000015', '1234567890128', '5901234123457', '2000000000016', '200000000001', 'abcdefghijklm']
C128 = ['ART01', 'TST1A2B3C', 'POT-05/x', 'a b.c', 'Z' * 30]
# the lengths at the edge of each version (M): 14 26 42 62 84 106 122 152 180 213
QR = ['A', 'x' * 14, 'x' * 15, 'y' * 26, 'y' * 27, 'http://192.168.1.10:8090/web/#/item/ART01', 'z' * 62,
      'z' * 84, 'k' * 106, 'k' * 122, 'q' * 152, 'w' * 180, 'e' * 213, 'ψωμί χωριάτικο 1 kg ' * 5]


@pytest.fixture(scope='module')
def out():
    r = subprocess.run(['node', os.path.join(HERE, 'codes_check.mjs'), json.dumps({'ean': EAN, 'c128': C128, 'qr': QR})],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def bars_picture(bars, s=3):
    im = Image.new('L', ((len(bars) + 20) * s, 80), 255)
    for i, b in enumerate(bars):
        if b == '1':
            im.paste(0, ((i + 10) * s, 5, (i + 11) * s, 75))
    return im


def read(im):
    return {(x.format.name, x.text) for x in zxingcpp.read_barcodes(im)}


def test_ean13(out):
    assert [e['ok'] for e in out['ean']] == [True, True, True, False, False, False]   # the check digit
    for e in out['ean']:
        if e['ok']:
            assert len(e['bars']) == 95
            assert read(bars_picture(e['bars'])) == {('EAN13', e['text'])}


def test_code128(out):
    for e in out['c128']:
        assert read(bars_picture(e['bars'])) == {('Code128', e['text'])}


def test_qr(out):
    sizes = []
    for e in out['qr']:
        m = e['m']
        n = len(m)
        sizes.append(n)
        im = Image.new('L', ((n + 8) * 4, (n + 8) * 4), 255)
        for y, row in enumerate(m):
            for x, c in enumerate(row):
                if c == '1':
                    im.paste(0, ((x + 4) * 4, (y + 4) * 4, (x + 5) * 4, (y + 5) * 4))
        assert read(im) == {('QRCode', e['text'])}, (n, e['text'][:30])
    assert {(s - 17) // 4 for s in sizes} == set(range(1, 11))          # every version
    assert sizes[1] == 21 and sizes[2] == 25                             # 14 bytes: version 1; 15: version 2
