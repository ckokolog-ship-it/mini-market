// web_check.js -- the pages of the mini market in a real browser (Chromium, Playwright), from
// tests/test_web.py: BASE, MGR / CASHIER (users), PW, ITEM (an item code), XSS (its name), SHOTS (a folder).
const { chromium } = require('playwright');

const { BASE, MGR, CASHIER, PW, ITEM, ITEM_B, XSS, SHOTS, LABELS, DOC_SENT, SENT_MARK } = process.env;
let failed = 0;
function ok(cond, what) {
  console.log((cond ? 'ok   ' : 'FAIL ') + what);
  if (!cond) failed += 1;
}

// the page shows this text (a hash of the same page loads in the background: wait for its content)
async function waitText(page, sel, text) {
  try {
    await page.waitForFunction(([q, t]) => {
      const e = document.querySelector(q);
      return e && e.textContent.includes(t);
    }, [sel, text], { timeout: 15000 });
  } catch (e) {
    console.log('FAIL waiting for ' + JSON.stringify(text) + ' in ' + sel + '; the page: '
      + (await page.textContent('main')).slice(0, 400) + ' | ' + (await page.textContent('#toast')));
    throw e;
  }
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => {
    // (the 401 of the wrong password, as the browser writes every failed request: expected)
    if (m.type() === 'error' && !/status of 401/.test(m.text())) errors.push(m.text());
  });
  page.on('dialog', (d) => d.accept());

  // the address of the server: to the pages; their headers
  const r = await page.goto(BASE + '/');
  ok(page.url() === BASE + '/web/', 'the root goes to /web/');
  const csp = r.headers()['content-security-policy'] || '';
  ok(csp.includes("script-src 'self'") && csp.includes("frame-ancestors 'none'"), 'the CSP of the pages');
  ok((await page.request.get(BASE + '/web/../pom.xml')).status() === 404, 'nothing but the pages');

  // the login: wrong, then right
  await page.fill('input[name=username]', MGR);
  await page.fill('input[name=password]', 'Wrong-pass-1');
  await page.click('button[type=submit]');
  await page.waitForSelector('main [role=alert]:not(:empty)');
  ok((await page.textContent('main [role=alert]')).includes('Λάθος'), 'a wrong password: its message');
  ok((await page.inputValue('input[name=password]')) === '', 'the password does not stay');
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
  ok((await page.textContent('#who')).includes(MGR), 'logged in: who');
  const nav = await page.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(nav.includes('Πελάτες') && nav.includes('ΦΠΑ') && nav.includes('Απογραφή'), 'the menu of a manager');
  const groups = await page.$$eval('#nav summary', (x) => x.map((y) => y.textContent));
  ok(groups.join(',') === 'Πωλήσεις,Αποθήκη,Γραφείο,Αναφορές', 'the groups of the menu: ' + groups.join(','));
  ok(await page.isVisible('#nav') && await page.isHidden('#menu'), 'a desk: the menu a column, no ☰');

  // the items: a search, an item, a barcode
  await page.fill('input[name=q]', 'Ψωμί');
  await page.waitForFunction(() => [...document.querySelectorAll('tbody tr')].some((t) => t.textContent.includes('ART01')));
  ok(true, 'the search finds the bread');
  await page.click('tbody tr:has-text("ART01")');
  await page.waitForSelector('h1:has-text("Ψωμί")');
  ok((await page.textContent('.kv')).includes('2000000000015'), 'an item and its barcode');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/item.png' });
  await page.goto(BASE + '/web/#/items');
  await page.fill('input[name=q]', '2000000000015');
  await page.press('input[name=q]', 'Enter');
  await page.waitForSelector('h1:has-text("Ψωμί")');
  ok(true, 'a barcode and Enter: straight to the item');

  // a name with HTML in it: shown as text, never run
  await page.goto(BASE + '/web/#/item/' + ITEM);
  await waitText(page, 'h1', XSS);
  ok((await page.textContent('h1')) === XSS, 'the name of the item as text');
  ok(await page.evaluate(() => window.__xss === undefined && !document.querySelector('main img')), 'nothing of it run');

  // a customer, its ledger
  await page.goto(BASE + '/web/#/partners/customers');
  await waitText(page, 'main', 'Επωνυμία');
  await page.click('tbody tr >> nth=0');
  await page.waitForSelector('dd.big');
  await page.click('button:has-text("Καρτέλα")');
  await page.waitForSelector('tr.carry');
  ok((await page.textContent('tr.carry')).includes('Από μεταφορά'), 'a ledger: from the carry-over');
  ok((await page.textContent('tbody')).includes('Γενικό υπόλοιπο'), 'a ledger: the balance at the end');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/ledger.png', fullPage: true });

  // pages: 25 a page; the items in pages; the ledger of the item b (30 moves) in two
  await page.goto(BASE + '/web/#/items');
  await waitText(page, 'main', 'Σελίδα 1 από');
  await page.selectOption('.pager select', '25');
  await page.waitForFunction(() => document.querySelectorAll('main tbody tr').length === 25);   // drawn again
  const firstCode = await page.textContent('tbody tr td');
  await page.click('.pager button:has-text("Επόμενη")');
  await waitText(page, '.pager', 'Σελίδα 2 από');
  ok((await page.textContent('tbody tr td')) !== firstCode, 'the items: the next page, other rows');
  await page.goto(BASE + '/web/#/ledger/item/' + ITEM_B + '?from=1900-01-01');
  await waitText(page, '.pager', 'Σελίδα 1 από 2');
  const carryOut = await page.$$eval('tr.carry', (t) => t.map((r) => r.textContent));
  ok(carryOut.length === 2 && carryOut[1].startsWith('Σε μεταφορά'), 'a page of the ledger: from and to the carry-over');
  await page.click('.pager button:has-text("Επόμενη")');
  await waitText(page, '.pager', 'Σελίδα 2 από 2');
  const carryIn = await page.textContent('tr.carry');
  ok(carryIn.replace('Από μεταφορά', '') === carryOut[1].replace('Σε μεταφορά', ''), 'the next page starts where the last ended');
  ok((await page.textContent('tbody')).includes('Τελικό απόθεμα'), 'the last page: the totals');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/ledger_page2.png', fullPage: true });
  await page.selectOption('.pager select', '50');
  await waitText(page, '.pager', 'Σελίδα 1 από 1');

  // the reports
  for (const [path, word] of [['sales?from=1900-01-01', 'Σύνολο περιόδου'], ['vat?from=1900-01-01', 'Προς απόδοση'],
    ['min-stock', 'ελάχιστο']]) {
    await page.goto(BASE + '/web/#/reports/' + path);
    await page.waitForFunction((w) => document.querySelector('main').textContent.includes(w), word);
    ok(!/\bnull\b|undefined/.test(await page.textContent('main')), 'the report ' + path.split('?')[0] + ': no "null" in it');
  }
  if (SHOTS) await page.screenshot({ path: SHOTS + '/vat.png' });
  // the orders to the suppliers (the item b under its minimum, tests/test_web.py): a draft delivery note of
  // purchase, printed as an order
  await page.goto(BASE + '/web/#/reports/min-stock');
  await page.click('button:has-text("Φτιάξε τις παραγγελίες")');
  await waitText(page, 'main', 'γραμμές μπήκαν σε πρόχειρα δελτία παραλαβής');
  await page.click('main li a');
  await waitText(page, 'h1', 'Δελτίο παραλαβής');
  await page.evaluate(() => { window.print = () => {}; });
  await page.click('button:has-text("Εκτύπωση παραγγελίας")');
  await page.waitForSelector('#docprint', { state: 'attached' });
  ok((await page.textContent('#docprint')).includes('Παραγγελία προς προμηθευτή'), 'the order to the supplier: a draft, printed as an order');
  await page.evaluate(() => document.body.classList.remove('printing-doc'));
  // the trial balances: a row each; the customers with their totals; an item opens its ledger for the
  // same period, with the same stock at the end
  await page.goto(BASE + '/web/#/reports/trial-customers?from=2000-01-01');
  await waitText(page, 'main', 'Σύνολα');
  ok((await page.$$('main tbody tr.click')).length >= 1, 'the trial balance of the customers: its rows and totals');
  await page.goto(BASE + '/web/#/reports/trial-suppliers?from=2000-01-01');
  await waitText(page, 'main', 'Σύνολα');
  const CODE_B = ITEM.replace(/A$/, 'B');                            // the item b: 30 moves of its stock
  await page.goto(BASE + '/web/#/reports/trial-items?from=2000-01-01');
  await waitText(page, 'main', CODE_B);
  ok(!(await page.textContent('main tbody')).includes(ITEM), 'the trial balance: an item with nothing not there');
  ok(await page.evaluate(() => window.__xss === undefined && !document.querySelector('main img')), 'the trial balance: the names as text');
  const tb = await page.$$eval('main tbody tr', (trs, code) => trs.filter((tr) => tr.cells[0].textContent === code)
    .map((tr) => tr.cells[tr.cells.length - 1].textContent), CODE_B);
  if (SHOTS) await page.screenshot({ path: SHOTS + '/trial_items.png', fullPage: true });
  await page.click(`main tbody tr:has(td:text-is("${CODE_B}"))`);
  await waitText(page, 'tbody', 'Τελικό απόθεμα');
  const end = await page.$$eval('tbody tr.total', (trs) => trs.map((tr) => tr.textContent).find((t) => t.includes('Τελικό απόθεμα')));
  ok(tb.length === 1 && end.replace('Τελικό απόθεμα', '').trim() === tb[0].trim(),
    `the trial balance -> the ledger of the item, the same stock: ${tb[0]} / ${end}`);

  // the scratch tickets: the page; a game with an item without serials: refused, said why
  await page.goto(BASE + '/web/#/scratch');
  await waitText(page, 'main', 'Εκδόσεις');
  ok(await page.isVisible('input[name=code]'), 'the scratch tickets: the page');
  await page.fill('input[name=game]', '9999');
  await page.fill('input[name=item]', ITEM);
  const errs1 = errors.length;
  await page.click('button:has-text("Δήλωση έκδοσης")');
  await waitText(page, '#toast', 'serials');
  if (errors.slice(errs1).every((e) => /status of 400/.test(e))) errors.splice(errs1);   // (that refusal: a 400, meant)
  ok(true, 'a game of an item without serials: refused, said why');
  // a count: started, two scans, posted
  await page.goto(BASE + '/web/#/counts');
  await page.fill('main form input', 'TST web');
  await page.click('main form button');
  await page.waitForSelector('input[name=code]');
  for (let k = 0; k < 2; k += 1) {
    await page.fill('input[name=code]', ITEM);
    await page.press('input[name=code]', 'Enter');
    await page.waitForFunction((n) => document.querySelector('p.big').textContent.endsWith(': ' + n), String(k + 1));
  }
  await waitText(page, 'tbody', ITEM);
  ok(true, 'the count: its line');
  ok(await page.evaluate(() => document.activeElement.name === 'code'), 'the cursor back on the scan');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/count.png' });
  await page.click('button:has-text("Καταχώριση")');
  await page.waitForSelector('h1:has-text("καταχωρήθηκε")');
  ok(await page.isHidden('form.scan'), 'posted: no more scans');

  // the till: the register TST, its Z opened, an item scanned (the name with HTML: as text), one
  // more of it, paid by cash with F9 (the change), the Z closed
  await page.goto(BASE + '/web/#/pos');
  await page.waitForSelector('select[aria-label="Ταμείο"]');
  await page.selectOption('select[aria-label="Ταμείο"]', 'TST');
  await waitText(page, 'main', 'Κλειστό');
  await page.click('button:has-text("Άνοιγμα Ζ")');
  await page.waitForSelector('form.scan:not([hidden]) input[name=code]');
  await page.fill('input[name=code]', ITEM);
  await page.press('input[name=code]', 'Enter');
  await waitText(page, '.total-due', '12,40');
  ok(await page.evaluate(() => window.__xss === undefined && !document.querySelector('main img')), 'the till: the name as text');
  ok(await page.evaluate(() => document.activeElement.name === 'code'), 'the till: the cursor back on the scan');
  await page.click('button[aria-label="Μία ακόμα"]');
  await waitText(page, '.total-due', '24,80');
  await page.fill('input[name=given]', '30');
  await page.keyboard.press('F9');
  await waitText(page, 'main', 'Ρέστα: 5,20');
  await waitText(page, 'main', 'Τελευταίες αποδείξεις');
  ok(await page.isHidden('input[name=given]'), 'paid: no receipt open');
  // its print: a receipt of 80 mm, alone on its page (window.print counted, not a dialog in the test)
  await page.evaluate(() => { window.print = () => { window.__printed = (window.__printed || 0) + 1; }; });
  await page.click('button:has-text("Εκτύπωση απόδειξης")');
  await page.waitForFunction(() => window.__printed === 1);
  ok((await page.textContent('#receipt')).includes('ΑΠΟΔΕΙΞΗ ΛΙΑΝΙΚΗΣ') && (await page.textContent('#receipt')).includes('24,80'), 'the receipt: its title, its total');
  ok((await page.textContent('#receipt')).includes('Ρέστα'), 'the receipt: the change');
  await page.emulateMedia({ media: 'print' });
  ok(await page.isHidden('main') && await page.isVisible('#receipt'), 'the print: the receipt alone');
  if (SHOTS) await page.locator('#receipt').screenshot({ path: SHOTS + '/receipt.png' });    // (as printed: before
  // page.pdf, whose afterprint ends the print of the receipt)
  const rpdf = (await page.pdf({ preferCSSPageSize: true, printBackground: true })).toString('latin1');
  const box = /\/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]/.exec(rpdf);
  ok(box && Math.abs(Number(box[1]) - 226.8) < 1.5 && Number(box[2]) > 150, 'the print: a page 80 mm wide: ' + (box && box[1] + ' x ' + box[2]));
  await page.emulateMedia({ media: 'screen' });
  await page.evaluate(() => document.body.classList.remove('printing-receipt'));
  await page.click('button[aria-label^="Εκτύπωση ΑΛΠ"]');
  await page.waitForFunction(() => window.__printed === 2);
  ok(true, 'a receipt printed again from the last ones');
  // a prize of a scratch ticket: out of the drawer
  const drawer0 = await page.textContent('main');
  await page.fill('input[name=prize]', '2');
  await page.fill('input[name=ticket]', '12340000001005');
  await page.click('button:has-text("Πληρωμή κέρδους")');
  await waitText(page, '#toast', 'Κέρδος σκρατς 2,00');
  ok(drawer0 !== await page.textContent('main'), 'the till: a prize of a scratch ticket paid from the drawer');
  // the points: a new customer with a card into the receipt (its card printed, the size of a bank card),
  // an item, paid: its points on the receipt; then its page: the card, the points, their move
  await page.evaluate(() => { window.print = () => { window.__cards = (window.__cards || 0) + 1; }; });
  const who = 'Test web card ' + Date.now() % 100000;
  await page.click('summary:has-text("Νέος πελάτης με κάρτα")');
  await page.fill('input[name=new_name]', who);
  await page.fill('input[name=new_phone]', '69' + String(Date.now()).slice(-8));
  await page.click('button:has-text("Νέα κάρτα")');
  await waitText(page, '.cust', 'κάρτα 2990');
  ok((await page.textContent('#cardprint')).includes(who) && await page.evaluate(() => window.__cards === 1),
    'a new customer with a card: in the receipt, its card printed');
  await page.fill('input[name=code]', ITEM);
  await page.press('input[name=code]', 'Enter');
  await waitText(page, '.cust', '+12 πόντοι');
  ok(!(await page.textContent('.cust')).includes('null'), 'the customer of the receipt: its points, nothing empty as text');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/pos_points.png', fullPage: true });
  await page.click('button:has-text("Μετρητά (F9)")');
  await waitText(page, '#toast', 'καταχωρήθηκε');
  ok(!(await page.textContent('.cust')).includes(who), 'paid: the next receipt without a customer');
  await page.goto(BASE + '/web/#/partners/customers?q=' + encodeURIComponent(who));
  await page.click(`main tbody tr.click:has-text("${who}")`);
  await waitText(page, 'main', 'Κάρτα πόντων');
  await waitText(page, 'main', '12 πόντοι');
  ok((await page.textContent('main tbody')).includes('Αγορά'), 'the customer: its card, its points, their move');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/customer_points.png', fullPage: true });
  await page.goto(BASE + '/web/#/pos');
  await waitText(page, 'main', 'Τελευταίες αποδείξεις');
  // an order: written, an item by scan, the bread by a search, picked, ready; to the till, all of it
  await page.goto(BASE + '/web/#/orders');
  await page.waitForSelector('input[name=name]');
  await page.fill('input[name=name]', 'Test web order');
  await page.fill('input[name=phone]', '6912345678');
  await page.click('button:has-text("Νέα παραγγελία")');
  await page.waitForSelector('form.scan input[name=code]');
  await page.fill('input[name=code]', ITEM);
  await page.press('input[name=code]', 'Enter');
  await waitText(page, 'main', '12,40');
  await page.fill('input[name=code]', 'Ψωμί χωριάτικο');           // a word, one item: straight in
  await page.press('input[name=code]', 'Enter');
  await waitText(page, 'main', '14,50');
  ok(await page.evaluate(() => window.__xss === undefined && !document.querySelector('main img')), 'the order: the name as text');
  await page.check(`input[aria-label="Μαζεύτηκε ${ITEM}"]`);
  await page.waitForSelector('tr.picked');
  ok((await page.$$('tr.picked')).length === 1, 'the order: one line picked');
  await page.click('button:has-text("Έτοιμη")');
  await waitText(page, '.kv', 'έτοιμη');
  ok((await page.$$('tr.picked')).length === 2, 'ready: all of it picked');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/order.png', fullPage: true });
  await page.click('button:has-text("Στο ταμείο")');
  await waitText(page, '.order-text', 'Παραγγελία');
  await waitText(page, '.total-due', '14,50');
  ok((await page.$$('main tbody tr')).length >= 2, 'the till: the order in the receipt, all of it');
  await page.keyboard.press('F9');
  await waitText(page, '#toast', 'καταχωρήθηκε');
  await page.goto(BASE + '/web/#/orders?all=1');
  await waitText(page, 'main', 'παραδόθηκε');
  ok(true, 'the order: delivered');
  await page.goto(BASE + '/web/#/pos');
  await waitText(page, 'main', 'Τελευταίες αποδείξεις');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/pos.png', fullPage: true });
  await page.click('button:has-text("Κλείσιμο Ζ")');
  await waitText(page, '#toast', 'έκλεισε');
  ok(true, 'the Z closed: its totals');
  // then (a manager, yes to the question) the summary of the day: the Z closed in it, the sales, the
  // scratch prize paid above; the day before, back
  await waitText(page, 'main h1', 'Σύνοψη ημέρας');
  await waitText(page, 'main', 'Τα 10 είδη');
  const sum = await page.textContent('main');
  ok(/Ζ ταμείων/.test(sum) && sum.includes('Κέρδη που πληρώθηκαν') && sum.includes(ITEM) && !sum.includes('Κανένα Ζ'),
    'after the Z: the summary of the day, the Z, the items, the scratch');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/day.png', fullPage: true });
  await page.click('button:has-text("Προηγούμενη")');
  await page.waitForFunction(() => /date=\d{4}-\d\d-\d\d/.test(location.hash));
  const prev = new URL(page.url().replace('#/', '')).searchParams.get('date');
  await waitText(page, 'main h1', prev.split('-').reverse().join('/'));
  ok(true, 'the summary: the day before, ' + prev);
  // the charts of the sales: 30 days with a year before, the hours; a day's tooltip; the numbers as a table
  await page.goto(BASE + '/web/#/chart?days=30');
  await page.waitForSelector('svg.chart path.ch-bar');
  const charts = await page.$$eval('svg.chart', (ss) => ss.map((x) => x.querySelectorAll('path.ch-bar').length));
  ok(charts.length === 2 && charts[0] >= 1 && (await page.$$('svg.chart polyline.ch-line')).length === 1,
    `the charts: by day with a year before, by hour (${charts})`);
  const hits = await (await page.$$('svg.chart'))[0].$$('rect.ch-hit');          // (the chart by day)
  await hits[hits.length - 1].hover();
  await page.waitForSelector('.ch-tip:not([hidden])');
  ok(/Φέτος: .*Πέρσι/s.test(await page.textContent('.ch-tip')), 'the chart: a day, its tooltip (this year, a year before)');
  ok((await page.$$('details tbody tr')).length === 30, 'the chart: its numbers as a table');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/chart.png', fullPage: true });
  // dark, and a phone: redrawn to its width, no page wider than the screen
  await page.emulateMedia({ colorScheme: 'dark' });
  if (SHOTS) await page.screenshot({ path: SHOTS + '/chart_dark.png', fullPage: true });
  await page.emulateMedia({ colorScheme: 'light' });
  const size = page.viewportSize();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'the chart on a phone: no page wider than it');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/chart_phone.png', fullPage: true });
  await page.setViewportSize(size);

  // the labels (a sharp screen: each label a picture, read back by tests/test_web.py): the item of
  // the tests by a scan (no barcode: its code in Code 128; its name with HTML: as text), the bread by a
  // search (its EAN-13), 3 of it; the sheet as it prints: A4, the menu not on it
  if (LABELS) {
    const sharp = await browser.newContext({ deviceScaleFactor: 4, viewport: { width: 1200, height: 900 } });
    const lp = await sharp.newPage();
    lp.on('pageerror', (e) => errors.push(String(e)));
    lp.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await lp.goto(BASE + '/web/');
    await lp.fill('input[name=username]', MGR);
    await lp.fill('input[name=password]', PW);
    await lp.click('button[type=submit]');
    await lp.waitForSelector('#nav a', { state: 'attached' });
    await lp.goto(BASE + '/web/#/labels');
    await lp.waitForSelector('input[name=q]');
    await lp.click('button:has-text("Καθάρισε")');
    await lp.fill('input[name=base]', 'http://192.168.1.10:8090');
    await lp.press('input[name=base]', 'Tab');
    await lp.fill('input[name=q]', ITEM);
    await lp.press('input[name=q]', 'Enter');
    await waitText(lp, '.sheets', ITEM);
    await lp.fill('input[name=q]', 'Ψωμί');
    await lp.waitForSelector('button:has-text("+ 1")');
    await lp.click('tr:has-text("ART01") button:has-text("+ 1")');
    await waitText(lp, 'main', '2 ετικέτες');
    await lp.fill('input[aria-label="Ετικέτες ART01"]', '3');
    await lp.press('input[aria-label="Ετικέτες ART01"]', 'Tab');
    await waitText(lp, 'main', '4 ετικέτες');
    ok((await lp.$$('.sheet .label:not(.empty)')).length === 4, 'the labels: 4 on the sheet');
    ok(await lp.evaluate(() => window.__xss === undefined && !document.querySelector('.sheet img')), 'the labels: the name as text');
    const shots = await lp.$$('.sheet .label:not(.empty)');
    for (let k = 0; k < 2; k += 1) await shots[k === 0 ? 0 : 1].screenshot({ path: `${LABELS}/label${k}.png` });
    await lp.emulateMedia({ media: 'print' });
    ok(await lp.isHidden('header') && await lp.isHidden('input[name=q]'), 'the print: only the sheet');
    await lp.pdf({ path: LABELS + '/labels.pdf', preferCSSPageSize: true, printBackground: true });
    await lp.emulateMedia({ media: 'screen' });
    // the start on a sheet already used: the 23rd and 24th, then a second sheet
    await lp.fill('input[name=start]', '23');
    await lp.press('input[name=start]', 'Tab');
    await lp.waitForFunction(() => document.querySelectorAll('.sheet').length === 2);
    ok((await lp.$$('.sheet:first-child .label.empty')).length === 22, 'from the 23rd: two sheets, 22 empty');
    await lp.fill('input[name=start]', '1');
    await lp.press('input[name=start]', 'Tab');
    if (SHOTS) await lp.screenshot({ path: SHOTS + '/labels.png' });
    await sharp.close();
  }

  // the office: a delivery note (the bread by a word), posted; its invoice; goods back; a receipt of money
  await page.goto(BASE + '/web/#/docs');
  await page.waitForSelector('select[name=partner] option:nth-child(2)', { state: 'attached' });
  await page.selectOption('select[name=type]', 'DAP');
  await page.selectOption('select[name=partner]', { index: 1 });
  await page.click('form button:has-text("Νέο")');
  await page.waitForSelector('input[name=code]');
  await page.fill('input[name=code]', 'Ψωμί χωριάτικο');
  await page.fill('input[name=qty]', '6');
  await page.press('input[name=code]', 'Enter');
  await waitText(page, 'main tbody', 'ART01');
  await page.click('button:has-text("Καταχώριση")');
  await waitText(page, '.kv', 'καταχωρημένο');
  ok(true, 'the office: a delivery note posted');
  await page.click('button:has-text("Τιμολόγιο από αυτό")');
  await waitText(page, 'h1', 'Τιμολόγιο πώλησης');
  await waitText(page, '.kv', 'Δελτία του');
  await page.click('button:has-text("Καταχώριση")');
  await waitText(page, '.kv', 'καταχωρημένο');
  ok(true, 'its invoice, posted');
  // myDATA: the invoice not sent yet; sent (the little AADE of the tests): its MARK
  ok((await page.textContent('.kv')).includes('δεν διαβιβάστηκε'), 'the invoice: myDATA, not sent yet');
  await page.click('button:has-text("Διαβίβαση στο myDATA")');
  await waitText(page, '#toast', 'Διαβιβάστηκε: MARK');
  ok((await page.textContent('.kv')).includes('διαβιβάστηκε · MARK'), 'myDATA: sent, its MARK on the page');
  ok(await page.isVisible('button:has-text("Ακύρωση (και στο myDATA)")'), 'sent: cancelled at AADE first');
  await page.click('button:has-text("Επιστροφή")');
  await waitText(page, 'h1', 'Δελτίο επιστροφής');
  ok((await page.textContent('.kv')).includes('πρόχειρο'), 'goods back: a draft return note of its lines');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/doc.png', fullPage: true });
  await page.click('button:has-text("Σβήσε πρόχειρο")');
  await page.waitForSelector('select[name=type]');
  await page.goto(BASE + '/web/#/payments');
  await page.waitForSelector('select[name=partner_id] option:nth-child(2)', { state: 'attached' });
  await page.selectOption('select[name=partner_id]', { index: 1 });
  await waitText(page, 'main', 'Χρωστάει');
  await page.fill('input[name=amount]', '3.5');
  await page.fill('input[name=notes]', 'TST web');
  await page.click('form button:has-text("Καταχώριση")');
  await waitText(page, 'main tbody', 'TST web');
  ok(true, 'a receipt of money, in the list');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/payments.png', fullPage: true });
  await page.click('tr:has-text("TST web") button:has-text("Ακύρωση")');
  await page.waitForSelector('tr.cancelled:has-text("TST web")');
  ok(true, 'cancelled');

  // an invoice sent to myDATA (tests/test_web.py): its print on A4, alone, with its MARK and the QR of AADE
  await page.goto(BASE + '/web/#/doc/' + DOC_SENT);
  await waitText(page, '.kv', 'MARK ' + SENT_MARK);
  await page.evaluate(() => { window.print = () => { window.__printed = (window.__printed || 0) + 1; }; });
  await page.click('main button:text-is("Εκτύπωση")');
  await page.waitForSelector('#docprint svg.qr', { state: 'attached' });
  const dp = await page.textContent('#docprint');
  ok(dp.includes('MARK ' + SENT_MARK) && dp.includes('Τιμολόγιο') && dp.includes('Σύνολο') && dp.includes('ΑΦΜ'),
    'the print of the invoice: its title, the customer, the total, its MARK');
  await page.emulateMedia({ media: 'print' });
  ok(await page.isHidden('main') && await page.isVisible('#docprint'), 'the print of the invoice: alone');
  if (SHOTS) await page.locator('#docprint').screenshot({ path: SHOTS + '/invoice.png' });
  const ipdf = (await page.pdf({ preferCSSPageSize: true, printBackground: true })).toString('latin1');
  const ibox = /\/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]/.exec(ipdf);
  ok(ibox && Math.abs(Number(ibox[1]) - 595) < 3 && (ipdf.match(/\/Type \/Page\b/g) || []).length === 1,
    'the print of the invoice: one page A4: ' + (ibox && ibox[1] + ' x ' + ibox[2]));
  await page.emulateMedia({ media: 'screen' });
  await page.evaluate(() => document.body.classList.remove('printing-doc'));
  // the backup failed (tests/test_web.py): a manager sees it on every page
  await waitText(page, '#notice', 'Το τελευταίο backup της βάσης απέτυχε');
  ok(await page.isVisible('#notice') && (await page.textContent('#notice')).includes('expdp: test'), 'the backup failed: the manager sees it');
  // logout: the token gone
  await page.click('#logout');
  await page.waitForSelector('input[name=username]');
  ok((await page.evaluate(() => sessionStorage.getItem('mm'))) === null, 'logout: nothing kept');
  ok(errors.length === 0, 'no error in the page: ' + errors.join(' | '));

  // a cashier on a phone: the till, the items and the counts only
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p2 = await phone.newPage();
  await p2.goto(BASE + '/web/');
  await p2.fill('input[name=username]', CASHIER);
  await p2.fill('input[name=password]', PW);
  await p2.click('button[type=submit]');
  await p2.waitForSelector('#nav a', { state: 'attached' });
  const nav2 = await p2.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(nav2.join(',') === 'Ταμείο,Παραγγελίες,Είδη,Ετικέτες,Απογραφή', 'the menu of a cashier: ' + nav2.join(','));
  ok(await p2.isHidden('#notice'), 'a cashier: no word about the backup');
  // the menu on a phone: hidden, ☰ opens it, a group opens (the other closes), a page closes it
  ok(await p2.isHidden('#nav'), 'a phone: the menu hidden');
  await p2.click('#menu');
  await p2.waitForSelector('#nav', { state: 'visible' });
  ok(await p2.isVisible('#nav a:has-text("Ετικέτες")'), 'a phone: the group of the page (the items) open');
  await p2.click('#nav summary:has-text("Πωλήσεις")');                 // another group: this one closes
  ok(await p2.isHidden('#nav a:has-text("Ετικέτες")'), 'one group open at a time');
  await p2.click('#nav a:has-text("Ταμείο")');
  await p2.waitForSelector('h1:has-text("Ταμείο")');
  ok(await p2.isHidden('#nav'), 'a phone: a page chosen, the menu closed');
  await p2.click('#menu');
  ok(await p2.isVisible('#nav a:has-text("Ταμείο")') && await p2.isHidden('#nav a:has-text("Είδη")'), 'the group of the page open');
  if (SHOTS) await p2.screenshot({ path: SHOTS + '/phone_menu.png' });
  await p2.click('#menu');
  await p2.goto(BASE + '/web/#/reports/sales');
  await p2.waitForSelector('h1:has-text("Δεν επιτρέπεται")');
  ok(true, 'a cashier: no reports');
  ok(await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'a phone: no page wider than it');
  if (SHOTS) await p2.screenshot({ path: SHOTS + '/phone.png' });
  await p2.goto(BASE + '/web/#/pos');
  await waitText(p2, 'main', 'Αρχικό ταμείο');
  ok(await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'a phone: the till fits');
  if (SHOTS) await p2.screenshot({ path: SHOTS + '/phone_pos.png' });

  // a customer on a phone (/shop/, no login): the item by a search, two in the cart, the order sent;
  // the cashier confirms it (the order: online); the customer sees it confirmed, no cancel any more
  const cust = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p3 = await cust.newPage();
  p3.on('pageerror', (e) => errors.push(String(e)));
  await p3.goto(BASE + '/shop');
  await p3.waitForSelector('input[name=q]');
  ok((await p3.textContent('#shopname')).trim().length > 0, 'the shop: its name');
  await p3.waitForSelector('.shop-item');
  ok(await p3.evaluate(() => window.__xss === undefined && !document.querySelector('main img')), 'the shop: the names as text');
  await p3.fill('input[name=q]', 'Ψωμί χωριάτικο');
  await p3.waitForFunction(() => document.querySelectorAll('.shop-item').length === 1);
  await p3.click('button[aria-label^="Στο καλάθι Ψωμί χωριάτικο"]');
  await p3.click('button[aria-label^="Περισσότερο Ψωμί χωριάτικο"]');
  await waitText(p3, '#cartn', '1');
  await p3.click('#cartlink');
  await p3.waitForSelector('input[name=phone]');
  await waitText(p3, 'main', 'Σύνολο: 4,20');
  await p3.fill('input[name=name]', 'Test online πελάτης');
  await p3.fill('input[name=phone]', '6900000001');
  await p2.goto(BASE + '/web/#/pos');                              // the cashier at the till: the bell asked
  await waitText(p2, 'main', 'Αρχικό ταμείο');
  await p2.waitForTimeout(500);
  await p3.click('button:has-text("Αποστολή παραγγελίας")');
  await waitText(p3, '.state', 'Στάλθηκε');
  await p2.evaluate(() => window.dispatchEvent(new Event('focus')));   // (else in 30 seconds)
  await waitText(p2, '#toast', 'Νέα online παραγγελία: Test online πελάτης');
  await p2.waitForSelector('#menu[data-n]', { state: 'attached' });
  ok(/^\(\d+\) /.test(await p2.title()), 'the bell: the count in the title of the tab: ' + await p2.title());
  await p2.click('#menu');
  ok(Number(await p2.textContent('#nav a[href="#/orders"] .nav-count')) >= 1, 'the bell: the count next to «Παραγγελίες»');
  if (SHOTS) await p2.screenshot({ path: SHOTS + '/bell.png' });
  await p2.click('#menu');
  ok(await p3.isVisible('button:has-text("Ακύρωση παραγγελίας")'), 'sent: the customer may cancel it');
  ok((await p3.textContent('#cartn')) === '0', 'sent: the cart empty');
  ok(await p3.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'the shop fits a phone');
  if (SHOTS) await p3.screenshot({ path: SHOTS + '/shop_sent.png', fullPage: true });
  const no = (await p3.textContent('h1')).replace(/\D/g, '');
  await p2.goto(BASE + '/web/#/orders');
  await waitText(p2, 'main', 'online · προς επιβεβαίωση');
  await p2.goto(BASE + '/web/#/order/' + no);
  await waitText(p2, 'main', 'προς επιβεβαίωση');
  ok(await p2.isVisible('a[href="tel:6900000001"]'), 'the order: the phone to call');
  const waiting = Number(await p2.evaluate(() => document.querySelector('#menu').dataset.n || 0));
  await p2.click('button:has-text("Επιβεβαιώθηκε")');
  await waitText(p2, 'main', 'online · επιβεβαιώθηκε');
  ok(await p2.isHidden('button:has-text("Επιβεβαιώθηκε")'), 'confirmed: once');
  await p2.evaluate(() => window.dispatchEvent(new Event('focus')));
  await p2.waitForFunction((n) => Number(document.querySelector('#menu').dataset.n || 0) === n - 1, waiting, { timeout: 15000 });
  ok(true, 'confirmed: the count of the bell one less');
  await p3.reload();
  await waitText(p3, '.state', 'Επιβεβαιώθηκε');
  ok(await p3.isHidden('button:has-text("Ακύρωση παραγγελίας")'), 'confirmed: no cancel by the customer');
  if (SHOTS) await p3.screenshot({ path: SHOTS + '/shop_confirmed.png', fullPage: true });
  await p3.goto(BASE + '/shop/#/');
  await p3.waitForSelector('a:has-text("Η παραγγελία μου")');
  ok(true, 'the shop: my order kept in this browser');
  await p2.goto(BASE + '/web/#/poster');
  await p2.waitForSelector('.poster svg');
  ok((await p2.textContent('.poster-url')).endsWith('/shop/'), 'the poster: its QR to /shop/');
  ok(await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'the poster fits a phone');
  if (SHOTS) await p2.screenshot({ path: SHOTS + '/poster.png', fullPage: true });

  await browser.close();
  console.log(failed ? `== ${failed} FAILED` : '== web OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
