// app.js -- the pages of the mini market (step 8): a login, then the till, the items, the customers
// and the suppliers, the ledgers, the reports and the counts of the stock, through /api/ with the token of the
// login (sessionStorage: gone with the tab). Every value goes in as text (textContent), never as HTML.
// The pages by role: CASHIER the till, the items and the counts; MANAGER all the rest; as the REST service.

import { barsSvg, itemBars, qrSvg } from './codes.js';
import { canScan, codeOf, scanOnce } from './scan.js';

const $ = (sel) => document.querySelector(sel);
const main = () => $('#main');
const RANK = { CASHIER: 1, MANAGER: 2, ADMIN: 3 };
// the pages the web has (the menu itself, its groups, their order, names: from the database, MM_RIGHTS: only
// the screens with a page here and a right to read them)
const MENU = [
  ['Πωλήσεις', [['#/pos', 'Ταμείο', 'CASHIER'], ['#/orders', 'Παραγγελίες', 'CASHIER']]],
  ['Αποθήκη', [['#/items', 'Είδη', 'CASHIER'], ['#/labels', 'Ετικέτες', 'CASHIER'], ['#/counts', 'Απογραφή', 'CASHIER'], ['#/scratch', 'Σκρατς', 'MANAGER'], ['#/expiry', 'Λήξεις', 'MANAGER'],
    ['#/warehouses', 'Αποθήκες', 'MANAGER']]],
  ['Διαχείριση', [['#/users', 'Χρήστες', 'ADMIN'], ['#/roles', 'Ρόλοι και δικαιώματα', 'ADMIN'], ['#/audit', 'Ιστορικό ενεργειών', 'ADMIN']]],
  ['Γραφείο', [['#/docs', 'Τιμολόγια', 'MANAGER'], ['#/payments', 'Εισπράξεις', 'MANAGER'],
    ['#/partners/customers', 'Πελάτες', 'MANAGER'], ['#/partners/suppliers', 'Προμηθευτές', 'MANAGER']]],
  ['Αναφορές', [['#/day', 'Σύνοψη ημέρας', 'MANAGER'], ['#/chart', 'Γράφημα πωλήσεων', 'MANAGER'], ['#/reports/sales', 'Πωλήσεις', 'MANAGER'], ['#/reports/vat', 'ΦΠΑ', 'MANAGER'],
    ['#/reports/min-stock', 'Ελάχιστο απόθεμα', 'MANAGER'], ['#/reports/sales-by', 'Πωλήσεις ανά κατάστημα', 'MANAGER'],
    ['#/reports/consumption', 'Αναλώσεις', 'MANAGER'], ['#/reports/trial-items', 'Ισοζύγιο ειδών', 'MANAGER'],
    ['#/reports/trial-customers', 'Ισοζύγιο πελατών', 'MANAGER'], ['#/reports/trial-suppliers', 'Ισοζύγιο προμηθευτών', 'MANAGER'],
    ['#/reports/profit', 'Μικτό κέρδος', 'MANAGER'], ['#/reports/stock-value', 'Αξία αποθήκης', 'MANAGER']]],
];

let session = null;
try { session = JSON.parse(sessionStorage.getItem('mm') || 'null'); } catch (e) { session = null; }

// the app of Android (Capacitor): the pages from the phone itself (http://localhost), the REST service at
// the address of the shop, kept on the phone (e.g. http://192.168.1.10:8090). In a browser: this server
const APP = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
let server = '';
if (APP) {
  try { server = localStorage.getItem('mm.server') || ''; } catch (e) { server = ''; }
}

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
// the rights of the user (MM_RIGHTS, /api/auth/rights): a screen (e.g. ITEMS), a field or an action of it
// (ITEMS.COST, DOCS.POST): N none, R read, W write; the server checks them too
const LV = { N: 0, R: 1, W: 2 };
const may = (screen, item, level = 'R') => !!(session && session.rights)
  && LV[session.rights[item ? `${screen}.${item}` : screen] || 'N'] >= LV[level];
const act = (screen, item) => may(screen, item, 'W');
async function loadRights() {
  const r = await api('auth/rights');
  session.rights = r.rights;
  session.menu = r.menu;
  sessionStorage.setItem('mm', JSON.stringify(session));
}
const nf2 = new Intl.NumberFormat('el-GR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf3 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 3 });
const money = (v) => (v === null || v === undefined ? '' : nf2.format(v));
const qty = (v) => (v === null || v === undefined ? '' : nf3.format(v));
const nf4 = new Intl.NumberFormat('el-GR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
const money4 = (v) => (v === null || v === undefined ? '' : nf4.format(v));      // a cost by piece
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
// a button of the camera next to a field of scans (where the page may use the camera): the code read
// goes into the field, then done (a form sent, or the Enter of the field)
function camera(input, done) {
  if (!canScan()) return null;
  return el('button', {
    type: 'button', class: 'cam', 'aria-label': 'Σάρωση με την κάμερα', title: 'Κάμερα',
    onclick: async () => {
      try {
        const text = await scanOnce();
        if (!text) return;
        input.value = codeOf(text);
        if (done) done(); else if (input.form) input.form.requestSubmit();
        else input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      } catch (e) { toast(e.message, true); }
    },
  }, '📷');
}
function show(...kids) {
  main().replaceChildren(...kids.filter((k) => k !== null && k !== undefined && k !== false));   // (else "null" as text)
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
  let r;
  try {
    r = await fetch(server + '/api/' + path, opts);
  } catch (e) {                                    // no answer at all: the network, the address
    throw new Error(APP ? 'Δεν απαντά το μαγαζί (' + server + '): WiFi, διεύθυνση;' : 'Δεν απαντά ο server');
  }
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
function logoutLocal(quiet) {
  bellStop();
  session = null;
  sessionStorage.removeItem('mm');
  if (!quiet) render();
}
// -- the bell: the orders of the customers (/shop/) not confirmed yet, asked every 30 seconds; their
// count next to «Παραγγελίες» (and ☰, and the title of the tab); a new one: a sound (Web Audio, no file:
// the browser allows it after a click on the page, e.g. the login) and a message
const bell = { timer: null, seen: null, count: 0, audio: null, title: document.title };
const soundOn = () => { try { return localStorage.getItem('mm.sound') !== 'off'; } catch (e) { return true; } };
function bellSound() {
  if (!soundOn() || !bell.audio) return;
  const t = bell.audio.currentTime;
  [[880, 0], [1320, 0.18], [880, 0.5], [1320, 0.68]].forEach(([f, at]) => {
    const o = bell.audio.createOscillator();
    const g = bell.audio.createGain();
    o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t + at);
    g.gain.exponentialRampToValueAtTime(0.3, t + at + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + at + 0.16);
    o.connect(g).connect(bell.audio.destination);
    o.start(t + at);
    o.stop(t + at + 0.17);
  });
}
// the sound needs a gesture of the user first: the first click or key makes it ready
function bellAudio() {
  const A = window.AudioContext || window.webkitAudioContext;
  if (!A) return;
  if (!bell.audio) bell.audio = new A();
  if (bell.audio.state === 'suspended') bell.audio.resume().catch(() => {});
}
document.addEventListener('pointerdown', bellAudio, { capture: true });
document.addEventListener('keydown', bellAudio, { capture: true });
function bellBadge() {
  const n = bell.count;
  const a = $('#nav a[href="#/orders"]');
  if (a) {
    let b = a.querySelector('.nav-count');
    if (n && !b) a.append(b = el('span', { class: 'nav-count', 'aria-label': n + ' νέες online' }));
    if (b) { if (n) b.textContent = String(n); else b.remove(); }
  }
  if (n) $('#menu').dataset.n = String(n); else delete $('#menu').dataset.n;
  document.title = (n ? `(${n}) ` : '') + bell.title;
}
async function bellCheck() {
  if (!session || !may('ORDERS')) return;
  let r;
  try { r = await api('orders/new'); } catch (e) { return; }      // the network: next time
  bell.count = r.count || 0;
  const last = r.last_id || 0;
  if (bell.seen === null) bell.seen = last;                        // the first time: no sound
  else if (last > bell.seen) {
    bell.seen = last;
    bellSound();
    toast('Νέα online παραγγελία: ' + (r.last_name || '') + ' · Παραγγελίες');
    // the list of the orders open (no new one being written): shown again with it
    const f = $('main form input[name=name]');
    if (location.hash.startsWith('#/orders') && !(f && f.value) && !($('main form input[name=phone]') || {}).value) render();
  }
  bellBadge();
}
// back to the tab (a browser asks seldom in a tab in the background): at once
window.addEventListener('focus', () => { if (bell.timer) bellCheck(); });
function bellStart() {
  if (bell.timer) return;
  bellCheck();
  bell.timer = setInterval(bellCheck, 30000);
}
// -- the backup (db/backup.ps1): a manager sees on every page when the last good one is too old or the
// last one failed; asked at the login and every 30 minutes
const backupCheck = { timer: null };
async function backupNotice() {
  const box = $('#notice');
  if (!session || !may('DAY')) { box.hidden = true; return; }
  let r;
  try { r = await api('backup'); } catch (e) { return; }
  const text = {
    NEVER: 'Δεν έχει γίνει ακόμα backup της βάσης: backup.ps1 -Install στο PC του μαγαζιού.',
    OLD: `Το τελευταίο backup της βάσης έγινε πριν από ${Math.floor(r.days)} μέρες (${day(r.ok_at)}): backup.ps1 -Status στο PC του μαγαζιού.`,
    FAILED: `Το τελευταίο backup της βάσης απέτυχε (${day(r.failed_at)}): ${r.error || ''}`,
  }[r.state];
  box.textContent = text || '';
  box.hidden = !text;
}
function backupStart() {
  if (backupCheck.timer) return;
  backupNotice();
  backupCheck.timer = setInterval(backupNotice, 30 * 60000);
}
function bellStop() {
  clearInterval(backupCheck.timer);
  backupCheck.timer = null;
  $('#notice').hidden = true;
  clearInterval(bell.timer);
  Object.assign(bell, { timer: null, seen: null, count: 0 });
  bellBadge();
}

// the address of the shop, once (the app): asked, its service checked (/api/health), kept on the phone
function serverPage() {
  $('#top').hidden = true;
  const addr = el('input', { name: 'server', inputmode: 'url', autocomplete: 'off', placeholder: 'π.χ. 192.168.1.10:8090', value: server.replace(/^https?:\/\//, '') });
  const msg = el('p', { class: 'neg', role: 'alert' });
  const form = el('form', {
    onsubmit: async (ev) => {
      ev.preventDefault();
      msg.textContent = '';
      let v = addr.value.trim().replace(/\/+$/, '');
      if (!v) return;
      if (!/^https?:\/\//i.test(v)) v = 'http://' + v;
      if (!/:\d+$/.test(v.replace(/^https?:\/\//i, ''))) v += ':8090';
      try {
        const r = await fetch(v + '/api/health');
        if (!r.ok) throw new Error();
        if (v !== server) logoutLocal(true);
        server = v;
        try { localStorage.setItem('mm.server', server); } catch (e) { /* kept for this time only */ }
        render();
      } catch (e) {
        msg.textContent = 'Δεν απαντά: ' + v + '. Είναι το κινητό στο WiFi του μαγαζιού, και τρέχει το mm-api εκεί;';
      }
    },
  }, el('label', {}, 'Η διεύθυνση του μαγαζιού', addr), el('button', { class: 'primary', type: 'submit' }, 'Σύνδεση'), msg);
  show(el('div', { class: 'panel login' }, el('h1', {}, 'Mini market'),
    el('p', { class: 'muted' }, 'Η διεύθυνση του υπολογιστή όπου τρέχει το mm-api (run_api.ps1 -Bind 0.0.0.0).'), form));
  addr.focus();
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
        session = { token: r.token, username: r.username, role: r.role, warehouse_id: r.warehouse_id, warehouse: r.warehouse,
          warehouse_name: r.warehouse_name, register: r.register };
        sessionStorage.setItem('mm', JSON.stringify(session));
        await loadRights();
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
  show(el('div', { class: 'panel login' }, el('h1', {}, 'Mini market'), form,
    APP ? el('p', { class: 'muted' }, 'Μαγαζί: ' + server + ' · ', el('a', {
      href: '#', onclick: (ev) => { ev.preventDefault(); serverPage(); },
    }, 'αλλαγή')) : null));
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
  show(el('h1', {}, 'Είδη'), el('div', { class: 'panel row' }, el('label', { style: null }, 'Αναζήτηση', q), camera(q)), out);
  q.focus();
  go();
}

async function itemPage(code) {
  try {
    const x = await api('items/' + encodeURIComponent(code));
    // (a field the user may not read: not there)
    const f = (item, row) => (may('ITEMS', item) ? [row] : []);
    const rows = [['Κωδικός', x.code], ['Barcode', x.barcode], ['Κατηγορία', x.category], ['Μονάδα', x.unit],
      ...f('PRICE', ['Τιμή λιανικής', money(x.price)]), ...f('WHOLESALE_PRICE', ['Χονδρική', money(x.wholesale_price)]),
      ['ΦΠΑ', x.vat_code + ' ' + x.vat_rate + '%'],
      ...f('STOCK', ['Απόθεμα', qty(x.stock)]), ...f('STOCK', ['Δεσμευμένα', qty(x.reserved)]), ...f('STOCK', ['Διαθέσιμα', qty(x.available)]),
      ...f('MIN_STOCK', ['Ελάχιστο', qty(x.min_stock)])];
    if (x.serial_tracked === 'Y') rows.push(['Διαθέσιμες κάρτες', x.cards]);
    if (may('ITEMS', 'COST')) rows.splice(6, 0, ['Κόστος (τελευταία αγορά)', money(x.cost)]);
    if (may('ITEMS', 'FIFO')) rows.splice(7, 0, ['Κόστος FIFO (επόμενο)', x.fifo_next === null ? '' : money4(x.fifo_next)]);
    show(el('h1', {}, x.name),
      el('div', { class: 'panel' }, el('dl', { class: 'kv' }, rows.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v ?? '')]))),
      // more than one warehouse (the central store, the branches): its stock in each
      x.warehouses && x.warehouses.length > 1 && may('ITEMS', 'STOCK') ? el('div', { class: 'panel' }, el('h2', {}, 'Απόθεμα ανά αποθήκη'),
        table([['Αποθήκη'], ['Απόθεμα', 'num'], ['Ελάχιστο', 'num']], x.warehouses.map((w) => el('tr', {},
          el('td', {}, `${w.code} ${w.name}` + (w.main === 'Y' ? ' (κεντρική)' : '')),
          el('td', { class: 'num' + (w.stock < w.min_stock ? ' neg' : '') }, qty(w.stock)),
          el('td', { class: 'num' }, may('WAREHOUSES') && w.main !== 'Y' ? el('a', { href: '#/warehouse/' + w.id }, qty(w.min_stock)) : qty(w.min_stock)))))) : null,
      may('ITEMS', 'FIFO') && x.fifo && x.fifo.length ? el('div', { class: 'panel' }, el('h2', {}, `Το απόθεμα ανά παραλαβή (FIFO): ${money(x.fifo_value)} €`),
        el('p', { class: 'muted' }, 'Πρώτα φεύγουν τα παλιότερα, με το κόστος τους.'),
        table([['Παραλαβή'], ['Από'], ['Ποσότητα', 'num'], ['Μένουν', 'num'], ['Κόστος', 'num'], ['Αξία', 'num']],
          fifoRows(x.fifo).map((f) => el('tr', { class: f.left_ < 0 ? 'expired' : null },
            el('td', {}, f.left_ < 0 ? 'Έλλειμμα (πουλήθηκαν πριν έρθουν)' : day(f.in_at) + (f.n > 1 ? ' – ' + day(f.last_at) : '')),
            el('td', {}, f.n > 1 ? `${f.n} κινήσεις` : f.doc_id ? el('a', { href: '#/doc/' + f.doc_id }, `${f.doc_type} ${f.doc_no}`) : 'κίνηση αποθήκης'),
            num(f.qty, qty), num(f.left_, qty), num(f.unit_cost, money4), num(f.left_ * f.unit_cost))))) : null,
      el('div', { class: 'row' },
        el('button', { onclick: () => history.back() }, 'Πίσω'),
        el('button', { onclick: () => { labelAdd(x, 1); location.hash = '#/labels'; } }, 'Ετικέτα'),
        may('LEDGERS') && el('button', { class: 'primary', onclick: () => { location.hash = '#/ledger/item/' + x.id; } }, 'Καρτέλα')));
  } catch (e) {
    fail(e);
    show(el('h1', {}, 'Είδη'), el('p', { class: 'muted' }, 'Δεν βρέθηκε: ' + code), el('a', { href: '#/items' }, 'Στα είδη'));
  }
}

// the layers of an item one after another at the same cost: one row (the same for FIFO), its first and
// last date, how many
function fifoRows(layers) {
  const out = [];
  for (const f of layers) {
    const p = out[out.length - 1];
    if (p && f.left_ > 0 && p.left_ > 0 && f.unit_cost === p.unit_cost) {
      p.qty += f.qty; p.left_ += f.left_; p.n += 1; p.last_at = f.in_at;
    } else out.push({ ...f, n: 1, last_at: f.in_at });
  }
  return out;
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
      kind === 'customers' ? pointsBox(x) : null,
      el('div', { class: 'row' }, el('button', { onclick: () => history.back() }, 'Πίσω'),
        el('button', { class: 'primary', onclick: () => { location.hash = `#/ledger/${who}/${x.id}`; } }, 'Καρτέλα')));
  } catch (e) { fail(e); }
}

// -- the points of a customer: its card (a barcode, printed the size of a bank card), its points, their
// moves; a card for one without
function pointsBox(x) {
  const box = el('div', { class: 'panel' }, el('h2', {}, 'Κάρτα πόντων'));
  if (!x.card) {
    box.append(el('p', { class: 'muted' }, 'Ο πελάτης δεν έχει κάρτα πόντων.'),
      el('button', {
        type: 'button',
        onclick: async () => {
          try { await api(`customers/${x.id}/card`, {}); toast('Νέα κάρτα'); render(); } catch (e) { fail(e); }
        },
      }, 'Νέα κάρτα'));
    return box;
  }
  box.append(el('div', { class: 'row' }, loyaltyCard(x.name, x.card),
    el('div', {}, el('p', { class: 'big' }, `${x.points} πόντοι`),
      el('button', { type: 'button', onclick: () => printCard(x.name, x.card) }, 'Εκτύπωση κάρτας'))),
  x.point_moves.length ? table([['Ημέρα'], ['Απόδειξη'], ['Κίνηση'], ['Πόντοι', 'num']],
    x.point_moves.map((m) => el('tr', {}, el('td', {}, day(m.move_at)), el('td', {}, m.doc_no ? 'ΑΛΠ ' + m.doc_no : ''),
      el('td', {}, m.note || ''), num(m.points, (v) => (v > 0 ? '+' : '') + v))))
    : el('p', { class: 'muted' }, 'Καμία κίνηση πόντων ακόμα.'));
  return box;
}
function loyaltyCard(name, card) {
  const b = itemBars({ barcode: card, code: card });
  return el('div', { class: 'loyalty-card' }, el('div', { class: 'lc-title' }, 'Κάρτα πόντων'),
    el('div', { class: 'lc-name' }, name), el('div', { class: 'bc' }, barsSvg(b.bars), el('div', { class: 'digits' }, b.text)));
}
function printCard(name, card) {
  const old = document.getElementById('cardprint');
  if (old) old.remove();
  document.body.classList.remove('printing-doc', 'printing-receipt');
  document.body.append(el('div', { id: 'cardprint' }, loyaltyCard(name, card)));
  document.body.classList.add('printing-card');
  const done = () => { document.body.classList.remove('printing-card'); window.removeEventListener('afterprint', done); };
  window.addEventListener('afterprint', done);
  window.print();
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
  const titles = { sales: 'Πωλήσεις ανά ημέρα', vat: 'ΦΠΑ πωλήσεων και αγορών', 'min-stock': 'Είδη κάτω από το ελάχιστο απόθεμα',
    'trial-items': 'Ισοζύγιο ειδών', 'trial-customers': 'Ισοζύγιο πελατών', 'trial-suppliers': 'Ισοζύγιο προμηθευτών',
    profit: 'Μικτό κέρδος', 'stock-value': 'Αξία αποθήκης', 'sales-by': 'Πωλήσεις ανά κατάστημα, ταμείο και ταμία',
    consumption: 'Αναλώσεις (δελτία ανάλωσης)' };
  if (!titles[name]) { show(el('h1', {}, 'Δεν υπάρχει αυτή η αναφορά')); return; }
  const trial = name.startsWith('trial-');
  const all = el('input', { type: 'checkbox', name: 'all', checked: params.get('all') === '1' });
  const from = el('input', { type: 'date', value: params.get('from') || isoYearStart() });
  const to = el('input', { type: 'date', value: params.get('to') || isoToday() });
  const out = el('div');
  // the costs (the gross profit, the value of the stock): FIFO or the last purchase; the one of the shop by default
  const costs = name === 'profit' || name === 'stock-value' || name === 'consumption' || (name === 'sales-by' && may('PROFIT'));
  // the sales by: store, register, cashier
  const by = el('select', { name: 'by' }, [['warehouse', 'Κατάστημα'], ['register', 'Ταμείο'], ['user', 'Ταμίας']]
    .map(([k, t]) => el('option', { value: k, selected: (params.get('by') || 'warehouse') === k }, t)));
  let rwhs = [];
  if (name === 'stock-value' || name === 'consumption') {
    try { rwhs = (await api('warehouses')).rows; } catch (e) { rwhs = []; }
  }
  const rwh = el('select', { name: 'warehouse' }, ...options(rwhs, 'code', (w) => `${w.code} ${w.name}`, params.get('warehouse') || '', 'Όλες οι αποθήκες'));
  const method = el('select', { name: 'method' }, el('option', { value: 'FIFO' }, 'FIFO (πρώτα τα παλιότερα)'),
    el('option', { value: 'LAST' }, 'Τελευταία τιμή αγοράς'));
  const makeDefault = el('button', {
    type: 'button',
    onclick: async () => {
      try { await api('reports/cost-method', { method: method.value }); toast('Η μέθοδος κόστους του συστήματος: ' + method.selectedOptions[0].text); go(); } catch (e) { fail(e); }
    },
  }, 'Να είναι η μέθοδος του συστήματος');
  makeDefault.hidden = !act('STOCK_VALUE', 'COST_METHOD');
  let first = true;
  const go = async () => {
    try {
      const m = costs ? (first ? params.get('method') || '' : method.value) : '';
      const r = await api(`reports/${name}?from=${from.value}&to=${to.value}` + (trial && all.checked ? '&all=1' : '') + (m ? '&method=' + m : '')
        + (name === 'sales-by' ? '&by=' + by.value : '')
        + (rwhs.length > 1 && rwh.value ? '&warehouse=' + encodeURIComponent(rwh.value) : ''));
      first = false;
      if (costs) { method.value = r.method; makeDefault.hidden = !r.default_method || r.method === r.default_method || !act('STOCK_VALUE', 'COST_METHOD'); }
      out.replaceChildren(trial ? trialTable(name, r, from.value, to.value) : name === 'sales' ? salesTable(r.rows) : name === 'vat' ? vatTable(r.rows)
        : name === 'profit' ? profitTable(r) : name === 'stock-value' ? stockValueTable(r) : name === 'sales-by' ? salesByTable(r)
          : name === 'consumption' ? consumptionTable(r) : minTable(r.rows));
      if (name === 'min-stock' && r.rows.length && act('REP_MIN_STOCK', 'ORDER')) out.append(orderBox(r.rows));
    } catch (e) { fail(e); }
  };
  const form = name === 'min-stock' ? null
    : el('form', { class: 'panel row', onsubmit: (ev) => { ev.preventDefault(); go(); } },
      name === 'stock-value' ? null : el('label', {}, 'Από', from), name === 'stock-value' ? null : el('label', {}, 'Έως', to),
      name === 'sales-by' ? el('label', {}, 'Ανά', by) : null,
      costs ? el('label', {}, 'Μέθοδος κόστους', method) : null,
      rwhs.length > 1 ? el('label', {}, 'Αποθήκη', rwh) : null,
      trial ? el('label', { class: 'check' }, all, 'Και όσα έχουν μηδέν παντού') : null,
      el('button', { class: 'primary', type: 'submit' }, 'Εμφάνιση'), costs ? makeDefault : null);
  show(el('h1', {}, titles[name]), form, out);
  go();
}
// the consumptions: by warehouse and reason, their items, how many, what they cost; a subtotal of each
function consumptionTable(r) {
  if (!r.rows.length) return el('p', { class: 'muted' }, 'Καμία ανάλωση σε αυτό το διάστημα.');
  const out = [];
  let key = null;
  let sub = 0;
  let all = 0;
  const close = () => { if (key !== null) out.push(el('tr', { class: 'total' }, el('td', { colspan: 4 }, 'Σύνολο ' + key), num(sub))); };
  for (const x of r.rows) {
    const k = `${x.warehouse} · ${REASONS[x.reason] || x.reason}`;
    if (k !== key) { close(); key = k; sub = 0; out.push(el('tr', { class: 'group' }, el('th', { colspan: 5 }, k))); }
    sub += x.cost || 0;
    all += x.cost || 0;
    out.push(el('tr', {}, el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.qty, qty), el('td', { class: 'num hide-phone' }, x.docs), num(x.cost)));
  }
  close();
  out.push(el('tr', { class: 'total' }, el('td', { colspan: 4 }, `Γενικό σύνολο (${r.method === 'LAST' ? 'τελευταία τιμή αγοράς' : 'FIFO'})`), num(all)));
  return table([['Κωδικός'], ['Είδος'], ['Ποσότητα', 'num'], ['Δελτία', 'num hide-phone'], ['Κόστος', 'num']], out);
}
// the sales by store, register or cashier: documents (receipts and invoices, less credit notes), net, total, the
// average; with a right to the gross profit, what they cost and the profit
function salesByTable(r) {
  const cost = r.rows.some((x) => x.cost !== null);
  const head = { warehouse: 'Κατάστημα', register: 'Ταμείο', user: 'Ταμίας' }[r.by];
  const sum = (k) => r.rows.reduce((a, x) => a + (x[k] || 0), 0);
  return table([[head], ['Παραστατικά', 'num'], ['Καθαρά', 'num'], ['Σύνολο', 'num'], ['Μέση απόδειξη', 'num hide-phone'],
    ...(cost ? [['Κόστος', 'num hide-phone'], ['Μικτό κέρδος', 'num']] : [])],
  [...r.rows.map((x) => el('tr', {}, el('td', {}, x.name || (r.by === 'register' ? 'Γραφείο (τιμολόγια)' : '-')),
    el('td', { class: 'num' }, x.docs), num(x.net), num(x.total), num(x.avg_total, money, 'num hide-phone'),
    ...(cost ? [num(x.cost, money, 'num hide-phone'), num(x.profit)] : []))),
  el('tr', { class: 'total' }, el('td', {}, 'Σύνολο'), el('td', { class: 'num' }, sum('docs')), num(sum('net')), num(sum('total')),
    el('td', { class: 'hide-phone' }), ...(cost ? [num(sum('cost'), money, 'num hide-phone'), num(sum('profit'))] : []))]);
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
// the gross profit of the items in a period: the net of the sales less what they cost, by the method
// chosen (FIFO: the oldest first, at their costs; LAST: at the cost of the last purchase then), the cost
// by the other beside it; the differences of the stock (counts, withdrawals) apart
const METHOD = { FIFO: 'FIFO', LAST: 'τελευταίας αγοράς' };
function profitTable(r) {
  if (!r.rows.length) return el('p', { class: 'muted' }, 'Καμία πώληση στο διάστημα.');
  const other = r.method === 'LAST' ? 'FIFO' : 'LAST';
  const otherCost = (x) => (other === 'LAST' ? x.cost_last : x.cost_fifo);
  const t = r.rows.reduce((a, x) => ({ revenue: a.revenue + x.revenue, cost: a.cost + x.cost, profit: a.profit + x.profit, other: a.other + otherCost(x) }),
    { revenue: 0, cost: 0, profit: 0, other: 0 });
  const pct = (p, v) => (v ? nf2.format(p / v * 100) + '%' : '');
  const fig = (label, value, note) => el('div', { class: 'fig' }, el('div', { class: 'fig-label' }, label), el('div', { class: 'fig-value' }, value),
    note ? el('div', { class: 'fig-note' }, note) : null);
  return el('div', {},
    el('div', { class: 'figs' },
      fig('Καθαρές πωλήσεις', money(t.revenue) + ' €'),
      fig(`Κόστος (${METHOD[r.method]})`, money(t.cost) + ' €', `με ${METHOD[other]}: ${money(t.other)} €`),
      fig('Μικτό κέρδος', money(t.profit) + ' €', `${pct(t.profit, t.revenue)} · με ${METHOD[other]}: ${money(t.revenue - t.other)} €`),
      fig('Διαφορές αποθήκης (απογραφές, αποσύρσεις)', (r.stock_diff > 0 ? '−' : r.stock_diff < 0 ? '+' : '') + money(Math.abs(r.stock_diff)) + ' €',
        r.stock_diff > 0 ? 'έλλειμμα: λιγότερα από όσα έπρεπε' : r.stock_diff < 0 ? 'περίσσευμα: περισσότερα από όσα έπρεπε' : null)),
    table([['Κωδικός', 'hide-phone'], ['Είδος'], ['Ποσότητα', 'num'], ['Πωλήσεις', 'num'], [`Κόστος ${METHOD[r.method]}`, 'num'],
      [`Κόστος ${METHOD[other]}`, 'num hide-phone muted-col'], ['Κέρδος', 'num'], ['%', 'num hide-phone']],
    [...r.rows.map((x) => el('tr', {}, el('td', { class: 'hide-phone' }, x.code), el('td', { class: 'wrap' }, x.name),
      num(x.qty, qty), num(x.revenue), num(x.cost), num(otherCost(x), money, 'num hide-phone muted-col'), num(x.profit),
      el('td', { class: 'num hide-phone' }, pct(x.profit, x.revenue)))),
    el('tr', { class: 'total' }, el('td', { class: 'hide-phone' }), el('td', {}, 'Σύνολο'), el('td'), num(t.revenue), num(t.cost),
      num(t.other, money, 'num hide-phone muted-col'), num(t.profit), el('td', { class: 'num hide-phone' }, pct(t.profit, t.revenue)))]));
}
// the value of the stock now: by the method chosen, by the other beside it
function stockValueTable(r) {
  const rows = r.rows;
  if (!rows.length) return el('p', { class: 'muted' }, 'Κανένα απόθεμα.');
  const sum = (k) => rows.reduce((a, x) => a + x[k], 0);
  const [mine, theirs] = r.method === 'LAST' ? ['value_last', 'value_fifo'] : ['value_fifo', 'value_last'];
  const other = r.method === 'LAST' ? 'FIFO' : 'LAST';
  return el('div', {},
    el('div', { class: 'figs' },
      el('div', { class: 'fig' }, el('div', { class: 'fig-label' }, `Αξία αποθήκης (${METHOD[r.method]})`), el('div', { class: 'fig-value' }, money(sum(mine)) + ' €'),
        el('div', { class: 'fig-note' }, `με ${METHOD[other]}: ${money(sum(theirs))} €`))),
    table([['Κατηγορία', 'hide-phone'], ['Κωδικός'], ['Είδος'], ['Απόθεμα', 'num'], ['Κόστος FIFO', 'num hide-phone'], ['Τελευταίας αγοράς', 'num hide-phone'],
      [`Αξία ${METHOD[r.method]}`, 'num'], [`Αξία ${METHOD[other]}`, 'num hide-phone muted-col']],
    [...rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = '#/item/' + encodeURIComponent(x.code); } },
      el('td', { class: 'hide-phone' }, x.category), el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.stock, qty),
      num(x.unit_cost, money4, 'num hide-phone'), num(x.last_cost, money4, 'num hide-phone'), num(x[mine]), num(x[theirs], money, 'num hide-phone muted-col'))),
    el('tr', { class: 'total' }, el('td', { class: 'hide-phone' }), el('td', {}, 'Σύνολο'), el('td'), el('td'), el('td', { class: 'hide-phone' }),
      el('td', { class: 'hide-phone' }), num(sum(mine)), num(sum(theirs), money, 'num hide-phone muted-col'))]));
}
function vatTable(rows) {
  const sums = ['s_net', 's_vat', 'p_net', 'p_vat', 'payable'];
  return table([['ΦΠΑ'], ['Καθαρά πωλ.', 'num'], ['ΦΠΑ πωλ.', 'num'], ['Καθαρά αγορ.', 'num'], ['ΦΠΑ αγορ.', 'num'], ['Προς απόδοση', 'num']],
    byMonth(rows, (x) => x.month.slice(5) + '/' + x.month.slice(0, 4),
      (x) => [el('td', {}, x.vat_code + ' ' + x.vat_rate + '%'), num(x.s_net), num(x.s_vat), num(x.p_net), num(x.p_vat), num(x.payable)],
      sums, (s) => sums.map((k) => num(s[k]))));
}
// a trial balance (ισοζύγιο): a row each, the totals of its ledger (no moves); a row opens its ledger for
// the same period. The items in quantities (no total of them: kilos and pieces), the partners in euros
function trialTable(name, r, f, t) {
  const item = name === 'trial-items';
  const who = { 'trial-items': 'item', 'trial-customers': 'customer', 'trial-suppliers': 'supplier' }[name];
  const fmt = item ? qty : money;
  const head = item ? [['Κωδικός'], ['Περιγραφή'], ['Μ.Μ.', 'hide-phone'], ['Από μεταφορά', 'num'], ['Εισαγωγές', 'num'], ['Εξαγωγές', 'num'], ['Απόθεμα', 'num']]
    : [['ΑΦΜ', 'hide-phone'], ['Επωνυμία'], ['Από μεταφορά', 'num'], ['Χρέωση', 'num'], ['Πίστωση', 'num'], ['Υπόλοιπο', 'num']];
  if (!r.rows.length) return el('p', { class: 'muted' }, 'Καμία κίνηση και κανένα υπόλοιπο σε αυτό το διάστημα.');
  const rows = r.rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = `#/ledger/${who}/${x.id}?from=${f}&to=${t}`; } },
    item ? el('td', {}, x.code) : el('td', { class: 'hide-phone' }, x.code || ''), el('td', { class: 'wrap' }, x.name),
    item ? el('td', { class: 'hide-phone' }, x.unit || '') : null,
    num(x.open_bal, fmt), num(x.debit, fmt), num(x.credit, fmt), num(x.close_bal, fmt)));
  if (!item) {
    const s = r.totals;
    rows.push(el('tr', { class: 'total' }, el('td', { class: 'hide-phone' }), el('td', {}, 'Σύνολα'),
      num(s.open_bal), num(s.debit), num(s.credit), num(s.close_bal)));
  }
  return el('div', {}, el('p', { class: 'muted' }, `${day(r.from)} - ${day(r.to)} · ${r.rows.length} ` + (item ? 'είδη' : name === 'trial-customers' ? 'πελάτες' : 'προμηθευτές')),
    table(head, rows));
}
// the orders to the suppliers from the minimum stock: a draft delivery note of purchase each (the last
// supplier of the items; its draft, if there is one), printed as an order, posted when the goods come
function orderBox(rows) {
  const box = el('div', { class: 'panel' });
  const none = rows.filter((x) => !x.supplier).length;
  const draw = (r) => box.replaceChildren(el('h2', {}, 'Παραγγελίες σε προμηθευτές'),
    r ? el('p', {}, `${r.lines} γραμμές μπήκαν σε πρόχειρα δελτία παραλαβής:`) : el('p', { class: 'muted' },
      'Ένα πρόχειρο δελτίο παραλαβής για κάθε προμηθευτή (τον τελευταίο κάθε είδους), με όσα λείπουν, στο κόστος. Τυπώνεται ως παραγγελία· όταν έρθουν τα είδη, διόρθωσε τις ποσότητες και καταχώρισέ το.'
      + (none ? ` ${none} είδη δεν έχουν ακόμα προμηθευτή και μένουν έξω.` : '')),
    r ? el('ul', {}, r.drafts.map((x) => el('li', {}, el('a', { href: '#/doc/' + x.id }, `${x.supplier}: ${x.lines} είδη, ${money(x.total)}`))))
      : el('button', {
        type: 'button', class: 'primary',
        onclick: async () => { try { draw(await api('docs/from-min-stock', {})); } catch (e) { fail(e); } },
      }, 'Φτιάξε τις παραγγελίες'));
  draw(null);
  return box;
}
function minTable(rows) {
  if (!rows.length) return el('p', { class: 'muted' }, 'Κανένα είδος κάτω από το ελάχιστο.');
  return table([['Κατηγορία', 'hide-phone'], ['Κωδικός'], ['Περιγραφή'], ['Απόθεμα', 'num'], ['Ελάχιστο', 'num'], ['Λείπουν', 'num'],
    ['Τελευταίος προμηθευτής', 'hide-phone']],
  rows.map((x) => el('tr', {}, el('td', { class: 'hide-phone' }, x.category), el('td', {}, x.code), el('td', { class: 'wrap' }, x.name),
    num(x.stock, qty), num(x.min_stock, qty), num(x.missing, qty), el('td', { class: 'hide-phone' }, x.supplier || ''))));
}

