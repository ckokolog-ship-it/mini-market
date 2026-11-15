// app.js -- the pages of the mini market (step 8): a login, then the items, the customers and the
// suppliers, the ledgers, the reports and the counts of the stock, through /api/ with the token of the
// login (sessionStorage: gone with the tab). Every value goes in as text (textContent), never as HTML.
// The pages by role: CASHIER the items and the counts; MANAGER all the rest; as the REST service.

const $ = (sel) => document.querySelector(sel);
const main = () => $('#main');
const RANK = { CASHIER: 1, MANAGER: 2, ADMIN: 3 };
const PAGES = [
  ['#/items', 'Είδη', 'CASHIER'],
  ['#/partners/customers', 'Πελάτες', 'MANAGER'],
  ['#/partners/suppliers', 'Προμηθευτές', 'MANAGER'],
  ['#/reports/sales', 'Πωλήσεις', 'MANAGER'],
  ['#/reports/vat', 'ΦΠΑ', 'MANAGER'],
  ['#/reports/min-stock', 'Ελάχιστο απόθεμα', 'MANAGER'],
  ['#/counts', 'Απογραφή', 'CASHIER'],
];

let session = null;
try { session = JSON.parse(sessionStorage.getItem('mm') || 'null'); } catch (e) { session = null; }

// -- a little DOM ------------------------------------------------------------------------------------
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'class') e.className = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) {
    if (k === null || k === undefined || k === false) continue;
    e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return e;
}
const can = (role) => session && RANK[session.role] >= RANK[role];
const nf2 = new Intl.NumberFormat('el-GR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf3 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 3 });
const money = (v) => (v === null || v === undefined ? '' : nf2.format(v));
const qty = (v) => (v === null || v === undefined ? '' : nf3.format(v));
function day(iso) {           // 2026-11-15 or 2026-11-15T09:30 -> 15/11/2026 (09:30)
  if (!iso) return '';
  const [d, t] = String(iso).split('T');
  const [y, m, dd] = d.split('-');
  return `${dd}/${m}/${y}` + (t ? ' ' + t.slice(0, 5) : '');
}
const isoToday = () => new Date().toISOString().slice(0, 10);
const isoYearStart = () => new Date().getFullYear() + '-01-01';
function num(v, fmt = money, cls = 'num') {
  return el('td', { class: cls + (v < 0 ? ' neg' : '') }, fmt(v));
}
function table(head, rows) {
  return el('div', { class: 'table-wrap' },
    el('table', {}, el('thead', {}, el('tr', {}, head.map(([t, c]) => el('th', { class: c || null }, t)))),
      el('tbody', {}, rows)));
}
// pages: "< Previous  Page 2 of 7 (312)  Next >" and the rows of a page (25, 50, 100)
let pageSize = 50;
try { pageSize = Number(localStorage.getItem('mm.pageSize')) || 50; } catch (e) { pageSize = 50; }
function pager(total, offset, limit, go) {
  const pages = Math.max(1, Math.ceil(total / limit));
  const page = Math.floor(offset / limit) + 1;
  const size = el('select', {
    'aria-label': 'Γραμμές ανά σελίδα',
    onchange: () => {
      pageSize = Number(size.value);
      try { localStorage.setItem('mm.pageSize', String(pageSize)); } catch (e) { /* a private window */ }
      go(0);
    },
  }, [25, 50, 100].map((n) => el('option', { value: n, selected: n === limit }, n + ' ανά σελίδα')));
  return el('div', { class: 'row pager' },
    el('button', { type: 'button', disabled: page <= 1, onclick: () => go(0) }, '«'),
    el('button', { type: 'button', disabled: page <= 1, onclick: () => go(offset - limit) }, '‹ Προηγούμενη'),
    el('span', { class: 'muted' }, `Σελίδα ${page} από ${pages} (${total})`),
    el('button', { type: 'button', disabled: page >= pages, onclick: () => go(offset + limit) }, 'Επόμενη ›'),
    el('button', { type: 'button', disabled: page >= pages, onclick: () => go((pages - 1) * limit) }, '»'),
    size);
}
function toast(text, bad) {
  const t = $('#toast');
  t.textContent = text;
  t.className = 'show' + (bad ? ' bad' : '');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.className = ''; }, bad ? 5000 : 2500);
}
function show(...kids) {
  main().replaceChildren(...kids);
}

