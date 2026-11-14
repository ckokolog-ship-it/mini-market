"""test_forms.py -- the forms of forms/mkforms.py, without the Forms:

- the XML: ASCII, every LOV of an item exists, every return item is an item of the form;
- the record groups: each query runs in the database, with the columns the LOV maps, in order;
- the package UI of each form, compiled in the database against small stubs of the built-ins of
  the Forms (NAME_IN, COPY, MESSAGE, SHOW_LOV, GO_BLOCK, EXECUTE_QUERY, SET_*_PROPERTY), then
  called as the triggers call it. The stubs and UI are dropped at the end.

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 -m pytest tests
"""
import importlib.util
import os
import xml.etree.ElementTree as ET

import pytest

oracledb = pytest.importorskip('oracledb')
from test_db import DSN  # noqa: E402
import test_core  # noqa: E402

env = test_core.env      # its items, customer, supplier, register TST

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
NS = {'f': 'http://xmlns.oracle.com/Forms'}

spec = importlib.util.spec_from_file_location('mkforms', os.path.join(ROOT, 'forms', 'mkforms.py'))
mkforms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mkforms)
BUILT = {name: mkforms.build(name, f) for name, f in mkforms.FORMS.items()}
WORDS = dict(mkforms.WORDS.words)

STUBS = [
    """create or replace package fstub as
  type t_map is table of varchar2(4000) index by varchar2(200);
  items t_map; props t_map; msgs varchar2(32767); block varchar2(30); queries varchar2(4000);
  lov_answer boolean := true; lov_id varchar2(40);
  procedure clear;
end;""",
    """create or replace package body fstub as
  procedure clear is
  begin
    items.delete; props.delete; msgs := null; block := null; queries := null;
    lov_answer := true; lov_id := null;
  end;
end;""",
    """create or replace function name_in(p varchar2) return varchar2 is
begin
  if fstub.items.exists(upper(p)) then return fstub.items(upper(p)); end if;
  return null;
end;""",
    "create or replace procedure copy(v varchar2, p varchar2) is begin fstub.items(upper(p)) := v; end;",
    "create or replace procedure message(m varchar2) is begin fstub.msgs := fstub.msgs || m || chr(10); end;",
    "create or replace function title return number is begin return 1; end;",
    "create or replace function label return number is begin return 2; end;",
    "create or replace function prompt_text return number is begin return 3; end;",
    "create or replace function default_where return number is begin return 4; end;",
    "create or replace function format_mask return number is begin return 5; end;",
    """create or replace procedure set_window_property(w varchar2, p number, v varchar2) is
begin fstub.props('WINDOW ' || upper(w) || '#' || p) := v; end;""",
    """create or replace procedure set_item_property(i varchar2, p number, v varchar2) is
begin fstub.props(upper(i) || '#' || p) := v; end;""",
    """create or replace procedure set_lov_property(l varchar2, p number, v varchar2) is
begin fstub.props('LOV ' || upper(l) || '#' || p) := v; end;""",
    """create or replace procedure set_lov_column_property(l varchar2, c number, p number, v varchar2) is
begin fstub.props('LOV ' || upper(l) || '.' || c || '#' || p) := v; end;""",
    """create or replace procedure set_block_property(b varchar2, p number, v varchar2) is
begin fstub.props('BLOCK ' || upper(b) || '#' || p) := v; end;""",
    "create or replace procedure go_block(b varchar2) is begin fstub.block := upper(b); end;",
    """create or replace procedure execute_query is
  w varchar2(4000);
begin
  if fstub.props.exists('BLOCK ' || fstub.block || '#4') then w := fstub.props('BLOCK ' || fstub.block || '#4'); end if;
  fstub.queries := fstub.queries || fstub.block || ':' || w || ';';
end;""",
    "create or replace procedure forms_ddl(p varchar2) is begin execute immediate p; end;",
    "create or replace procedure call_form(f varchar2) is begin fstub.props('CALL_FORM') := f; end;",
    "create or replace procedure do_key(k varchar2) is begin fstub.props('DO_KEY') := k; end;",
    "create or replace function lov_name return number is begin return 9; end;",
    """create or replace function get_item_property(i varchar2, p number) return varchar2 is
begin if fstub.props.exists(upper(i) || '#' || p) then return fstub.props(upper(i) || '#' || p); end if; return null; end;""",
    "create or replace function status return number is begin return 7; end;",
    "create or replace function query_status return number is begin return 8; end;",
    """create or replace procedure set_record_property(r number, b varchar2, p number, v number) is
begin fstub.props('RECORD ' || upper(b) || '#' || p) := v; end;""",
    "create or replace procedure new_form(f varchar2) is begin fstub.props('NEW_FORM') := f; end;",
    """create or replace procedure set_menu_item_property(m varchar2, p number, v varchar2) is
begin fstub.props('MENU ' || upper(m) || '#' || p) := v; end;""",
    "create or replace procedure exit_form is begin fstub.props('EXIT_FORM') := 'Y'; end;",
    """create or replace function show_lov(l varchar2) return boolean is
begin
  if fstub.lov_answer then fstub.items('CTL.FIND_ID') := fstub.lov_id; end if;
  return fstub.lov_answer;
end;""",
]
DROP = ['package ui', 'function lov_name', 'function get_item_property', 'function status', 'function query_status', 'procedure set_record_property',
        'procedure do_key', 'procedure new_form', 'procedure set_menu_item_property', 'procedure call_form', 'procedure exit_form', 'procedure forms_ddl', 'function show_lov', 'procedure execute_query', 'procedure go_block',
        'procedure set_block_property', 'procedure set_lov_column_property', 'procedure set_lov_property',
        'procedure set_item_property', 'procedure set_window_property', 'function default_where', 'function format_mask',
        'function prompt_text', 'function label', 'function title', 'procedure message', 'procedure copy',
        'function name_in', 'package fstub']


def xml_of(name):
    return ET.fromstring(BUILT[name][0])