// -- the summary of a day (σύνοψη ημέρας), after the Z: the Z of the registers, the sales and their VAT,
// the items sold most, the scratch tickets, the orders, myDATA, the minimum stock, the backup. A day back
// and forth; printed on A4
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
function dayShift(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  return isoDay(new Date(y, m - 1, d + n));
}
const MYDATA_STATE = { '-': 'Δεν στάλθηκαν', Q: 'Σε αναμονή', S: 'Διαβιβάστηκαν', E: 'Απέτυχαν', X: 'Ακυρώθηκαν' };
const BACKUP_STATE = { OK: 'Εντάξει', OLD: 'Παλιό', FAILED: 'Απέτυχε', NEVER: 'Δεν έγινε ποτέ' };
async function dayPage(params) {
  const date = params.get('date') || isoDay(new Date());
  const go = (d) => { location.hash = '#/day?date=' + d; };
  const pick = el('input', { type: 'date', name: 'date', value: date, onchange: () => pick.value && go(pick.value) });
  const out = el('div', { class: 'day-sheet' });
  const pair = (k, v, bad) => el('tr', { class: bad ? 'neg' : null }, el('th', {}, k), el('td', { class: 'num' }, v));
  const box = (title, ...kids) => el('section', { class: 'day-box' }, el('h2', {}, title), ...kids);
  show(el('h1', {}, 'Σύνοψη ημέρας ' + day(date)),
    el('div', { class: 'panel row no-print' },
      el('button', { type: 'button', onclick: () => go(dayShift(date, -1)) }, '‹ Προηγούμενη'),
      el('label', {}, 'Ημέρα', pick),
      el('button', { type: 'button', onclick: () => go(dayShift(date, 1)) }, 'Επόμενη ›'),
      el('button', { type: 'button', class: 'primary', onclick: () => window.print() }, 'Εκτύπωση')),
    out);
  let r;
  try { r = await api('day?date=' + date); } catch (e) { fail(e); return; }
  const zs = r.zs.length
    ? table([['Ταμείο'], ['Ζ', 'num'], ['Άνοιξε', 'hide-phone'], ['Έκλεισε'], ['Αποδείξεις', 'num'], ['Σύνολο', 'num'], ['Μετρητά', 'num'],
      ['Κάρτα', 'num'], ['Μπήκαν', 'num hide-phone'], ['Βγήκαν', 'num hide-phone'], ['Συρτάρι', 'num']],
    r.zs.map((z) => el('tr', {}, el('td', {}, z.register_name), el('td', { class: 'num' }, z.z_no),
      el('td', { class: 'hide-phone' }, day(z.opened_at)), el('td', {}, z.status === 'O' ? 'ανοιχτό' : day(z.closed_at)),
      el('td', { class: 'num' }, z.docs), num(z.total), num(z.cash), num(z.card),
      num(z.money_in, money, 'num hide-phone'), num(z.money_out, money, 'num hide-phone'), num(z.drawer))))
    : el('p', { class: 'muted' }, 'Κανένα Ζ αυτή την ημέρα.');
  const s = r.sales;
  const vat = r.vat.length
    ? table([['ΦΠΑ'], ['Καθαρή αξία', 'num'], ['ΦΠΑ', 'num'], ['Σύνολο', 'num']],
      r.vat.map((v) => el('tr', {}, el('td', {}, v.vat_rate + '%'), num(v.net), num(v.vat), num(v.net + v.vat))))
    : el('p', { class: 'muted' }, 'Καμία πώληση.');
  const top = r.top.length
    ? table([['#', 'num'], ['Κωδικός', 'hide-phone'], ['Είδος'], ['Ποσότητα', 'num'], ['Αξία', 'num']],
      r.top.map((x, i) => el('tr', {}, el('td', { class: 'num' }, i + 1), el('td', { class: 'hide-phone' }, x.code),
        el('td', { class: 'wrap' }, x.name), num(x.qty, qty), num(x.total))))
    : el('p', { class: 'muted' }, 'Κανένα είδος δεν πουλήθηκε.');
  const sc = r.scratch;
  const o = r.orders;
  const my = r.mydata;
  const b = r.backup;
  out.replaceChildren(
    box('Ζ ταμείων', zs),
    el('div', { class: 'day-grid' },
      box('Πωλήσεις', el('table', { class: 'pairs' }, el('tbody', {},
        pair('Αποδείξεις λιανικής', `${s.alp_docs} · ${money(s.alp_total)}`),
        pair('Τιμολόγια', money(s.tpy_total)),
        pair('Πιστωτικά', money(s.ppy_total)),
        pair('Σύνολο', money(s.total)),
        pair('Καθαρές πωλήσεις (χωρίς ΦΠΑ)', money(r.profit.revenue)),
        pair(`Κόστος τους (${r.profit.method === 'LAST' ? 'τελευταία τιμή αγοράς' : 'FIFO'})`, money(r.profit.cost)),
        pair('Μικτό κέρδος', money(r.profit.profit) + (r.profit.revenue ? ` (${nf2.format(r.profit.profit / r.profit.revenue * 100)}%)` : ''), r.profit.profit < 0)))),
      box('ΦΠΑ πωλήσεων', vat),
      box('Σκρατς', el('table', { class: 'pairs' }, el('tbody', {},
        pair('Δελτία που πουλήθηκαν', `${sc.tickets} · ${money(sc.value)}`),
        pair('Κέρδη που πληρώθηκαν', `${sc.prizes} · ${money(sc.prizes_total)}`),
        pair('Διαφορά', money(sc.value - sc.prizes_total))))),
      box('Παραγγελίες', el('table', { class: 'pairs' }, el('tbody', {},
        pair('Νέες την ημέρα', `${o.new_} (online ${o.online_new})`),
        pair('Ανοιχτές τώρα', o.open_now),
        pair('Online χωρίς επιβεβαίωση', o.to_confirm, o.to_confirm > 0)))),
      box('myDATA', el('table', { class: 'pairs' }, el('tbody', {},
        ...(my.day.length ? my.day.map((x) => pair('Τιμολόγια ημέρας: ' + (MYDATA_STATE[x.state] || x.state).toLowerCase(), x.n, x.state === 'E'))
          : [pair('Τιμολόγια ημέρας', 0)]),
        pair('Σε αναμονή (όλες οι ημέρες)', my.waiting),
        pair('Απέτυχαν (όλες οι ημέρες)', my.failed, my.failed > 0)))),
      box('Αποθήκη και backup', el('table', { class: 'pairs' }, el('tbody', {},
        pair('Είδη κάτω από το ελάχιστο', r.min_stock, r.min_stock > 0),
        pair('Έληξαν (μένουν στο απόθεμα)', r.expiry.expired, r.expiry.expired > 0),
        pair(`Λήγουν σε ${r.expiry.days} ημέρες`, r.expiry.soon, r.expiry.soon > 0),
        pair('Backup', (BACKUP_STATE[b.state] || b.state) + (b.ok_at ? ' · ' + day(b.ok_at) : ''), b.state !== 'OK'))),
      r.min_stock > 0 ? el('p', { class: 'no-print' }, el('a', { href: '#/reports/min-stock' }, 'Τα είδη κάτω από το ελάχιστο ›')) : null,
      r.expiry.expired + r.expiry.soon > 0 ? el('p', { class: 'no-print' }, el('a', { href: '#/expiry' }, 'Οι λήξεις ›')) : null)),
    box('Τα 10 είδη με τις περισσότερες πωλήσεις', top),
    // the sales of the day by store and by cashier
    (r.by_warehouse || []).length > 1 ? box('Ανά κατάστημα', table([['Κατάστημα'], ['Παραστατικά', 'num'], ['Σύνολο', 'num']],
      r.by_warehouse.map((x) => el('tr', {}, el('td', {}, `${x.code} ${x.name}`), el('td', { class: 'num' }, x.docs), num(x.total))))) : null,
    (r.by_user || []).length ? box('Ανά ταμία', table([['Ταμίας'], ['Παραστατικά', 'num'], ['Σύνολο', 'num']],
      r.by_user.map((x) => el('tr', {}, el('td', {}, x.name || x.username), el('td', { class: 'num' }, x.docs), num(x.total))))) : null);
}