// -- the REST service ------------------------------------------------------------------------------
async function api(path, body) {
  const opts = { headers: {} };
  if (session) opts.headers.Authorization = 'Bearer ' + session.token;
  if (body !== undefined) {
    opts.method = 'POST';
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch('/api/' + path, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { data = { error: 'http_' + r.status, message: r.statusText }; }
  if (r.status === 401 && path !== 'auth/login') {
    logoutLocal();
    toast('Η σύνδεση έληξε: συνδέσου ξανά', true);
    throw new Error('auth');
  }
  if (!r.ok) {
    const err = new Error(data && data.message ? data.message : 'σφάλμα ' + r.status);
    err.code = data && data.error;
    throw err;
  }
  return data;
}
function fail(e) {
  if (e && e.message !== 'auth') toast(e.message, true);
}

// -- login -----------------------------------------------------------------------------------------
function logoutLocal() {
  session = null;
  sessionStorage.removeItem('mm');
  render();
}
function loginPage() {
  $('#top').hidden = true;
  const user = el('input', { name: 'username', autocomplete: 'username', required: true, autofocus: true });
  const pw = el('input', { name: 'password', type: 'password', autocomplete: 'current-password', required: true });
  const msg = el('p', { class: 'neg', role: 'alert' });
  const form = el('form', {
    onsubmit: async (ev) => {
      ev.preventDefault();
      msg.textContent = '';
      try {
        const r = await api('auth/login', { username: user.value, password: pw.value });
        session = { token: r.token, username: r.username, role: r.role };
        sessionStorage.setItem('mm', JSON.stringify(session));
        pw.value = '';
        if (!location.hash || location.hash === '#/login') location.hash = '#/items';
        render();
      } catch (e) {
        pw.value = '';
        msg.textContent = e.message;
        pw.focus();
      }
    },
  }, el('label', {}, 'Όνομα χρήστη', user), el('label', {}, 'Κωδικός', pw),
  el('button', { class: 'primary', type: 'submit' }, 'Σύνδεση'), msg);
  show(el('div', { class: 'panel login' }, el('h1', {}, 'Mini market'), form));
  user.focus();
}

// -- the items -------------------------------------------------------------------------------------
async function itemsPage(params) {
  const q = el('input', { name: 'q', type: 'search', placeholder: 'περιγραφή, κωδικός ή barcode', value: params.get('q') || '' });
  const out = el('div');
  const go = async (offset = 0) => {
    try {
      const r = await api(`items?limit=${pageSize}&offset=${Math.max(0, offset)}&q=` + encodeURIComponent(q.value.trim()));
      out.replaceChildren(pager(r.total, r.offset, r.limit, go), table(
        [['Κωδικός'], ['Περιγραφή'], ['Κατηγορία', 'hide-phone'], ['Τιμή', 'num'], ['Απόθεμα', 'num'], ['Ελάχ.', 'num hide-phone']],
        r.rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = '#/item/' + encodeURIComponent(x.code); } },
          el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), el('td', { class: 'hide-phone' }, x.category),
          num(x.price), el('td', { class: 'num' + (x.stock < x.min_stock ? ' neg' : '') }, qty(x.stock)),
          el('td', { class: 'num hide-phone' }, qty(x.min_stock))))), r.total > r.limit ? pager(r.total, r.offset, r.limit, go) : null);
      if (!r.rows.length) out.replaceChildren(el('p', { class: 'muted' }, 'Τίποτα.'));
    } catch (e) { fail(e); }
  };
  let timer;
  q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => go(0), 250); });
  q.addEventListener('keydown', async (ev) => {
    if (ev.key !== 'Enter') return;
    ev.preventDefault();
    const v = q.value.trim();
    if (/^\d{8,14}$/.test(v)) location.hash = '#/item/' + encodeURIComponent(v);   // a barcode: straight to it
    else go(0);
  });
  show(el('h1', {}, 'Είδη'), el('div', { class: 'panel row' }, el('label', { style: null }, 'Αναζήτηση', q)), out);
  q.focus();
  go();
}

