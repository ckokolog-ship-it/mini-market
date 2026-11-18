"""mkdocs.py -- the reference of the mini market, made from the code and the database itself, so it never
goes out of date:

    docs/ANAFORA_VASIS.md        the database: every table (its columns, keys, checks, what each is), view,
                                 package (its specification, as it is written), trigger, sequence of the
                                 errors MM-1xx, kinds of documents
    docs/ANAFORA_EFARMOGIS.md    the application: the REST service (every call), the screens of the menu
                                 (page, form, fields, actions, the rights of the roles of the system), the
                                 Oracle Forms, the Oracle Reports, the tests

The descriptions are the comments of the source (db/*.sql: the lines -- above a table, a view, a trigger;
those beside a column); the columns, keys and checks are read from the database (after INSTALL.sql).

    MM_DSN=mm/<password>@localhost:1521/FREEPDB1 python3 tools/mkdocs.py
"""
import ast
import datetime
import glob
import importlib.util
import os
import re
import sys

import oracledb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkdocs_el as EL  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DB = os.path.join(ROOT, 'db')
DOCS = os.path.join(ROOT, 'docs')
# the scripts of the installation, in the order INSTALL.sql runs them (the others: demo, tools)
SOURCES = ['MM_TABLES.sql', 'MM_BASE.sql', 'MM_PIN.sql', 'MM_CORE.sql', 'MM_LEDGER.sql', 'MM_REPORT.sql',
           'MM_AUTH.sql', 'MM_RIGHTS.sql', 'MM_MONTHS.sql', 'MM_TEXT.sql', 'MM_AUDIT.sql']


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def comment_above(lines, i):
    """the comment lines (--) right above line i, as one text"""
    out = []
    j = i - 1
    while j >= 0 and lines[j].lstrip().startswith('--'):
        out.insert(0, lines[j].strip()[2:].strip())
        j -= 1
    return ' '.join(x for x in out if x)


def scan_sources():
    """from the SQL: the comment of each table, view, trigger, sequence of a package, its file; the comments
    beside the columns"""
    objs, cols = {}, {}
    for name in SOURCES:
        lines = read(os.path.join(DB, name)).split('\n')
        table = None
        for i, line in enumerate(lines):
            m = re.match(r'\s*create (?:or replace )?(table|view|trigger|package)(?: if not exists)?\s+(\w+)', line, re.I)
            if m and not re.match(r'\s*create or replace package body', line, re.I):
                kind, obj = m.group(1).lower(), m.group(2).upper()
                if obj not in objs or not objs[obj][1]:
                    objs[obj] = (kind, comment_above(lines, i), name)
                table = obj if kind == 'table' else None
                continue
            if table:
                if re.match(r'\s*\);', line):
                    table = None
                    continue
                c = re.match(r'\s+(\w+)\s+\w+.*?--\s*(.+)$', line)
                if c and c.group(1).lower() not in ('constraint', 'primary', 'foreign', 'unique', 'check'):
                    cols[(table, c.group(1).upper())] = c.group(2).strip()
            # a column added later: add_col('TABLE', 'COLUMN', ...) with its comment above
            a = re.search(r"add_col\('(\w+)',\s*'(\w+)'", line)
            if a:
                cols.setdefault((a.group(1).upper(), a.group(2).upper()), comment_above(lines, i))
    return objs, cols


def package_specs():
    """the specification of each package, as written (its comments: what each call does)"""
    out = {}
    for name in SOURCES:
        src = read(os.path.join(DB, name))
        for m in re.finditer(r'create or replace package (\w+) as\n(.*?)\nend \1;', src, re.I | re.S):
            out[m.group(1).upper()] = (name, m.group(2).rstrip())
    return out


def errors():
    """the errors MM-1xx: fail(n, 'text') of the packages (the text up to its first concatenation)"""
    out = {}
    for path in sorted(glob.glob(os.path.join(DB, '*.sql'))):
        src = read(path)
        for m in re.finditer(r"fail\((\d+),\s*'((?:[^']|'')*)'", src):
            code = 100 + int(m.group(1))
            text = m.group(2).replace("''", "'").strip()
            out.setdefault(code, [])
            if text and text not in out[code]:
                out[code].append(text)
        for m in re.finditer(r"raise_application_error\(-20(\d{3}),\s*'MM-\d+: ((?:[^']|'')*)'", src):
            out.setdefault(int(m.group(1)) - 100 + 100, []).append(m.group(2))
    return dict(sorted(out.items()))


