// app.js -- the pages of the mini market (step 8): a login, then the till, the items, the customers
// and the suppliers, the ledgers, the reports and the counts of the stock, through /api/ with the token of the
// login (sessionStorage: gone with the tab). Every value goes in as text (textContent), never as HTML.
// The pages by role: CASHIER the till, the items and the counts; MANAGER all the rest; as the REST service.

import { barsSvg, itemBars, qrSvg } from './codes.js';
import { canScan, codeOf, scanOnce } from './scan.js';

const $ = (sel) => document.querySelector(sel);
const main = () => $('#main');
const RANK = { CASHIER: 1, MANAGER: 2, ADMIN: 3 };
// the menu: its groups and their pages (by role: CASHIER the till, the store; MANAGER the office too)
const MENU = [
  ['Πωλήσεις', [['#/pos', 'Ταμείο', 'CASHIER'], ['#/orders', 'Παραγγελίες', 'CASHIER']]],
  ['Αποθήκη', [['#/items', 'Είδη', 'CASHIER'], ['#/labels', 'Ετικέτες', 'CASHIER'], ['#/counts', 'Απογραφή', 'CASHIER']]],
  ['Γραφείο', [['#/docs', 'Τιμολόγια', 'MANAGER'], ['#/payments', 'Εισπράξεις', 'MANAGER'],
    ['#/partners/customers', 'Πελάτες', 'MANAGER'], ['#/partners/suppliers', 'Προμηθευτές', 'MANAGER']]],
  ['Αναφορές', [['#/reports/sales', 'Πωλήσεις', 'MANAGER'], ['#/reports/vat', 'ΦΠΑ', 'MANAGER'],
    ['#/reports/min-stock', 'Ελάχιστο απόθεμα', 'MANAGER'], ['#/reports/trial-items', 'Ισοζύγιο ειδών', 'MANAGER'],
    ['#/reports/trial-customers', 'Ισοζύγιο πελατών', 'MANAGER'], ['#/reports/trial-suppliers', 'Ισοζύγιο προμηθευτών', 'MANAGER']]],
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
  if (!session || !can('CASHIER')) return;
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
  if (!session || !can('MANAGER')) { box.hidden = true; return; }
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
        el('button', { onclick: () => { labelAdd(x, 1); location.hash = '#/labels'; } }, 'Ετικέτα'),
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
  const titles = { sales: 'Πωλήσεις ανά ημέρα', vat: 'ΦΠΑ πωλήσεων και αγορών', 'min-stock': 'Είδη κάτω από το ελάχιστο απόθεμα',
    'trial-items': 'Ισοζύγιο ειδών', 'trial-customers': 'Ισοζύγιο πελατών', 'trial-suppliers': 'Ισοζύγιο προμηθευτών' };
  if (!titles[name]) { show(el('h1', {}, 'Δεν υπάρχει αυτή η αναφορά')); return; }
  const trial = name.startsWith('trial-');
  const all = el('input', { type: 'checkbox', name: 'all', checked: params.get('all') === '1' });
  const from = el('input', { type: 'date', value: params.get('from') || isoYearStart() });
  const to = el('input', { type: 'date', value: params.get('to') || isoToday() });
  const out = el('div');
  const go = async () => {
    try {
      const r = await api(`reports/${name}?from=${from.value}&to=${to.value}` + (trial && all.checked ? '&all=1' : ''));
      out.replaceChildren(trial ? trialTable(name, r, from.value, to.value) : name === 'sales' ? salesTable(r.rows) : name === 'vat' ? vatTable(r.rows) : minTable(r.rows));
    } catch (e) { fail(e); }
  };
  const form = name === 'min-stock' ? null
    : el('form', { class: 'panel row', onsubmit: (ev) => { ev.preventDefault(); go(); } },
      el('label', {}, 'Από', from), el('label', {}, 'Έως', to),
      trial ? el('label', { class: 'check' }, all, 'Και όσα έχουν μηδέν παντού') : null,
      el('button', { class: 'primary', type: 'submit' }, 'Εμφάνιση'));
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
  }, el('label', {}, 'Σάρωση (Enter)', code), camera(code), el('label', {}, 'Ποσότητα', n), el('label', {}, 'Τρόπος', mode),
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
  if (!regs.some((r) => r.code === posReg)) posReg = regs[0].code;
  const pick = el('select', {
    'aria-label': 'Ταμείο',
    onchange: () => {
      posReg = pick.value;
      try { localStorage.setItem('mm.register', posReg); } catch (e) { /* a private window */ }
      load();
    },
  }, regs.map((r) => el('option', { value: r.code, selected: r.code === posReg }, `${r.code} ${r.name}`)));
  const zText = el('span', { class: 'muted' });
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
  let st = null;
  const run = async (path, body) => {
    try {
      st = await api(`pos/${encodeURIComponent(posReg)}${path}`, body);
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
    if (z) {
      const amount = el('input', { type: 'number', step: '0.01', placeholder: '+ μπαίνουν, − βγαίνουν', class: 'w11' });
      const note = el('input', { placeholder: 'αιτιολογία' });
      zBox.replaceChildren(
        el('label', {}, 'Κίνηση συρταριού', amount), el('label', {}, 'Αιτιολογία', note),
        el('button', { type: 'button', onclick: () => run('/cash', { amount: Number(amount.value), note: note.value.trim() }) }, 'Καταχώριση κίνησης'),
        el('button', {
          type: 'button',
          class: 'danger',
          onclick: async () => {
            if (!confirm(`Κλείσιμο του Ζ ${z.z_no};`)) return;
            const r = await run('/close', {});
            if (r && r.closed) toast(`Ζ ${r.closed.z_no} έκλεισε: σύνολο ${money(r.closed.total)}, μετρητά ${money(r.closed.cash)}, κάρτα ${money(r.closed.card)}`);
          },
        }, 'Κλείσιμο Ζ'));
    } else {
      const cash = el('input', { type: 'number', step: '0.01', min: '0', value: '0', class: 'w8' });
      zBox.replaceChildren(el('label', {}, 'Αρχικό ταμείο', cash),
        el('button', { type: 'button', class: 'primary', onclick: () => run('/open', { cash: Number(cash.value || 0) }) }, 'Άνοιγμα Ζ'));
    }
    scan.hidden = !z;
    pay.hidden = !st.receipt;
    const r = st.receipt;
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
  const setup = can('MANAGER') ? el('details', { class: 'receipt-setup' }, el('summary', {}, 'Επικεφαλίδα και υποσέλιδο της απόδειξης')) : null;
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
  show(el('h1', {}, 'Ταμείο'), el('div', { class: 'panel' }, el('div', { class: 'row' }, el('label', {}, 'Ταμείο', pick), zText), zBox),
    scan, orders, lines, pay, change, el('label', { class: 'check' }, autoPrint, 'Εκτύπωση απόδειξης αυτόματα'), last, setup);
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
    r.status === 'C' ? el('div', { class: 'rc-title' }, '*** ΑΚΥΡΩΘΗΚΕ ***') : null,
    el('hr'),
    r.lines.map((x) => el('div', { class: 'rc-line' }, el('div', {}, x.name),
      pair(`${nfQty.format(x.qty)} x ${money(x.price)}` + (x.discount > 0 ? ` -${nfQty.format(x.discount)}%` : ''), money(x.total) + ' ' + x.vat_code))),
    el('hr'),
    pair('ΣΥΝΟΛΟ', money(r.total) + ' €', 'rc-total'),
    r.deposit > 0 ? [pair('Προκαταβολή', money(r.deposit)), pair('Πληρωτέο', money(r.due))] : null,
    pair(r.payment === 'CARD' ? 'Κάρτα' : 'Μετρητά', money(r.due)),
    extra.given !== undefined && extra.given !== null ? [pair('Δόθηκαν', money(extra.given)), pair('Ρέστα', money(extra.change))] : null,
    el('hr'),
    r.vat_rows.map((v) => pair(`ΦΠΑ ${v.vat_code} ${nfQty.format(v.vat_rate)}%`, `${money(v.net)} + ${money(v.vat)}`)),
    r.cards.length ? [el('hr'), r.cards.map((c) => el('div', { class: 'rc-card' }, el('div', {}, c.name), pair('Serial', c.serial),
      c.pin ? pair('PIN', c.pin, 'rc-pin') : null))] : null,
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
  document.body.classList.remove('printing-doc');         // (a document before it, with no afterprint)
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
  const box = el('div', { class: 'docprint', id: 'docprint' },
    el('div', { class: 'dp-head' }, el('div', { class: 'dp-shop' }, lines(shop.header)),
      el('div', { class: 'dp-title' }, el('div', { class: 'dp-type' }, d.type_name), el('div', {}, `${d.doc_type} ${d.doc_no || ''}`),
        el('div', {}, day(d.doc_date)), d.status === 'C' ? el('div', { class: 'dp-cancel' }, 'ΑΚΥΡΩΘΗΚΕ') : null)),
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
  document.body.classList.remove('printing-receipt');     // (a receipt before it, with no afterprint)
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
  if (can('MANAGER')) {
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
  can('MANAGER') ? el('label', {}, 'Πελάτης (χονδρική)', cust) : null, el('label', { class: 'grow' }, 'Σημείωση', notes),
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
      can('MANAGER') && o.customer_id ? btn('Δελτίο αποστολής', async () => {
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
  const fill = async () => {
    const t = types.find((x) => x.code === type.value);
    try {
      const rows = await partnersOf(t.side === 'S' ? 'customers' : 'suppliers');
      partner.replaceChildren(...options(rows, 'id', (x) => x.name, partner.value, t.side === 'S' ? '— πελάτης —' : '— προμηθευτής —'));
    } catch (e) { fail(e); }
  };
  type.addEventListener('change', fill);
  const form = el('form', {
    class: 'panel row',
    onsubmit: async (ev) => {
      ev.preventDefault();
      const t = types.find((x) => x.code === type.value);
      const body = { doc_type: t.code, payment: pay.value, doc_date: date.value || null };
      if (partner.value) body[t.side === 'S' ? 'customer_id' : 'supplier_id'] = Number(partner.value);
      try {
        const d = await api('docs', body);
        location.hash = '#/doc/' + d.id;
      } catch (e) { fail(e); }
    },
  }, el('label', {}, 'Είδος', type), el('label', { class: 'grow' }, 'Πελάτης / προμηθευτής', partner),
  el('label', {}, 'Πληρωμή', pay), el('label', {}, 'Ημερομηνία', date), el('button', { class: 'primary', type: 'submit' }, 'Νέο'));
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
    if (await run('lines', body)) { code.value = ''; n.value = '1'; price.value = ''; disc.value = '0'; found.replaceChildren(); }
    code.focus();
  };
  const draw = () => {
    const draft = d.status === 'D';
    title.textContent = `${d.type_name} ${d.doc_no || '(πρόχειρο)'}`;
    head.replaceChildren(el('dl', { class: 'kv' }, [
      ['Είδος', `${d.doc_type} ${d.type_name}`], ['Ημερομηνία', day(d.doc_date)], ['Κατάσταση', DOC_ST[d.status]],
      [d.side === 'S' ? 'Πελάτης' : 'Προμηθευτής', d.partner], ['Πληρωμή', { CREDIT: 'πίστωση', CASH: 'μετρητά', CARD: 'κάρτα' }[d.payment]],
      ['Από', d.ref_text], ['Στο τιμολόγιο', d.invoice_text],
      ['Δελτία του', d.notes_in.length ? d.notes_in.map(docText).join(', ') : null],
      ['Καθαρό', money(d.net)], ['ΦΠΑ', money(d.vat)], ['Σύνολο', money(d.total)],
      ['myDATA', d.mydata_type && d.status !== 'D' ? MYDATA_ST[d.mydata_state || ''] + (d.mydata_mark ? ' · MARK ' + d.mydata_mark : '')
        + (d.mydata_cancel_mark ? ' · ακύρωση ' + d.mydata_cancel_mark : '') : null],
      ['Λάθος myDATA', d.mydata_state === 'E' || d.mydata_state === 'Q' ? d.mydata_error : null]]
      .filter(([, v]) => v !== null && v !== undefined && v !== '').flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)])));
    addForm.hidden = !draft;
    lines.replaceChildren(d.lines.length ? table([['#'], ['Είδος'], ['Ποσότητα', 'num'], ['Τιμή', 'num'], ['Έκπτ. %', 'num hide-phone'], ['Σύνολο', 'num'], ['']],
      d.lines.map((x) => {
        const setQ = (q) => run(`lines/${x.id}`, { qty: q });
        const q = draft && x.serial_tracked !== 'Y'
          ? el('input', { type: 'number', step: 'any', min: '0', value: x.qty, class: 'w6', 'aria-label': 'Ποσότητα ' + x.code, onchange: (ev) => setQ(Number(ev.target.value)) })
          : qty(x.qty);
        return el('tr', {}, el('td', {}, x.line_no),
          el('td', { class: 'wrap' }, `${x.code} ${x.name}`, x.serials ? el('div', { class: 'muted' }, x.serials) : null),
          el('td', { class: 'num' }, q), num(x.price, (v) => nf2.format(v)), num(x.discount, qty, 'num hide-phone'), num(x.total),
          el('td', { class: 'num' }, draft ? el('button', { type: 'button', class: 'danger', 'aria-label': 'Σβήσε ' + x.code, onclick: () => setQ(0) }, '×') : null));
      })) : el('p', { class: 'muted' }, draft ? 'Καμία γραμμή ακόμα.' : ''));
    const btn = (text, fn, cls) => el('button', { type: 'button', class: cls || null, onclick: fn }, text);
    const ask = (text, fn) => () => { if (confirm(text)) fn(); };
    const isInvoice = !!d.ref_type;
    const canInvoice = d.status === 'P' && !d.invoice_id && docTypes && docTypes.some((t) => t.ref_type === d.doc_type);
    actions.replaceChildren(...[
      draft ? btn('Καταχώριση', ask('Καταχώριση;', async () => { if (await run('post', {})) toast('Καταχωρήθηκε με αριθμό ' + d.doc_no); }), 'primary') : null,
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
      d.status === 'P' && d.mydata_state === 'S'
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
  }, el('label', { class: 'grow' }, 'Είδος (Enter)', code), camera(code), el('label', {}, 'Ποσότητα', n), el('label', {}, 'Τιμή', price),
  el('label', {}, 'Έκπτ. %', disc), el('button', { class: 'primary', type: 'submit' }, 'Βάλε γραμμή'));
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
          num(x.amount), el('td', { class: 'num' }, x.status === 'C' ? 'ακυρώθηκε' : el('button', {
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
const SECTION = { item: '#/items', partner: '#/partners/', ledger: '#/partners/', count: '#/counts', order: '#/orders', doc: '#/docs' };
function navBar() {
  $('#top').hidden = false;
  $('#who').textContent = `${session.username} (${session.role})`;
  const hash = location.hash || '#/items';
  const first = hash.slice(2).split(/[/?]/)[0];
  const here = (h) => hash.startsWith(h) || (SECTION[first] && h.startsWith(SECTION[first]));
  let open = null;
  try { open = sessionStorage.getItem('mm.menu'); } catch (e) { open = null; }
  $('#nav').replaceChildren(...MENU.map(([group, pages]) => {
    const mine = pages.filter(([, , r]) => can(r));
    if (!mine.length) return null;
    const current = mine.some(([h]) => here(h));
    const d = el('details', { name: 'menu', open: current || (!MENU.some(([, ps]) => ps.some(([h]) => here(h))) && open === group) },
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
  navBar();
  bellStart();
  backupStart();
  const [path, query] = (location.hash.slice(1) || '/items').split('?');
  const params = new URLSearchParams(query || '');
  const p = path.split('/').filter(Boolean).map(decodeURIComponent);
  const need = (role, fn) => (can(role) ? fn() : show(el('h1', {}, 'Δεν επιτρέπεται'),
    el('p', { class: 'muted' }, 'Η σελίδα αυτή θέλει ρόλο ' + role + '.')));
  switch (p[0]) {
    case 'pos': return posPage(params);
    case 'orders': return ordersPage(params);
    case 'poster': return posterPage();
    case 'docs': return need('MANAGER', () => docsPage(params));
    case 'doc': return need('MANAGER', () => docPage(p[1]));
    case 'payments': return need('MANAGER', () => paymentsPage());
    case 'order': return orderPage(p[1]);
    case 'labels': return labelsPage();
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
