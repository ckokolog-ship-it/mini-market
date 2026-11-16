// shop.js -- the page of the shop for its customers (/shop/, the WiFi of the shop; no login): the items
// with their price and whether there are any, a cart (kept in this browser), an order of a name and a
// phone for today; the shop confirms it with a call. Its page of status by its token (#/o/<token>); the
// orders of this browser listed. Every value as text (textContent), never as HTML.

const $ = (sel) => document.querySelector(sel);
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
const nf2 = new Intl.NumberFormat('el-GR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf3 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 3 });
const euro = (v) => nf2.format(v) + ' €';
const show = (...kids) => $('#main').replaceChildren(...kids);
function toast(text, bad) {
  const t = $('#toast');
  t.textContent = text;
  t.className = 'show' + (bad ? ' bad' : '');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.className = ''; }, bad ? 5000 : 2500);
}
function load(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; }
}
function save(key, v) {
  try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* a private window: for this visit */ }
}
async function api(path, body) {
  const opts = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  let r;
  try { r = await fetch('/api/shop/' + path, opts); } catch (e) { throw new Error('Δεν απαντά το μαγαζί: είσαι στο WiFi του;'); }
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  if (!r.ok) throw new Error(data && data.message ? data.message : 'σφάλμα ' + r.status);
  return data;
}

// -- the cart: {code: {name, price, unit, qty}} ---------------------------------------------------------
let cart = load('mm.shop.cart', {});
const step = (unit) => (unit === 'KG' ? 0.5 : 1);
function setQty(item, qty) {
  const q = Math.max(0, Math.min(99, Math.round(qty * 1000) / 1000));
  if (q === 0) delete cart[item.code];
  else cart[item.code] = { name: item.name, price: item.price, unit: item.unit, qty: q };
  save('mm.shop.cart', cart);
  badge();
}
function badge() {
  $('#cartn').textContent = String(Object.keys(cart).length);
}
const cartTotal = () => Object.values(cart).reduce((a, x) => a + Math.round(x.qty * x.price * 100) / 100, 0);
function qtyBox(item, redraw) {
  const have = cart[item.code] ? cart[item.code].qty : 0;
  if (!have) {
    return el('button', {
      type: 'button', class: 'primary', disabled: item.available === 'N', 'aria-label': 'Στο καλάθι ' + item.name,
      onclick: () => { setQty(item, step(item.unit)); redraw(); },
    }, item.available === 'N' ? 'Εξαντλήθηκε' : 'Στο καλάθι');
  }
  return el('div', { class: 'qty' },
    el('button', { type: 'button', 'aria-label': 'Λιγότερο ' + item.name, onclick: () => { setQty(item, have - step(item.unit)); redraw(); } }, '−'),
    el('span', {}, nf3.format(have) + (item.unit === 'KG' ? ' κιλά' : '')),
    el('button', { type: 'button', 'aria-label': 'Περισσότερο ' + item.name, onclick: () => { setQty(item, have + step(item.unit)); redraw(); } }, '+'));
}

// -- the items -----------------------------------------------------------------------------------------
async function catalog() {
  const q = el('input', { type: 'search', name: 'q', placeholder: 'Αναζήτηση (π.χ. ψωμί, γάλα)', autocomplete: 'off' });
  const cat = el('select', { name: 'category', 'aria-label': 'Κατηγορία' }, el('option', { value: '' }, 'Όλες οι κατηγορίες'));
  const list = el('div', { class: 'shop-items' });
  const more = el('div');
  let rows = [];
  let total = 0;
  const draw = () => {
    list.replaceChildren(...rows.map((x) => el('div', { class: 'shop-item' + (x.available === 'N' ? ' out' : '') },
      el('div', { class: 'shop-name' }, x.name), el('div', { class: 'muted' }, x.category),
      el('div', { class: 'shop-price' }, euro(x.price) + (x.unit === 'KG' ? ' / κιλό' : '')),
      qtyBox(x, draw))));
    if (!rows.length) list.replaceChildren(el('p', { class: 'muted' }, 'Τίποτα.'));
    more.replaceChildren(rows.length < total ? el('button', { type: 'button', onclick: () => go(rows.length) }, 'Περισσότερα') : '');
  };
  const go = async (offset = 0) => {
    try {
      const r = await api(`items?limit=60&offset=${offset}&category=${cat.value}&q=` + encodeURIComponent(q.value.trim()));
      rows = offset ? rows.concat(r.rows) : r.rows;
      total = r.total;
      draw();
    } catch (e) { toast(e.message, true); }
  };
  let timer;
  q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => go(0), 300); });
  cat.addEventListener('change', () => go(0));
  api('categories').then((r) => r.rows.forEach((c) => cat.append(el('option', { value: c.id }, c.name)))).catch(() => {});
  const mine = load('mm.shop.orders', []);
  show(mine.length ? el('p', {}, el('a', { href: '#/o/' + mine[0].token }, 'Η παραγγελία μου')) : null,
    el('div', { class: 'panel row' }, el('label', { class: 'grow' }, 'Αναζήτηση', q), el('label', {}, 'Κατηγορία', cat)), list, more,
    el('a', { class: 'cart-bar', href: '#/cart', hidden: !Object.keys(cart).length }, 'Το καλάθι: ' + euro(cartTotal()) + ' →'));
  go(0);
}

