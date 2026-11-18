// rights_check.js -- the rights (MM_RIGHTS) in a real browser (Chromium, Playwright), from
// tests/test_rights_api.py: BASE, USER (only a role of the shop: the items without their prices, the
// documents, the users), PW, ITEM. Its menu from the database; an item without its price; a page not allowed.
const { chromium } = require('playwright');

const { BASE, USER, PW, ITEM, SHOTS } = process.env;
let failed = 0;
function ok(cond, what) {
  console.log((cond ? 'ok   ' : 'FAIL ') + what);
  if (!cond) failed += 1;
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const page = await (await browser.newContext()).newPage();
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + '/web/');
  await page.waitForSelector('input[name=username]');
  await page.fill('input[name=username]', USER);
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
  const groups = await page.$$eval('#nav summary', (x) => x.map((y) => y.textContent));
  const nav = await page.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(groups.join(',') === 'Αποθήκη,Γραφείο,Διαχείριση', 'the menu from the database: its groups: ' + groups.join(','));
  ok(nav.join(',') === 'Είδη,Τιμολόγια και δελτία,Χρήστες', 'the menu: its screens: ' + nav.join(','));
  await page.goto(BASE + '/web/#/item/' + encodeURIComponent(ITEM));
  await page.waitForSelector('main dl.kv');
  const terms = await page.$$eval('main dl.kv dt', (x) => x.map((y) => y.textContent));
  ok(!terms.includes('Τιμή λιανικής') && !terms.includes('Χονδρική') && terms.includes('Απόθεμα') && !terms.includes('Κόστος (τελευταία αγορά)'),
    'an item: no price, no cost, its stock: ' + terms.join(','));
  if (SHOTS) await page.screenshot({ path: SHOTS + '/rights-item.png', fullPage: true });
  await page.goto(BASE + '/web/#/pos');
  await page.waitForFunction(() => document.querySelector('main h1') && document.querySelector('main h1').textContent === 'Δεν επιτρέπεται');
  ok(true, 'the till: not allowed');
  ok(errors.length === 0, 'no errors in the pages: ' + errors.join(' | '));
  await browser.close();
  console.log(failed ? `== rights FAILED (${failed})` : '== rights OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('FAIL ' + e); process.exit(1); });