async function itemPage(code) {
  try {
    const x = await api('items/' + encodeURIComponent(code));
    const rows = [['Κωδικός', x.code], ['Barcode', x.barcode], ['Κατηγορία', x.category], ['Μονάδα', x.unit],
      ['Τιμή λιανικής', money(x.price)], ['Χονδρική', money(x.wholesale_price)], ['ΦΠΑ', x.vat_code + ' ' + x.vat_rate + '%'],
      ['Απόθεμα', qty(x.stock)], ['Δεσμευμένα', qty(x.reserved)], ['Διαθέσιμα', qty(x.available)],
      ['Ελάχιστο', qty(x.min_stock)]];
    if (x.serial_tracked === 'Y') rows.push(['Διαθέσιμες κάρτες', x.cards]);
    if (can('MANAGER')) rows.splice(6, 0, ['Κόστος', money(x.cost)]);
    show(el('h1', {}, x.name),
      el('div', { class: 'panel' }, el('dl', { class: 'kv' }, rows.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v ?? '')]))),
      el('div', { class: 'row' },
        el('button', { onclick: () => history.back() }, 'Πίσω'),
        can('MANAGER') && el('button', { class: 'primary', onclick: () => { location.hash = '#/ledger/item/' + x.id; } }, 'Καρτέλα')));
  } catch (e) {
    fail(e);
    show(el('h1', {}, 'Είδη'), el('p', { class: 'muted' }, 'Δεν βρέθηκε: ' + code), el('a', { href: '#/items' }, 'Στα είδη'));
  }
}

// -- customers and suppliers -----------------------------------------------------------------------
async function partnersPage(kind, params) {
  const one = kind === 'customers' ? 'Πελάτες' : 'Προμηθευτές';
  const q = el('input', { type: 'search', placeholder: 'επωνυμία ή ΑΦΜ', value: params.get('q') || '' });
  const out = el('div');
  const go = async (offset = 0) => {
    try {
      const r = await api(`${kind}?limit=${pageSize}&offset=${Math.max(0, offset)}&q=` + encodeURIComponent(q.value.trim()));
      out.replaceChildren(pager(r.total, r.offset, r.limit, go), table([['Επωνυμία'], ['ΑΦΜ'], ['Τηλέφωνο', 'hide-phone'], ['Email', 'hide-phone']],
        r.rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = `#/partner/${kind}/${x.id}`; } },
          el('td', { class: 'wrap' }, x.name), el('td', {}, x.afm || ''), el('td', { class: 'hide-phone' }, x.phone || ''),
          el('td', { class: 'hide-phone' }, x.email || '')))));
    } catch (e) { fail(e); }
  };
  let timer;
  q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => go(0), 250); });
  show(el('h1', {}, one), el('div', { class: 'panel row' }, el('label', {}, 'Αναζήτηση', q)), out);
  go();
}

async function partnerPage(kind, id) {
  try {
    const x = await api(`${kind}/${id}`);
    const who = kind === 'customers' ? 'customer' : 'supplier';
    show(el('h1', {}, x.name),
      el('div', { class: 'panel' }, el('dl', { class: 'kv' },
        [['ΑΦΜ', x.afm], ['ΔΟΥ', x.doy], ['Διεύθυνση', x.address], ['Τηλέφωνο', x.phone], ['Email', x.email]]
          .flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v || '')]),
        el('dt', {}, kind === 'customers' ? 'Υπόλοιπο (χρωστάει)' : 'Υπόλοιπο (του χρωστάμε)'),
        el('dd', { class: 'big' + (x.balance < 0 ? ' neg' : '') }, money(x.balance)))),
      el('div', { class: 'row' }, el('button', { onclick: () => history.back() }, 'Πίσω'),
        el('button', { class: 'primary', onclick: () => { location.hash = `#/ledger/${who}/${x.id}`; } }, 'Καρτέλα')));
  } catch (e) { fail(e); }
}

