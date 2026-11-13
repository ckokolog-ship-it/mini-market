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
    """create or replace function show_lov(l varchar2) return boolean is
begin
  if fstub.lov_answer then fstub.items('CTL.FIND_ID') := fstub.lov_id; end if;
  return fstub.lov_answer;
end;""",
]
DROP = ['package ui', 'function show_lov', 'procedure execute_query', 'procedure go_block',
        'procedure set_block_property', 'procedure set_lov_column_property', 'procedure set_lov_property',
        'procedure set_item_property', 'procedure set_window_property', 'function default_where',
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
    assert 'LOV_FIND' in lovs


def test_items_form_stock_is_not_a_column():
    items = {i.get('Name'): i for i in xml_of('MM_ITEMS').iter('{%s}Item' % NS['f'])}
    assert items['STOCK'].get('DatabaseItem') == 'false'           # reservable: never written
    assert items['CAT_NAME'].get('LovName') == 'LOV_CAT' and items['CAT_NAME'].get('ValidateFromList') == 'true'
    assert items['ACTIVE'].get('ItemType') == 'Check Box' and items['ACTIVE'].get('InitializeValue') == 'Y'


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
    run(cur, "ui.post_query('ITEM');", ITEM__ID=str(iid))
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