// -- the cart and the order --------------------------------------------------------------------------
function cartPage() {
  const name = el('input', { name: 'name', required: true, maxlength: 60, autocomplete: 'name' });
  const phone = el('input', { name: 'phone', type: 'tel', required: true, maxlength: 20, autocomplete: 'tel', placeholder: '69…' });
  const notes = el('input', { name: 'notes', maxlength: 300, placeholder: 'π.χ. θα περάσω στις 6' });
  const body = el('div');
  const draw = () => {
    const items = Object.entries(cart);
    body.replaceChildren(items.length ? el('div', {},
      el('div', { class: 'shop-items' }, items.map(([code, x]) => el('div', { class: 'shop-item' },
        el('div', { class: 'shop-name' }, x.name), el('div', { class: 'shop-price' }, euro(Math.round(x.qty * x.price * 100) / 100)),
        qtyBox({ code, name: x.name, price: x.price, unit: x.unit, available: 'Y' }, draw)))),
      el('p', { class: 'big' }, 'Σύνολο: ' + euro(cartTotal())),
      el('p', { class: 'muted' }, 'Οι τιμές είναι του καταστήματος· στο ταμείο ισχύουν και οι προσφορές της ημέρας.'),
      el('form', {
        class: 'panel shop-form',
        onsubmit: async (ev) => {
          ev.preventDefault();
          const btn = ev.target.querySelector('button[type=submit]');
          btn.disabled = true;
          try {
            const o = await api('orders', {
              name: name.value.trim(), phone: phone.value.trim(), notes: notes.value.trim() || null,
              lines: Object.entries(cart).map(([code, x]) => ({ code, qty: x.qty })),
            });
            cart = {};
            save('mm.shop.cart', cart);
            badge();
            save('mm.shop.orders', [{ token: o.token, id: o.id }, ...load('mm.shop.orders', [])].slice(0, 10));
            location.hash = '#/o/' + o.token;
          } catch (e) {
            toast(e.message, true);
            btn.disabled = false;
          }
        },
      }, el('label', {}, 'Όνομα', name), el('label', {}, 'Κινητό', phone), el('label', {}, 'Σημείωση (προαιρετικά)', notes),
      el('button', { class: 'primary', type: 'submit' }, 'Αποστολή παραγγελίας'),
      el('p', { class: 'muted' }, 'Θα σε πάρουμε τηλέφωνο για επιβεβαίωση, και μετά την ετοιμάζουμε για σήμερα.')))
      : el('p', { class: 'muted' }, 'Το καλάθι είναι άδειο. ', el('a', { href: '#/' }, 'Στα είδη')));
  };
  show(el('h1', {}, 'Καλάθι'), body);
  draw();
}

// -- the status of an order ----------------------------------------------------------------------------
const STATE = {
  sent: ['Στάλθηκε', 'Θα σε πάρουμε τηλέφωνο για επιβεβαίωση.'],
  confirmed: ['Επιβεβαιώθηκε', 'Την ετοιμάζουμε.'],
  ready: ['Έτοιμη', 'Πέρασε από το ταμείο να την παραλάβεις.'],
  delivered: ['Παραδόθηκε', 'Ευχαριστούμε!'],
  cancelled: ['Ακυρώθηκε', ''],
};
async function statusPage(token) {
  let timer = null;
  const draw = async () => {
    let o;
    try { o = await api('orders/' + encodeURIComponent(token)); } catch (e) { show(el('h1', {}, 'Παραγγελία'), el('p', { class: 'muted' }, e.message)); return; }
    const [title, text] = STATE[o.state];
    show(el('h1', {}, `Παραγγελία ${o.id}`),
      el('div', { class: 'panel state state-' + o.state }, el('p', { class: 'big' }, title), el('p', {}, text)),
      el('div', { class: 'shop-items' }, o.lines.map((x) => el('div', { class: 'shop-item' }, el('div', { class: 'shop-name' }, x.name),
        el('div', {}, nf3.format(x.qty) + (x.unit === 'KG' ? ' κιλά' : '') + ' × ' + euro(x.price)), el('div', { class: 'shop-price' }, euro(x.total))))),
      el('p', { class: 'big' }, 'Σύνολο: ' + euro(o.total)),
      o.state === 'sent' ? el('button', {
        type: 'button', class: 'danger',
        onclick: async () => {
          if (!confirm('Ακύρωση της παραγγελίας;')) return;
          try { await api(`orders/${encodeURIComponent(token)}/cancel`, {}); draw(); } catch (e) { toast(e.message, true); }
        },
      }, 'Ακύρωση παραγγελίας') : null,
      el('p', {}, el('a', { href: '#/' }, 'Στα είδη')));
    if (['delivered', 'cancelled'].includes(o.state)) clearInterval(timer);
  };
  await draw();
  timer = setInterval(() => { if (location.hash.endsWith(token)) draw(); else clearInterval(timer); }, 30000);
}

function route() {
  const h = location.hash.slice(1) || '/';
  if (h.startsWith('/o/')) statusPage(h.slice(3));
  else if (h === '/cart') cartPage();
  else catalog();
  window.scrollTo(0, 0);
}
api('info').then((r) => { $('#shopname').textContent = r.name; document.title = 'Παραγγελία · ' + r.name; }).catch(() => {});
badge();
window.addEventListener('hashchange', route);
route();