// -- the charts of the sales: by day (bars) with the same day a year before (a line), by hour (bars); the
// totals of the period as figures, against a year before. SVG drawn here, a tooltip on each day or hour,
// the numbers as a table too. One axis each; the colors by role (app.css: --series-1 this year, --series-2
// the year before)
const SVGNS = 'http://www.w3.org/2000/svg';
function sv(tag, attrs, ...kids) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) e.setAttribute(k, v);
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
function niceStep(v) {                 // a step of the axis: 1, 2, 2.5 or 5 x 10^n, just above v
  if (!(v > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}
const nf0 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 0 });
function barPath(x, w, y, y0, r) {     // a bar from the baseline y0 to y: its data end rounded, square at y0
  const h = Math.abs(y0 - y);
  const rr = Math.min(r, w / 2, h);
  if (h < 0.5) return '';
  if (y <= y0) return `M${x},${y0}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y0}Z`;
  return `M${x},${y0}V${y - rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y - rr}V${y0}Z`;
}
// a chart of bars (and a line) over bands: rows, bar(r) the bar, line(r) the line or null, label(r, i,
// band) the text under a band (or ''; band its width in px), tip(r) the lines of its tooltip
function barChart(wrap, { rows, bar, line, label, tip, aria }) {
  const W = Math.max(320, wrap.clientWidth || 720);
  const H = 240;
  const m = { l: 56, r: 12, t: 12, b: 28 };
  const vals = rows.flatMap((r) => [bar(r), line ? line(r) : 0]);
  const step = niceStep((Math.max(...vals, 0) - Math.min(...vals, 0)) / 4);
  const top = Math.max(step, Math.ceil(Math.max(...vals, 0) / step) * step);
  const bottom = Math.floor(Math.min(...vals, 0) / step) * step;
  const y = (v) => m.t + (H - m.t - m.b) * (top - v) / (top - bottom);
  const band = (W - m.l - m.r) / rows.length;
  const bw = Math.max(2, Math.min(24, band * 0.7));
  const x = (i) => m.l + band * i + band / 2;
  const svg = sv('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': aria, class: 'chart' });
  for (let v = bottom; v <= top + step / 2; v += step) {   // the grid at round steps, recessive; euros
    svg.append(sv('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: Math.abs(v) < step / 2 ? 'ch-base' : 'ch-grid' }),
      sv('text', { x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end', class: 'ch-axis' }, nf0.format(v) + ' €'));
  }
  rows.forEach((r, i) => {
    const t = label(r, i, band);
    if (t) svg.append(sv('text', { x: x(i), y: H - 8, 'text-anchor': 'middle', class: 'ch-axis' }, t));
    const d = barPath(x(i) - bw / 2, bw, y(bar(r)), y(0), 4);
    if (d) svg.append(sv('path', { d, class: 'ch-bar' }));
  });
  if (line) {
    svg.append(sv('polyline', { points: rows.map((r, i) => `${x(i)},${y(line(r))}`).join(' '), class: 'ch-line' }));
  }
  // the hover: the whole band is the target; a tooltip with its numbers, a marker on the line
  const tipBox = el('div', { class: 'ch-tip', hidden: true });
  const mark = line ? sv('circle', { r: 4, class: 'ch-dot', visibility: 'hidden' }) : null;
  const hl = sv('rect', { y: m.t, height: H - m.t - m.b, width: band, class: 'ch-hl', visibility: 'hidden' });
  svg.insertBefore(hl, svg.firstChild);
  if (mark) svg.append(mark);
  rows.forEach((r, i) => {
    const hit = sv('rect', { x: m.l + band * i, y: m.t, width: band, height: H - m.t - m.b, class: 'ch-hit' });
    const on = () => {
      hl.setAttribute('x', m.l + band * i);
      hl.setAttribute('visibility', 'visible');
      if (mark) { mark.setAttribute('cx', x(i)); mark.setAttribute('cy', y(line(r))); mark.setAttribute('visibility', 'visible'); }
      tipBox.replaceChildren(...tip(r).map((t, k) => el('div', { class: k ? null : 'ch-tip-head' }, t)));
      tipBox.hidden = false;
      const left = Math.min(Math.max(x(i) + 12, 0), W - tipBox.offsetWidth - 4);
      tipBox.style.left = (x(i) + 12 + tipBox.offsetWidth > W ? x(i) - 12 - tipBox.offsetWidth : left) + 'px';
      tipBox.style.top = m.t + 'px';
    };
    const off = () => { tipBox.hidden = true; hl.setAttribute('visibility', 'hidden'); if (mark) mark.setAttribute('visibility', 'hidden'); };
    hit.addEventListener('mouseenter', on);
    hit.addEventListener('mouseleave', off);
    hit.addEventListener('click', on);                   // a phone: a tap
    svg.append(hit);
  });
  wrap.replaceChildren(svg, tipBox);
}
async function chartPage(params) {
  const to = el('input', { type: 'date', name: 'to', value: params.get('to') || isoDay(new Date()) });
  const days = el('select', { name: 'days' }, [[7, '7 ημέρες'], [30, '30 ημέρες'], [91, '3 μήνες'], [364, 'Ένας χρόνος']]
    .map(([v, t]) => el('option', { value: v, selected: String(v) === (params.get('days') || '30') }, t)));
  const go = () => { location.hash = `#/chart?days=${days.value}&to=${to.value}`; };
  const figs = el('div', { class: 'figs' });
  const byDay = el('div', { class: 'ch-wrap' });
  const byHour = el('div', { class: 'ch-wrap' });
  const tableBox = el('details', { class: 'no-print' }, el('summary', {}, 'Τα νούμερα σε πίνακα'));
  show(el('h1', {}, 'Γράφημα πωλήσεων'),
    el('form', { class: 'panel row no-print', onsubmit: (ev) => { ev.preventDefault(); go(); } },
      el('label', {}, 'Διάστημα', days), el('label', {}, 'Έως', to), el('button', { class: 'primary', type: 'submit' }, 'Εμφάνιση')),
    figs,
    el('section', { class: 'panel' }, el('h2', {}, 'Πωλήσεις ανά ημέρα'),
      el('div', { class: 'legend' }, el('span', { class: 'sw sw-1' }), 'Φέτος', el('span', { class: 'sw sw-2' }), 'Πέρσι, την ίδια μέρα της εβδομάδας'),
      byDay),
    el('section', { class: 'panel' }, el('h2', {}, 'Αποδείξεις λιανικής ανά ώρα'), byHour),
    tableBox);
  let r;
  try { r = await api(`chart?days=${days.value}&to=${to.value}`); } catch (e) { fail(e); return; }
  const s = r.sums;
  const pct = s.last_year > 0 ? (s.total - s.last_year) / s.last_year * 100 : null;
  const fig = (label, value, note, cls) => el('div', { class: 'fig' }, el('div', { class: 'fig-label' }, label),
    el('div', { class: 'fig-value' }, value), note ? el('div', { class: 'fig-note ' + (cls || '') }, note) : null);
  figs.replaceChildren(
    fig(`Πωλήσεις ${day(r.from)} – ${day(r.to)}`, money(s.total) + ' €',
      pct === null ? 'πέρσι: καμία πώληση' : `${pct >= 0 ? '▲ +' : '▼ '}${nf2.format(pct)}% από πέρσι (${money(s.last_year)} €)`, pct === null ? '' : pct >= 0 ? 'up' : 'down'),
    fig('Αποδείξεις λιανικής', String(s.receipts), money(s.receipts_total) + ' €'),
    fig('Μέσο ποσό απόδειξης', s.avg_receipt === null ? '–' : money(s.avg_receipt) + ' €'));
  const many = r.days.length;
  const every = many <= 10 ? 1 : many <= 31 ? 3 : many <= 92 ? 7 : 30;
  const dm = (iso) => day(iso).slice(0, 5);
  const lastYear = (iso) => dayShift(iso, -364);
  const draw = () => {
    if (!document.body.contains(byDay)) { window.removeEventListener('resize', draw); return; }
    barChart(byDay, {
      rows: r.days,
      bar: (x) => x.total,
      line: (x) => x.last_year,
      label: (x, i, band) => ((many - 1 - i) % Math.max(every, Math.ceil(44 / band)) === 0 ? dm(x.day) : ''),   // (44px a date)
      tip: (x) => [day(x.day), `Φέτος: ${money(x.total)} €`, `Πέρσι (${day(lastYear(x.day))}): ${money(x.last_year)} €`, `Αποδείξεις: ${x.receipts}`],
      aria: 'Πωλήσεις ανά ημέρα, φέτος και πέρσι',
    });
    const used = r.hours.filter((h) => h.receipts > 0).map((h) => h.hour);
    const hours = used.length ? r.hours.filter((h) => h.hour >= Math.min(...used) && h.hour <= Math.max(...used)) : r.hours.slice(8, 22);
    barChart(byHour, {
      rows: hours,
      bar: (h) => h.total,
      line: null,
      label: (h, i, band) => (i % Math.ceil(22 / band) === 0 ? String(h.hour).padStart(2, '0') : ''),
      tip: (h) => [`${String(h.hour).padStart(2, '0')}:00 – ${String(h.hour).padStart(2, '0')}:59`, `Ποσό: ${money(h.total)} €`, `Αποδείξεις: ${h.receipts}`],
      aria: 'Αποδείξεις λιανικής ανά ώρα',
    });
  };
  draw();
  window.addEventListener('resize', draw);
  tableBox.append(table([['Ημέρα'], ['Φέτος', 'num'], ['Πέρσι', 'num'], ['Αποδείξεις', 'num']],
    r.days.slice().reverse().map((x) => el('tr', {}, el('td', {}, day(x.day)), num(x.total), num(x.last_year), el('td', { class: 'num' }, x.receipts)))));
}

// -- the expiry of the goods: the receipts with a date, what is left of each (FIFO: the oldest goes
// first), expired and expiring in N days; one taken out of the stock (a move by hand, its reason the date)
// the reasons of a consumption (Δελτίο ανάλωσης, DAN)
const REASONS = { USE: 'Ανάλωση (χρήση του καταστήματος)', DAMAGE: 'Φθορά', SAMPLE: 'Δείγμα', EXPIRED: 'Λήξη' };
async function expiryPage(params) {
  const sel = el('select', { name: 'days' });
  const out = el('div');
  // more than one warehouse: the goods of each (a transfer takes their expiry with it); the store of the user first
  let whs = [];
  try { whs = (await api('warehouses')).rows.filter((w) => w.active === 'Y'); } catch (e) { whs = []; }
  const mine = whs.find((w) => w.id === session.warehouse_id);
  const wh = el('select', { name: 'warehouse' }, ...options(whs, 'code', (w) => `${w.code} ${w.name}`,
    params.get('warehouse') || (mine ? mine.code : ''), 'Όλες οι αποθήκες'));
  const draw = (r) => {
    const opts = [...new Set([r.days, 7, 14, 30, 60])].sort((a, b) => a - b);
    sel.replaceChildren(...opts.map((v) => el('option', { value: v, selected: v === r.days }, `${v} ημέρες`)));
    const when = (x) => (x.days_left < 0 ? `έληξε πριν ${-x.days_left} ${-x.days_left === 1 ? 'ημέρα' : 'ημέρες'}`
      : x.days_left === 0 ? 'λήγει σήμερα' : `σε ${x.days_left} ${x.days_left === 1 ? 'ημέρα' : 'ημέρες'}`);
    const many = whs.length > 1;
    out.replaceChildren(r.rows.length ? table([['Λήξη'], ['Πότε'], ['Κωδικός', 'hide-phone'], ['Είδος'], ...(many ? [['Αποθήκη']] : []), ['Μένουν', 'num'], ['Παραλαβή', 'hide-phone'], ['Προμηθευτής', 'hide-phone'], ['']],
      r.rows.map((x) => el('tr', { class: x.days_left < 0 ? 'expired' : null },
        el('td', {}, day(x.expires)), el('td', { class: x.days_left < 0 ? 'neg' : null }, (x.days_left < 0 ? '⚠ ' : '') + when(x)),
        el('td', { class: 'hide-phone' }, x.code), el('td', { class: 'wrap' }, x.name), many ? el('td', {}, x.warehouse) : null,
        num(x.left_, qty), el('td', { class: 'hide-phone' }, x.doc_id ? el('a', { href: '#/doc/' + x.doc_id }, `${x.doc_type} ${x.doc_no} · ${day(x.doc_date)}`) : ''),
        el('td', { class: 'hide-phone wrap' }, x.supplier || ''),
        el('td', { class: 'num' }, el('button', {
          type: 'button',
          class: x.days_left < 0 ? 'danger' : null,
          onclick: async () => {
            const n = prompt(`Απόσυρση από το απόθεμα${many ? ' της ' + x.warehouse : ''}: ${x.code} ${x.name}, λήξη ${day(x.expires)}. Πόσα;`, String(x.left_));
            if (n === null || !n.trim()) return;
            try {
              const w = await api('expiry/withdraw', { fifo_id: x.fifo_id, qty: Number(n.replace(',', '.')) });
              await load();                          // (the list of the warehouse chosen, then the message)
              toast(`Αποσύρθηκαν ${qty(w.withdrawn)} ${x.code}`);
            } catch (e) { fail(e); }
          },
        }, 'Απόσυρση')))))
      : el('p', { class: 'muted' }, `Τίποτα δεν λήγει τις επόμενες ${r.days} ημέρες, και τίποτα δεν έχει λήξει.`));
  };
  const load = async () => {
    const q = new URLSearchParams();
    if (sel.value || params.get('days')) q.set('days', sel.value || params.get('days'));
    if (whs.length > 1 && wh.value) q.set('warehouse', wh.value);
    try { draw(await api('expiry?' + q)); } catch (e) { fail(e); }
  };
  sel.addEventListener('change', load);
  wh.addEventListener('change', load);
  show(el('h1', {}, 'Λήξεις'), el('p', { class: 'muted' },
    'Η ημερομηνία λήξης μπαίνει σε κάθε γραμμή της παραλαβής (δελτίο παραλαβής ή τιμολόγιο - δελτίο παραλαβής) και πηγαίνει με τα είδη όταν μεταφέρονται σε άλλη αποθήκη. Το «Μένουν» είναι ό,τι μένει από την παραλαβή στην αποθήκη: τα παλιότερα φεύγουν πρώτα.'),
  el('div', { class: 'panel row' }, el('label', {}, 'Λήγουν μέσα σε', sel), whs.length > 1 ? el('label', {}, 'Αποθήκη', wh) : null), out);
  await load();
}

// -- the warehouses: the central store and the branches; what each has (items, value by FIFO,
// registers); a new one; renamed, (not) active (the main one stays)
async function warehousesPage() {
  const out = el('div');
  const code = el('input', { name: 'wh_code', maxlength: 10, class: 'w6', placeholder: 'Y1' });
  const name = el('input', { name: 'wh_name', maxlength: 60, placeholder: 'Υποκατάστημα Ρίου' });
  const draw = (r) => out.replaceChildren(table([['Κωδικός'], ['Όνομα'], ['Είδη με απόθεμα', 'num'], ['Αξία (FIFO)', 'num'], ['Ταμεία', 'num hide-phone'],
    ['Κάτω από το ελάχιστο', 'num'], ['Ενεργή'], ['']],
    r.rows.map((w) => {
      const nm = el('input', { value: w.name, maxlength: 60, 'aria-label': 'Όνομα ' + w.code });
      return el('tr', { class: w.active === 'Y' ? null : 'cancelled' },
        el('td', {}, w.code + (w.main === 'Y' ? ' (κεντρική)' : '')), el('td', {}, nm),
        el('td', { class: 'num' }, w.items), num(w.value), el('td', { class: 'num hide-phone' }, w.registers),
        // the items under their minimum there: the central store, the report (orders to the suppliers);
        // a branch, its page (its minimum, goods sent from the central store)
        el('td', { class: 'num' + (w.under_min > 0 ? ' neg' : '') }, el('a', {
          href: w.main === 'Y' ? '#/reports/min-stock' : '#/warehouse/' + w.id,
          'aria-label': 'Ελάχιστο ' + w.code,
        }, String(w.under_min))),
        el('td', {}, w.main === 'Y' ? 'ναι' : el('input', {
          type: 'checkbox',
          checked: w.active === 'Y',
          'aria-label': 'Ενεργή ' + w.code,
          onchange: async (ev) => { try { draw(await api('warehouses/' + w.id, { active: ev.target.checked })); } catch (e) { fail(e); } },
        })),
        el('td', { class: 'num' }, el('button', {
          type: 'button',
          onclick: async () => { try { draw(await api('warehouses/' + w.id, { name: nm.value.trim() })); toast('Αποθηκεύτηκε'); } catch (e) { fail(e); } },
        }, 'Αποθήκευση'),
        el('a', { class: 'btn-link', href: '#/reports/stock-value?warehouse=' + encodeURIComponent(w.code) }, 'Αξία ›')));
    })));
  show(el('h1', {}, 'Αποθήκες'),
    el('p', { class: 'muted' }, 'Η κεντρική και τα υποκαταστήματα. Κάθε ταμείο πουλά από την αποθήκη του (Ταμείο → Αποθήκη)· από αποθήκη σε αποθήκη: Δελτίο ενδοδιακίνησης (DEN) στα «Τιμολόγια και δελτία».'),
    el('form', {
      class: 'panel row',
      onsubmit: async (ev) => {
        ev.preventDefault();
        try {
          draw(await api('warehouses', { code: code.value.trim(), name: name.value.trim() }));
          toast('Νέα αποθήκη ' + code.value.trim().toUpperCase());
          code.value = ''; name.value = '';
        } catch (e) { fail(e); }
      },
    }, el('label', {}, 'Κωδικός', code), el('label', { class: 'grow' }, 'Όνομα', name), el('button', { class: 'primary', type: 'submit' }, 'Νέα αποθήκη')),
    out);
  try { draw(await api('warehouses')); } catch (e) { fail(e); }
}

// -- a branch and its minimum stock: the minimum of each item there (0: none); the items under it, what
// is missing, what the central store has; what is missing, a draft transfer (DEN) from the central store,
// checked and posted in «Τιμολόγια και δελτία» when the goods leave
async function warehousePage(id) {
  const out = el('div');
  const code = el('input', { name: 'min_code', placeholder: 'Κωδικός ή barcode' });
  const min = el('input', { name: 'min_qty', type: 'number', step: 'any', min: '0', class: 'w6' });
  const draw = (r, lines) => {
    const w = r.warehouse;
    const under = r.rows.filter((x) => x.missing > 0);
    out.replaceChildren(
      el('h1', {}, `Ελάχιστο απόθεμα: ${w.code} ${w.name}`),
      w.main === 'Y' ? el('p', {}, 'Της κεντρικής: στο είδος (Ελάχιστο) και στην ', el('a', { href: '#/reports/min-stock' }, 'αναφορά ›')) : null,
      el('form', {
        class: 'panel row no-print',
        onsubmit: async (ev) => {
          ev.preventDefault();
          try {
            draw(await api(`warehouses/${id}/min`, { code: code.value.trim(), min: Number(min.value || 0) }));
            toast('Αποθηκεύτηκε'); code.value = ''; min.value = ''; code.focus();
          } catch (e) { fail(e); }
        },
      }, el('label', { class: 'grow' }, 'Είδος', code), camera(code), el('label', {}, 'Ελάχιστο', min),
      el('button', { class: 'primary', type: 'submit' }, 'Ορισμός')),
      el('p', { class: 'muted' }, 'Ελάχιστο 0: χωρίς ελάχιστο εκεί.'),
      r.rows.length ? table([['Κωδικός'], ['Περιγραφή'], ['Απόθεμα', 'num'], ['Ελάχιστο', 'num'], ['Λείπουν', 'num'], ['Κεντρικό', 'num hide-phone']],
        r.rows.map((x) => el('tr', { class: x.missing > 0 ? 'expired' : null },
          el('td', {}, el('a', { href: '#/item/' + encodeURIComponent(x.code) }, x.code)), el('td', { class: 'wrap' }, x.name),
          num(x.stock, qty), el('td', { class: 'num' }, el('input', {
            type: 'number', step: 'any', min: '0', value: x.min_stock, class: 'w6', 'aria-label': 'Ελάχιστο ' + x.code,
            onchange: async (ev) => { try { draw(await api(`warehouses/${id}/min`, { code: x.code, min: Number(ev.target.value || 0) })); } catch (e) { fail(e); } },
          })), num(x.missing, qty), num(x.central, qty, 'num hide-phone')))) : el('p', { class: 'muted' }, 'Κανένα είδος με ελάχιστο εδώ.'),
      w.main === 'Y' ? null : el('div', { class: 'panel' }, el('h2', {}, 'Από το κεντρικό'),
        lines !== undefined ? el('p', {}, `${lines} γραμμές μπήκαν στο πρόχειρο δελτίο ενδοδιακίνησης.`)
          : el('p', { class: 'muted' }, `${under.length} είδη κάτω από το ελάχιστο. Ένα πρόχειρο δελτίο ενδοδιακίνησης (DEN) από το κεντρικό, με όσα λείπουν (όχι περισσότερα από όσα έχει το κεντρικό), στο κόστος. Έλεγξέ το και καταχώρισέ το όταν φύγουν τα είδη.`),
        r.drafts.length ? el('ul', {}, r.drafts.map((d) => el('li', {}, el('a', { href: '#/doc/' + d.id }, `Πρόχειρο DEN ${day(d.doc_date)}: ${d.lines} γραμμές, ${money(d.total)} €`)))) : null,
        el('button', {
          type: 'button', class: 'primary', disabled: !under.length,
          onclick: async () => { try { const x = await api(`warehouses/${id}/transfer`, {}); draw(x, x.lines); } catch (e) { fail(e); } },
        }, 'Φτιάξε το δελτίο ενδοδιακίνησης')),
      el('div', { class: 'row' }, el('button', { onclick: () => { location.hash = '#/warehouses'; } }, 'Αποθήκες')));
  };
  show(out);
  try { draw(await api('warehouses/' + id)); } catch (e) { fail(e); }
}

// -- the users (ADMIN): a new one; each: its name, role, active, a new password, unlocked, and where it
// works: its store (the registers of it) and its register (the till opens on it; a cashier: only that)
async function usersPage() {
  let whs = [];
  let regs = [];
  try { whs = (await api('warehouses')).rows.filter((w) => w.active === 'Y'); } catch (e) { whs = []; }
  try { regs = (await api('pos')).rows; } catch (e) { regs = []; }
  const roles = [['CASHIER', 'Ταμίας'], ['MANAGER', 'Προϊστάμενος'], ['ADMIN', 'Διαχειριστής']];
  const roleSel = (v, label) => el('select', { 'aria-label': label }, roles.map(([k, t]) => el('option', { value: k, selected: k === v }, t)));
  const whSel = (v, label) => el('select', { 'aria-label': label }, el('option', { value: '' }, 'Όλα'),
    whs.map((w) => el('option', { value: w.id, selected: w.id === v }, `${w.code} ${w.name}`)));
  const regSel = (v, label) => el('select', { 'aria-label': label }, el('option', { value: '' }, 'Κανένα'),
    regs.map((r) => el('option', { value: r.id, selected: r.id === v }, `${r.code} ${r.name}`)));
  const num_ = (v) => (v ? Number(v) : null);
  const out = el('div');
  let allRoles = [];
  if (act('ROLES')) { try { allRoles = (await api('roles')).rows.filter((x) => x.active === 'Y'); } catch (e) { allRoles = []; } }
  // the roles of a user (more than one: the most of each); only with a right to change the roles
  const rolesOf = (x) => {
    const mine = new Set((x.roles || '').split(',').filter(Boolean));
    if (!allRoles.length) return el('span', {}, [...mine].join(', '));
    const boxes = allRoles.map((r) => el('label', { class: 'check' }, el('input', {
      type: 'checkbox', checked: mine.has(r.code), value: r.code, 'aria-label': `Ρόλος ${r.code} ${x.username}`,
      onchange: async () => {
        const roles = boxes.map((b) => b.querySelector('input')).filter((i) => i.checked).map((i) => i.value);
        try { draw(await api(`users/${x.id}/roles`, { roles })); toast('Οι ρόλοι του ' + x.username); } catch (e) { fail(e); draw(await api('users')); }
      },
    }), ' ' + r.name));
    return el('div', { class: 'roles' }, boxes);
  };
  const draw = (r) => out.replaceChildren(table([['Χρήστης'], ['Όνομα', 'hide-phone'], ['Επίπεδο'], ['Ρόλοι'], ['Κατάστημα'], ['Ταμείο'], ['Ενεργός'],
    ['Τελευταία σύνδεση', 'hide-phone'], ['']],
  r.rows.map((x) => {
    const full = el('input', { value: x.full_name || '', maxlength: 100, 'aria-label': 'Όνομα ' + x.username });
    const role = roleSel(x.role, 'Ρόλος ' + x.username);
    const w = whSel(x.warehouse_id, 'Κατάστημα ' + x.username);
    const g = regSel(x.register_id, 'Ταμείο ' + x.username);
    const act = el('input', { type: 'checkbox', checked: x.active === 'Y', 'aria-label': 'Ενεργός ' + x.username });
    const pw = el('input', { type: 'password', autocomplete: 'new-password', placeholder: 'νέος κωδικός', 'aria-label': 'Κωδικός ' + x.username, class: 'w11' });
    const save = async () => {
      const body = { full_name: full.value.trim() || null, warehouse_id: num_(w.value), register_id: num_(g.value) };
      if (role.value !== x.role) body.role = role.value;
      if (act.checked !== (x.active === 'Y')) body.active = act.checked;
      if (pw.value) body.password = pw.value;
      if (x.locked === 'Y') body.unlock = true;
      try { draw(await api('users/' + x.id, body)); toast('Αποθηκεύτηκε: ' + x.username); } catch (e) { pw.value = ''; fail(e); }
    };
    return el('tr', { class: x.active === 'Y' ? null : 'cancelled' },
      el('td', {}, x.username + (x.locked === 'Y' ? ' (κλειδωμένος)' : '')), el('td', { class: 'hide-phone' }, full),
      el('td', {}, role), el('td', {}, rolesOf(x)), el('td', {}, w), el('td', {}, g), el('td', {}, act),
      el('td', { class: 'hide-phone' }, x.last_login ? day(x.last_login) : ''),
      el('td', { class: 'num' }, pw, el('button', { type: 'button', onclick: save }, 'Αποθήκευση')));
  })));
  const uname = el('input', { name: 'new_username', maxlength: 30, placeholder: 'maria', autocomplete: 'off' });
  const ufull = el('input', { name: 'new_full_name', maxlength: 100, placeholder: 'Μαρία Π.' });
  const urole = roleSel('CASHIER', 'Ρόλος νέου χρήστη');
  const uwh = whSel(null, 'Κατάστημα νέου χρήστη');
  const ureg = regSel(null, 'Ταμείο νέου χρήστη');
  const upw = el('input', { name: 'new_password', type: 'password', autocomplete: 'new-password' });
  show(el('h1', {}, 'Χρήστες'),
    el('p', { class: 'muted' }, 'Το κατάστημα και το ταμείο του χρήστη: το ταμείο ανοίγει στο δικό του· ο ταμίας με ταμείο δουλεύει μόνο σε αυτό, με κατάστημα στα ταμεία του καταστήματος· ο προϊστάμενος στα ταμεία του καταστήματός του· ο διαχειριστής παντού. «Όλα»: χωρίς περιορισμό. Ταμείο χωρίς κατάστημα: το κατάστημα του ταμείου.'),
    el('form', {
      class: 'panel row',
      onsubmit: async (ev) => {
        ev.preventDefault();
        try {
          draw(await api('users', {
            username: uname.value.trim(), full_name: ufull.value.trim() || null, role: urole.value, password: upw.value,
            warehouse_id: num_(uwh.value), register_id: num_(ureg.value),
          }));
          toast('Νέος χρήστης ' + uname.value.trim().toLowerCase());
          uname.value = ''; ufull.value = ''; upw.value = '';
        } catch (e) { upw.value = ''; fail(e); }
      },
    }, el('label', {}, 'Χρήστης', uname), el('label', { class: 'grow' }, 'Όνομα', ufull), el('label', {}, 'Ρόλος', urole),
    el('label', {}, 'Κατάστημα', uwh), el('label', {}, 'Ταμείο', ureg), el('label', {}, 'Κωδικός', upw),
    el('button', { class: 'primary', type: 'submit' }, 'Νέος χρήστης')),
    out);
  try { draw(await api('users')); } catch (e) { fail(e); }
}

// -- the roles and their rights (MM_RIGHTS): the roles (new, renamed, active, out; the rights of another
// copied); of one role, the menu with what it may do: each screen N R W, its fields (as the screen, or N R
// W, never above it) and actions (as the screen: allowed when it is W; or N W); what it comes to
const LEVELS = { N: 'Τίποτα', R: 'Ανάγνωση', W: 'Αλλαγή' };
async function rolesPage(code) {
  const out = el('div');
  const head = el('div');
  const newCode = el('input', { name: 'role_code', maxlength: 30, placeholder: 'STORE_MGR', class: 'w11' });
  const newName = el('input', { name: 'role_name', maxlength: 100, placeholder: 'Υπεύθυνος καταστήματος' });
  const drawRoles = (r) => head.replaceChildren(table([['Κωδικός'], ['Όνομα'], ['Χρήστες', 'num'], ['Δικαιώματα', 'num hide-phone'], ['Ενεργός'], ['']],
    r.rows.map((x) => {
      const nm = el('input', { value: x.name, maxlength: 100, 'aria-label': 'Όνομα ρόλου ' + x.code });
      return el('tr', { class: (x.active === 'Y' ? '' : 'cancelled ') + (x.code === code ? 'on' : '') || null },
        el('td', {}, el('a', { href: '#/roles/' + x.code }, x.code), x.system === 'Y' ? ' (συστήματος)' : ''), el('td', {}, nm),
        el('td', { class: 'num' }, x.users), el('td', { class: 'num hide-phone' }, x.all_rights === 'Y' ? 'όλα' : x.grants),
        el('td', {}, x.system === 'Y' ? 'ναι' : el('input', {
          type: 'checkbox', checked: x.active === 'Y', 'aria-label': 'Ενεργός ρόλος ' + x.code,
          onchange: async (ev) => { try { drawRoles(await api('roles/' + x.code, { name: nm.value, active: ev.target.checked })); } catch (e) { fail(e); } },
        })),
        el('td', { class: 'num' },
          el('button', { type: 'button', onclick: async () => { try { drawRoles(await api('roles/' + x.code, { name: nm.value, active: x.active === 'Y' })); toast('Αποθηκεύτηκε'); } catch (e) { fail(e); } } }, 'Αποθήκευση'),
          x.system === 'Y' ? null : el('button', {
            type: 'button', class: 'danger',
            onclick: async () => {
              if (!confirm(`Διαγραφή του ρόλου ${x.code}; Οι χρήστες του τον χάνουν.`)) return;
              try { drawRoles(await api(`roles/${x.code}/delete`, {})); if (x.code === code) location.hash = '#/roles'; } catch (e) { fail(e); }
            },
          }, 'Διαγραφή')));
    })));
  // the rights of one role
  const drawGrants = (g, roles) => {
    const role = g.role;
    const all = role.all_rights === 'Y';
    const set = (screen, item) => async (ev) => {
      try { drawGrants(await api(`roles/${role.code}/grants`, { screen, item, level: ev.target.value || null }), roles); } catch (e) { fail(e); }
    };
    const pick = (v, opts, label, on) => el('select', { 'aria-label': label, disabled: all, onchange: on },
      opts.map(([k, t]) => el('option', { value: k, selected: (v || '') === k }, t)));
    const from = el('select', { 'aria-label': 'Αντιγραφή από' }, roles.filter((x) => x.code !== role.code && x.all_rights !== 'Y')
      .map((x) => el('option', { value: x.code }, `${x.code} ${x.name}`)));
    let group = null;
    const rows = [];
    for (const sc of g.screens) {
      if (sc.group_code !== group) {
        group = sc.group_code;
        rows.push(el('tr', { class: 'group' }, el('th', { colspan: 3 }, sc.group_name || '')));
      }
      const where = [sc.route ? 'σελίδα' : null, sc.form ? 'φόρμα ' + sc.form : null].filter(Boolean).join(', ');
      const items = sc.items.length ? el('details', {}, el('summary', {}, `Πεδία και ενέργειες (${sc.items.length})`),
        table([['Πεδίο / ενέργεια'], ['Δικαίωμα'], ['Ισχύει']], sc.items.map((i) => el('tr', {},
          el('td', {}, (i.kind === 'A' ? 'Ενέργεια: ' : 'Πεδίο: ') + i.name),
          el('td', {}, pick(i.grant, i.kind === 'A' ? [['', 'Όπως η οθόνη'], ['N', 'Όχι'], ['W', 'Ναι']]
            : [['', 'Όπως η οθόνη'], ['N', LEVELS.N], ['R', LEVELS.R], ['W', LEVELS.W]], `${sc.code}.${i.code}`, set(sc.code, i.code))),
          el('td', { class: i.lvl === 'N' ? 'muted' : null }, i.kind === 'A' ? (i.lvl === 'W' ? 'ναι' : 'όχι') : LEVELS[i.lvl]))))) : null;
      rows.push(el('tr', { class: sc.active === 'Y' ? null : 'cancelled' },
        el('td', { class: 'wrap' }, el('b', {}, sc.name), el('div', { class: 'muted' }, where), items),
        el('td', {}, pick(sc.grant || 'N', [['N', LEVELS.N], ['R', LEVELS.R], ['W', LEVELS.W]], sc.code, set(sc.code, null))),
        el('td', { class: sc.lvl === 'N' ? 'muted' : null }, LEVELS[sc.lvl])));
    }
    out.replaceChildren(el('h2', {}, `Τα δικαιώματα του ρόλου ${role.code}: ${role.name}`),
      all ? el('p', {}, 'Ο ρόλος αυτός έχει όλα τα δικαιώματα, πάντα.') : el('div', { class: 'panel row' },
        el('label', {}, 'Αντιγραφή από', from), el('button', {
          type: 'button',
          onclick: async () => {
            if (!confirm(`Τα δικαιώματα του ${role.code} γίνονται ίδια με του ${from.value};`)) return;
            try { drawGrants(await api(`roles/${role.code}/copy`, { from: from.value }), roles); toast('Αντιγράφηκαν'); } catch (e) { fail(e); }
          },
        }, 'Αντιγραφή')),
      el('p', { class: 'muted' }, 'Οθόνη: τίποτα, ανάγνωση ή αλλαγή. Πεδίο: όπως η οθόνη, ή λιγότερο. Ενέργεια: όπως η οθόνη (επιτρέπεται με «Αλλαγή»), ή ρητά ναι/όχι. Ένας χρήστης με πολλούς ρόλους παίρνει το περισσότερο του καθενός.'),
      table([['Οθόνη'], ['Δικαίωμα'], ['Ισχύει']], rows));
  };
  show(el('h1', {}, 'Ρόλοι και δικαιώματα'),
    el('p', {}, el('a', { href: '#/menu' }, 'Το μενού (ονόματα, σειρά, ομάδες) ›'), ' · ', el('a', { href: '#/users' }, 'Οι χρήστες και οι ρόλοι τους ›')),
    head,
    el('form', {
      class: 'panel row',
      onsubmit: async (ev) => {
        ev.preventDefault();
        try {
          drawRoles(await api('roles', { code: newCode.value.trim().toUpperCase(), name: newName.value.trim() }));
          location.hash = '#/roles/' + newCode.value.trim().toUpperCase();
        } catch (e) { fail(e); }
      },
    }, el('label', {}, 'Κωδικός', newCode), el('label', { class: 'grow' }, 'Όνομα', newName), el('button', { class: 'primary', type: 'submit' }, 'Νέος ρόλος')),
    out);
  try {
    const r = await api('roles');
    drawRoles(r);
    if (code) drawGrants(await api(`roles/${encodeURIComponent(code)}/grants`), r.rows);
    else out.replaceChildren(el('p', { class: 'muted' }, 'Διάλεξε έναν ρόλο για τα δικαιώματά του.'));
  } catch (e) { fail(e); }
}

// -- the menu (MM_RIGHTS): its groups and screens renamed, their order, the group of a screen, (not) active;
// the same menu for the pages and the forms
async function menuPage() {
  const out = el('div');
  const draw = (r) => {
    const groups = r.rows.filter((x) => x.kind === 'G');
    out.replaceChildren(table([['Κωδικός'], ['Όνομα'], ['Ομάδα'], ['Σειρά', 'num'], ['Ενεργό'], ['']], r.rows.map((x) => {
      const nm = el('input', { value: x.name, maxlength: 100, 'aria-label': 'Όνομα ' + x.code });
      const sort = el('input', { type: 'number', value: x.sort_no, class: 'w6', 'aria-label': 'Σειρά ' + x.code });
      const grp = x.kind === 'G' ? null : el('select', { 'aria-label': 'Ομάδα ' + x.code },
        groups.map((g) => el('option', { value: g.code, selected: g.code === x.group_code }, g.name)));
      const on = el('input', { type: 'checkbox', checked: x.active === 'Y', 'aria-label': 'Ενεργό ' + x.code });
      return el('tr', { class: (x.kind === 'G' ? 'group ' : '') + (x.active === 'Y' ? '' : 'cancelled') || null },
        el('td', {}, x.code), el('td', {}, nm), el('td', {}, grp || 'ομάδα'), el('td', { class: 'num' }, sort), el('td', {}, on),
        el('td', { class: 'num' }, el('button', {
          type: 'button',
          onclick: async () => {
            try {
              draw(await api('menu/' + x.code, { name: nm.value.trim(), sort_no: Number(sort.value || 0), group: grp ? grp.value : null, active: on.checked }));
              await loadRights(); navBar(); toast('Αποθηκεύτηκε');
            } catch (e) { fail(e); }
          },
        }, 'Αποθήκευση')));
    })));
  };
  show(el('h1', {}, 'Μενού'), el('p', { class: 'muted' }, 'Τα ίδια ονόματα, η ίδια σειρά και οι ίδιες ομάδες για τις σελίδες και τις φόρμες. Μια οθόνη που δεν είναι ενεργή δεν φαίνεται σε κανέναν.'),
    el('p', {}, el('a', { href: '#/roles' }, '‹ Ρόλοι και δικαιώματα')), out);
  try { draw(await api('menu')); } catch (e) { fail(e); }
}

// -- the history of what was done (MM_AUDIT: by triggers, whatever did it) and the logins: who, when, from
// where, what, of what; by days, user, kind, text; the newest first, in pages
const AUDIT = {
  DOC_POST: 'Καταχώριση παραστατικού', DOC_CANCEL: 'Ακύρωση παραστατικού', DOC_DELETE: 'Σβήσιμο πρόχειρου',
  Z_OPEN: 'Άνοιγμα Ζ', Z_CLOSE: 'Κλείσιμο Ζ', CASH_IN: 'Μετρητά μέσα', CASH_OUT: 'Μετρητά έξω',
  STOCK_ADJ: 'Διόρθωση αποθέματος', COUNT_POST: 'Καταχώριση απογραφής', COUNT_CANCEL: 'Ακύρωση απογραφής',
  PAYMENT_IN: 'Είσπραξη', PAYMENT_OUT: 'Πληρωμή', PAYMENT_CANCEL: 'Ακύρωση είσπραξης/πληρωμής',
  ITEM_NEW: 'Νέο είδος', ITEM_CHANGE: 'Αλλαγή είδους', CUSTOMER_NEW: 'Νέος πελάτης', CUSTOMER_CHANGE: 'Αλλαγή πελάτη',
  SUPPLIER_NEW: 'Νέος προμηθευτής', SUPPLIER_CHANGE: 'Αλλαγή προμηθευτή', USER_NEW: 'Νέος χρήστης', USER_CHANGE: 'Αλλαγή χρήστη',
  USER_ROLE_ADD: 'Ρόλος σε χρήστη', USER_ROLE_DROP: 'Ρόλος από χρήστη', ROLE_NEW: 'Νέος ρόλος', ROLE_CHANGE: 'Αλλαγή ρόλου',
  ROLE_DROP: 'Διαγραφή ρόλου', GRANT: 'Δικαίωμα', MENU_CHANGE: 'Αλλαγή μενού', SETTING: 'Ρύθμιση',
  WAREHOUSE_NEW: 'Νέα αποθήκη', WAREHOUSE_CHANGE: 'Αλλαγή αποθήκης', AUTH_LOGIN: 'Σύνδεση', AUTH_LOGOUT: 'Αποσύνδεση',
  AUTH_FAIL: 'Λάθος κωδικός', AUTH_LOCKED: 'Κλείδωμα', AUTH_CREATE: 'Νέος χρήστης (login)', AUTH_PASSWORD: 'Νέος κωδικός',
  AUTH_ROLE: 'Αλλαγή επιπέδου', AUTH_ACTIVE: 'Ενεργός ή όχι', AUTH_UNLOCK: 'Ξεκλείδωμα', AUTH_PLACE: 'Κατάστημα και ταμείο',
};
const AUDIT_KINDS = [['', 'Όλα'], ['DOC_', 'Παραστατικά'], ['Z_', 'Ζ'], ['CASH_', 'Μετρητά ταμείου'], ['STOCK_', 'Διορθώσεις αποθέματος'],
  ['COUNT_', 'Απογραφές'], ['PAYMENT_', 'Εισπράξεις και πληρωμές'], ['ITEM_', 'Είδη'], ['CUSTOMER_', 'Πελάτες'], ['SUPPLIER_', 'Προμηθευτές'],
  ['USER', 'Χρήστες'], ['ROLE_', 'Ρόλοι'], ['GRANT', 'Δικαιώματα'], ['MENU_', 'Μενού'], ['SETTING', 'Ρυθμίσεις'], ['WAREHOUSE_', 'Αποθήκες'],
  ['AUTH_', 'Συνδέσεις']];
async function auditPage(params) {
  const from = el('input', { name: 'from', type: 'date', value: params.get('from') || '' });
  const to = el('input', { name: 'to', type: 'date', value: params.get('to') || isoToday() });
  const user = el('select', { name: 'user' }, el('option', { value: '' }, 'Όλοι'));
  const kind = el('select', { name: 'action' }, AUDIT_KINDS.map(([k, t]) => el('option', { value: k, selected: (params.get('action') || '') === k }, t)));
  const text = el('input', { name: 'q', value: params.get('q') || '', placeholder: 'π.χ. ΑΛΠ 12, GAL01' });
  const out = el('div');
  const ref = (x) => (x.ref_type === 'DOC' && x.ref_id ? el('a', { href: '#/doc/' + x.ref_id }, x.ref_text)
    : x.ref_type === 'ITEM' && x.ref_text ? el('a', { href: '#/item/' + encodeURIComponent(x.ref_text) }, x.ref_text)
      : x.ref_type === 'ROLE' && x.ref_text && !x.ref_text.startsWith('#') ? el('a', { href: '#/roles/' + x.ref_text }, x.ref_text)
        : x.ref_text || '');
  const go = async (offset = 0) => {
    const q = new URLSearchParams({ from: from.value, to: to.value, user: user.value, action: kind.value, q: text.value.trim(), offset, limit: pageSize });
    try {
      const r = await api('audit?' + q);
      if (!from.value) from.value = r.from;
      if (user.options.length === 1) r.users.forEach((u) => user.append(el('option', { value: u.username, selected: params.get('user') === u.username }, u.username)));
      out.replaceChildren(r.rows.length ? table([['Πότε'], ['Ποιος'], ['Από', 'hide-phone'], ['Τι'], ['Σε'], ['Λεπτομέρειες', 'hide-phone']],
        r.rows.map((x) => el('tr', { class: /FAIL|LOCKED|CANCEL|DROP|DELETE/.test(x.action) ? 'expired' : null },
          el('td', {}, day(x.at) + ' ' + String(x.at).slice(11, 19)), el('td', {}, x.username || ''),
          el('td', { class: 'hide-phone muted' }, x.source || ''), el('td', {}, AUDIT[x.action] || x.action), el('td', {}, ref(x)),
          el('td', { class: 'hide-phone wrap' }, x.detail || '')))) : el('p', { class: 'muted' }, 'Τίποτα σε αυτές τις ημέρες.'),
      r.total > r.limit ? pager(r.total, r.offset, r.limit, go) : null);
    } catch (e) { fail(e); }
  };
  show(el('h1', {}, 'Ιστορικό ενεργειών'),
    el('p', { class: 'muted' }, 'Ό,τι έγινε, από τις σελίδες, τις φόρμες ή με SQL: ποιος, πότε, από πού. Και οι συνδέσεις.'),
    el('form', { class: 'panel row', onsubmit: (ev) => { ev.preventDefault(); go(0); } },
      el('label', {}, 'Από', from), el('label', {}, 'Έως', to), el('label', {}, 'Χρήστης', user), el('label', {}, 'Τι', kind),
      el('label', { class: 'grow' }, 'Κείμενο', text), el('button', { class: 'primary', type: 'submit' }, 'Αναζήτηση')),
    out);
  await go(0);
}

// -- the scratch tickets (σκρατς): bought in packs, sold one by one by the barcode of each (its game 4
// digits, its pack 7, its number 3). A pack loaded by a scan of one of its tickets; the games (έκδοση: the
// item it is sold as, the tickets of a pack); the packs, sold and left; the prizes paid, by day
async function scratchPage() {
  const code = el('input', { name: 'code', inputmode: 'numeric', autocomplete: 'off', placeholder: 'σάρωση ενός δελτίου του πακέτου' });
  const count = el('input', { name: 'count', type: 'number', min: '1', max: '999', class: 'w6', placeholder: '300' });
  const game = el('input', { name: 'game', inputmode: 'numeric', maxlength: 4, class: 'w6', placeholder: '1234' });
  const item = el('input', { name: 'item', autocomplete: 'off', placeholder: 'π.χ. SKR01' });
  const size = el('input', { name: 'pack_size', type: 'number', min: '1', max: '999', value: '300', class: 'w6' });
  const out = el('div');
  const draw = (r) => {
    out.replaceChildren(
      el('h2', {}, 'Εκδόσεις'),
      r.games.length ? table([['Έκδοση'], ['Είδος'], ['Τιμή', 'num'], ['Δελτία / πακέτο', 'num'], ['Διαθέσιμα', 'num']],
        r.games.map((x) => el('tr', {}, el('td', {}, x.game), el('td', { class: 'wrap' }, `${x.code} ${x.name}`),
          num(x.price), el('td', { class: 'num' }, x.pack_size), el('td', { class: 'num' }, x.left_))))
        : el('p', { class: 'muted' }, 'Καμία έκδοση ακόμα: δήλωσε την πρώτη παρακάτω (τα 4 πρώτα ψηφία του barcode).'),
      el('form', {
        class: 'panel row',
        onsubmit: async (ev) => {
          ev.preventDefault();
          try { draw(await api('scratch/games', { game: game.value.trim(), code: item.value.trim(), pack_size: Number(size.value || 300) })); toast('Η έκδοση ' + game.value + ' δηλώθηκε'); game.value = ''; } catch (e) { fail(e); }
        },
      }, el('label', {}, 'Έκδοση', game), el('label', { class: 'grow' }, 'Είδος (κωδικός ή barcode)', item),
      el('label', {}, 'Δελτία / πακέτο', size), el('button', { type: 'submit' }, 'Δήλωση έκδοσης')),
      el('h2', {}, 'Πακέτα'),
      r.packs.length ? table([['Έκδοση'], ['Πακέτο'], ['Είδος', 'hide-phone'], ['Δελτία', 'num'], ['Πουλήθηκαν', 'num'], ['Μένουν', 'num'], ['Επιστράφηκαν', 'num'], ['Φορτώθηκε', 'hide-phone']],
        r.packs.map((x) => el('tr', { class: x.left_ === 0 ? 'cancelled' : null }, el('td', {}, x.game), el('td', {}, x.pack),
          el('td', { class: 'hide-phone wrap' }, x.name), el('td', { class: 'num' }, x.tickets), el('td', { class: 'num' }, x.sold),
          el('td', { class: 'num' }, x.left_), el('td', { class: 'num' }, x.returned || ''), el('td', { class: 'hide-phone' }, day(x.loaded_at)))))
        : el('p', { class: 'muted' }, 'Κανένα πακέτο ακόμα.'),
      el('h2', {}, 'Κέρδη που πληρώθηκαν (31 ημέρες)'),
      r.prizes.length ? table([['Ημέρα'], ['Κέρδη', 'num'], ['Ποσό', 'num']],
        r.prizes.map((x) => el('tr', {}, el('td', {}, day(x.day)), el('td', { class: 'num' }, x.prizes), num(x.total))))
        : el('p', { class: 'muted' }, 'Κανένα κέρδος.'));
  };
  const form = el('form', {
    class: 'panel row',
    onsubmit: async (ev) => {
      ev.preventDefault();
      try {
        const r = await api('scratch/packs', { code: code.value.trim(), count: count.value ? Number(count.value) : null });
        toast(`Φορτώθηκαν ${r.loaded} δελτία`);
        code.value = '';
        count.value = '';
        draw(r);
      } catch (e) { fail(e); }
      code.focus();
    },
  }, el('label', { class: 'grow' }, 'Φόρτωση πακέτου', code), el('label', {}, 'Δελτία', count), camera(code), el('button', { class: 'primary', type: 'submit' }, 'Φόρτωση'));
  // the tickets of a pack not sold, back to the supplier
  const back = el('input', { name: 'return_code', inputmode: 'numeric', autocomplete: 'off', placeholder: 'σάρωση ενός δελτίου του πακέτου' });
  const returns = el('form', {
    class: 'panel row',
    onsubmit: async (ev) => {
      ev.preventDefault();
      if (!back.value.trim() || !confirm('Επιστροφή στον προμηθευτή όσων δελτίων του πακέτου δεν πουλήθηκαν;')) return;
      try {
        const r = await api('scratch/returns', { code: back.value.trim() });
        toast(`Επιστράφηκαν ${r.returned} δελτία: βγήκαν από το απόθεμα`);
        back.value = '';
        draw(r);
      } catch (e) { fail(e); }
    },
  }, el('label', { class: 'grow' }, 'Επιστροφή απούλητων', back), el('button', { type: 'submit', class: 'danger' }, 'Επιστροφή'));
  show(el('h1', {}, 'Σκρατς'), el('p', { class: 'muted' },
    'Το barcode ενός δελτίου: έκδοση (4 ψηφία), πακέτο (7), δελτίο (3). Σάρωσε ένα δελτίο του πακέτου για να μπουν όλα στο απόθεμα· στο ταμείο, η σάρωση ενός δελτίου πουλά αυτό το δελτίο.'),
  form, out, returns);
  try { draw(await api('scratch')); } catch (e) { fail(e); }
  code.focus();
}

// -- the counts of the stock: a phone scans (a scanner types the barcode and Enter) ------------------
async function countsPage() {
  const name = el('input', { placeholder: 'π.χ. Απογραφή ραφιών Νοεμβρίου' });
  // more than one warehouse: the count is of one of them
  let whs = [];
  try { whs = (await api('warehouses')).rows.filter((w) => w.active === 'Y'); } catch (e) { whs = []; }
  // (the store of the user first)
  const myWh = whs.some((w) => w.id === session.warehouse_id) ? session.warehouse_id : whs.length ? whs[0].id : '';
  const wh = el('select', { name: 'warehouse_id' }, ...options(whs, 'id', (w) => `${w.code} ${w.name}`, myWh));
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
    act('COUNTS', 'CREATE') && el('form', {
      class: 'panel row',
      onsubmit: async (ev) => {
        ev.preventDefault();
        try {
          const c = await api('counts', { name: name.value.trim() || null, warehouse_id: whs.length > 1 ? Number(wh.value) : null });
          location.hash = '#/count/' + c.id;
        } catch (e) { fail(e); }
      },
    }, el('label', {}, 'Νέα απογραφή', name), whs.length > 1 ? el('label', {}, 'Αποθήκη', wh) : null,
    el('button', { class: 'primary', type: 'submit' }, 'Ξεκίνα')),
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
      actions.hidden = !(open && (act('COUNTS', 'POST') || act('COUNTS', 'CANCEL')));
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
  }, el('label', {}, 'Σάρωση (Enter)', code), camera(code), el('label', {}, 'Ποσότητα', n), el('label', {}, 'Τρόπος', mode),
  el('button', { class: 'primary', type: 'submit' }, 'Βάλε'));
  const doIt = (what, ask) => async () => {
    if (!confirm(ask)) return;
    try {
      await api(`counts/${id}/${what}`, {});
      toast(what === 'post' ? 'Καταχωρήθηκε στο απόθεμα' : 'Ακυρώθηκε');
      load();
    } catch (e) { fail(e); }
  };
  const actions = el('div', { class: 'row' },
    act('COUNTS', 'POST') && el('button', { class: 'primary', onclick: doIt('post', 'Καταχώριση της απογραφής στο απόθεμα;') }, 'Καταχώριση'),
    act('COUNTS', 'CANCEL') && el('button', { class: 'danger', onclick: doIt('cancel', 'Ακύρωση της απογραφής;') }, 'Ακύρωση'));
  show(title, form, last, out, el('h2', {}), actions, el('p', {}, el('a', { href: '#/counts' }, 'Όλες οι απογραφές')));
  await load();
  code.focus();
}

// -- the labels: A4 sheets of stickers (3 x 8 or 3 x 7), each the name, the price, the barcode (its
// EAN-13, else its code in Code 128) and a QR of the address of the item in these pages ---------------
const SHEETS = {
  '3x8': { cols: 3, rows: 8, w: 70, h: 37, name: '3 × 8 (70 × 37 mm)' },
  '3x7': { cols: 3, rows: 7, w: 70, h: 42.3, name: '3 × 7 (70 × 42,3 mm)' },
};
function store(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; }
}
function keep(key, v) {
  try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* a private window */ }
}
let labelList = store('mm.labels', []);          // [{ code, barcode, name, price, unit, n }]
function labelAdd(x, n) {
  const have = labelList.find((l) => l.code === x.code);
  if (have) have.n += n;
  else labelList.push({ code: x.code, barcode: x.barcode, name: x.name, price: x.price, unit: x.unit, n });
  keep('mm.labels', labelList);
}
function label(x, opt) {
  const b = itemBars(x);
  const price = opt.price && x.price !== null && x.price !== undefined
    ? el('div', { class: 'price' }, money(x.price) + ' €' + (x.unit === 'KG' ? ' / κιλό' : '')) : null;
  return el('div', { class: 'label' },
    el('div', { class: 'txt' }, el('div', { class: 'name' }, x.name), price, el('div', { class: 'code' }, x.code)),
    el('div', { class: 'qr-box' }, qrSvg(opt.base.replace(/\/+$/, '') + '/web/#/item/' + encodeURIComponent(x.code))),
    el('div', { class: 'bc', 'data-kind': b.kind }, barsSvg(b.bars), el('div', { class: 'digits' }, b.text)));
}
function labelSheets(opt) {
  const s = SHEETS[opt.sheet];
  const per = s.cols * s.rows;
  const cells = new Array(Math.max(0, Math.min(per, opt.start) - 1)).fill(null);
  labelList.forEach((x) => { for (let k = 0; k < x.n; k += 1) cells.push(x); });
  const sheets = [];
  for (let i = 0; i < cells.length; i += per) {
    const page = el('div', { class: 'sheet sheet-' + opt.sheet });
    cells.slice(i, i + per).forEach((x) => page.append(x ? label(x, opt) : el('div', { class: 'label empty' })));
    sheets.push(page);
  }
  return sheets;
}
async function labelsPage() {
  const opt = { sheet: '3x8', start: 1, price: true, base: server || location.origin, ...store('mm.labelOpt', {}) };
  const q = el('input', { name: 'q', type: 'search', placeholder: 'περιγραφή, κωδικός ή barcode (Enter: σάρωση)', autocomplete: 'off' });
  const found = el('div');
  const chosen = el('div');
  const preview = el('div', { class: 'sheets' });
  const sheet = el('select', { name: 'sheet' }, Object.entries(SHEETS).map(([k, v]) => el('option', { value: k, selected: k === opt.sheet }, v.name)));
  const start = el('input', { name: 'start', type: 'number', min: '1', max: '24', value: opt.start, class: 'w6' });
  const price = el('input', { name: 'price', type: 'checkbox', checked: opt.price });
  const base = el('input', { name: 'base', value: opt.base, class: 'w-wide' });
  const redraw = () => {
    Object.assign(opt, { sheet: sheet.value, start: Math.max(1, Number(start.value) || 1), price: price.checked, base: base.value.trim() || location.origin });
    keep('mm.labelOpt', opt);
    const total = labelList.reduce((a, x) => a + x.n, 0);
    chosen.replaceChildren(labelList.length ? table([['Κωδικός'], ['Περιγραφή'], ['Τιμή', 'num'], ['Ετικέτες', 'num'], ['']],
      labelList.map((x) => {
        const n = el('input', { type: 'number', min: '0', value: x.n, class: 'w6', 'aria-label': 'Ετικέτες ' + x.code });
        n.addEventListener('change', () => {
          x.n = Math.max(0, Math.floor(Number(n.value) || 0));
          labelList = labelList.filter((y) => y.n > 0);
          keep('mm.labels', labelList);
          redraw();
        });
        return el('tr', {}, el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.price), el('td', { class: 'num' }, n),
          el('td', { class: 'num' }, el('button', {
            type: 'button', class: 'danger', 'aria-label': 'Βγάλε ' + x.code,
            onclick: () => { labelList = labelList.filter((y) => y !== x); keep('mm.labels', labelList); redraw(); },
          }, '×')));
      })) : el('p', { class: 'muted' }, 'Καμία ετικέτα ακόμα: ψάξε ή σάρωσε είδη.'),
    el('p', { class: 'muted' }, `${total} ετικέτες`));
    try {
      preview.replaceChildren(...labelSheets(opt));
    } catch (e) { fail(e); }
    printBtn.disabled = !total;
  };
  const search = async () => {
    const v = q.value.trim();
    if (!v) { found.replaceChildren(); return; }
    try {
      const r = await api('items?limit=20&q=' + encodeURIComponent(v));
      found.replaceChildren(r.rows.length ? el('div', {},
        table([['Κωδικός'], ['Περιγραφή'], ['Τιμή', 'num'], ['']], r.rows.map((x) => el('tr', {},
          el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.price),
          el('td', { class: 'num' }, el('button', { type: 'button', onclick: () => { labelAdd(x, 1); redraw(); } }, '+ 1'))))),
        el('div', { class: 'row' }, el('button', {
          type: 'button', onclick: () => { r.rows.forEach((x) => labelAdd(x, 1)); redraw(); },
        }, `Όλα αυτά (${r.rows.length})`), r.total > r.rows.length ? el('span', { class: 'muted' }, `τα πρώτα 20 από ${r.total}`) : null))
        : el('p', { class: 'muted' }, 'Τίποτα.'));
    } catch (e) { fail(e); }
  };
  let timer;
  q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 250); });
  q.addEventListener('keydown', async (ev) => {
    if (ev.key !== 'Enter') return;
    ev.preventDefault();
    const v = q.value.trim();
    if (!v) return;
    try {                                           // a scan: the item straight to the labels
      labelAdd(await api('items/' + encodeURIComponent(v)), 1);
      q.value = '';
      found.replaceChildren();
      redraw();
    } catch (e) { search(); }
    q.focus();
  });
  [sheet, start, price, base].forEach((e) => e.addEventListener('change', redraw));
  const printBtn = el('button', { type: 'button', class: 'primary', onclick: () => window.print() }, 'Εκτύπωση');
  show(el('div', { class: 'no-print' },
    el('h1', {}, 'Ετικέτες'),
    el('div', { class: 'panel row' }, el('label', { class: 'grow' }, 'Είδος', q), camera(q)), found,
    el('h2', {}, 'Για εκτύπωση'), chosen,
    el('div', { class: 'panel row' }, el('label', {}, 'Φύλλο A4', sheet), el('label', {}, 'Από την ετικέτα', start),
      el('label', { class: 'check' }, price, 'Τιμή'), el('label', {}, 'Διεύθυνση για το QR', base),
      printBtn, el('button', { type: 'button', onclick: () => { labelList = []; keep('mm.labels', labelList); redraw(); } }, 'Καθάρισε')),
    el('p', { class: 'muted' }, 'Στην εκτύπωση: μέγεθος A4, κλίμακα 100% (όχι «Προσαρμογή»), χωρίς περιθώρια, κεφαλίδες και υποσέλιδα. «Από την ετικέτα»: για φύλλο που έχει ήδη χρησιμοποιηθεί.')),
  preview);
  redraw();
  q.focus();
}