# -- the XML, without a database ---------------------------------------------------------------

@pytest.mark.parametrize('name', list(BUILT))
def test_xml_ascii_and_references(name):
    xml = BUILT[name][0]
    assert all(ord(c) < 128 for c in xml)
    # what the schema of XML2Forms 14.1.2 refused (XML-24535, XML-24523)
    assert 'DMLDataTargetName' not in xml and 'ColumnDataType="Char"' not in xml
    root = xml_of(name)
    items = {'%s.%s' % (b.get('Name'), i.get('Name'))
             for b in root.iter('{%s}Block' % NS['f']) for i in b.findall('f:Item', NS)}
    lovs = {lv.get('Name'): lv for lv in root.iter('{%s}LOV' % NS['f'])}
    groups = {g.get('Name') for g in root.iter('{%s}RecordGroup' % NS['f'])}
    for b in root.iter('{%s}Block' % NS['f']):
        for i in b.findall('f:Item', NS):
            if i.get('LovName'):
                assert i.get('LovName') in lovs, i.get('Name')
    for lv in lovs.values():
        assert lv.get('RecordGroupName') in groups
        for m in lv.findall('f:LOVColumnMapping', NS):
            if m.get('ReturnItem'):
                assert m.get('ReturnItem') in items, m.get('ReturnItem')
    assert 'LOV_FIND' in lovs or name in ('MM_MAIN', 'MM_LEDGER')   # the menu, the ledgers (lists) find nothing


BUILTINS = ('NAME_IN', 'COPY', 'SHOW_LOV', 'GO_BLOCK', 'EXECUTE_QUERY', 'MESSAGE', 'TX')


@pytest.mark.parametrize('name', list(BUILT))
def test_no_forms_builtins_in_sql(name):
    """frmcmp: "function 'NAME_IN' may not be used in SQL" (PL/SQL 231). The stubs of the database
    are ordinary functions, so the compile in the database does not see it: a check of the text."""
    import re
    body = re.sub(r'--[^\n]*', '', BUILT[name][2]).upper()     # without the comments
    for stmt in re.findall(r'\b(?:SELECT|INSERT|UPDATE|DELETE|MERGE)\b[^;]*;', body):
        for b in BUILTINS:
            assert not re.search(r'\b%s\s*\(' % b, stmt), '%s in SQL: %s' % (b, stmt[:120])


@pytest.mark.parametrize('name', list(BUILT))
def test_plsql_of_the_forms(name):
    """what the database takes and the PL/SQL of the Forms does not (frmcmp on Windows): a SELECT
    inside an expression (PL/SQL 103 at "(SELECT ... ),"), ANSI joins, a unit named like a keyword"""
    import re
    body = re.sub(r'--[^\n]*', '', BUILT[name][2]).upper()
    assert not re.search(r'\(\s*SELECT\b', body), 'a SELECT inside an expression'
    assert not re.search(r'\b(LEFT|RIGHT|FULL|INNER|CROSS)\s+(OUTER\s+)?JOIN\b|\bJOIN\b', body), 'an ANSI join'
    assert not re.search(r'\b(FUNCTION|PROCEDURE)\s+(DAY|MONTH|YEAR|DATE|LEVEL|SIZE|MODE)\b', body)


def test_items_form_stock_is_not_a_column():
    items = {i.get('Name'): i for i in xml_of('MM_ITEMS').iter('{%s}Item' % NS['f'])}
    assert items['STOCK'].get('DatabaseItem') == 'false'           # reservable: never written
    assert items['CAT_NAME'].get('LovName') == 'LOV_CAT' and items['CAT_NAME'].get('ValidateFromList') == 'true'
    assert items['ACTIVE'].get('ItemType') == 'Check Box' and items['ACTIVE'].get('InitializeValue') == 'Y'
    assert items['PRICE'].get('FormatMask') == '99G990D00'        # 0,45 and 4,60


# -- in the database ---------------------------------------------------------------------------

needs_db = pytest.mark.skipif(not DSN, reason='MM_DSN not set (user/password@host:port/service)')


@pytest.fixture(scope='module')
def cur():
    user, rest = DSN.split('/', 1)
    pw, where = rest.rsplit('@', 1)
    conn = oracledb.connect(user=user, password=pw, dsn=where)
    c = conn.cursor()
    for s in STUBS:
        c.execute(s)
    yield c
    conn.rollback()
    for d in DROP:
        try:
            c.execute('drop ' + d)
        except oracledb.DatabaseError:
            pass
    conn.close()


def compile_ui(cur, name):
    """UI of the form, as the form has it; FORM_TRIGGER_FAILURE (a built-in of the Forms) declared"""
    _, spec, body = BUILT[name]
    body = body.replace('PACKAGE BODY ui IS', 'PACKAGE BODY ui IS\n  form_trigger_failure EXCEPTION;', 1)
    for src in (spec, body):
        cur.execute('create or replace ' + src)
    cur.execute("select line, text from user_errors where name = 'UI' order by sequence")
    errors = cur.fetchall()
    assert not errors, errors


def run(cur, plsql, **items):
    cur.execute('begin fstub.clear; end;')
    for k, v in items.items():
        cur.execute('begin fstub.items(:k) := :v; end;', k=k.replace('__', '.'), v=v)
    cur.execute('begin %s end;' % plsql)


def item(cur, name):
    return cur.callfunc('name_in', str, [name])


def prop(cur, key):
    v = cur.var(str, 4000)
    cur.execute("begin if fstub.props.exists(:k) then :v := fstub.props(:k); end if; end;", k=key, v=v)
    return v.getvalue()


def fails(cur, plsql, **items):
    with pytest.raises(oracledb.DatabaseError) as e:
        run(cur, plsql, **items)
    assert 'ORA-06510' in str(e.value)        # the user-defined exception: form_trigger_failure
    return msgs(cur)


def msgs(cur):
    v = cur.var(str, 32767)
    cur.execute('begin :v := fstub.msgs; end;', v=v)
    return v.getvalue() or ''