// -- a ledger: the carry-over, the moves with the running balance, the totals ----------------------
async function ledgerPage(what, id, params) {
  const from = el('input', { type: 'date', value: params.get('from') || isoYearStart() });
  const to = el('input', { type: 'date', value: params.get('to') || isoToday() });
  const out = el('div');
  const item = what === 'item';
  const go = async (offset = 0) => {
    try {
      const r = await api(`ledger/${what}/${id}?from=${from.value}&to=${to.value}&limit=${pageSize}&offset=${Math.max(0, offset)}`);
      const f = item ? qty : money;
      const lastPage = r.offset + r.limit >= r.total;
      const carry = (label, c) => el('tr', { class: 'carry' }, el('td'), el('td'), el('td', { class: 'wrap' }, label),
        num(c.debit, f), num(c.credit, f), num(c.balance, f));
      const rows = [carry('Από μεταφορά', r.carry_in)];
      r.rows.forEach((x) => rows.push(el('tr', {}, el('td', {}, day(x.ldate)), el('td', {}, x.doc_text || ''),
        el('td', { class: 'wrap' }, item && x.partner ? x.partner + ' - ' + x.descr : x.descr),
        num(x.debit, f), num(x.credit, f), num(x.balance, f))));
      if (!lastPage) {
        rows.push(carry('Σε μεταφορά', r.carry_out));
      } else {
        rows.push(el('tr', { class: 'total' }, el('td'), el('td'), el('td', {}, 'Σύνολα περιόδου'), num(r.debit, f), num(r.credit, f), el('td')));
        rows.push(el('tr', { class: 'total' }, el('td'), el('td'), el('td', {}, 'Από προηγούμενη περίοδο'), el('td'), el('td'), num(r.open, f)));
        rows.push(el('tr', { class: 'total' }, el('td'), el('td'), el('td', {}, item ? 'Τελικό απόθεμα' : 'Γενικό υπόλοιπο'),
          el('td'), el('td'), num(r.close, f)));
      }
      out.replaceChildren(el('p', { class: 'muted' }, `${day(r.from)} - ${day(r.to)} · ${r.total} κινήσεις`),
        pager(r.total, r.offset, r.limit, go),
        table([['Ημερομηνία'], ['Παραστατικό'], ['Περιγραφή'], [item ? 'Εισαγωγή' : 'Χρέωση', 'num'],
          [item ? 'Εξαγωγή' : 'Πίστωση', 'num'], [item ? 'Απόθεμα' : 'Υπόλοιπο', 'num']], rows),
        r.total > r.limit ? pager(r.total, r.offset, r.limit, go) : null);
      title.textContent = r.title;
    } catch (e) { fail(e); }
  };
  const title = el('h1', {}, 'Καρτέλα');
  show(title, el('form', { class: 'panel row', onsubmit: (ev) => { ev.preventDefault(); go(0); } },
    el('label', {}, 'Από', from), el('label', {}, 'Έως', to), el('button', { class: 'primary', type: 'submit' }, 'Εμφάνιση'),
    el('button', { type: 'button', onclick: () => history.back() }, 'Πίσω')), out);
  go(0);
}