// -- the till (as the form MM_POS): a register, its Z, the receipt of the register (made at the first
// scan: Enter of a scanner), its lines, paid by cash (what was given: the change) or card --------------
let posReg = null;
try { posReg = localStorage.getItem('mm.register'); } catch (e) { posReg = null; }
async function posPage(params) {
  let regs;
  try { regs = (await api('pos')).rows; } catch (e) { fail(e); return; }
  if (!regs.length) { show(el('h1', {}, 'Ταμείο'), el('p', { class: 'muted' }, 'Κανένα ταμείο.')); return; }
  // (the register chosen last on this device, if the user may use it; else its own, else the first)
  if (!regs.some((r) => r.code === posReg)) posReg = (regs.find((r) => r.mine === 'Y') || regs[0]).code;
  const pick = el('select', {
    'aria-label': 'Ταμείο',
    onchange: () => {
      posReg = pick.value;
      try { localStorage.setItem('mm.register', posReg); } catch (e) { /* a private window */ }
      load();
    },
  }, regs.map((r) => el('option', { value: r.code, selected: r.code === posReg }, `${r.code} ${r.name}`)));
  const zText = el('span', { class: 'muted' });
  const whBox = el('span');
  let posWhs = [];
  try { posWhs = (await api('warehouses')).rows.filter((w) => w.active === 'Y'); } catch (e) { posWhs = []; }
  const zBox = el('div', { class: 'row' });
  const code = el('input', { name: 'code', autocomplete: 'off', placeholder: 'barcode, κωδικός ή serial' });
  const n = el('input', { name: 'qty', type: 'number', step: 'any', min: '0', value: '1', class: 'w6' });
  const total = el('p', { class: 'big total-due' });
  const orderText = el('span', { class: 'muted order-text' });
  const orders = el('div');
  const lines = el('div');
  const given = el('input', { name: 'given', type: 'number', step: '0.01', min: '0', class: 'w8' });
  const change = el('p', { class: 'big' });
  const last = el('div');
  const cust = el('div', { class: 'panel row cust' });
  let st = null;
  let seq = 0;              // (an answer after a newer call, or of a register left: not drawn)
  const run = async (path, body) => {
    const reg = posReg;
    const mine = ++seq;
    try {
      const r = await api(`pos/${encodeURIComponent(reg)}${path}`, body);
      if (mine !== seq || reg !== posReg) return r;
      st = r;
      draw();
      return st;
    } catch (e) {
      fail(e);
      return null;
    } finally { code.focus(); }
  };
  const load = () => run('');
  const draw = () => {
    const z = st.z;
    zText.textContent = z ? `Ζ ${z.z_no}, ανοιχτό από ${day(z.opened_at)} · ${z.docs} αποδείξεις · μετρητά ${money(z.cash)}, κάρτα ${money(z.card)} · στο συρτάρι ${money(z.drawer)}`
      : 'Κλειστό: «Άνοιγμα Ζ» για να ξεκινήσεις';
    // more than one warehouse: the one of the register (its sales from there); a manager changes it
    whBox.replaceChildren();
    if (posWhs.length > 1) {
      const sel = el('select', { name: 'register_warehouse', disabled: !act('POS', 'WAREHOUSE') || !!st.receipt, 'aria-label': 'Αποθήκη του ταμείου' },
        ...options(posWhs, 'id', (w) => `${w.code} ${w.name}`, st.warehouse_id));
      sel.addEventListener('change', async () => {
        if (await run('/warehouse', { warehouse_id: Number(sel.value) })) toast('Οι πωλήσεις του ταμείου από: ' + sel.selectedOptions[0].text);
      });
      whBox.append(el('label', {}, 'Αποθήκη', sel));
    }
    if (z) {
      const amount = el('input', { type: 'number', step: '0.01', placeholder: '+ μπαίνουν, − βγαίνουν', class: 'w11' });
      const note = el('input', { placeholder: 'αιτιολογία' });
      const prize = el('input', { type: 'number', step: '0.01', min: '0', name: 'prize', class: 'w6' });
      const ticket = el('input', { name: 'ticket', placeholder: 'barcode', autocomplete: 'off', class: 'w11' });
      zBox.replaceChildren(
        el('label', {}, 'Κίνηση συρταριού', amount), el('label', {}, 'Αιτιολογία', note),
        el('button', { type: 'button', onclick: () => run('/cash', { amount: Number(amount.value), note: note.value.trim() }) }, 'Καταχώριση κίνησης'),
        // a prize of a scratch ticket: out of the drawer (its barcode, if scanned: in the note)
        el('label', {}, 'Κέρδος σκρατς €', prize), el('label', {}, 'Δελτίο (προαιρετικά)', ticket),
        el('button', {
          type: 'button',
          onclick: async () => {
            if (!(Number(prize.value) > 0)) { toast('Το κέρδος: ένα ποσό', true); return; }
            if (await run('/prize', { amount: Number(prize.value), ticket: ticket.value.trim() || null })) toast('Κέρδος σκρατς ' + money(Number(prize.value)) + ' από το συρτάρι');
          },
        }, 'Πληρωμή κέρδους'),
        el('button', {
          type: 'button',
          class: 'danger',
          onclick: async () => {
            if (!confirm(`Κλείσιμο του Ζ ${z.z_no};`)) return;
            const r = await run('/close', {});
            if (r && r.closed) toast(`Ζ ${r.closed.z_no} έκλεισε: σύνολο ${money(r.closed.total)}, μετρητά ${money(r.closed.cash)}, κάρτα ${money(r.closed.card)}`);
            if (r && r.closed && may('DAY') && confirm('Να ανοίξει η σύνοψη της ημέρας;')) location.hash = '#/day';
          },
        }, 'Κλείσιμο Ζ'));
    } else {
      const cash = el('input', { type: 'number', step: '0.01', min: '0', value: '0', class: 'w8' });
      zBox.replaceChildren(el('label', {}, 'Αρχικό ταμείο', cash),
        act('POS', 'OPEN_Z') ? el('button', { type: 'button', class: 'primary', onclick: () => run('/open', { cash: Number(cash.value || 0) }) }, 'Άνοιγμα Ζ') : null);
    }
    scan.hidden = !z;
    pay.hidden = !st.receipt;
    const r = st.receipt;
    drawCustomer(r);
    total.textContent = 'Σύνολο: ' + money(r ? r.total : 0)
      + (r && r.deposit > 0 ? ` · προκαταβολή ${money(r.deposit)} · πληρωτέο ${money(r.due)}` : '');
    orderText.textContent = r && r.order_id ? `Παραγγελία ${r.order_id}` : '';
    orders.replaceChildren();
    lines.replaceChildren(r && r.lines.length ? table([['#'], ['Είδος'], ['Ποσότητα', 'num'], ['Τιμή', 'num'], ['Ποσό', 'num'], ['']],
      r.lines.map((x) => {
        const setQ = (q) => run(`/lines/${x.id}`, { qty: q });
        return el('tr', {}, el('td', {}, x.line_no),
          el('td', { class: 'wrap' }, `${x.code} ${x.name}`, x.serials ? el('div', { class: 'muted' }, x.serials) : null),
          num(x.qty, qty), num(x.price), num(x.total),
          el('td', { class: 'num' },
            x.serial_tracked === 'Y' ? null : el('button', { type: 'button', 'aria-label': 'Μία λιγότερη', disabled: x.qty <= 1, onclick: () => setQ(x.qty - 1) }, '−'),
            x.serial_tracked === 'Y' ? null : el('button', { type: 'button', 'aria-label': 'Μία ακόμα', onclick: () => setQ(x.qty + 1) }, '+'),
            el('button', { type: 'button', class: 'danger', 'aria-label': 'Σβήσε τη γραμμή', onclick: () => setQ(0) }, '×')));
      })) : el('p', { class: 'muted' }, z ? 'Σάρωσε το πρώτο είδος.' : ''));
    last.replaceChildren(st.last.length ? el('div', {}, el('h2', {}, 'Τελευταίες αποδείξεις'),
      table([['Αριθμός'], ['Ώρα'], ['Πληρωμή'], ['Ποσό', 'num'], ['']], st.last.map((x) => el('tr', {},
        el('td', {}, 'ΑΛΠ ' + x.doc_no + (x.status === 'C' ? ' (ακυρώθηκε)' : '')), el('td', {}, day(x.created_at)),
        el('td', {}, x.payment === 'CARD' ? 'κάρτα' : 'μετρητά'), num(x.total),
        el('td', { class: 'num' }, el('button', { type: 'button', 'aria-label': 'Εκτύπωση ΑΛΠ ' + x.doc_no, onclick: () => printReceipt(posReg, x.id) }, '🖨')))))) : '');
  };
  const scan = el('form', {
    class: 'panel row scan',
    onsubmit: async (ev) => {
      ev.preventDefault();
      const v = code.value.trim();
      if (!v) return;
      const r = await run('/scan', { code: v, qty: Number(n.value || 1) });
      if (r) {
        code.value = '';
        n.value = '1';
        change.textContent = '';
      } else code.select();
    },
  }, el('label', {}, 'Σάρωση (Enter)', code), camera(code), el('label', {}, 'Ποσότητα', n), el('button', { class: 'primary', type: 'submit' }, 'Βάλε'),
  el('button', { type: 'button', onclick: () => pickOrder() }, 'Παραγγελία'), orderText, total);
  // the customer of the receipt (its points): a scan of its card (here or in the scan above) or its phone;
  // a new one with a card; its points used as the discount of the receipt
  const drawCustomer = (r) => {
    cust.hidden = !st.z;
    const c = r && r.customer;
    const pts = st.points;
    if (!c) {
      const who = el('input', { name: 'customer', autocomplete: 'off', placeholder: 'κάρτα ή τηλέφωνο', class: 'w11' });
      const nm = el('input', { name: 'new_name', placeholder: 'ονοματεπώνυμο' });
      const ph = el('input', { name: 'new_phone', type: 'tel', placeholder: 'τηλέφωνο', class: 'w11' });
      cust.replaceChildren(
        el('form', { class: 'row', onsubmit: (ev) => { ev.preventDefault(); if (who.value.trim()) run('/customer', { code: who.value.trim() }); } },
          el('label', {}, 'Πελάτης με κάρτα', who), el('button', { type: 'submit' }, 'Πελάτης')),
        el('details', {}, el('summary', {}, 'Νέος πελάτης με κάρτα'),
          el('form', {
            class: 'row',
            onsubmit: async (ev) => {
              ev.preventDefault();
              const s2 = await run('/customer/new', { name: nm.value.trim(), phone: ph.value.trim() || null });
              if (s2 && s2.receipt && s2.receipt.customer) {
                const k = s2.receipt.customer;
                toast(`Νέα κάρτα ${k.card} για ${k.name}`);
                if (confirm('Εκτύπωση της κάρτας;')) printCard(k.name, k.card);
              }
            },
          }, el('label', { class: 'grow' }, 'Όνομα', nm), el('label', {}, 'Τηλέφωνο', ph), el('button', { type: 'submit' }, 'Νέα κάρτα'))));
      return;
    }
    const most = Math.min(c.points, Math.floor((r.total + (r.points_used > 0 ? r.disc_amount : 0)) / pts.value + 1e-9));
    const use = el('input', { name: 'points', type: 'number', min: '0', step: '1', class: 'w6', value: r.points_used || (most >= pts.min ? most : '') });
    cust.replaceChildren(...[                 // (replaceChildren writes a null as text: out first)
      el('div', { class: 'grow' }, el('strong', {}, c.name), ` · κάρτα ${c.card} · ${c.points} πόντοι`,
        el('div', { class: 'muted' }, `Με αυτή την απόδειξη: +${c.earn} πόντοι`
          + (r.points_used > 0 ? ` · εξαργύρωση ${r.points_used} πόντων = ${money(r.disc_amount)} €` : ''))),
      c.points >= pts.min ? el('label', {}, `Πόντοι (από ${pts.min})`, use) : null,
      c.points >= pts.min ? el('button', { type: 'button', onclick: () => run('/points', { points: Number(use.value || 0) }) }, 'Εξαργύρωση') : null,
      r.points_used > 0 ? el('button', { type: 'button', onclick: () => run('/points', { points: 0 }) }, 'Χωρίς πόντους') : null,
      el('button', { type: 'button', class: 'danger', 'aria-label': 'Χωρίς πελάτη', onclick: () => run('/customer', { code: '' }) }, '×'),
    ].filter(Boolean));
  };
  // an order into the receipt, all of it: the open ones of today and before, the ready ones first
  const loadOrder = async (id) => {
    const r = await run('/order', { id });
    if (r) toast(`Η παραγγελία ${id} μπήκε στην απόδειξη`);
  };
  const pickOrder = async () => {
    try {
      const r = await api('orders');
      const today = isoToday();
      const rows = r.rows.filter((x) => x.pickup_date <= today && !x.doc_id)
        .sort((x, y) => (y.ready_at ? 1 : 0) - (x.ready_at ? 1 : 0) || x.id - y.id);
      orders.replaceChildren(el('div', { class: 'panel' }, el('h2', {}, 'Παραγγελίες για σήμερα'),
        rows.length ? table([['#'], ['Όνομα'], ['Είδη', 'num'], ['Ποσό', 'num'], ['']], rows.map((x) => el('tr', {
          class: 'click', onclick: () => loadOrder(x.id),
        }, el('td', {}, x.id), el('td', { class: 'wrap' }, x.name + (x.customer ? ' · ' + x.customer : '')),
        num(x.lines, qty), num(x.total), el('td', {}, x.ready_at ? 'έτοιμη' : 'μαζεύεται'))))
          : el('p', { class: 'muted' }, 'Καμία ανοιχτή παραγγελία για σήμερα.'),
        el('button', { type: 'button', onclick: () => orders.replaceChildren() }, 'Κλείσε')));
    } catch (e) { fail(e); }
  };
  const payWith = async (how) => {
    const body = { payment: how };
    if (how === 'CASH' && given.value !== '') body.given = Number(given.value);
    const r = await run('/pay', body);
    if (r && r.paid) {
      given.value = '';
      const p = r.paid;
      const print = () => printReceipt(posReg, p.id, { given: p.given, change: p.change });
      change.replaceChildren(p.change !== null ? 'Ρέστα: ' + money(p.change) + ' ' : '',
        el('button', { type: 'button', class: 'print-btn', onclick: print }, 'Εκτύπωση απόδειξης'));
      toast(`Απόδειξη ${p.doc_no} καταχωρήθηκε: ${money(p.total)}`);
      if (autoPrint.checked) print();
    }
  };
  const pay = el('div', { class: 'panel row' },
    el('label', {}, 'Δόθηκαν', given),
    el('button', { type: 'button', class: 'primary', onclick: () => payWith('CASH') }, 'Μετρητά (F9)'),
    el('button', { type: 'button', onclick: () => payWith('CARD') }, 'Κάρτα (F8)'),
    el('button', { type: 'button', class: 'danger', onclick: () => { if (confirm('Ακύρωση της απόδειξης;')) run('/void', {}); } }, 'Ακύρωση απόδειξης'));
  const keys = (ev) => {
    if (!document.body.contains(pay)) { document.removeEventListener('keydown', keys); return; }
    if (pay.hidden) return;
    if (ev.key === 'F9') { ev.preventDefault(); payWith('CASH'); }
    if (ev.key === 'F8') { ev.preventDefault(); payWith('CARD'); }
  };
  document.addEventListener('keydown', keys);
  // the print: by hand after each receipt, or by itself (kept in this browser); the header and the footer
  // of the receipts (a manager)
  const autoPrint = el('input', { type: 'checkbox', name: 'autoprint', checked: !!store('mm.autoprint', false) });
  autoPrint.addEventListener('change', () => keep('mm.autoprint', autoPrint.checked));
  const setup = act('POS', 'SETTINGS') ? el('details', { class: 'receipt-setup' }, el('summary', {}, 'Επικεφαλίδα και υποσέλιδο της απόδειξης')) : null;
  if (setup) {
    const head = el('textarea', { name: 'header', rows: 4, maxlength: 400, placeholder: 'π.χ. MINI MARKET Ο ΓΙΑΝΝΗΣ\nΑγ. Νικολάου 10, Πάτρα\nΑΦΜ 123456789 ΔΟΥ Α΄ Πατρών' });
    const foot = el('textarea', { name: 'footer', rows: 2, maxlength: 400, placeholder: 'π.χ. Ευχαριστούμε!' });
    setup.addEventListener('toggle', async () => {
      if (!setup.open || setup.dataset.loaded) return;
      try {
        const r = await api('pos/settings');
        head.value = r.header || '';
        foot.value = r.footer || '';
        setup.dataset.loaded = '1';
      } catch (e) { fail(e); }
    });
    setup.append(el('div', { class: 'row' }, el('label', { class: 'grow' }, 'Επικεφαλίδα', head), el('label', { class: 'grow' }, 'Υποσέλιδο', foot),
      el('button', {
        type: 'button',
        onclick: async () => {
          try { await api('pos/settings', { header: head.value.trim() || null, footer: foot.value.trim() || null }); toast('Αποθηκεύτηκε'); } catch (e) { fail(e); }
        },
      }, 'Αποθήκευση')));
  }
  show(el('h1', {}, 'Ταμείο'), el('div', { class: 'panel' }, el('div', { class: 'row' }, el('label', {}, 'Ταμείο', pick), whBox, zText), zBox),
    scan, cust, orders, lines, pay, change, el('label', { class: 'check' }, autoPrint, 'Εκτύπωση απόδειξης αυτόματα'), last, setup);
  await load();
  if (params && params.get('order') && st && st.z) loadOrder(Number(params.get('order')));
}