@needs_db
def test_mm_text_has_every_word(cur):
    for k, t in WORDS.items():
        assert cur.callfunc('mm_text.t', str, [k]) == t, k


@needs_db
@pytest.mark.parametrize('name', list(BUILT))
def test_record_groups_run(cur, name):
    for g in xml_of(name).iter('{%s}RecordGroup' % NS['f']):
        cur.execute(g.get('RecordGroupQuery'))
        got = [d[0] for d in cur.description]
        want = [c.get('Name') for c in g.findall('f:RecordGroupColumn', NS)]
        assert got == want, g.get('Name')
        assert cur.fetchall(), g.get('Name') + ': no rows (the demo of INSTALL.sql demo)'


@needs_db
def test_items_form(cur):
    compile_ui(cur, 'MM_ITEMS')
    run(cur, 'ui.init;')
    assert prop(cur, 'WINDOW WIN#1') == 'Είδη'
    assert prop(cur, 'ITEM.CAT_NAME#3') == 'Κατηγορία'
    assert prop(cur, 'LOV LOV_CAT#1') == 'Κατηγορίες'
    assert prop(cur, 'LOV LOV_VAT.3#1') == 'Περιγραφή'
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert q.getvalue() == 'ITEM:;'
    # the checks of the items
    run(cur, "ui.validate('ITEM.BARCODE');", ITEM__BARCODE='2000000000015')
    assert 'barcode' in fails(cur, "ui.validate('ITEM.BARCODE');", ITEM__BARCODE='2000000000016')
    assert 'αρνητικός' in fails(cur, "ui.validate('ITEM.PRICE');", ITEM__PRICE='-1')
    run(cur, "ui.validate('ITEM.PRICE');", ITEM__PRICE='1')
    run(cur, "ui.validate('ITEM.BARCODE');")                       # empty: nothing to check
    # the post-query: the category, the VAT rate, the stock
    cur.execute("select id, stock from mm_item where code = 'ART01'")
    iid, stock = cur.fetchone()
    run(cur, "ui.post_query('ITEM');", ITEM__ID=str(iid), SYSTEM__TRIGGER_RECORD='1')
    assert prop(cur, 'RECORD ITEM#7') == '8'           # STATUS = QUERY_STATUS: what it filled is no change
    assert item(cur, 'ITEM.CAT_NAME') == 'Αρτοποιήματα'
    assert float(item(cur, 'ITEM.VAT_RATE')) == 13
    assert float(item(cur, 'ITEM.STOCK')) == float(stock)
    # Find...: the record chosen alone, then the where clause back to nothing
    run(cur, f"fstub.lov_id := '{iid}'; ui.press('CTL.FIND');")
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert q.getvalue() == f'ITEM:id = {iid};'
    assert prop(cur, 'BLOCK ITEM#4') is None                      # '' is NULL in Oracle
    run(cur, "fstub.lov_answer := false; ui.press('CTL.FIND');")    # Esc in the LOV: nothing
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert q.getvalue() is None
    run(cur, "ui.press('CTL.ALL');")
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert q.getvalue() == 'ITEM:;'


@needs_db
@pytest.mark.parametrize('name,one', [('MM_CUSTOMERS', 'Πελάτες'), ('MM_SUPPLIERS', 'Προμηθευτές')])
def test_partner_forms(cur, name, one):
    compile_ui(cur, name)
    run(cur, 'ui.init;')
    assert prop(cur, 'WINDOW WIN#1') == one
    assert prop(cur, 'PARTNER.AFM#3') == 'ΑΦΜ'
    assert prop(cur, 'CTL.FIND#2') == 'Βρες...'
    run(cur, "ui.validate('PARTNER.AFM');", PARTNER__AFM='999000018')
    assert 'ΑΦΜ' in fails(cur, "ui.validate('PARTNER.AFM');", PARTNER__AFM='999000019')
    assert 'email' in fails(cur, "ui.validate('PARTNER.EMAIL');", PARTNER__EMAIL='nobody')
    run(cur, "ui.validate('PARTNER.EMAIL');", PARTNER__EMAIL='a@b.gr')
    run(cur, "ui.post_query('PARTNER');")                            # nothing to fill


@needs_db
def test_error_messages(cur):
    compile_ui(cur, 'MM_ITEMS')
    f = lambda t: cur.callfunc('ui.friendly', str, [t])  # noqa: E731
    assert f('ORA-00001: unique constraint (MM.MM_ITEM_CODE_UK) violated') == \
        'Υπάρχει ήδη είδος με αυτόν τον κωδικό'
    assert f('ORA-02292: integrity constraint (MM.MM_DOC_LINE_ITEM_FK) violated - child record found') \
        .startswith('Το είδος έχει παραστατικά')
    assert f('ORA-20112: MM-112: Το ταμείο δεν έχει ανοιχτό Ζ\nORA-06512: at line 1') == \
        'MM-112: Το ταμείο δεν έχει ανοιχτό Ζ'
    assert f('ORA-01400: cannot insert NULL') == 'ORA-01400: cannot insert NULL'
    run(cur, "ui.on_error(40508, 'FRM', 'ORACLE error: unable to INSERT record.', "
             "'ORA-00001: unique constraint (MM.MM_ITEM_BARCODE_UK) violated');")
    assert msgs(cur) == 'Υπάρχει ήδη είδος με αυτό το barcode\n'
    run(cur, "ui.on_error(40100, 'FRM', 'At first record.', null);")
    assert msgs(cur) == 'FRM-40100: At first record.\n'


# -- the forms of the cards and of the reservations: the buttons, against MM_CORE (they commit) --------

