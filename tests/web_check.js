// web_check.js -- the pages of the mini market in a real browser (Chromium, Playwright), from
// tests/test_web.py: BASE, MGR / CASHIER (users), PW, ITEM (an item code), XSS (its name), SHOTS (a folder).
const { chromium } = require('playwright');

const { BASE, MGR, CASHIER, PW, ITEM, ITEM_B, XSS, SHOTS } = process.env;
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
  await page.waitForSelector('[role=alert]:not(:empty)');
  ok((await page.textContent('[role=alert]')).includes('Λάθος'), 'a wrong password: its message');
  ok((await page.inputValue('input[name=password]')) === '', 'the password does not stay');
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a');
  ok((await page.textContent('#who')).includes(MGR), 'logged in: who');
  const nav = await page.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(nav.includes('Πελάτες') && nav.includes('ΦΠΑ') && nav.includes('Απογραφή'), 'the menu of a manager');

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
  await waitText(page, '.pager', 'Σελίδα 1 από');
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
    ok(true, 'the report ' + path.split('?')[0]);
  }
  if (SHOTS) await page.screenshot({ path: SHOTS + '/vat.png' });

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

  // logout: the token gone
  await page.click('#logout');
  await page.waitForSelector('input[name=username]');
  ok((await page.evaluate(() => sessionStorage.getItem('mm'))) === null, 'logout: nothing kept');
  ok(errors.length === 0, 'no error in the page: ' + errors.join(' | '));

  // a cashier on a phone: the items and the counts only
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p2 = await phone.newPage();
  await p2.goto(BASE + '/web/');
  await p2.fill('input[name=username]', CASHIER);
  await p2.fill('input[name=password]', PW);
  await p2.click('button[type=submit]');
  await p2.waitForSelector('#nav a');
  const nav2 = await p2.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(nav2.join(',') === 'Είδη,Απογραφή', 'the menu of a cashier: ' + nav2.join(','));
  await p2.goto(BASE + '/web/#/reports/sales');
  await p2.waitForSelector('h1:has-text("Δεν επιτρέπεται")');
  ok(true, 'a cashier: no reports');
  ok(await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'a phone: no page wider than it');
  if (SHOTS) await p2.screenshot({ path: SHOTS + '/phone.png' });

  await browser.close();
  console.log(failed ? `== ${failed} FAILED` : '== web OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