// -- the poster of the door: a QR of the page of the orders of the customers (/shop/), A4, printed
function posterPage() {
  const base = (server || location.origin).replace(/\/+$/, '');
  const url = base + '/shop/';
  const addr = el('input', { name: 'base', value: base, class: 'w-wide' });
  const box = el('div', { class: 'poster' });
  const draw = () => {
    const u = addr.value.trim().replace(/\/+$/, '') + '/shop/';
    box.replaceChildren(el('div', { class: 'poster-title' }, 'Παράγγειλε από το κινητό σου'),
      el('div', { class: 'poster-text' }, 'Σύνδεσε το κινητό στο WiFi του μαγαζιού και σκάναρε:'),
      qrSvg(u), el('div', { class: 'poster-url' }, u),
      el('div', { class: 'poster-text' }, 'Σε παίρνουμε τηλέφωνο για επιβεβαίωση και την ετοιμάζουμε για σήμερα.'));
  };
  addr.addEventListener('change', draw);
  show(el('div', { class: 'no-print' }, el('h1', {}, 'Αφίσα για τις παραγγελίες'),
    el('div', { class: 'panel row' }, el('label', {}, 'Η διεύθυνση που βλέπουν τα κινητά', addr),
      el('button', { type: 'button', class: 'primary', onclick: () => window.print() }, 'Εκτύπωση'),
      el('a', { href: url, target: '_blank', rel: 'noopener' }, 'Άνοιγμα της σελίδας'))), box);
  draw();
}