def test_cards_and_reservations_forms_shape():
    root = xml_of('MM_CARDS')
    blocks = {b.get('Name'): b for b in root.iter('{%s}Block' % NS['f'])}
    assert blocks['CARD'].get('WhereClause') == "serial_tracked = 'Y'"
    assert blocks['SER'].get('WhereClause') == 'item_id = :CARD.ID'
    assert blocks['SER'].get('UpdateAllowed') == 'false'
    items = {i.get('Name'): i for i in blocks['CTL'].findall('f:Item', NS)}
    assert items['NEW_PIN'].get('ConcealData') == 'true'                     # dots, not the PIN
    trig = [t.get('Name') for t in blocks['CARD'].findall('f:Trigger', NS)]
    assert 'WHEN-NEW-RECORD-INSTANCE' in trig
    res = {b.get('Name'): b for b in xml_of('MM_RESERVATIONS').iter('{%s}Block' % NS['f'])}
    assert res['RL'].get('WhereClause') == 'reservation_id = :RES.ID'


@needs_db
def test_cards_form(cur, env):
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, serial_tracked) "
                   "values (:c, 'Test card form', :cat, 'A', 5, 'Y')", c=f"TST{ids['tag']}F", cat=cat)
    db.cur.execute("insert into mm_pin_user (username) values ('TSTFORMS')")
    db.commit()
    card = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}F")[0]
    compile_ui(cur, 'MM_CARDS')
    run(cur, 'ui.init;')
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert q.getvalue() == "CARD:serial_tracked = 'Y';"
    serial = f"FRM-{ids['tag']}-1"
    run(cur, "ui.press('CTL.LOAD');", CARD__ID=str(card), CTL__NEW_SERIAL=serial, CTL__NEW_PIN='123456')
    assert 'φορτώθηκε' in msgs(cur)
    assert item(cur, 'CTL.NEW_SERIAL') is None and item(cur, 'CTL.NEW_PIN') is None
    assert item(cur, 'CARD.STOCK') == '1'
    sid = db.one('select id from mm_serial where serial = :s', s=serial)[0]   # committed: the other session sees it
    run(cur, "ui.press('CTL.LOAD');", CARD__ID=str(card), CTL__NEW_SERIAL=serial, CTL__NEW_PIN='1')
    assert 'MM-136' in msgs(cur) or 'MM-135' in msgs(cur)                   # twice: a message, no failure
    run(cur, "ui.press('CTL.PIN');", SER__ID=str(sid), CTL__USERNAME='TSTFORMS')
    assert item(cur, 'SER.PIN_SHOW') == '123456'
    run(cur, "ui.press('CTL.PIN');", SER__ID=str(sid), CTL__USERNAME='NOBODY')
    assert 'MM-143' in msgs(cur) and item(cur, 'SER.PIN_SHOW') is None
    # the detail once for each master record
    run(cur, "ui.master('CARD');", CARD__ID=str(card))
    cur.execute('begin :v := fstub.queries; ui.master(\'CARD\'); :w := fstub.queries; end;',
                v=(a := cur.var(str)), w=(b := cur.var(str)))
    assert a.getvalue() == 'SER:;' and b.getvalue() == 'SER:;'


@needs_db
def test_reservations_form(cur, env):
    db, ids = env
    if not db.fn('open_z_of', int, ids['reg']):
        db.fn('open_z', int, ids['reg'])
        db.commit()
    compile_ui(cur, 'MM_RESERVATIONS')
    today = __import__('datetime').date.today().strftime('%d/%m/%Y')
    run(cur, "ui.press('CTL.NEWRES');", CTL__R_NAME='Test Φόρμα', CTL__R_PHONE='6912345678', CTL__R_DATE=today)
    r = db.one("select max(id) from mm_reservation where name = 'Test Φόρμα'")[0]
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert r and f'RES:id = {r};' in q.getvalue()                            # the new one alone
    run(cur, "ui.press('CTL.RESERVE');", RES__ID=str(r), CTL__ITEM_ID=str(ids['b']), CTL__QTY='2')
    assert float(db.one('select qty from mm_reservation_line where reservation_id = :r', r=r)[0]) == 2
    run(cur, "ui.press('CTL.DEPOSIT');", RES__ID=str(r), CTL__AMOUNT='1', CTL__PAY='CASH', CTL__REG_CODE='TST')
    assert float(db.one('select deposit from mm_reservation where id = :r', r=r)[0]) == 1
    assert 'NOWHERE' not in msgs(cur)
    fails(cur, "ui.press('CTL.DEPOSIT');", RES__ID=str(r), CTL__AMOUNT='1', CTL__REG_CODE='NOWHERE')
    run(cur, "ui.press('CTL.DELIVER');", RES__ID=str(r), CTL__PAY='CASH', CTL__REG_CODE='TST')
    status, doc = db.one('select status, doc_id from mm_reservation where id = :r', r=r)
    assert status == 'D' and db.one('select status from mm_doc where id = :d', d=doc)[0] == 'P'
    assert 'απόδειξη' in msgs(cur)
    run(cur, "ui.post_query('RL');", RL__ITEM_ID=str(ids['b']))
    assert item(cur, 'RL.ITEM_TEXT').startswith(f"TST{ids['tag']}B ")


@needs_db
def test_kits_form(cur, env):
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price) "
                   "values (:c, 'Test basket form', :cat, 'A', 9)", c=f"TST{ids['tag']}W", cat=cat)
    db.commit()
    kit = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}W")[0]
    compile_ui(cur, 'MM_KITS')
    run(cur, 'ui.init;')
    run(cur, "ui.press('CTL.ADDCOMP');", CTL__NEWKIT_ID=str(kit), CTL__COMP_ID=str(ids['a']), CTL__COMP_QTY='1')
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert f'KIT:id = {kit};' in q.getvalue() and item(cur, 'CTL.NEWKIT_ID') is None
    run(cur, "ui.press('CTL.ADDCOMP');", KIT__ID=str(kit), CTL__COMP_ID=str(ids['b']), CTL__COMP_QTY='2')
    assert db.one('select kit from mm_item where id = :k', k=kit)[0] == 'Y'
    assert db.one('select count(*) from mm_kit_component where kit_id = :k', k=kit)[0] == 2
    s = db.stock(kit)
    run(cur, "ui.press('CTL.ASSEMBLE');", KIT__ID=str(kit), CTL__ASM_QTY='1')
    assert db.stock(kit) == s + 1
    run(cur, "ui.post_query('KIT');", KIT__ID=str(kit))
    assert float(item(cur, 'KIT.STOCK')) == s + 1 and item(cur, 'KIT.CAN_MAKE') is not None
    run(cur, "ui.post_query('KC');", KC__COMPONENT_ID=str(ids['b']))
    assert item(cur, 'KC.COMP_TEXT').startswith(f"TST{ids['tag']}B ")
    run(cur, "ui.press('CTL.ADDCOMP');", KIT__ID=str(kit), CTL__COMP_ID=str(kit), CTL__COMP_QTY='1')
    assert 'MM-155' in msgs(cur)                                              # itself: a message