def data_type(r):
    t, length, prec, scale = r['DATA_TYPE'], r['DATA_LENGTH'], r['DATA_PRECISION'], r['DATA_SCALE']
    if t in ('VARCHAR2', 'CHAR', 'RAW'):
        return '%s(%d)' % (t, r['CHAR_LENGTH'] or length)
    if t == 'NUMBER' and prec:
        return 'NUMBER(%d%s)' % (prec, ',%d' % scale if scale else '')
    return t


def rows(cur, sql, **b):
    cur.execute(sql, **b)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur]


def md(text):
    return (text or '').replace('|', '\\|').replace('\n', ' ')


def db_doc(cur):
    objs, colnotes = scan_sources()
    specs = package_specs()
    out = ['# Αναφορά της βάσης',
           '',
           'Φτιάχνεται αυτόματα από τη βάση και τα σχόλια του κώδικα (`tools/mkdocs.py`). Μην την αλλάζεις με το '
           'χέρι: άλλαξε το σχόλιο στο `db/*.sql` και τρέξε ξανά το script. Πώς στήνεται η βάση: '
           '[ODIGIES_VASI.md](ODIGIES_VASI.md)· η αρχιτεκτονική: [ARXITEKTONIKI.md](ARXITEKTONIKI.md).',
           '']
    tables = rows(cur, "select table_name from user_tables where table_name like 'MM\\_%' escape '\\' order by 1")
    views = rows(cur, "select view_name from user_views where view_name like 'MM\\_%' escape '\\' order by 1")
    packages = rows(cur, "select object_name from user_objects where object_type = 'PACKAGE' "
                         "and object_name like 'MM\\_%' escape '\\' order by 1")
    triggers = rows(cur, "select trigger_name, table_name, triggering_event, trigger_type from user_triggers "
                         "where trigger_name like 'MM\\_%' escape '\\' order by table_name, trigger_name")
    out += ['## Περιεχόμενα', '',
            '- [Πίνακες](#πίνακες) (%d)' % len(tables), '- [Όψεις](#όψεις) (%d)' % len(views),
            '- [Πακέτα](#πακέτα) (%d)' % len(packages), '- [Triggers](#triggers) (%d)' % len(triggers),
            '- [Είδη παραστατικών](#είδη-παραστατικών)', '- [Λάθη MM-1xx](#λάθη-mm-1xx)', '']
    # the tables
    out += ['## Πίνακες', '', '| Πίνακας | Τι κρατά |', '|---|---|']
    for t in tables:
        n = t['TABLE_NAME']
        out.append('| [`%s`](#%s) | %s |' % (n, n.lower(), md(EL.TABLES.get(n) or objs.get(n, ('', ''))[1])))
    out.append('')
    for t in tables:
        n = t['TABLE_NAME']
        kind, note, src = objs.get(n, ('table', '', ''))
        out += ['### %s' % n, '']
        if EL.TABLES.get(n):
            out += [EL.TABLES[n], '']
        if note:
            out += ['> %s' % note, '']
        if src:
            out += ['_Ορίζεται στο `db/%s`._' % src, '']
        cols = rows(cur, """select column_name, data_type, data_length, char_length, data_precision, data_scale,
                                   nullable, data_default, identity_column
                            from user_tab_columns where table_name = :t order by column_id""", t=n)
        pk = {r['COLUMN_NAME'] for r in rows(cur, """select cc.column_name from user_constraints c
                join user_cons_columns cc on cc.constraint_name = c.constraint_name
                where c.table_name = :t and c.constraint_type = 'P'""", t=n)}
        fks = {}
        for r in rows(cur, """select cc.column_name, rc.table_name ref_table, c.delete_rule
                from user_constraints c join user_cons_columns cc on cc.constraint_name = c.constraint_name
                join user_constraints rc on rc.constraint_name = c.r_constraint_name
                where c.table_name = :t and c.constraint_type = 'R'""", t=n):
            fks[r['COLUMN_NAME']] = r['REF_TABLE'] + (' (on delete %s)' % r['DELETE_RULE'].lower()
                                                     if r['DELETE_RULE'] != 'NO ACTION' else '')
        out += ['| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |', '|---|---|---|---|---|---|']
        for c in cols:
            cn = c['COLUMN_NAME']
            key = 'PK' if cn in pk else ''
            if cn in fks:
                key = (key + ' ' if key else '') + 'FK → [`%s`](#%s)' % (fks[cn].split(' ')[0], fks[cn].split(' ')[0].lower()) \
                    + (' ' + ' '.join(fks[cn].split(' ')[1:]) if ' ' in fks[cn] else '')
            dflt = 'identity' if c['IDENTITY_COLUMN'] == 'YES' else (c['DATA_DEFAULT'] or '').strip()
            out.append('| `%s` | %s | %s | %s | %s | %s |' % (
                cn.lower(), data_type(c), 'ναι' if c['NULLABLE'] == 'Y' else 'όχι', md(dflt)[:40] if dflt else '',
                key, md(colnotes.get((n, cn), ''))))
        checks = [r['SEARCH_CONDITION_VC'] for r in rows(cur, """select search_condition_vc from user_constraints
                where table_name = :t and constraint_type = 'C' and generated = 'USER NAME'
                and search_condition_vc not like '%IS NOT NULL' order by constraint_name""", t=n)]
        uks = [r['COLS'] for r in rows(cur, """select listagg(cc.column_name, ', ') within group (order by cc.position) cols
                from user_constraints c join user_cons_columns cc on cc.constraint_name = c.constraint_name
                where c.table_name = :t and c.constraint_type = 'U' group by c.constraint_name""", t=n)]
        if uks or checks:
            out.append('')
        for u in uks:
            out.append('- μοναδικό: `%s`' % u.lower())
        for k in checks:
            out.append('- έλεγχος: `%s`' % ' '.join(k.split()))
        out.append('')
    # the views
    out += ['## Όψεις', '', 'Ό,τι δείχνουν οι σελίδες, οι φόρμες και τα reports βγαίνει από αυτές.', '',
            '| Όψη | Τι δείχνει | Στήλες |', '|---|---|---|']
    for v in views:
        n = v['VIEW_NAME']
        cs = [r['COLUMN_NAME'].lower() for r in rows(cur, 'select column_name from user_tab_columns where table_name = :t '
                                                          'order by column_id', t=n)]
        out.append('| `%s` | %s | %s |' % (n, md(EL.VIEWS.get(n) or objs.get(n, ('', ''))[1]), ', '.join('`%s`' % c for c in cs)))
    out.append('')
    # the packages: their specification, as written
    out += ['## Πακέτα', '',
            'Η προδιαγραφή κάθε πακέτου, όπως είναι γραμμένη στον κώδικα: οι διαδικασίες και οι συναρτήσεις του, '
            'με τα σχόλιά τους. Όλοι οι κανόνες είναι εδώ· οι φόρμες, οι σελίδες και το REST καλούν αυτά.', '']
    for p in packages:
        n = p['OBJECT_NAME']
        src, spec = specs.get(n, ('', ''))
        note = objs.get(n, ('', ''))[1]
        head = read(os.path.join(DB, src)).split('\n') if src else []
        intro = []
        for line in head:                                    # (the comment at the top of its file)
            if not line.startswith('--'):
                break
            intro.append(line[2:].strip())
        out += ['### %s' % n, '']
        if EL.PACKAGES.get(n):
            out += [EL.PACKAGES[n], '']
        if src:
            out += ['_`db/%s`_' % src, '']
        if intro:
            out += ['```', '\n'.join(intro).strip(), '```', '']
        elif note:
            out += [note, '']
        if spec:
            out += ['```sql', spec.strip('\n'), '```', '']
    # the triggers
    out += ['## Triggers', '', '| Trigger | Πίνακας | Πότε | Τι κάνει |', '|---|---|---|---|']
    for t in triggers:
        out.append('| `%s` | `%s` | %s %s | %s |' % (t['TRIGGER_NAME'], t['TABLE_NAME'], t['TRIGGER_TYPE'].lower(),
                                                     t['TRIGGERING_EVENT'].lower(),
                                                     md(EL.TRIGGERS.get(t['TRIGGER_NAME']) or objs.get(t['TRIGGER_NAME'], ('', ''))[1])))
    out.append('')
    # the kinds of documents
    out += ['## Είδη παραστατικών', '',
            '`side`: S πώληση, P αγορά, T εσωτερικό (ενδοδιακίνηση, ανάλωση). Τα πρόσημα: απόθεμα, υπόλοιπο '
            'πελάτη/προμηθευτή, ΦΠΑ.', '',
            '| Κωδικός | Όνομα | side | Απόθεμα | Υπόλοιπο | ΦΠΑ | Τιμές με ΦΠΑ | Θέλει πελάτη/προμηθευτή | Από δελτίο | myDATA |',
            '|---|---|---|---|---|---|---|---|---|---|']
    for t in rows(cur, 'select * from mm_doc_type order by side, code'):
        out.append('| `%s` | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            t['CODE'], t['NAME'], t['SIDE'], t['STOCK_SIGN'], t['PARTNER_SIGN'], t['VAT_SIGN'], t['PRICES_INCL_VAT'],
            t['PARTNER_NEEDED'], t.get('REF_TYPE') or '', t.get('MYDATA_TYPE') or ''))
    out.append('')
    # the errors
    out += ['## Λάθη MM-1xx', '',
            'Κάθε κανόνας που δεν τηρείται σταματά με `ORA-20xxx: MM-1xx: μήνυμα`. Το REST τα επιστρέφει ως '
            '`400 {"error": "MM-1xx", "message": ...}` (το 177 και το 179 ως 401, το 178 ως 423).', '',
            '| Κωδικός | Μηνύματα |', '|---|---|']
    for code, texts in errors().items():
        out.append('| MM-%d | %s |' % (code, '<br>'.join(md(t) for t in texts[:6])))
    out.append('')
    return '\n'.join(out)