// -- the receipt on a printer of receipts (80 mm, its driver in Windows: the paper 80 mm wide): a page of
// its own size (a named @page: the A4 of the labels stays), what the till prints
const nfQty = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 3 });
async function printReceipt(reg, id, extra = {}) {
  let r;
  try { r = await api(`pos/${encodeURIComponent(reg)}/receipt/${id}`); } catch (e) { fail(e); return; }
  const lines = (text) => String(text || '').split('\n').filter((x) => x.trim()).map((x) => el('div', {}, x));
  const pair = (a, b, cls) => el('div', { class: 'rc-pair' + (cls ? ' ' + cls : '') }, el('span', {}, a), el('span', {}, b));
  const box = el('div', { class: 'receipt', id: 'receipt' },
    el('div', { class: 'rc-head' }, lines(r.header)),
    el('div', { class: 'rc-title' }, 'ΑΠΟΔΕΙΞΗ ΛΙΑΝΙΚΗΣ ΠΩΛΗΣΗΣ'),
    pair('ΑΛΠ ' + r.doc_no, day(r.created_at)), pair('Ταμείο ' + r.register, r.z_no ? 'Ζ ' + r.z_no : ''),
    r.cashier ? pair('Ταμίας', r.cashier) : null,
    r.status === 'C' ? el('div', { class: 'rc-title' }, '*** ΑΚΥΡΩΘΗΚΕ ***') : null,
    el('hr'),
    r.lines.map((x) => el('div', { class: 'rc-line' }, el('div', {}, x.name),
      pair(`${nfQty.format(x.qty)} x ${money(x.price)}` + (x.discount > 0 ? ` -${nfQty.format(x.discount)}%` : ''), money(x.total) + ' ' + x.vat_code))),
    el('hr'),
    r.disc_amount > 0 ? pair('Έκπτωση' + (r.disc_reason ? ' (' + r.disc_reason + ')' : ''), '-' + money(r.disc_amount)) : null,
    pair('ΣΥΝΟΛΟ', money(r.total) + ' €', 'rc-total'),
    r.deposit > 0 ? [pair('Προκαταβολή', money(r.deposit)), pair('Πληρωτέο', money(r.due))] : null,
    pair(r.payment === 'CARD' ? 'Κάρτα' : 'Μετρητά', money(r.due)),
    extra.given !== undefined && extra.given !== null ? [pair('Δόθηκαν', money(extra.given)), pair('Ρέστα', money(extra.change))] : null,
    el('hr'),
    r.vat_rows.map((v) => pair(`ΦΠΑ ${v.vat_code} ${nfQty.format(v.vat_rate)}%`, `${money(v.net)} + ${money(v.vat)}`)),
    r.cards.length ? [el('hr'), r.cards.map((c) => el('div', { class: 'rc-card' }, el('div', {}, c.name), pair('Serial', c.serial),
      c.pin ? pair('PIN', c.pin, 'rc-pin') : null))] : null,
    r.card ? [el('hr'), el('div', {}, r.customer), pair('Κάρτα', r.card),
      r.points_used > 0 ? pair('Πόντοι που εξαργυρώθηκαν', '-' + r.points_used) : null,
      pair('Πόντοι από αυτή την αγορά', '+' + r.points_earned), pair('Πόντοι τώρα', String(r.points))] : null,
    el('div', { class: 'rc-foot' }, lines(r.footer)));
  const old = $('#receipt');
  if (old) old.remove();
  document.body.append(box);
  // its length: as tall as it is (in mm, for the @page of the receipt; the CSSOM: the CSP allows it)
  const mm = Math.ceil(box.getBoundingClientRect().height * 25.4 / 96) + 12;
  const sheet = [...document.styleSheets].find((x) => (x.href || '').endsWith('app.css'));
  if (sheet) {
    for (let k = sheet.cssRules.length - 1; k >= 0; k -= 1) {
      if (sheet.cssRules[k].cssText.startsWith('@page receipt')) sheet.deleteRule(k);
    }
    sheet.insertRule(`@page receipt { size: 80mm ${mm}mm; margin: 0; }`, sheet.cssRules.length);
  }
  document.body.classList.remove('printing-doc', 'printing-card');   // (one before it, with no afterprint)
  document.body.classList.add('printing-receipt');
  const done = () => { document.body.classList.remove('printing-receipt'); window.removeEventListener('afterprint', done); };
  window.addEventListener('afterprint', done);
  window.print();
}

// -- a document of the office on A4 (an invoice, a delivery note ...): the shop (the header of the
// receipts), the partner, its lines, the VAT by rate, the totals; sent to myDATA: its MARK, UID and the QR
// of AADE. As the receipt: a box off the screen, alone on the page while printed
async function printDoc(d) {
  let shop = { header: '', footer: '' };
  try { shop = await api('pos/settings'); } catch (e) { /* the shop without a header */ }
  const lines = (text) => String(text || '').split('\n').filter((x) => x.trim()).map((x) => el('div', {}, x));
  const vat = {};
  d.lines.forEach((x) => {
    const k = String(x.vat_rate);
    vat[k] = vat[k] || { net: 0, vat: 0 };
    vat[k].net += x.net;
    vat[k].vat += x.vat;
  });
  const sent = d.mydata_state === 'S' && d.mydata_mark;
  const order = d.status === 'D' && d.doc_type === 'DPA';      // a draft delivery note of purchase: an order
  const box = el('div', { class: 'docprint', id: 'docprint' },
    el('div', { class: 'dp-head' }, el('div', { class: 'dp-shop' }, lines(shop.header)),
      el('div', { class: 'dp-title' }, el('div', { class: 'dp-type' }, order ? 'Παραγγελία προς προμηθευτή' : d.type_name),
        order ? null : el('div', {}, `${d.doc_type} ${d.doc_no || ''}`),
        el('div', {}, day(d.doc_date)), d.status === 'C' ? el('div', { class: 'dp-cancel' }, 'ΑΚΥΡΩΘΗΚΕ') : null)),
    d.doc_type === 'DAN' ? el('div', { class: 'dp-partner' }, el('div', { class: 'dp-label' }, 'Ανάλωση'),
      el('div', { class: 'dp-name' }, `Αποθήκη: ${d.warehouse} ${d.warehouse_name}`), el('div', {}, 'Αιτία: ' + REASONS[d.reason || 'USE']),
      el('div', {}, 'Στην τιμή κόστους κάθε παραλαβής (FIFO), χωρίς ΦΠΑ')) :
    d.side === 'T' ? el('div', { class: 'dp-partner' }, el('div', { class: 'dp-label' }, 'Ενδοδιακίνηση'),
      el('div', { class: 'dp-name' }, `Από: ${d.warehouse} ${d.warehouse_name}`), el('div', { class: 'dp-name' }, `Προς: ${d.to_warehouse} ${d.to_warehouse_name}`),
      el('div', {}, 'Στην τιμή κόστους κάθε παραλαβής (FIFO), χωρίς ΦΠΑ')) :
    el('div', { class: 'dp-partner' }, el('div', { class: 'dp-label' }, d.side === 'S' ? 'Πελάτης' : 'Προμηθευτής'),
      el('div', { class: 'dp-name' }, d.partner || ''), d.partner_afm ? el('div', {}, 'ΑΦΜ ' + d.partner_afm + (d.partner_doy ? ' · ΔΟΥ ' + d.partner_doy : '')) : null,
      d.partner_address ? el('div', {}, d.partner_address) : null,
      el('div', {}, 'Πληρωμή: ' + { CREDIT: 'επί πιστώσει', CASH: 'μετρητά', CARD: 'κάρτα' }[d.payment]),
      d.ref_text ? el('div', {}, 'Σχετικό: ' + d.ref_text) : null,
      d.notes_in.length ? el('div', {}, 'Δελτία: ' + d.notes_in.map(docText).join(', ')) : null),
    el('table', { class: 'dp-lines' }, el('thead', {}, el('tr', {}, ['#', 'Κωδικός', 'Περιγραφή', 'Ποσότητα', 'Τιμή', 'Έκπτ. %', 'ΦΠΑ %', 'Καθαρό']
      .map((h, k) => el('th', { class: k >= 3 ? 'num' : null }, h)))),
    el('tbody', {}, d.lines.map((x) => el('tr', {}, el('td', {}, x.line_no), el('td', {}, x.code),
      el('td', {}, x.name, x.serials ? el('div', { class: 'dp-small' }, x.serials) : null), el('td', { class: 'num' }, qty(x.qty)),
      el('td', { class: 'num' }, nf2.format(x.price)), el('td', { class: 'num' }, x.discount ? qty(x.discount) : ''),
      el('td', { class: 'num' }, qty(x.vat_rate)), el('td', { class: 'num' }, money(x.net)))))),
    el('div', { class: 'dp-foot' },
      el('div', { class: 'dp-mydata' }, sent ? [
        qrSvg(d.mydata_qr || ('MARK ' + d.mydata_mark)),
        el('div', {}, el('div', {}, 'MARK ' + d.mydata_mark), d.mydata_uid ? el('div', { class: 'dp-small' }, 'UID ' + d.mydata_uid) : null,
          el('div', { class: 'dp-small' }, 'Διαβιβάστηκε στο myDATA της ΑΑΔΕ'))] : null),
      el('table', { class: 'dp-sums' }, el('tbody', {},
        Object.entries(vat).map(([r, v]) => el('tr', {}, el('td', {}, `ΦΠΑ ${qty(Number(r))}%`), el('td', { class: 'num' }, money(v.net)), el('td', { class: 'num' }, money(v.vat)))),
        el('tr', { class: 'dp-total' }, el('td', {}, 'Καθαρό'), el('td'), el('td', { class: 'num' }, money(d.net))),
        el('tr', { class: 'dp-total' }, el('td', {}, 'ΦΠΑ'), el('td'), el('td', { class: 'num' }, money(d.vat))),
        el('tr', { class: 'dp-total dp-grand' }, el('td', {}, 'Σύνολο'), el('td'), el('td', { class: 'num' }, money(d.total) + ' €'))))),
    el('div', { class: 'dp-shop dp-footer' }, lines(shop.footer)));
  const old = $('#docprint');
  if (old) old.remove();
  document.body.append(box);
  document.body.classList.remove('printing-receipt', 'printing-card');   // (one before it, with no afterprint)
  document.body.classList.add('printing-doc');
  const done = () => { document.body.classList.remove('printing-doc'); window.removeEventListener('afterprint', done); };
  window.addEventListener('afterprint', done);
  window.print();
}

