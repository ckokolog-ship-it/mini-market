// roles_check.js -- the page «Ρόλοι και δικαιώματα» in a real browser (Chromium, Playwright), from
// tests/test_roles_api.py: BASE, ADMIN (an administrator), USER (a cashier), PW, ROLE (the code of a new role).
// A role made; the documents to it (read); given to the cashier in «Χρήστες»; the menu page.
const { chromium } = require('playwright');

const { BASE, ADMIN, USER, PW, ROLE, SHOTS } = process.env;
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
  page.on('dialog', (d) => d.accept());
  await page.goto(BASE + '/web/');
  await page.waitForSelector('input[name=username]');
  await page.fill('input[name=username]', ADMIN);
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
  const nav = await page.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(nav.includes('Ρόλοι και δικαιώματα') && nav.includes('Χρήστες'), 'the menu of an administrator: the roles, the users');
  await page.goto(BASE + '/web/#/roles');
  await page.waitForSelector('input[name=role_code]');
  await page.waitForSelector('main a[href="#/roles/CASHIER"]');
  ok((await page.textContent('main')).includes('CASHIER (συστήματος)'), 'the roles: those of the system');
  await page.fill('input[name=role_code]', ROLE);
  await page.fill('input[name=role_name]', 'Test από τον browser');
  await page.click('main form button[type=submit]');
  await page.waitForSelector('select[aria-label="DOCS"]');
  ok((await page.textContent('main h2')).includes(ROLE), 'a new role: its rights');
  await page.selectOption('select[aria-label="DOCS"]', 'R');
  await page.waitForFunction(() => {
    const s = document.querySelector('select[aria-label="DOCS"]');
    return s && s.value === 'R' && s.closest('tr').lastChild.textContent === 'Ανάγνωση';
  });
  ok(true, 'the documents to the role: read');
  ok(await page.$eval('select[aria-label="DOCS.POST"]', (s) => s.value === ''), 'an action: as its screen');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/roles.png', fullPage: true });
  // the users: the role to the cashier
  await page.goto(BASE + '/web/#/users');
  const box = `input[aria-label="Ρόλος ${ROLE} ${USER}"]`;
  await page.waitForSelector(box);
  await page.check(box);
  await page.waitForFunction((b) => document.querySelector('#toast').textContent.includes('Οι ρόλοι'), box);
  ok(await page.isChecked(box), 'the users: the role given');
  // the menu
  await page.goto(BASE + '/web/#/menu');
  await page.waitForSelector('input[aria-label="Όνομα ITEMS"]');
  ok(await page.isVisible('select[aria-label="Ομάδα ITEMS"]'), 'the menu: a screen, its group');
  ok(errors.length === 0, 'no errors in the pages: ' + errors.join(' | '));
  await browser.close();
  console.log(failed ? `== roles FAILED (${failed})` : '== roles OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('FAIL ' + e); process.exit(1); });