# -- the application ------------------------------------------------------------------------------------

def rest_calls():
    """the calls of the REST service: the <pre> of the header of each class (Api.java first)"""
    out = []
    files = sorted(glob.glob(os.path.join(ROOT, 'api/src/main/java/mm/api/*.java')),
                   key=lambda p: (not p.endswith('Api.java'), p))
    for path in files:
        src = read(path)
        m = re.search(r'/\*\*(.*?)\*/\s*(?:final\s+)?(?:public\s+)?class', src, re.S)
        if not m:
            continue
        body = [re.sub(r'^\s*\* ?', '', x) for x in m.group(1).split('\n')]
        text = '\n'.join(body)
        pre = re.search(r'<pre>(.*?)</pre>', text, re.S)
        intro = re.sub(r'<pre>.*?</pre>', '', text, flags=re.S).strip()
        out.append((os.path.basename(path), ' '.join(intro.split()), pre.group(1).strip('\n') if pre else ''))
    return out


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def app_doc(cur):
    out = ['# Αναφορά της εφαρμογής', '',
           'Φτιάχνεται αυτόματα από τον κώδικα και τη βάση (`tools/mkdocs.py`): το REST, οι οθόνες και τα '
           'δικαιώματά τους, οι σελίδες web, οι φόρμες του Oracle, τα reports, τα tests. Η βάση: '
           '[ANAFORA_VASIS.md](ANAFORA_VASIS.md)· η αρχιτεκτονική: [ARXITEKTONIKI.md](ARXITEKTONIKI.md).', '',
           '## Περιεχόμενα', '', '- [Οθόνες και δικαιώματα](#οθόνες-και-δικαιώματα)', '- [Η υπηρεσία REST](#η-υπηρεσία-rest)',
           '- [Φόρμες του Oracle](#φόρμες-του-oracle)', '- [Oracle Reports](#oracle-reports)', '- [Tests](#tests)', '']
    # the screens: the menu of the pages and the forms, their fields and actions, the roles of the system
    out += ['## Οθόνες και δικαιώματα', '',
            'Το μενού είναι στη βάση (`MM_OBJECT`): κάθε οθόνη είναι μια σελίδα web (`route`), μια φόρμα, ή και τα '
            'δύο, με τα ίδια δικαιώματα. N: τίποτα, R: ανάγνωση, W: αλλαγή. Οι ρόλοι του συστήματος όπως '
            'εγκαθίστανται· ο `ADMIN` έχει πάντα τα πάντα. Τα αλλάζει η σελίδα «Ρόλοι και δικαιώματα».', '']
    role_ids = {r['CODE']: r['ID'] for r in rows(cur, 'select id, code from mm_role where system = :y', y='Y')}

    def lvl(role, obj, item=None):
        r = rows(cur, """select substr('NRW', lv + 1, 1) l from mm_role_right where role_id = :r and object_code = :o
                         and nvl(item_code, '-') = nvl(:i, '-')""", r=role_ids[role], o=obj, i=item)
        return r[0]['L'] if r else 'N'
    groups = rows(cur, "select id, code, name from mm_object where kind = 'G' order by sort_no, code")
    for g in groups:
        out += ['### %s' % g['NAME'], '', '| Οθόνη | Σελίδα | Φόρμα | Ταμίας | Προϊστάμενος | Πεδία και ενέργειες |',
                '|---|---|---|---|---|---|']
        for s in rows(cur, "select id, code, name, route, form from mm_object where parent_id = :g order by sort_no, code", g=g['ID']):
            items = rows(cur, 'select code, kind, name from mm_object_item where object_id = :o order by sort_no', o=s['ID'])
            its = '<br>'.join('%s `%s` %s (%s/%s)' % ('πεδίο' if i['KIND'] == 'F' else 'ενέργεια', i['CODE'], md(i['NAME']),
                                                     lvl('CASHIER', s['CODE'], i['CODE']), lvl('MANAGER', s['CODE'], i['CODE']))
                              for i in items)
            out.append('| **%s** `%s` | %s | %s | %s | %s | %s |' % (
                md(s['NAME']), s['CODE'], '`%s`' % s['ROUTE'] if s['ROUTE'] else '', '`%s`' % s['FORM'] if s['FORM'] else '',
                lvl('CASHIER', s['CODE']), lvl('MANAGER', s['CODE']), its))
        out.append('')
    # REST
    out += ['## Η υπηρεσία REST', '',
            'Η υπηρεσία `mm-api` (Java, `api/`): `/api/...` σε JSON, με token από το login. Κάθε κλήση ελέγχεται '
            'με τα δικαιώματα (`Rights.java`). Οδηγίες: [ODIGIES_REST.md](ODIGIES_REST.md).', '']
    for f, intro, pre in rest_calls():
        out += ['### %s' % f, '']
        if intro:
            out += [intro, '']
        if pre:
            out += ['```', pre, '```', '']
    # forms
    mk = load(os.path.join(ROOT, 'forms/mkforms.py'), 'mkforms')
    out += ['## Φόρμες του Oracle', '',
            'Οι φόρμες φτιάχνονται από το `forms/mkforms.py` (XML → `.fmb` → `.fmx`, `build_forms.ps1`). Όλες έχουν '
            'το ίδιο πακέτο `UI` (`forms/MM_UI.pls`): τα triggers μόνο το καλούν. Οδηγίες: [ODIGIES_FORMS.md](ODIGIES_FORMS.md).', '',
            '| Φόρμα | Τίτλος | Οθόνη | Blocks (πίνακας) | Κουμπιά |', '|---|---|---|---|---|']
    for n, f in mk.FORMS.items():
        blocks = ', '.join('`%s` (%s)' % (b['name'], b.get('table', '')) for b in f.get('blocks', [])) \
            or ('`%s` (%s)' % (f.get('block', ''), f.get('table', '')) if f.get('table') else '')
        buttons = ', '.join(c[5] for c in f.get('ctl', []) if c[1] == 'button')
        out.append('| `%s` | %s | %s | %s | %s |' % (n, f.get('title', ''), '`%s`' % mk.FORM_SCREENS[n] if n in mk.FORM_SCREENS else '',
                                                     blocks, md(buttons)))
    out += ['', '**Τα δικαιώματα μέσα στις φόρμες** (`FORM_RIGHTS`): F πεδίο (κρυφό χωρίς δικαίωμα, μόνο για '
            'ανάγνωση με R), B κουμπί (απενεργοποιημένο χωρίς το δικαίωμα).', '',
            '| Φόρμα | Τι | Οθόνη.δικαίωμα | Item |', '|---|---|---|---|']
    for n, rules in mk.FORM_RIGHTS.items():
        for kind, sc, item, level, target in rules:
            out.append('| `%s` | %s | `%s%s` | `%s` |' % (n, 'πεδίο' if kind == 'F' else 'κουμπί (%s)' % level,
                                                         sc, '.' + item if item else '', target))
    out.append('')
    # reports
    rp = load(os.path.join(ROOT, 'reports/mkreports.py'), 'mkreports')
    out += ['## Oracle Reports', '',
            'Τα reports φτιάχνονται από το `reports/mkreports.py` (XML → `.rdf`, `build_reports.ps1`) και ανοίγουν σε '
            'PDF από τις φόρμες και τις σελίδες, μέσω του Reports Server. Οδηγίες: [ODIGIES_REPORTS.md](ODIGIES_REPORTS.md).', '',
            '| Report | Από | Παράμετροι |', '|---|---|---|']
    for n, r in rp.REPORTS.items():
        out.append('| `%s` | `mm_ledger.report_rows` (καρτέλα %s) | P_KIND, P_ID, P_FROM, P_TO |' % (
            n, {'I': 'είδους', 'C': 'πελάτη ή προμηθευτή'}.get(r['kind'], r['kind'])))
    for n, t in rp.TABLES.items():
        src = re.search(r'from\s+([\w.(]+)', t['query'])
        out.append('| `%s` | `%s` | %s |' % (n, src.group(1).rstrip('(') if src else '', ', '.join(p[0] for p in t['params']) or '—'))
    out.append('')
    # tests
    out += ['## Tests', '',
            'Σε Python (`pytest`, `oracledb`), πάνω σε ζωντανή βάση· τα tests του REST ξεκινούν το `mm-api.jar`, και '
            'όσα του browser τρέχουν Chromium (Playwright). `MM_DSN=mm/<κωδικός>@localhost:1521/FREEPDB1 python -m pytest tests`.', '',
            '| Αρχείο (tests) | Τι ελέγχει (από το σχόλιο του αρχείου) |', '|---|---|']
    for path in sorted(glob.glob(os.path.join(ROOT, 'tests/test_*.py'))):
        doc = ast.get_docstring(ast.parse(read(path))) or ''
        first = doc.split('\n\n')[0]
        first = re.sub(r'^\S+\.py\s*--\s*', '', ' '.join(first.split()))
        n = len(re.findall(r'^def test_', read(path), re.M))
        out.append('| `%s` (%d) | %s |' % (os.path.basename(path), n, md(first)))
    out.append('')
    return '\n'.join(out)


def main():
    dsn = os.environ.get('MM_DSN')
    if not dsn:
        sys.exit('MM_DSN=mm/<password>@host:port/service')
    user, rest = dsn.split('/', 1)
    pw, where = rest.rsplit('@', 1)
    with oracledb.connect(user=user, password=pw, dsn=where) as conn:
        cur = conn.cursor()
        stamp = '\n_Φτιάχτηκε στις %s._\n' % datetime.date.today().strftime('%d/%m/%Y')
        for name, text in (('ANAFORA_VASIS.md', db_doc(cur)), ('ANAFORA_EFARMOGIS.md', app_doc(cur))):
            with open(os.path.join(DOCS, name), 'w', encoding='utf-8', newline='\n') as f:
                f.write(text.rstrip() + '\n' + stamp)
            print('docs/%s: %d lines' % (name, text.count('\n') + 2))


if __name__ == '__main__':
    main()