// -- the reports -----------------------------------------------------------------------------------
async function reportPage(name, params) {
  const titles = { sales: 'Πωλήσεις ανά ημέρα', vat: 'ΦΠΑ πωλήσεων και αγορών', 'min-stock': 'Είδη κάτω από το ελάχιστο απόθεμα' };
  const from = el('input', { type: 'date', value: params.get('from') || isoYearStart() });
  const to = el('input', { type: 'date', value: params.get('to') || isoToday() });
  const out = el('div');
  const go = async () => {
    try {
      const r = await api(`reports/${name}?from=${from.value}&to=${to.value}`);
      out.replaceChildren(name === 'sales' ? salesTable(r.rows) : name === 'vat' ? vatTable(r.rows) : minTable(r.rows));
    } catch (e) { fail(e); }
  };
  const form = name === 'min-stock' ? null
    : el('form', { class: 'panel row', onsubmit: (ev) => { ev.preventDefault(); go(); } },
      el('label', {}, 'Από', from), el('label', {}, 'Έως', to), el('button', { class: 'primary', type: 'submit' }, 'Εμφάνιση'));
  show(el('h1', {}, titles[name]), form, out);
  go();
}
// rows under their month, with the subtotal of each month and the grand total
function byMonth(rows, keyOf, cells, sums, label) {
  const out = [];
  const grand = Object.fromEntries(sums.map((s) => [s, 0]));
  let month = null;
  let sub = null;
  const close = () => {
    if (month !== null) out.push(el('tr', { class: 'total' }, el('td', {}, 'Σύνολο ' + month), ...label(sub)));
  };
  for (const x of rows) {
    const m = keyOf(x);
    if (m !== month) {
      close();
      month = m;
      sub = Object.fromEntries(sums.map((s) => [s, 0]));
    }
    sums.forEach((s) => { sub[s] += x[s] || 0; grand[s] += x[s] || 0; });
    out.push(el('tr', {}, ...cells(x)));
  }
  close();
  out.push(el('tr', { class: 'total' }, el('td', {}, 'Γενικό σύνολο'), ...label(grand)));
  return out;
}
function salesTable(rows) {
  const sums = ['alp_docs', 'alp_total', 'tpy_total', 'ppy_total', 'total'];
  const months = [...new Set(rows.map((x) => x.day.slice(0, 7)))];          // a page for each month
  const box = el('div');
  const head = [['Ημέρα'], ['Αποδείξεις', 'num'], ['Λιανική', 'num'], ['Τιμολόγια', 'num'], ['Πιστωτικά', 'num'], ['Σύνολο', 'num']];
  const cells = (s) => [num(s.alp_docs, qty), num(s.alp_total), num(s.tpy_total), num(s.ppy_total), num(s.total)];
  const all = Object.fromEntries(sums.map((k) => [k, rows.reduce((a, x) => a + (x[k] || 0), 0)]));
  const showMonth = (k) => {
    const m = months[k];
    const label = (x) => x.slice(5, 7) + '/' + x.slice(0, 4);
    const nav = months.length > 1 && el('div', { class: 'row pager' },
      el('button', { type: 'button', disabled: k <= 0, onclick: () => showMonth(k - 1) }, '‹ Προηγούμενος μήνας'),
      el('select', { 'aria-label': 'Μήνας', onchange: (ev) => showMonth(Number(ev.target.value)) },
        months.map((x, i) => el('option', { value: i, selected: i === k }, label(x)))),
      el('button', { type: 'button', disabled: k >= months.length - 1, onclick: () => showMonth(k + 1) }, 'Επόμενος μήνας ›'));
    const body = byMonth(rows.filter((x) => x.day.startsWith(m)), () => label(m),
      (x) => [el('td', {}, day(x.day)), num(x.alp_docs, qty), num(x.alp_total), num(x.tpy_total), num(x.ppy_total), num(x.total)],
      sums, cells);
    body.pop();                                       // (the month is the page: its total, not a grand one)
    body.push(el('tr', { class: 'total' }, el('td', {}, 'Σύνολο περιόδου'), ...cells(all)));
    box.replaceChildren(nav || '', table(head, body));
  };
  if (!months.length) return el('p', { class: 'muted' }, 'Καμία πώληση στο διάστημα.');
  showMonth(months.length - 1);                       // the last month first
  return box;
}
function vatTable(rows) {
  const sums = ['s_net', 's_vat', 'p_net', 'p_vat', 'payable'];
  return table([['ΦΠΑ'], ['Καθαρά πωλ.', 'num'], ['ΦΠΑ πωλ.', 'num'], ['Καθαρά αγορ.', 'num'], ['ΦΠΑ αγορ.', 'num'], ['Προς απόδοση', 'num']],
    byMonth(rows, (x) => x.month.slice(5) + '/' + x.month.slice(0, 4),
      (x) => [el('td', {}, x.vat_code + ' ' + x.vat_rate + '%'), num(x.s_net), num(x.s_vat), num(x.p_net), num(x.p_vat), num(x.payable)],
      sums, (s) => sums.map((k) => num(s[k]))));
}
function minTable(rows) {
  if (!rows.length) return el('p', { class: 'muted' }, 'Κανένα είδος κάτω από το ελάχιστο.');
  return table([['Κατηγορία', 'hide-phone'], ['Κωδικός'], ['Περιγραφή'], ['Απόθεμα', 'num'], ['Ελάχιστο', 'num'], ['Λείπουν', 'num'],
    ['Τελευταίος προμηθευτής', 'hide-phone']],
  rows.map((x) => el('tr', {}, el('td', { class: 'hide-phone' }, x.category), el('td', {}, x.code), el('td', { class: 'wrap' }, x.name),
    num(x.stock, qty), num(x.min_stock, qty), num(x.missing, qty), el('td', { class: 'hide-phone' }, x.supplier || ''))));
}

