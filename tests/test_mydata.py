"""test_mydata.py -- myDATA of AADE (mm-api MyData.java) against a little AADE of the tests (fake_aade.py):
the XML of an invoice and of its credit note, checked against the XSD of AADE (xmllint) as well as by
the service; sent (MARK, UID, QR into the document), an error of AADE, sent by itself (MYDATA_AUTO and
the worker), cancelled at AADE then here; what is refused before anything goes.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

import pytest

import test_api
from test_api import get, post
from test_db import afm_ok

pytestmark = pytest.mark.skipif(not test_api.DSN, reason='MM_DSN not set')
api, env, users = test_api.api, test_api.env, test_api.users
XSD = os.path.join(test_api.ROOT, 'api', 'src', 'main', 'resources', 'mydata', 'InvoicesDoc-v1.0.12.xsd')
NS = {'i': 'http://www.aade.gr/myDATA/invoice/v1.0', 'c': 'https://www.aade.gr/myDATA/incomeClassificaton/v1.0'}
SHOP = '094014201'                      # (a valid ΑΦΜ in form: the shop of the tests)


def new_afm(db):
    rnd = random.Random()
    while True:
        a = '%08d' % rnd.randrange(10 ** 8)
        a += str(sum(int(d) * 2 ** (8 - k) for k, d in enumerate(a)) % 11 % 10)
        if afm_ok(a) and not db.one('select count(*) from mm_customer where afm = :a', a=a)[0]:
            return a


def xsd_ok(xml):
    if not shutil.which('xmllint'):
        return True
    d = tempfile.mkdtemp(prefix='mmxml-')
    try:
        f = os.path.join(d, 'doc.xml')
        open(f, 'w', encoding='utf-8').write(xml)
        r = subprocess.run(['xmllint', '--noout', '--schema', XSD, f], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def invoice(db, ids, lines, payment='CREDIT'):
    d = db.fn('new_doc', int, 'TDA', p_customer_id=ids['customer'], p_payment=payment)   # 1.1 too
    for it, q in lines:
        db.fn('add_line', int, d, ids[it], q)
    db.fn('post_doc', int, d)
    db.commit()
    return d


@pytest.fixture
def shop(env):
    db, ids = env
    db.cur.execute("select name, value from mm_setting where name like 'MYDATA%'")
    kept = list(db.cur)
    db.cur.execute("delete from mm_setting where name like 'MYDATA%'")
    db.cur.execute("insert into mm_setting (name, value) values ('MYDATA_AFM', :a)", a=SHOP)
    afm = new_afm(db)
    db.cur.execute('update mm_customer set afm = :a where id = :c', a=afm, c=ids['customer'])
    db.commit()
    yield db, ids, afm
    db.cur.execute("delete from mm_setting where name like 'MYDATA%'")
    for n, v in kept:
        db.cur.execute('insert into mm_setting (name, value) values (:n, :v)', n=n, v=v)
    db.cur.execute('update mm_customer set afm = null where id = :c', c=ids['customer'])
    db.commit()


def test_an_invoice_to_mydata_and_its_credit_note(api, shop, users):
    db, ids, afm = shop
    aade = test_api.AADE
    d = invoice(db, ids, [('a', 2), ('b', 3)])
    total = float(db.one('select total from mm_doc where id = :d', d=d)[0])
    # its XML: as the XSD of AADE; the shop, the customer (no name: AADE has it), its lines, its sums
    xml = get(api, '/api/docs/%d/mydata' % d)['xml']
    assert xsd_ok(xml)
    x = ET.fromstring(xml).find('i:invoice', NS)
    assert x.findtext('i:issuer/i:vatNumber', namespaces=NS) == SHOP
    assert x.findtext('i:counterpart/i:vatNumber', namespaces=NS) == afm and x.find('i:counterpart/i:name', NS) is None
    h = x.find('i:invoiceHeader', NS)
    no = db.one('select doc_no from mm_doc where id = :d', d=d)[0]
    assert (h.findtext('i:series', namespaces=NS), h.findtext('i:aa', namespaces=NS),
            h.findtext('i:invoiceType', namespaces=NS)) == ('TDA', str(no), '1.1')
    assert x.findtext('i:paymentMethods/i:paymentMethodDetails/i:type', namespaces=NS) == '5'     # on credit
    rows = x.findall('i:invoiceDetails', NS)
    assert [r.findtext('i:vatCategory', namespaces=NS) for r in rows] == ['1', '2']           # a 24%, b 13%
    s = x.find('i:invoiceSummary', NS)
    assert float(s.findtext('i:totalGrossValue', namespaces=NS)) == total
    assert float(s.findtext('i:totalNetValue', namespaces=NS)) == round(
        sum(float(r.findtext('i:netValue', namespaces=NS)) for r in rows), 2)
    assert s.findtext('i:incomeClassification/c:classificationType', namespaces=NS) == 'E3_561_001'
    # sent: its MARK, UID, QR from AADE; the account in the headers; once only
    # (the sender in the background, every 2 seconds, may send another one of the queue meanwhile: its MARK
    # after the one before, not above the last; its call the one with its number)
    n0, m0 = len(aade.got), aade.mark
    r = post(api, '/api/docs/%d/mydata' % d)
    assert r['mydata_state'] == 'S' and m0 < r['mydata_mark'] <= aade.mark and len(r['mydata_uid']) == 40
    assert r['mydata_qr'].startswith('https://') and r['mydata_error'] is None
    path, headers, body = [g for g in aade.got[n0:] if '<aa>%d</aa>' % no in g[2]][0]
    assert path == '/SendInvoices' and headers['aade-user-id'] == 'tst-user' and '<invoiceType>1.1' in body
    assert post(api, '/api/docs/%d/mydata' % d, status=400)['error'] == 'MM-189'               # sent already
    # its credit note (goods back: the return note, its credit note): 5.1, the MARK of the invoice
    dep = post(api, '/api/docs/%d/credit' % d)['id']
    post(api, '/api/docs/%d/post' % dep)
    ppy = post(api, '/api/docs', {'from_note': dep})['id']
    post(api, '/api/docs/%d/post' % ppy)
    xml = get(api, '/api/docs/%d/mydata' % ppy)['xml']
    assert xsd_ok(xml)
    h = ET.fromstring(xml).find('i:invoice/i:invoiceHeader', NS)
    assert (h.findtext('i:invoiceType', namespaces=NS), h.findtext('i:correlatedInvoices', namespaces=NS)) == (
        '5.1', str(r['mydata_mark']))
    assert post(api, '/api/docs/%d/mydata' % ppy)['mydata_state'] == 'S'
    # cancelled: not here while it is at AADE; at AADE first (its MARK), then here
    assert db.one('select count(*) from mm_doc where id = :d', d=ppy)[0] == 1
    db.fails(189, 'cancel_doc', ppy)
    m0 = aade.mark
    c = post(api, '/api/docs/%d/mydata/cancel' % ppy)
    assert (c['status'], c['mydata_state']) == ('C', 'X') and m0 < c['mydata_cancel_mark'] <= aade.mark
    assert '/CancelInvoice?mark=%d' % c['mydata_mark'] in [g[0] for g in aade.got]
    assert get(api, '/api/docs/%d' % ppy)['mydata_state'] == 'X'
    assert get(api, '/api/docs/%d/mydata' % d, status=403, token='CASHIER')['error'] == 'forbidden'


def test_mydata_errors_and_by_itself(api, shop, users):
    db, ids, afm = shop
    aade = test_api.AADE
    # AADE says no: failed (E) with its words; again when AADE is fine: sent
    d = invoice(db, ids, [('a', 1)], payment='CASH')
    aade.mode = 'invalid'
    try:
        r = post(api, '/api/docs/%d/mydata' % d)
        assert r['mydata_state'] == 'E' and 'ValidationError' in r['mydata_error'] and '104' in r['mydata_error']
        aade.mode = 'http500'
        r = post(api, '/api/docs/%d/mydata' % d)
        assert r['mydata_state'] == 'E' and 'HTTP 500' in r['mydata_error']
    finally:
        aade.mode = 'ok'
    r = post(api, '/api/docs/%d/mydata' % d)
    assert r['mydata_state'] == 'S' and r['mydata_error'] is None
    assert '<type>3</type>' in aade.got[-1][2]                                                # cash
    # by itself: MYDATA_AUTO Y, a posted invoice waits (Q), the worker of the service sends it
    db.cur.execute("insert into mm_setting (name, value) values ('MYDATA_AUTO', 'Y')")
    db.commit()
    q = invoice(db, ids, [('b', 1)])
    assert db.one('select mydata_state from mm_doc where id = :d', d=q)[0] == 'Q'
    for _ in range(40):
        if db.one('select mydata_state from mm_doc where id = :d', d=q)[0] == 'S':
            break
        time.sleep(0.5)
    assert db.one('select mydata_state, mydata_mark from mm_doc where id = :d', d=q)[0] == 'S'
    # refused before anything goes: a customer without ΑΦΜ, the shop without ΑΦΜ, 0% VAT without its
    # cause, a document not of myDATA, a draft
    n0 = len(aade.got)
    db.cur.execute("delete from mm_setting where name = 'MYDATA_AUTO'")
    db.cur.execute('update mm_customer set afm = null where id = :c', c=ids['customer'])
    db.commit()
    e = invoice(db, ids, [('a', 1)])
    assert 'ΑΦΜ' in post(api, '/api/docs/%d/mydata' % e, status=400)['message']
    db.cur.execute('update mm_customer set afm = :a where id = :c', a=afm, c=ids['customer'])
    db.cur.execute("update mm_setting set value = '12' where name = 'MYDATA_AFM'")
    db.commit()
    assert 'MYDATA_AFM' in post(api, '/api/docs/%d/mydata' % e, status=400)['message']
    db.cur.execute("update mm_setting set value = :a where name = 'MYDATA_AFM'", a=SHOP)
    db.cur.execute("update mm_doc_line set vat_rate = 0, vat = 0, total = net where doc_id = :d", d=e)
    db.cur.execute("update mm_doc set vat = 0, total = net where id = :d", d=e)
    db.commit()
    assert 'MYDATA_VAT_EXEMPTION' in post(api, '/api/docs/%d/mydata' % e, status=400)['message']
    db.cur.execute("insert into mm_setting (name, value) values ('MYDATA_VAT_EXEMPTION', '1')")
    db.commit()
    xml = get(api, '/api/docs/%d/mydata' % e)['xml']
    assert xsd_ok(xml) and re.search(r'<vatCategory>7</vatCategory>\s*<vatAmount>0.00</vatAmount>\s*'
                                     r'<vatExemptionCategory>1</vatExemptionCategory>', xml)
    note = db.fn('new_doc', int, 'DAP', p_customer_id=ids['customer'], p_payment='CREDIT')
    db.fn('add_line', int, note, ids['a'], 1)
    db.fn('post_doc', int, note)
    db.commit()
    assert post(api, '/api/docs/%d/mydata' % note, status=400)['error'] == 'MM-189'
    draft = db.fn('new_doc', int, 'TPY', p_customer_id=ids['customer'], p_payment='CREDIT')
    db.commit()
    assert post(api, '/api/docs/%d/mydata' % draft, status=400)['error'] == 'MM-189'
    db.proc('delete_doc', draft)
    db.commit()
    assert len(aade.got) == n0                                                                 # none of them went