@needs_db
def test_promos_form(cur, env):
    db, ids = env
    compile_ui(cur, 'MM_PROMOS')
    run(cur, 'ui.init;')
    today = __import__('datetime').date.today().strftime('%d/%m/%Y')
    assert item(cur, 'CTL.P_FROM') == today and item(cur, 'CTL.P_TO') == today   # ui.init: today
    run(cur, "ui.press('CTL.NEWPROMO');", CTL__P_NAME='Test form promo', CTL__P_KIND='PCT',
        CTL__P_FROM=today, CTL__P_TO=today, CTL__P_PCT='10')
    p = db.one("select id from mm_promo where name = 'Test form promo'")[0]
    run(cur, "ui.press('CTL.ADDPI');", PROMO__ID=str(p), CTL__PI_ITEM_ID=str(ids['a']), CTL__PI_QTY='1')
    assert db.one('select item_id from mm_promo_item where promo_id = :p', p=p)[0] == ids['a']
    assert item(cur, 'CTL.PI_ITEM_ID') is None
    run(cur, "ui.press('CTL.TOGGLE');", PROMO__ID=str(p), PROMO__ACTIVE='Y')
    assert db.one('select active from mm_promo where id = :p', p=p)[0] == 'N'
    run(cur, "ui.post_query('PI');", PI__ITEM_ID=str(ids['a']))
    assert item(cur, 'PI.TEXT').startswith(f"TST{ids['tag']}A ")
    cat = db.one('select min(id) from mm_category')[0]
    run(cur, "ui.post_query('PI');", PI__CATEGORY_ID=str(cat))
    assert item(cur, 'PI.TEXT') == db.one('select name from mm_category where id = :c', c=cat)[0]
    run(cur, "ui.press('CTL.NEWPROMO');", CTL__P_NAME='Test form promo 2', CTL__P_KIND='PCT',
        CTL__P_FROM=today, CTL__P_TO=today)
    assert 'MM-158' in msgs(cur)                                              # no %


@needs_db
def test_variants_form(cur, env):
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price) "
                   "values (:c, 'Test jacket', :cat, 'A', 40)", c=f"TST{ids['tag']}V", cat=cat)
    db.commit()
    model = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}V")[0]
    black = db.one("select id from mm_color where code = 'BLK'")[0]
    m, l_ = (db.one("select id from mm_size where size_group = 'CLOTHES' and code = :z", z=z)[0] for z in ('M', 'L'))
    compile_ui(cur, 'MM_VARIANTS')
    run(cur, 'ui.init;')
    run(cur, "ui.press('CTL.NEWVAR');", CTL__NEWMODEL_ID=str(model), CTL__V_COLOR_ID=str(black),
        CTL__V_SIZE_ID=str(m))
    assert db.one('select is_model from mm_item where id = :m', m=model)[0] == 'Y'
    run(cur, "ui.press('CTL.NEWVAR');", MODEL__ID=str(model), CTL__V_COLOR_ID=str(black), CTL__V_SIZE_ID=str(l_),
        CTL__V_BARCODE='')
    assert db.one('select count(*) from mm_item where parent_id = :m', m=model)[0] == 2
    run(cur, "ui.press('CTL.MPRICE');", MODEL__ID=str(model), CTL__M_PRICE='30')
    assert db.one('select count(*) from mm_item where parent_id = :m and price = 30', m=model)[0] == 2
    v = db.one('select min(id) from mm_item where parent_id = :m', m=model)[0]
    run(cur, "ui.post_query('VG');", VG__ID=str(v))
    assert item(cur, 'VG.COLOR_TEXT') == 'Μαύρο' and item(cur, 'VG.SIZE_TEXT') in ('M', 'L')
    assert item(cur, 'VG.STOCK') == '0'
    run(cur, "ui.press('CTL.NEWVAR');", MODEL__ID=str(model), CTL__V_COLOR_ID=str(black), CTL__V_SIZE_ID=str(m))
    assert 'MM-165' in msgs(cur)                                              # twice: a message


def test_menu_shape():
    """the menu: no block of a table, a button for each of the other forms, and the exit"""
    root = xml_of('MM_MAIN')
    blocks = [b.get('Name') for b in root.iter('{%s}Block' % NS['f'])]
    assert blocks == ['CTL', 'TB']                                           # and the toolbar
    buttons = [i.get('Name') for i in root.iter('{%s}Item' % NS['f'])]
    forms = {b[3:] for b in buttons if b.startswith('GO_')}
    assert forms == set(BUILT) - {'MM_MAIN'}
    assert 'EXIT' in buttons


@needs_db
def test_menu_form(cur):
    compile_ui(cur, 'MM_MAIN')
    run(cur, 'ui.init;')
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert q.getvalue() is None                                               # nothing to query
    assert prop(cur, 'WINDOW WIN#1') == 'Mini market'
    assert prop(cur, 'CTL.GO_MM_KITS#2') == 'Καλάθια και σετ'
    run(cur, "ui.press('CTL.GO_MM_RESERVATIONS');")
    assert prop(cur, 'CALL_FORM') == 'MM_RESERVATIONS'
    run(cur, "ui.press('CTL.EXIT');")
    assert prop(cur, 'EXIT_FORM') == 'Y'