// -- the counts of the stock: a phone scans (a scanner types the barcode and Enter) ------------------
async function countsPage() {
  const name = el('input', { placeholder: 'π.χ. Απογραφή ραφιών Νοεμβρίου' });
  const out = el('div');
  const load = async () => {
    try {
      const r = await api('counts');
      const st = { O: 'ανοιχτή', P: 'καταχωρήθηκε', C: 'ακυρώθηκε' };
      out.replaceChildren(r.rows.length ? table([['#'], ['Όνομα'], ['Κατάσταση'], ['Είδη', 'num'], ['Από', 'hide-phone']],
        r.rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = '#/count/' + x.id; } },
          el('td', {}, x.id), el('td', { class: 'wrap' }, x.name), el('td', {}, st[x.status] || x.status),
          el('td', { class: 'num' }, x.lines), el('td', { class: 'hide-phone' }, day(x.created_at)))))
        : el('p', { class: 'muted' }, 'Καμία απογραφή.'));
    } catch (e) { fail(e); }
  };
  show(el('h1', {}, 'Απογραφή'),
    can('MANAGER') && el('form', {
      class: 'panel row',
      onsubmit: async (ev) => {
        ev.preventDefault();
        try {
          const c = await api('counts', { name: name.value.trim() || null });
          location.hash = '#/count/' + c.id;
        } catch (e) { fail(e); }
      },
    }, el('label', {}, 'Νέα απογραφή', name), el('button', { class: 'primary', type: 'submit' }, 'Ξεκίνα')),
    out);
  load();
}

