// audit_check.js -- the page «Ιστορικό ενεργειών» in a real browser (Chromium, Playwright), from
// tests/test_audit.py: BASE, ADMIN (an administrator), PW. Its own login in the history; the logins only.
const { chromium } = require('playwright');

const { BASE, ADMIN, PW, SHOTS } = process.env;
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
  await page.fill('input[name=username]', ADMIN);
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
  ok((await page.$$eval('#nav a', (as) => as.map((a) => a.textContent))).includes('Ιστορικό ενεργειών'), 'the menu: the history');
  await page.goto(BASE + '/web/#/audit');
  await page.waitForSelector('main tbody tr');
  await page.selectOption('select[name=action]', 'AUTH_');
  await page.selectOption('select[name=user]', ADMIN);
  await page.click('main form button[type=submit]');
  await page.waitForFunction((u) => {
    const rows = [...document.querySelectorAll('main tbody tr')];
    return rows.length && rows.every((r) => r.children[1].textContent === u);
  }, ADMIN);
  const what = await page.$$eval('main tbody tr td:nth-child(4)', (x) => x.map((y) => y.textContent));
  ok(what.includes('Σύνδεση'), 'the logins of the administrator: ' + what.join(','));
  if (SHOTS) await page.screenshot({ path: SHOTS + '/audit.png', fullPage: true });
  ok(errors.length === 0, 'no errors in the pages: ' + errors.join(' | '));
  await browser.close();
  console.log(failed ? `== audit FAILED (${failed})` : '== audit OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('FAIL ' + e); process.exit(1); });