def test_pulldown_menu():
    """MM_MENU: every form hangs from it; each item of the bar has its menu; each item opens a form
    that exists (or does a known key)"""
    import re
    menu = ET.fromstring(mkforms.menu_xml())
    assert all(ord(c) < 128 for c in mkforms.menu_xml())
    mm = menu.find('f:MenuModule', NS)
    menus = {m.get('Name'): m for m in mm.findall('f:Menu', NS)}
    assert mm.get('MainMenu') in menus
    for it in menus['MAIN_MENU'].findall('f:MenuItem', NS):
        assert it.get('CommandType') == 'Menu' and it.get('SubMenuName') in menus
    opened = set()
    for name, m in menus.items():
        if name == 'MAIN_MENU':
            continue
        for it in m.findall('f:MenuItem', NS):
            code = it.get('MenuItemCode')
            assert it.get('CommandType') == 'PL/SQL' and code.endswith(';')
            opened |= set(re.findall(r"new_form\('(\w+)'\)", code))
            assert re.fullmatch(r"(new_form\('\w+'\)|do_key\('\w+'\));", code), code
    assert opened == set(BUILT)                                             # every form, once
    for name in BUILT:
        assert xml_of(name).find('f:FormModule', NS).get('MenuModule') == 'MM_MENU'


@needs_db
def test_menu_labels_in_greek(cur):
    compile_ui(cur, 'MM_ITEMS')
    run(cur, 'ui.init;')
    assert prop(cur, 'MENU MAIN_MENU.SALES#2') == 'Πωλήσεις'
    assert prop(cur, 'MENU STOCK_MENU.VARIANTS#2') == 'Ρούχα και παπούτσια'


def test_toolbar_shape():
    """every form: the block TB on a horizontal toolbar canvas of its window; its buttons do not
    take the cursor"""
    for name in BUILT:
        root = xml_of(name)
        canv = {c.get('Name'): c for c in root.iter('{%s}Canvas' % NS['f'])}
        assert canv['TBC'].get('CanvasType') == 'Horizontal Toolbar'
        win = root.find('.//f:Window', NS)
        assert win.get('HorizontalToolbarCanvasName') == 'TBC'
        tb = [b for b in root.iter('{%s}Block' % NS['f']) if b.get('Name') == 'TB'][0]
        items = tb.findall('f:Item', NS)
        assert [i.get('Name') for i in items] == [t[0] for t in mkforms.TOOLBAR]
        assert all(i.get('MouseNavigate') == 'false' and i.get('CanvasName') == 'TBC' for i in items)


@needs_db
def test_toolbar(cur):
    compile_ui(cur, 'MM_ITEMS')
    run(cur, 'ui.init;')
    assert prop(cur, 'TB.T_SAVE#2') == 'Αποθήκευση'
    for button, key in (('T_SAVE', 'COMMIT_FORM'), ('T_ENTERQ', 'ENTER_QUERY'), ('T_EXECQ', 'EXECUTE_QUERY'),
                        ('T_NEW', 'CREATE_RECORD'), ('T_DEL', 'DELETE_RECORD'), ('T_LOV', 'LIST_VALUES'),
                        ('T_PREV', 'PREVIOUS_RECORD'),
                        ('T_NEXT', 'NEXT_RECORD'), ('T_EXIT', 'EXIT_FORM')):
        run(cur, f"ui.tool('TB.{button}');")
        assert prop(cur, 'DO_KEY') == key, button
    run(cur, "ui.tool('TB.T_MAIN');")
    assert prop(cur, 'NEW_FORM') == 'MM_MAIN'


@needs_db
def test_invoices_form(cur, env):
    """a wholesale invoice: new, a line at the wholesale price, cards with their serials, post,
    a credit note (draft, then deleted), cancel"""
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("update mm_item set wholesale_price = 1.5 where id = :i", i=ids['b'])
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, serial_tracked) "
                   "values (:c, 'Test card inv', :cat, 'A', 10, 'Y')", c=f"TST{ids['tag']}I", cat=cat)
    card = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}I")[0]
    for k in range(3):
        db.fn('load_serial', int, card, f"INV-{ids['tag']}-{k}", '1234')
    db.commit()
    compile_ui(cur, 'MM_INVOICES')
    run(cur, 'ui.init;')
    today = __import__('datetime').date.today().strftime('%d/%m/%Y')
    assert item(cur, 'CTL.D_DATE') == today
    run(cur, "ui.press('CTL.NEWDOC');", CTL__D_TYPE='TPY', CTL__CUST_ID=str(ids['customer']),
        CTL__D_PAY='CREDIT', CTL__D_DATE=today)
    d = db.one('select max(id) from mm_doc where customer_id = :c', c=ids['customer'])[0]
    cur.execute('begin :v := fstub.queries; end;', v=(q := cur.var(str)))
    assert f'DOC:id = {d};' in q.getvalue()
    run(cur, "ui.press('CTL.ADDLINE');", DOC__ID=str(d), CTL__L_ITEM_ID=str(ids['b']), CTL__L_QTY='2')
    assert float(db.one('select price from mm_doc_line where doc_id = :d and item_id = :i', d=d, i=ids['b'])[0]) == 1.5
    run(cur, "ui.press('CTL.ADDLINE');", DOC__ID=str(d), CTL__L_ITEM_ID=str(card), CTL__L_QTY='2')
    assert db.one('select count(*) from mm_serial where out_doc_id = :d', d=d)[0] == 2   # their serials
    run(cur, "ui.press('CTL.POSTDOC');", DOC__ID=str(d))
    assert 'αριθμό' in msgs(cur)
    assert db.one('select status from mm_doc where id = :d', d=d)[0] == 'P'
    run(cur, "ui.post_query('DOC');", DOC__CUSTOMER_ID=str(ids['customer']))
    assert item(cur, 'DOC.PARTNER_TEXT') == db.one('select name from mm_customer where id = :c', c=ids['customer'])[0]
    run(cur, "ui.post_query('DL');", DL__ITEM_ID=str(ids['b']))
    assert item(cur, 'DL.ITEM_TEXT').startswith(f"TST{ids['tag']}B ")
    run(cur, "ui.press('CTL.CREDIT');", DOC__ID=str(d))
    assert 'MM-129' in msgs(cur)                                              # cards: no credit note
    run(cur, "ui.press('CTL.CANCELDOC');", DOC__ID=str(d))
    assert db.one('select status from mm_doc where id = :d', d=d)[0] == 'C'
    # an invoice without cards: its credit note, a draft, deleted
    run(cur, "ui.press('CTL.NEWDOC');", CTL__D_TYPE='TPY', CTL__CUST_ID=str(ids['customer']), CTL__D_DATE=today)
    d2 = db.one('select max(id) from mm_doc where customer_id = :c', c=ids['customer'])[0]
    run(cur, "ui.press('CTL.ADDLINE');", DOC__ID=str(d2), CTL__L_ITEM_ID=str(ids['b']), CTL__L_QTY='1',
        CTL__L_PRICE='3', CTL__L_DISC='10')
    assert float(db.one('select price from mm_doc_line where doc_id = :d', d=d2)[0]) == 3
    run(cur, "ui.press('CTL.POSTDOC');", DOC__ID=str(d2))
    run(cur, "ui.press('CTL.CREDIT');", DOC__ID=str(d2))
    c = db.one("select id from mm_doc where ref_doc_id = :d", d=d2)[0]
    assert db.one('select doc_type, status from mm_doc where id = :c', c=c) == ('PPY', 'D')
    run(cur, "ui.press('CTL.DELDOC');", DOC__ID=str(c))
    assert db.one('select count(*) from mm_doc where id = :c', c=c)[0] == 0
    db.cur.execute("update mm_item set wholesale_price = null where id = :i", i=ids['b'])
    db.commit()