// -- the orders: written on a phone (a call, the shop), picked from the shelves, ready; at the till all
// of it at once (Ταμείο, «Παραγγελία»); a customer on credit: a delivery note (a manager) ----------
const ORDER_ST = { O: 'ανοιχτή', D: 'παραδόθηκε', C: 'ακυρώθηκε' };
// myDATA of a document (MM_DOC.MYDATA_STATE)
const MYDATA_ST = { '': 'δεν διαβιβάστηκε', Q: 'περιμένει διαβίβαση', S: 'διαβιβάστηκε', E: 'απέτυχε', X: 'ακυρώθηκε στο myDATA' };
async function ordersPage(params) {
  const all = params.get('all') === '1';
  const name = el('input', { name: 'name', required: true, autocomplete: 'off' });
  const phone = el('input', { name: 'phone', type: 'tel', required: true, autocomplete: 'off' });
  const date = el('input', { name: 'pickup_date', type: 'date', value: isoToday() });
  const notes = el('input', { name: 'notes', autocomplete: 'off' });
  const cust = el('select', { name: 'customer_id' }, el('option', { value: '' }, '—'));
  const out = el('div');
  if (may('CUSTOMERS')) {
    api('customers?limit=500').then((r) => r.rows.forEach((x) => cust.append(el('option', { value: x.id }, x.name))))
      .catch(fail);
    cust.addEventListener('change', async () => {
      if (!cust.value) return;
      try {
        const x = await api('customers/' + cust.value);
        if (!name.value) name.value = x.name;
        if (!phone.value && x.phone) phone.value = x.phone;
      } catch (e) { fail(e); }
    });
  }
  const form = el('form', {
    class: 'panel row',
    onsubmit: async (ev) => {
      ev.preventDefault();
      try {
        const o = await api('orders', {
          name: name.value.trim(), phone: phone.value.trim(), pickup_date: date.value || null,
          notes: notes.value.trim() || null, customer_id: cust.value ? Number(cust.value) : null,
        });
        location.hash = '#/order/' + o.id;
      } catch (e) { fail(e); }
    },
  }, el('label', {}, 'Όνομα', name), el('label', {}, 'Τηλέφωνο', phone), el('label', {}, 'Για', date),
  may('CUSTOMERS') ? el('label', {}, 'Πελάτης (χονδρική)', cust) : null, el('label', { class: 'grow' }, 'Σημείωση', notes),
  el('button', { class: 'primary', type: 'submit' }, 'Νέα παραγγελία'));
  try {
    const r = await api('orders' + (all ? '?status=all' : ''));
    out.replaceChildren(r.rows.length ? table([['#'], ['Όνομα'], ['Για'], ['Είδη', 'num'], ['Ποσό', 'num'], ['Κατάσταση'], ['Από', 'hide-phone']],
      r.rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = '#/order/' + x.id; } },
        el('td', {}, x.id), el('td', { class: 'wrap' }, x.name + (x.customer ? ' · ' + x.customer : '')), el('td', {}, day(x.pickup_date)),
        num(x.lines, qty), num(x.total),
        el('td', {}, x.status === 'O' ? (x.doc_id ? 'στο ταμείο' : x.ready_at ? 'έτοιμη' : x.source === 'O' && !x.confirmed_at ? 'online · προς επιβεβαίωση' : 'μαζεύεται') : ORDER_ST[x.status],
          x.source === 'O' ? el('span', { class: 'badge' }, 'online') : null),
        el('td', { class: 'hide-phone' }, x.created_by || ''))))
      : el('p', { class: 'muted' }, 'Καμία παραγγελία.'));
  } catch (e) { fail(e); }
  show(el('h1', {}, 'Παραγγελίες'), form,
    el('p', { class: 'row' }, el('a', { href: all ? '#/orders' : '#/orders?all=1' }, all ? 'Μόνο οι ανοιχτές' : 'Και οι παλιές (90 ημερών)'),
      el('a', { href: '#/poster' }, 'Αφίσα με QR για τις παραγγελίες των πελατών'),
      el('label', { class: 'check' }, el('input', {
        type: 'checkbox', name: 'sound', checked: soundOn(),
        onchange: (ev) => { try { localStorage.setItem('mm.sound', ev.target.checked ? 'on' : 'off'); } catch (e) { /* */ } if (ev.target.checked) { bellAudio(); bellSound(); } },
      }), '🔔 Ήχος για νέες online παραγγελίες')), out);
  name.focus();
}

async function orderPage(id) {
  const code = el('input', { name: 'code', autocomplete: 'off', placeholder: 'barcode, κωδικός ή περιγραφή' });
  const n = el('input', { name: 'qty', type: 'number', step: 'any', min: '0', value: '1', class: 'w6' });
  const found = el('div');
  const head = el('div', { class: 'panel' });
  const lines = el('div');
  const actions = el('div', { class: 'row' });
  const title = el('h1', {}, 'Παραγγελία ' + id);
  let o = null;
  const run = async (path, body) => {
    try {
      o = path === '' ? await api('orders/' + id) : await api(`orders/${id}/${path}`, body);
      draw();
      return o;
    } catch (e) { fail(e); return null; }
  };
  const add = async (c, q, mode = 'ADD') => {
    const r = await run('lines', { code: c, qty: q, mode });
    if (r) { code.value = ''; n.value = '1'; found.replaceChildren(); }
    code.focus();
    return r;
  };
  const draw = () => {
    const open = o.status === 'O' && !o.doc_id;
    title.textContent = `Παραγγελία ${o.id}: ${o.name}`;
    head.replaceChildren(el('dl', { class: 'kv' },
      [['Τηλέφωνο', el('a', { href: 'tel:' + o.phone }, o.phone)],
        ['Από', o.source === 'O' ? (o.confirmed_at ? 'online · επιβεβαιώθηκε ' + day(o.confirmed_at) : 'online · προς επιβεβαίωση: τηλεφώνησε στον πελάτη') : null],
        ['Για', day(o.pickup_date)], ['Πελάτης', o.customer], ['Σημείωση', o.notes],
        ['Κατάσταση', o.status === 'O' ? (o.doc_id ? `στο ταμείο (${o.doc_text || 'πρόχειρη απόδειξη'})` : o.ready_at ? 'έτοιμη' : 'μαζεύεται') : ORDER_ST[o.status] + (o.doc_text ? ' · ' + o.doc_text : '')],
        ['Προκαταβολή', o.deposit > 0 ? money(o.deposit) : null], ['Έγραψε', o.created_by], ['Σύνολο', money(o.total)]]
        .filter(([, v]) => v !== null && v !== undefined && v !== '')
        .flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)])));
    scan.hidden = !open;
    lines.replaceChildren(o.lines.length ? table([['Κωδικός', 'hide-phone'], ['Είδος'], ['Ποσότητα', 'num'], ['Τιμή', 'num hide-phone'], ['Ποσό', 'num'], ['Μαζεύτηκε'], ['']],
      o.lines.map((x) => {
        const done = x.picked >= x.qty;
        return el('tr', { class: done ? 'picked' : null }, el('td', { class: 'hide-phone' }, x.code),
          el('td', { class: 'wrap' }, x.name, x.available < 0 ? el('div', { class: 'neg' }, 'δεν φτάνει το απόθεμα') : null),
          num(x.qty, qty), num(x.price, money, 'num hide-phone'), num(x.total),
          el('td', {}, el('input', {
            type: 'checkbox', checked: done, disabled: !open, 'aria-label': 'Μαζεύτηκε ' + x.code,
            onchange: (ev) => run('pick', { item_id: x.item_id, qty: ev.target.checked ? x.qty : 0 }),
          })),
          el('td', { class: 'num' }, open ? [
            el('button', { type: 'button', 'aria-label': 'Μία λιγότερη ' + x.code, disabled: x.qty <= 1, onclick: () => add(x.code, x.qty - 1, 'SET') }, '−'),
            el('button', { type: 'button', 'aria-label': 'Μία ακόμα ' + x.code, onclick: () => add(x.code, 1) }, '+'),
            el('button', { type: 'button', class: 'danger', 'aria-label': 'Βγάλε ' + x.code, onclick: () => add(x.code, 0, 'SET') }, '×')] : null));
      })) : el('p', { class: 'muted' }, 'Κανένα είδος ακόμα: σάρωσε ή ψάξε.'));
    const btn = (text, fn, cls) => el('button', { type: 'button', class: cls || null, onclick: fn }, text);
    actions.replaceChildren(...(open ? [
      o.source === 'O' && !o.confirmed_at ? btn('Επιβεβαιώθηκε (μίλησα με τον πελάτη)', () => run('confirm', {}), 'primary') : null,
      o.ready_at ? btn('Όχι έτοιμη', () => run('ready', { ready: false }))
        : btn('Έτοιμη (όλα μαζεύτηκαν)', () => run('ready', { ready: true }), 'primary'),
      btn('Στο ταμείο', () => { location.hash = '#/pos?order=' + o.id; }),
      act('ORDERS', 'NOTE') && o.customer_id ? btn('Δελτίο αποστολής', async () => {
        if (!confirm('Δελτίο αποστολής (με πίστωση) για όλη την παραγγελία;')) return;
        if (await run('note', {})) toast('Το δελτίο αποστολής καταχωρήθηκε');
      }) : null,
      btn('Ακύρωση παραγγελίας', async () => {
        if (!confirm('Ακύρωση της παραγγελίας;')) return;
        await run('cancel', o.deposit > 0 ? { register: posReg } : {});
      }, 'danger')] : []).filter(Boolean));
  };
  const scan = el('form', {
    class: 'panel row scan',
    onsubmit: async (ev) => {
      ev.preventDefault();
      const v = code.value.trim();
      if (!v) return;
      // a code or a barcode (a scanner): the item; a word: the one item it finds, else the list
      try {
        const r = await api('items?limit=10&q=' + encodeURIComponent(v));
        const one = r.rows.find((x) => x.code.toUpperCase() === v.toUpperCase() || x.barcode === v)
          || (r.total === 1 ? r.rows[0] : null);
        if (one) await add(one.code, Number(n.value || 1));
        else if (!r.rows.length) toast('Δεν βρέθηκε: ' + v, true);
        else search();
      } catch (e) { fail(e); }
    },
  }, el('label', {}, 'Σάρωση ή αναζήτηση (Enter)', code), camera(code), el('label', {}, 'Ποσότητα', n), el('button', { class: 'primary', type: 'submit' }, 'Βάλε'));
  const search = async () => {
    const v = code.value.trim();
    if (v.length < 2) { found.replaceChildren(); return; }
    try {
      const r = await api('items?limit=10&q=' + encodeURIComponent(v));
      found.replaceChildren(r.rows.length ? table([['Κωδικός'], ['Περιγραφή'], ['Τιμή', 'num'], ['Απόθεμα', 'num'], ['']],
        r.rows.map((x) => el('tr', {}, el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.price), num(x.stock, qty),
          el('td', { class: 'num' }, el('button', { type: 'button', onclick: () => add(x.code, Number(n.value || 1)) }, '+'))))) : '');
    } catch (e) { fail(e); }
  };
  let timer;
  code.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 300); });
  show(title, head, scan, found, lines, actions, el('p', {}, el('a', { href: '#/orders' }, 'Όλες οι παραγγελίες')));
  await run('');
  code.focus();
}

// -- the office: the documents but the retail receipts (as the form «Τιμολόγια»), the receipts and
// payments (as «Εισπράξεις και πληρωμές») ---------------------------------------------------------
const DOC_ST = { D: 'πρόχειρο', P: 'καταχωρημένο', C: 'ακυρωμένο' };
let docTypes = null;
async function kinds() {
  if (!docTypes) docTypes = (await api('doc-types')).rows.filter((t) => t.code !== 'ALP');
  return docTypes;
}
let partnerLists = {};
async function partnersOf(kind) {           // customers / suppliers: [{id, name}]
  if (!partnerLists[kind]) partnerLists[kind] = (await api(kind + '?limit=500')).rows.filter((x) => x.active !== 'N');
  return partnerLists[kind];
}
function options(rows, value, text, chosen, empty) {
  return [empty ? el('option', { value: '' }, empty) : null,
    ...rows.map((x) => el('option', { value: x[value], selected: String(x[value]) === String(chosen) }, text(x)))];
}
const docText = (x) => `${x.doc_type} ${x.doc_no || '(πρόχειρο)'}`;

async function docsPage(params) {
  let types;
  try { types = await kinds(); } catch (e) { fail(e); return; }
  const type = el('select', { name: 'type' }, options(types, 'code', (t) => `${t.code} ${t.name}`, params.get('type') || 'DAP'));
  const partner = el('select', { name: 'partner' });
  const pay = el('select', { name: 'payment' }, [['CREDIT', 'Πίστωση'], ['CASH', 'Μετρητά'], ['CARD', 'Κάρτα']]
    .map(([v, t]) => el('option', { value: v }, t)));
  const date = el('input', { name: 'doc_date', type: 'date', value: isoToday() });
  // a transfer (DEN): from a warehouse to another, no partner, no payment
  const fromWh = el('select', { name: 'warehouse_id' });
  const toWh = el('select', { name: 'to_warehouse_id' });
  let whs = [];
  try { whs = (await api('warehouses')).rows.filter((w) => w.active === 'Y'); } catch (e) { whs = []; }
  fromWh.replaceChildren(...options(whs, 'id', (w) => `${w.code} ${w.name}`, whs.length ? whs[0].id : ''));
  toWh.replaceChildren(...options(whs, 'id', (w) => `${w.code} ${w.name}`, whs.length > 1 ? whs[1].id : '', '— αποθήκη —'));
  const reason = el('select', { name: 'reason' }, Object.entries(REASONS).map(([k, v]) => el('option', { value: k }, v)));
  const fill = async () => {
    const t = types.find((x) => x.code === type.value);
    const transfer = t.side === 'T';
    const consumption = t.code === 'DAN';
    partnerBox.hidden = transfer;
    payBox.hidden = transfer;
    fromBox.hidden = !transfer;
    toBox.hidden = !transfer || consumption;
    reasonBox.hidden = !consumption;
    fromBox.firstChild.textContent = consumption ? 'Αποθήκη' : 'Από αποθήκη';
    if (transfer) return;
    try {
      const rows = await partnersOf(t.side === 'S' ? 'customers' : 'suppliers');
      partner.replaceChildren(...options(rows, 'id', (x) => x.name, partner.value, t.side === 'S' ? '— πελάτης —' : '— προμηθευτής —'));
    } catch (e) { fail(e); }
  };
  const partnerBox = el('label', { class: 'grow' }, 'Πελάτης / προμηθευτής', partner);
  const payBox = el('label', {}, 'Πληρωμή', pay);
  const fromBox = el('label', {}, 'Από αποθήκη', fromWh);
  const toBox = el('label', {}, 'Προς αποθήκη', toWh);
  const reasonBox = el('label', {}, 'Αιτία', reason);
  reasonBox.hidden = true;
  type.addEventListener('change', fill);
  const form = el('form', {
    class: 'panel row',
    onsubmit: async (ev) => {
      ev.preventDefault();
      const t = types.find((x) => x.code === type.value);
      const body = { doc_type: t.code, payment: pay.value, doc_date: date.value || null };
      if (t.code === 'DAN') {
        body.warehouse_id = Number(fromWh.value);
        body.reason = reason.value;
      } else if (t.side === 'T') {
        body.warehouse_id = Number(fromWh.value);
        body.to_warehouse_id = toWh.value ? Number(toWh.value) : null;
      } else if (partner.value) body[t.side === 'S' ? 'customer_id' : 'supplier_id'] = Number(partner.value);
      try {
        const d = await api('docs', body);
        location.hash = '#/doc/' + d.id;
      } catch (e) { fail(e); }
    },
  }, el('label', {}, 'Είδος', type), partnerBox, fromBox, toBox, reasonBox,
  payBox, el('label', {}, 'Ημερομηνία', date), el('button', { class: 'primary', type: 'submit' }, 'Νέο'));
  // the notes not in an invoice yet: an invoice of one of them
  const notes = el('div');
  api('docs/notes').then((r) => notes.replaceChildren(r.rows.length ? el('details', {},
    el('summary', {}, `Δελτία χωρίς τιμολόγιο (${r.rows.length})`),
    table([['Δελτίο'], ['Ημερομηνία'], ['Πελάτης / προμηθευτής'], ['Σύνολο', 'num'], ['']], r.rows.map((x) => el('tr', {},
      el('td', {}, el('a', { href: '#/doc/' + x.id }, docText(x))), el('td', {}, day(x.doc_date)), el('td', { class: 'wrap' }, x.partner),
      num(x.total), el('td', { class: 'num' }, el('button', {
        type: 'button',
        onclick: async () => {
          try { location.hash = '#/doc/' + (await api('docs', { from_note: x.id })).id; } catch (e) { fail(e); }
        },
      }, 'Τιμολόγιο')))))) : '')).catch(fail);
  // the list: by kind and state, a search, in pages
  const fType = el('select', { 'aria-label': 'Είδος' }, options(types, 'code', (t) => t.code + ' ' + t.name, params.get('ft') || '', 'Όλα τα είδη'));
  const fSt = el('select', { 'aria-label': 'Κατάσταση' }, options(Object.entries(DOC_ST).map(([k, v]) => ({ k, v })), 'k', (x) => x.v, '', 'Όλες'));
  const q = el('input', { type: 'search', placeholder: 'πελάτης, προμηθευτής ή αριθμός' });
  const out = el('div');
  const go = async (offset = 0) => {
    try {
      const r = await api(`docs?limit=${pageSize}&offset=${Math.max(0, offset)}&type=${fType.value}&status=${fSt.value}&q=` + encodeURIComponent(q.value.trim()));
      out.replaceChildren(pager(r.total, r.offset, r.limit, go), table([['Παραστατικό'], ['Ημερομηνία'], ['Πελάτης / προμηθευτής'], ['Κατάσταση', 'hide-phone'], ['Σύνολο', 'num'], ['Στο τιμολόγιο', 'hide-phone']],
        r.rows.map((x) => el('tr', { class: 'click', onclick: () => { location.hash = '#/doc/' + x.id; } },
          el('td', {}, docText(x)), el('td', {}, day(x.doc_date)), el('td', { class: 'wrap' }, x.partner || ''),
          el('td', { class: 'hide-phone' }, DOC_ST[x.status]), num(x.total), el('td', { class: 'hide-phone' }, x.invoice_text || '')))));
    } catch (e) { fail(e); }
  };
  [fType, fSt].forEach((e) => e.addEventListener('change', () => go(0)));
  let timer;
  q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => go(0), 300); });
  show(el('h1', {}, 'Τιμολόγια και δελτία'), form, notes,
    el('div', { class: 'panel row' }, el('label', {}, 'Είδος', fType), el('label', {}, 'Κατάσταση', fSt), el('label', { class: 'grow' }, 'Αναζήτηση', q)), out);
  await fill();
  go(0);
}