async function countPage(id) {
  const code = el('input', { name: 'code', inputmode: 'text', autocomplete: 'off', placeholder: 'barcode ή κωδικός' });
  const n = el('input', { name: 'qty', type: 'number', step: 'any', min: '0', value: '1', style: null });
  const mode = el('select', { name: 'mode' }, el('option', { value: 'ADD' }, 'πρόσθεσε'), el('option', { value: 'SET' }, 'όρισε'));
  const last = el('p', { class: 'big' });
  const out = el('div');
  const title = el('h1', {}, 'Απογραφή');
  let open = false;
  const load = async () => {
    try {
      const c = await api('counts/' + id);
      open = c.status === 'O';
      title.textContent = `${c.name} (${open ? 'ανοιχτή' : c.status === 'P' ? 'καταχωρήθηκε' : 'ακυρώθηκε'})`;
      form.hidden = !open;
      actions.hidden = !(open && can('MANAGER'));
      out.replaceChildren(table([['Κωδικός'], ['Περιγραφή'], ['Μετρήθηκαν', 'num'], ['Σύστημα', 'num'], ['Διαφορά', 'num'], ['Συσκευή', 'hide-phone']],
        c.lines.map((x) => el('tr', {}, el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.counted_qty, qty),
          num(x.system_qty, qty), num(x.diff, qty), el('td', { class: 'hide-phone' }, x.device || '')))));
    } catch (e) { fail(e); }
  };
  const form = el('form', {
    class: 'panel row scan',
    onsubmit: async (ev) => {
      ev.preventDefault();
      const v = code.value.trim();
      if (!v) return;
      try {
        const r = await api(`counts/${id}/scan`, { code: v, qty: Number(n.value || 1), mode: mode.value, device: 'web' });
        last.textContent = `${r.code} ${r.name}: ${qty(r.counted_qty)}`;
        code.value = '';
        n.value = '1';
        load();
      } catch (e) {
        fail(e);
        code.select();
      }
      code.focus();
    },
  }, el('label', {}, 'Σάρωση (Enter)', code), el('label', {}, 'Ποσότητα', n), el('label', {}, 'Τρόπος', mode),
  el('button', { class: 'primary', type: 'submit' }, 'Βάλε'));
  const act = (what, ask) => async () => {
    if (!confirm(ask)) return;
    try {
      await api(`counts/${id}/${what}`, {});
      toast(what === 'post' ? 'Καταχωρήθηκε στο απόθεμα' : 'Ακυρώθηκε');
      load();
    } catch (e) { fail(e); }
  };
  const actions = el('div', { class: 'row' },
    el('button', { class: 'primary', onclick: act('post', 'Καταχώριση της απογραφής στο απόθεμα;') }, 'Καταχώριση'),
    el('button', { class: 'danger', onclick: act('cancel', 'Ακύρωση της απογραφής;') }, 'Ακύρωση'));
  show(title, form, last, out, el('h2', {}), actions, el('p', {}, el('a', { href: '#/counts' }, 'Όλες οι απογραφές')));
  await load();
  code.focus();
}

// -- the pages, by the address (#/...) -------------------------------------------------------------
function navBar() {
  $('#top').hidden = false;
  $('#who').textContent = `${session.username} (${session.role})`;
  $('#nav').replaceChildren(...PAGES.filter(([, , r]) => can(r)).map(([h, t]) =>
    el('a', { href: h, class: location.hash.startsWith(h) ? 'on' : null }, t)));
}
function render() {
  if (!session) {
    loginPage();
    return;
  }
  navBar();
  const [path, query] = (location.hash.slice(1) || '/items').split('?');
  const params = new URLSearchParams(query || '');
  const p = path.split('/').filter(Boolean).map(decodeURIComponent);
  const need = (role, fn) => (can(role) ? fn() : show(el('h1', {}, 'Δεν επιτρέπεται'),
    el('p', { class: 'muted' }, 'Η σελίδα αυτή θέλει ρόλο ' + role + '.')));
  switch (p[0]) {
    case 'item': return itemPage(p[1]);
    case 'partners': return need('MANAGER', () => partnersPage(p[1], params));
    case 'partner': return need('MANAGER', () => partnerPage(p[1], p[2]));
    case 'ledger': return need('MANAGER', () => ledgerPage(p[1], p[2], params));
    case 'reports': return need('MANAGER', () => reportPage(p[1], params));
    case 'counts': return countsPage();
    case 'count': return countPage(p[1]);
    default: return itemsPage(params);
  }
}

$('#logout').addEventListener('click', async () => {
  try { await api('auth/logout', {}); } catch (e) { /* out all the same */ }
  logoutLocal();
});
window.addEventListener('hashchange', render);
render();