@needs_db
def test_lists_and_defaults(cur):
    """a double click opens the list of an item that has one; the defaults of CTL from ui.init"""
    compile_ui(cur, 'MM_INVOICES')
    run(cur, 'ui.init;')
    assert item(cur, 'CTL.D_TYPE') == 'TPY' and item(cur, 'CTL.D_PAY') == 'CREDIT' and item(cur, 'CTL.L_QTY') == '1'
    run(cur, "fstub.props('CTL.CUST_TEXT#9') := 'LOV_CUST'; ui.dblclick('CTL.CUST_TEXT');")
    assert prop(cur, 'DO_KEY') == 'LIST_VALUES'
    run(cur, "ui.dblclick('CTL.NEWDOC');")                                   # no list: nothing
    assert prop(cur, 'DO_KEY') is None
    assert 'WHEN-MOUSE-DOUBLECLICK' in [t.get('Name') for t in xml_of('MM_INVOICES').findall('f:FormModule/f:Trigger', NS)]


@needs_db
def test_invoice_serials(cur, env):
    """the serials of a line of cards: a sale takes a card scanned and gives one back; a purchase
    loads its cards with their PINs and is posted; the third level of the form (DL -> DS)"""
    db, ids = env
    cat = db.one('select min(id) from mm_category')[0]
    db.cur.execute("insert into mm_item (code, name, category_id, vat_code, price, serial_tracked) "
                   "values (:c, 'Test card ser', :cat, 'A', 10, 'Y')", c=f"TST{ids['tag']}S", cat=cat)
    card = db.one('select id from mm_item where code = :c', c=f"TST{ids['tag']}S")[0]
    for k in range(3):
        db.fn('load_serial', int, card, f"SER-{ids['tag']}-{k}", '4321')
    db.commit()
    compile_ui(cur, 'MM_INVOICES')
    today = __import__('datetime').date.today().strftime('%d/%m/%Y')
    # a sale: one card automatically, then a scanned one into the same line, then one back
    run(cur, "ui.press('CTL.NEWDOC');", CTL__D_TYPE='TPY', CTL__CUST_ID=str(ids['customer']), CTL__D_DATE=today)
    d = db.one('select max(id) from mm_doc where customer_id = :c', c=ids['customer'])[0]
    run(cur, "ui.press('CTL.ADDLINE');", DOC__ID=str(d), CTL__L_ITEM_ID=str(card), CTL__L_QTY='1')
    line = db.one('select id from mm_doc_line where doc_id = :d', d=d)[0]
    run(cur, "ui.press('CTL.ADDSER');", DOC__ID=str(d), CTL__S_SERIAL=f"SER-{ids['tag']}-2")
    assert 'serial' in msgs(cur)
    assert float(db.one('select qty from mm_doc_line where id = :l', l=line)[0]) == 2
    assert db.one('select out_line_id from mm_serial where serial = :s', s=f"SER-{ids['tag']}-2")[0] == line
    sid = db.one('select id from mm_serial where serial = :s', s=f"SER-{ids['tag']}-2")[0]
    run(cur, "ui.press('CTL.DELSER');", DOC__ID=str(d), DS__ID=str(sid))
    assert db.one('select status from mm_serial where id = :s', s=sid)[0] == 'A'
    assert float(db.one('select qty from mm_doc_line where id = :l', l=line)[0]) == 1
    # the third level: the serials of the line on the screen, once for each line
    cur.execute("begin fstub.clear; fstub.items('DL.ID') := :l; ui.master('DL'); ui.master('DL'); "
                ":q := fstub.queries; end;", l=str(line), q=(q := cur.var(str)))
    assert q.getvalue() == 'DS:;'
    # a purchase: two cards with their PINs, posted
    run(cur, "ui.press('CTL.NEWDOC');", CTL__D_TYPE='TAG', CTL__SUPP_ID=str(ids['supplier']), CTL__D_DATE=today)
    p = db.one('select max(id) from mm_doc where supplier_id = :s', s=ids['supplier'])[0]
    run(cur, "ui.press('CTL.ADDLINE');", DOC__ID=str(p), CTL__L_ITEM_ID=str(card), CTL__L_QTY='2', CTL__L_PRICE='9')
    pl = db.one('select id from mm_doc_line where doc_id = :d', d=p)[0]
    for k in (1, 2):
        run(cur, "ui.press('CTL.ADDSER');", DOC__ID=str(p), DL__ID=str(pl), CTL__S_SERIAL=f"BUY-{ids['tag']}-{k}",
            CTL__S_PIN='55556666')
    assert item(cur, 'CTL.S_PIN') is None                                    # the PIN is not left on the screen
    run(cur, "ui.press('CTL.POSTDOC');", DOC__ID=str(p))
    db.cur.execute("select status from mm_serial where serial like :s", s=f"BUY-{ids['tag']}-%")
    assert [r[0] for r in db.cur] == ['A', 'A']
    run(cur, "ui.press('CTL.ADDSER');", DOC__ID=str(p), DL__ID=str(pl), CTL__S_SERIAL=f"BUY-{ids['tag']}-9")
    assert 'MM-102' in msgs(cur)                                              # posted: no more