async function docPage(id) {
  const title = el('h1', {}, 'Παραστατικό');
  const head = el('div', { class: 'panel' });
  const lines = el('div');
  const actions = el('div', { class: 'row' });
  const code = el('input', { name: 'code', autocomplete: 'off', placeholder: 'barcode, κωδικός ή περιγραφή' });
  const n = el('input', { name: 'qty', type: 'number', step: 'any', min: '0', value: '1', class: 'w6' });
  const price = el('input', { name: 'price', type: 'number', step: '0.0001', min: '0', placeholder: 'αυτόματη', class: 'w8' });
  const disc = el('input', { name: 'discount', type: 'number', step: '0.01', min: '0', max: '100', value: '0', class: 'w6' });
  const exp = el('input', { name: 'expires', type: 'date' });
  const priceBox = el('label', {}, 'Τιμή', price);
  const discBox = el('label', {}, 'Έκπτ. %', disc);
  const expBox = el('label', {}, 'Λήξη', exp);
  const found = el('div');
  const extra = el('div');
  let d = null;
  const run = async (path, body) => {
    try {
      d = path === '' ? await api('docs/' + id) : await api(`docs/${id}/${path}`, body);
      draw();
      return d;
    } catch (e) { fail(e); return null; }
  };
  const addLine = async (c) => {
    const body = { code: c, qty: Number(n.value || 1), discount: Number(disc.value || 0) };
    if (price.value !== '') body.price = Number(price.value);
    if (receiving() && exp.value) body.expires = exp.value;
    if (await run('lines', body)) { code.value = ''; n.value = '1'; price.value = ''; disc.value = '0'; exp.value = ''; found.replaceChildren(); }
    code.focus();
  };
  // goods received from a supplier (DPA, TAD): each line its date of expiry
  const receiving = () => d && d.side === 'P' && d.stock_sign === 1;
  const reasonPick = () => el('select', {
    'aria-label': 'Αιτία',
    onchange: (ev) => run('reason', { reason: ev.target.value }),
  }, Object.entries(REASONS).map(([k, v]) => el('option', { value: k, selected: (d.reason || 'USE') === k }, v)));
  const draw = () => {
    const draft = d.status === 'D';
    title.textContent = `${d.type_name} ${d.doc_no || '(πρόχειρο)'}`;
    expBox.hidden = !receiving();
    head.replaceChildren(el('dl', { class: 'kv' }, [
      ['Είδος', `${d.doc_type} ${d.type_name}`], ['Ημερομηνία', day(d.doc_date)], ['Κατάσταση', DOC_ST[d.status]],
      ...(d.doc_type === 'DAN' ? [['Αποθήκη', `${d.warehouse} ${d.warehouse_name}`], ['Αιτία', d.status === 'D' ? reasonPick() : REASONS[d.reason || 'USE']]]
        : d.side === 'T' ? [['Από αποθήκη', `${d.warehouse} ${d.warehouse_name}`], ['Προς αποθήκη', `${d.to_warehouse} ${d.to_warehouse_name}`]]
        : [[d.side === 'S' ? 'Πελάτης' : 'Προμηθευτής', d.partner], ['Πληρωμή', { CREDIT: 'πίστωση', CASH: 'μετρητά', CARD: 'κάρτα' }[d.payment]]]),
      ['Από', d.ref_text], ['Στο τιμολόγιο', d.invoice_text],
      ['Δελτία του', d.notes_in.length ? d.notes_in.map(docText).join(', ') : null],
      ...(d.side === 'T' ? [['Αξία στο κόστος', money(d.total)]] : [['Καθαρό', money(d.net)], ['ΦΠΑ', money(d.vat)], ['Σύνολο', money(d.total)]]),
      ['myDATA', d.mydata_type && d.status !== 'D' ? MYDATA_ST[d.mydata_state || ''] + (d.mydata_mark ? ' · MARK ' + d.mydata_mark : '')
        + (d.mydata_cancel_mark ? ' · ακύρωση ' + d.mydata_cancel_mark : '') : null],
      ['Λάθος myDATA', d.mydata_state === 'E' || d.mydata_state === 'Q' ? d.mydata_error : null]]
      .filter(([, v]) => v !== null && v !== undefined && v !== '').flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)])));
    addForm.hidden = !draft;
    const withExp = receiving() && (draft || d.lines.some((x) => x.expires));
    priceBox.hidden = d.side === 'T';                 // (a transfer: at cost, by the layers)
    discBox.hidden = d.side === 'T';
    lines.replaceChildren(d.lines.length ? table([['#'], ['Είδος'], ['Ποσότητα', 'num'], [d.side === 'T' ? 'Κόστος' : 'Τιμή', 'num'], ['Έκπτ. %', 'num hide-phone'],
      ...(withExp ? [['Λήξη']] : []), ['Σύνολο', 'num'], ['']],
      d.lines.map((x) => {
        const setQ = (q) => run(`lines/${x.id}`, { qty: q });
        const q = draft && x.serial_tracked !== 'Y'
          ? el('input', { type: 'number', step: 'any', min: '0', value: x.qty, class: 'w6', 'aria-label': 'Ποσότητα ' + x.code, onchange: (ev) => setQ(Number(ev.target.value)) })
          : qty(x.qty);
        return el('tr', {}, el('td', {}, x.line_no),
          el('td', { class: 'wrap' }, `${x.code} ${x.name}`, x.serials ? el('div', { class: 'muted' }, x.serials) : null),
          el('td', { class: 'num' }, q), num(x.price, (v) => nf2.format(v)), num(x.discount, qty, 'num hide-phone'),
          withExp ? el('td', {}, draft
            ? el('input', { type: 'date', value: x.expires ? x.expires.slice(0, 10) : '', 'aria-label': 'Λήξη ' + x.code, onchange: (ev) => run(`lines/${x.id}`, { expires: ev.target.value }) })
            : day(x.expires)) : null,
          num(x.total),
          el('td', { class: 'num' }, draft ? el('button', { type: 'button', class: 'danger', 'aria-label': 'Σβήσε ' + x.code, onclick: () => setQ(0) }, '×') : null));
      })) : el('p', { class: 'muted' }, draft ? 'Καμία γραμμή ακόμα.' : ''));
    const btn = (text, fn, cls) => el('button', { type: 'button', class: cls || null, onclick: fn }, text);
    const ask = (text, fn) => () => { if (confirm(text)) fn(); };
    const isInvoice = !!d.ref_type;
    const canInvoice = d.status === 'P' && !d.invoice_id && docTypes && docTypes.some((t) => t.ref_type === d.doc_type);
    actions.replaceChildren(...[
      draft && act('DOCS', 'POST') ? btn('Καταχώριση', ask('Καταχώριση;', async () => { if (await run('post', {})) toast('Καταχωρήθηκε με αριθμό ' + d.doc_no); }), 'primary') : null,
      draft ? btn('Σβήσε πρόχειρο', ask('Σβήσιμο του πρόχειρου;', async () => {
        try { await api(`docs/${id}/delete`, {}); location.hash = '#/docs'; } catch (e) { fail(e); }
      }), 'danger') : null,
      canInvoice ? btn('Τιμολόγιο από αυτό', async () => {
        try { location.hash = '#/doc/' + (await api('docs', { from_note: d.id })).id; } catch (e) { fail(e); }
      }, 'primary') : null,
      d.status === 'P' && d.partner_sign === 1          // an invoice (TPY, TAG, TDA, TAD): goods back
        ? btn('Επιστροφή', ask('Πρόχειρο δελτίο επιστροφής με τις γραμμές του;', async () => {
          try { location.hash = '#/doc/' + (await api(`docs/${id}/credit`, {})).id; toast('Κράτησε ό,τι γύρισε και καταχώρισέ το· μετά «Τιμολόγιο από αυτό» για το πιστωτικό'); } catch (e) { fail(e); }
        })) : null,
      // myDATA (an invoice or a credit note of a sale): sent now; its XML; a sent one: cancelled there first
      d.status === 'P' && d.mydata_type && d.mydata_state !== 'S' && d.mydata_state !== 'X'
        ? btn('Διαβίβαση στο myDATA', ask('Διαβίβαση στην ΑΑΔΕ (myDATA);', async () => {
          if (await run('mydata', {})) toast(d.mydata_state === 'S' ? 'Διαβιβάστηκε: MARK ' + d.mydata_mark : (d.mydata_error || 'Δεν διαβιβάστηκε'), d.mydata_state !== 'S');
        }), 'primary') : null,
      d.status === 'P' && d.mydata_type ? btn('XML myDATA', async () => {
        try { mydataXml.replaceChildren(el('pre', { class: 'xml' }, (await api(`docs/${id}/mydata`)).xml)); } catch (e) { fail(e); }
      }) : null,
      d.status !== 'D' ? btn('Εκτύπωση', () => printDoc(d)) : null,
      draft && d.doc_type === 'DPA' && d.lines.length ? btn('Εκτύπωση παραγγελίας', () => printDoc(d)) : null,
      !act('DOCS', 'CANCEL') ? null : d.status === 'P' && d.mydata_state === 'S'
        ? btn('Ακύρωση (και στο myDATA)', ask('Ακύρωση στην ΑΑΔΕ (myDATA) και εδώ;', () => run('mydata/cancel', {})), 'danger')
        : d.status === 'P' ? btn('Ακύρωση', ask('Ακύρωση του παραστατικού;', () => run('cancel', {})), 'danger') : null,
    ].filter(Boolean));
    // a draft invoice: one more note of its partner, of its kind of note
    extra.replaceChildren();
    if (draft && isInvoice) {
      const who = d.customer_id ? 'customer_id=' + d.customer_id : 'supplier_id=' + d.supplier_id;
      api(`docs/notes?type=${d.ref_type}&${who}`).then((r) => extra.replaceChildren(r.rows.length ? el('div', { class: 'panel' },
        el('h2', {}, 'Από δελτίο'), table([['Δελτίο'], ['Ημερομηνία'], ['Σύνολο', 'num'], ['']], r.rows.map((x) => el('tr', {},
          el('td', {}, docText(x)), el('td', {}, day(x.doc_date)), num(x.total),
          el('td', { class: 'num' }, el('button', { type: 'button', onclick: () => run('notes', { note_id: x.id }) }, 'Βάλε')))))) : '')).catch(fail);
    }
  };
  const addForm = el('form', {
    class: 'panel row scan',
    onsubmit: async (ev) => {
      ev.preventDefault();
      const v = code.value.trim();
      if (!v) return;
      try {
        const r = await api('items?limit=10&q=' + encodeURIComponent(v));
        const one = r.rows.find((x) => x.code.toUpperCase() === v.toUpperCase() || x.barcode === v) || (r.total === 1 ? r.rows[0] : null);
        if (one) await addLine(one.code);
        else if (!r.rows.length) toast('Δεν βρέθηκε: ' + v, true);
        else {
          found.replaceChildren(table([['Κωδικός'], ['Περιγραφή'], ['Απόθεμα', 'num'], ['']], r.rows.map((x) => el('tr', {},
            el('td', {}, x.code), el('td', { class: 'wrap' }, x.name), num(x.stock, qty),
            el('td', { class: 'num' }, el('button', { type: 'button', onclick: () => addLine(x.code) }, '+'))))));
        }
      } catch (e) { fail(e); }
    },
  }, el('label', { class: 'grow' }, 'Είδος (Enter)', code), camera(code), el('label', {}, 'Ποσότητα', n), priceBox,
  discBox, expBox, el('button', { class: 'primary', type: 'submit' }, 'Βάλε γραμμή'));
  try { await kinds(); } catch (e) { /* the buttons without it */ }
  const mydataXml = el('div');
  show(title, head, addForm, found, lines, extra, actions, mydataXml, el('p', {}, el('a', { href: '#/docs' }, 'Όλα τα παραστατικά')));
  await run('');
  if (d && d.status === 'D') code.focus();
}

async function paymentsPage() {
  const kind = el('select', { name: 'kind' }, el('option', { value: 'R' }, 'Είσπραξη από πελάτη'), el('option', { value: 'P' }, 'Πληρωμή σε προμηθευτή'));
  const partner = el('select', { name: 'partner_id', required: true });
  const amount = el('input', { name: 'amount', type: 'number', step: '0.01', min: '0.01', required: true, class: 'w8' });
  const method = el('select', { name: 'method' }, [['CASH', 'Μετρητά'], ['CARD', 'Κάρτα'], ['BANK', 'Έμβασμα']].map(([v, t]) => el('option', { value: v }, t)));
  const date = el('input', { name: 'pay_date', type: 'date', value: isoToday() });
  const notes = el('input', { name: 'notes', autocomplete: 'off' });
  const reg = el('select', { name: 'register' }, el('option', { value: '' }, '—'));
  api('pos').then((r) => r.rows.forEach((x) => reg.append(el('option', { value: x.code }, `${x.code} ${x.name}`)))).catch(fail);
  const balance = el('span', { class: 'muted' });
  const fill = async () => {
    try {
      const rows = await partnersOf(kind.value === 'R' ? 'customers' : 'suppliers');
      partner.replaceChildren(...options(rows, 'id', (x) => x.name, '', kind.value === 'R' ? '— πελάτης —' : '— προμηθευτής —'));
      method.value = kind.value === 'R' ? 'CASH' : 'BANK';
      balance.textContent = '';
    } catch (e) { fail(e); }
  };
  kind.addEventListener('change', fill);
  partner.addEventListener('change', async () => {
    balance.textContent = '';
    if (!partner.value) return;
    try {
      const x = await api((kind.value === 'R' ? 'customers/' : 'suppliers/') + partner.value);
      balance.textContent = (kind.value === 'R' ? 'Χρωστάει: ' : 'Του χρωστάμε: ') + money(x.balance);
    } catch (e) { fail(e); }
  });
  const out = el('div');
  const go = async (offset = 0) => {
    try {
      const r = await api(`payments?limit=${pageSize}&offset=${Math.max(0, offset)}`);
      out.replaceChildren(pager(r.total, r.offset, r.limit, go), table([['Ημερομηνία'], ['Είδος'], ['Πελάτης / προμηθευτής'], ['Τρόπος', 'hide-phone'], ['Ποσό', 'num'], ['']],
        r.rows.map((x) => el('tr', { class: x.status === 'C' ? 'cancelled' : null }, el('td', {}, day(x.pay_date)),
          el('td', {}, x.kind === 'R' ? 'Είσπραξη' : 'Πληρωμή'), el('td', { class: 'wrap' }, x.partner + (x.notes ? ' · ' + x.notes : '')),
          el('td', { class: 'hide-phone' }, { CASH: 'μετρητά', CARD: 'κάρτα', BANK: 'έμβασμα' }[x.method] + (x.register ? ' (' + x.register + ')' : '')),
          num(x.amount), el('td', { class: 'num' }, x.status === 'C' ? 'ακυρώθηκε' : !act('PAYMENTS', 'CANCEL') ? '' : el('button', {
            type: 'button', class: 'danger',
            onclick: async () => {
              if (!confirm('Ακύρωση της κίνησης;')) return;
              try { await api(`payments/${x.id}/cancel`, {}); go(r.offset); } catch (e) { fail(e); }
            },
          }, 'Ακύρωση'))))));
    } catch (e) { fail(e); }
  };
  const form = el('form', {
    class: 'panel row',
    onsubmit: async (ev) => {
      ev.preventDefault();
      try {
        const p = await api('payments', {
          kind: kind.value, partner_id: Number(partner.value), amount: Number(amount.value), method: method.value,
          pay_date: date.value || null, notes: notes.value.trim() || null, register: reg.value || null,
        });
        toast(`${p.kind === 'R' ? 'Είσπραξη' : 'Πληρωμή'} ${money(p.amount)}: καταχωρήθηκε`);
        amount.value = '';
        notes.value = '';
        partner.dispatchEvent(new Event('change'));
        go(0);
      } catch (e) { fail(e); }
    },
  }, el('label', {}, 'Κίνηση', kind), el('label', { class: 'grow' }, 'Πελάτης / προμηθευτής', partner, balance),
  el('label', {}, 'Ποσό', amount), el('label', {}, 'Τρόπος', method), el('label', {}, 'Ημερομηνία', date),
  el('label', {}, 'Ταμείο (μετρητά/κάρτα)', reg), el('label', { class: 'grow' }, 'Σημείωση', notes),
  el('button', { class: 'primary', type: 'submit' }, 'Καταχώριση'));
  show(el('h1', {}, 'Εισπράξεις και πληρωμές'), form, out);
  await fill();
  go(0);
}

// -- the pages, by the address (#/...) -------------------------------------------------------------
// the pages of a page: where its group is (an item is of the items, a ledger of its own list ...)
const SECTION = { menu: '#/roles', item: '#/items', partner: '#/partners/', ledger: '#/partners/', count: '#/counts', order: '#/orders', doc: '#/docs' };
function navBar() {
  $('#top').hidden = false;
  $('#who').textContent = `${session.username} (${session.role})` + (session.warehouse ? ` · ${session.warehouse_name || session.warehouse}` : '');
  const hash = location.hash || '#/items';
  const first = hash.slice(2).split(/[/?]/)[0];
  const here = (h) => hash.startsWith(h) || (SECTION[first] && h.startsWith(SECTION[first]));
  let open = null;
  try { open = sessionStorage.getItem('mm.menu'); } catch (e) { open = null; }
  const known = new Set(MENU.flatMap(([, ps]) => ps.map(([h]) => h)));
  const groups = (session.menu || []).map((g) => [g.name, g.screens.filter((x) => known.has(x.route)).map((x) => [x.route, x.name])]);
  $('#nav').replaceChildren(...groups.map(([group, mine]) => {
    if (!mine.length) return null;
    const current = mine.some(([h]) => here(h));
    const d = el('details', { name: 'menu', open: current || (!groups.some(([, ps]) => ps.some(([h]) => here(h))) && open === group) },
      el('summary', {}, group),
      mine.map(([h, t]) => el('a', { href: h, class: here(h) ? 'on' : null, 'aria-current': here(h) ? 'page' : null }, t)));
    d.addEventListener('toggle', () => { if (d.open) { try { sessionStorage.setItem('mm.menu', group); } catch (e) { /* */ } } });
    return d;
  }).filter(Boolean));
  document.body.classList.remove('menu-open');
  $('#menu').setAttribute('aria-expanded', 'false');
  bellBadge();
}
$('#menu').addEventListener('click', () => {
  const on = document.body.classList.toggle('menu-open');
  $('#menu').setAttribute('aria-expanded', String(on));
});
$('#nav').addEventListener('click', (ev) => {        // a page chosen (the same one too): the drawer closed
  if (ev.target.closest('a')) {
    document.body.classList.remove('menu-open');
    $('#menu').setAttribute('aria-expanded', 'false');
  }
});
function render() {
  if (APP && !server) {
    serverPage();
    return;
  }
  if (!session) {
    loginPage();
    return;
  }
  if (!session.rights) {
    loadRights().then(render, (e) => { fail(e); logoutLocal(); });
    return;
  }
  navBar();
  bellStart();
  backupStart();
  const [path, query] = (location.hash.slice(1) || '/items').split('?');
  const params = new URLSearchParams(query || '');
  const p = path.split('/').filter(Boolean).map(decodeURIComponent);
  // a page: its screen (MM_RIGHTS), at least read
  const need = (screen, fn) => (may(screen) ? fn() : show(el('h1', {}, 'Δεν επιτρέπεται'),
    el('p', { class: 'muted' }, 'Δεν έχεις δικαίωμα σε αυτή τη σελίδα.')));
  const partner = (k) => (k === 'customers' || k === 'customer' ? 'CUSTOMERS' : 'SUPPLIERS');
  const REPORT = { consumption: 'REP_CONSUMPTION', 'sales-by': 'REP_SALES_BY', sales: 'REP_SALES', vat: 'REP_VAT', 'min-stock': 'REP_MIN_STOCK', 'trial-items': 'TRIAL_ITEMS',
    'trial-customers': 'TRIAL_CUSTOMERS', 'trial-suppliers': 'TRIAL_SUPPLIERS', profit: 'PROFIT', 'stock-value': 'STOCK_VALUE' };
  switch (p[0]) {
    case 'pos': return need('POS', () => posPage(params));
    case 'orders': return need('ORDERS', () => ordersPage(params));
    case 'poster': return need('ORDERS', () => posterPage());
    case 'docs': return need('DOCS', () => docsPage(params));
    case 'doc': return need('DOCS', () => docPage(p[1]));
    case 'payments': return need('PAYMENTS', () => paymentsPage());
    case 'order': return need('ORDERS', () => orderPage(p[1]));
    case 'labels': return need('LABELS', () => labelsPage());
    case 'item': return need('ITEMS', () => itemPage(p[1]));
    case 'partners': return need(partner(p[1]), () => partnersPage(p[1], params));
    case 'partner': return need(partner(p[1]), () => partnerPage(p[1], p[2]));
    case 'ledger': return need('LEDGERS', () => ledgerPage(p[1], p[2], params));
    case 'reports': return need(REPORT[p[1]] || 'NONE', () => reportPage(p[1], params));
    case 'counts': return need('COUNTS', () => countsPage());
    case 'scratch': return need('SCRATCH', () => scratchPage());
    case 'day': return need('DAY', () => dayPage(params));
    case 'chart': return need('CHART', () => chartPage(params));
    case 'expiry': return need('EXPIRY', () => expiryPage(params));
    case 'warehouses': return need('WAREHOUSES', () => warehousesPage());
    case 'warehouse': return need('WAREHOUSES', () => warehousePage(p[1]));
    case 'users': return need('USERS', () => usersPage());
    case 'roles': return need('ROLES', () => rolesPage(p[1]));
    case 'menu': return need('ROLES', () => menuPage());
    case 'audit': return need('AUDIT', () => auditPage(params));
    case 'count': return need('COUNTS', () => countPage(p[1]));
    default: {
      // the items, else the first page of the menu
      if (may('ITEMS')) return itemsPage(params);
      const first = (session.menu || []).flatMap((g) => g.screens).find((x) => x.route);
      if (first && first.route !== '#/items') { location.hash = first.route; return null; }
      return show(el('h1', {}, 'Καμία σελίδα'), el('p', { class: 'muted' }, 'Δεν έχεις δικαίωμα σε καμία σελίδα.'));
    }
  }
}

$('#logout').addEventListener('click', async () => {
  try { await api('auth/logout', {}); } catch (e) { /* out all the same */ }
  logoutLocal();
});
window.addEventListener('hashchange', render);
render();