@needs_db
def test_payments_form(cur, env):
    db, ids = env
    compile_ui(cur, 'MM_PAYMENTS')
    run(cur, 'ui.init;')
    assert item(cur, 'CTL.P_KIND') == 'R' and item(cur, 'CTL.P_METHOD') == 'CASH'
    today = __import__('datetime').date.today().strftime('%d/%m/%Y')
    run(cur, "ui.press('CTL.NEWPAY');", CTL__P_KIND='R', CTL__CUST_ID=str(ids['customer']), CTL__P_AMOUNT='12',
        CTL__P_METHOD='BANK', CTL__P_DATE=today, CTL__P_NOTES='Test form')
    r = db.one("select max(id) from mm_payment where customer_id = :c", c=ids['customer'])[0]
    assert db.one('select amount, method, register_id from mm_payment where id = :r', r=r) == (12, 'BANK', None)
    assert item(cur, 'CTL.P_AMOUNT') is None
    run(cur, "ui.press('CTL.NEWPAY');", CTL__P_KIND='P', CTL__SUPP_ID=str(ids['supplier']), CTL__P_AMOUNT='3',
        CTL__P_METHOD='BANK', CTL__P_DATE=today)
    assert db.one("select count(*) from mm_payment where supplier_id = :s", s=ids['supplier'])[0] >= 1
    run(cur, "ui.post_query('PAY');", PAY__CUSTOMER_ID=str(ids['customer']))
    assert item(cur, 'PAY.PARTNER_TEXT') == db.one('select name from mm_customer where id = :c', c=ids['customer'])[0]
    run(cur, "ui.press('CTL.CANCELPAY');", PAY__ID=str(r))
    assert db.one('select status from mm_payment where id = :r', r=r)[0] == 'C'
    run(cur, "ui.press('CTL.NEWPAY');", CTL__P_KIND='R', CTL__P_AMOUNT='5', CTL__P_DATE=today)
    assert 'MM-169' in msgs(cur)                                              # no customer: a message


@needs_db
def test_ledger_form(cur, env):
    db, ids = env
    compile_ui(cur, 'MM_LEDGER')
    run(cur, 'ui.init;')
    import datetime
    today = datetime.date.today()
    assert item(cur, 'CTL.L_FROM') == '01/01/%d' % today.year and item(cur, 'CTL.L_TO') == today.strftime('%d/%m/%Y')
    # a receipt of 7 from the customer today: its ledger has it, after the carry-over
    db.fn('receive', int, ids['customer'], 7, 'BANK')
    db.commit()
    run(cur, "ui.press('CTL.SHOWCUST');", CTL__CUST_ID=str(ids['customer']), CTL__CUST_TEXT='Test',
        CTL__L_FROM='01/01/2000', CTL__L_TO=today.strftime('%d/%m/%Y'))
    assert 'MM-' not in msgs(cur), msgs(cur)
    assert item(cur, 'CTL.O_OPEN') == '0' and float(item(cur, 'CTL.O_CREDIT').replace(',', '.')) >= 7
    assert item(cur, 'CTL.L_TITLE').startswith('Test: 01/01/2000')
    q = cur.var(str)
    cur.execute('begin :q := fstub.queries; end;', q=q)
    assert q.getvalue() == 'LED:;'
    db.cur.execute("select count(*) from mm_ledger_row")       # (another session: its own rows, none)
    assert db.cur.fetchone()[0] == 0
    cur.execute("select credit from mm_ledger_row where kind = 'M' and credit is not null")
    assert 7 in [float(c) for (c,) in cur.fetchall()]
    assert prop(cur, 'LED.DEBIT#3') == 'Χρέωση'
    # an item: in and out, its stock
    run(cur, "ui.press('CTL.SHOWITEM');", CTL__ITEM_ID=str(ids['a']), CTL__ITEM_TEXT='a',
        CTL__L_FROM='01/01/2000', CTL__L_TO=today.strftime('%d/%m/%Y'))
    assert float(item(cur, 'CTL.O_CLOSE').replace(',', '.')) == db.stock(ids['a'])
    assert prop(cur, 'LED.DEBIT#3') == 'Εισαγωγή'
    # no supplier chosen: a message
    run(cur, "ui.press('CTL.SHOWSUPP');", CTL__L_FROM='01/01/2000', CTL__L_TO='01/01/2001')
    assert 'MM-171' in msgs(cur)
    run(cur, "ui.press('CTL.SHOWSUPP');", CTL__SUPP_ID=str(ids['supplier']), CTL__L_FROM='02/01/2001', CTL__L_TO='01/01/2001')
    assert 'MM-172' in msgs(cur)
