// places_check.js -- where a user works, in a real browser (Chromium, Playwright), from tests/test_places.py:
// BASE, ADMIN (an administrator), USER (a cashier of a store), PW, REG1 / REG2 (the two registers of its
// store). The page Χρήστες: the cashier on REG2; then the till of the cashier: only REG2, opened on it.
const { chromium } = require('playwright');

const { BASE, ADMIN, USER, PW, REG1, REG2, SHOTS } = process.env;
let failed = 0;
function ok(cond, what) {
  console.log((cond ? 'ok   ' : 'FAIL ') + what);
  if (!cond) failed += 1;
}

async function login(page, name) {
  await page.goto(BASE + '/web/');
  await page.waitForSelector('input[name=username]');
  await page.fill('input[name=username]', name);
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const page = await (await browser.newContext()).newPage();
  page.on('pageerror', (e) => errors.push(String(e)));
  // the administrator: the page of the users, the cashier moved to the second register
  await login(page, ADMIN);
  ok((await page.$$eval('#nav a', (as) => as.map((a) => a.textContent))).includes('Χρήστες'), 'the menu of an administrator: Χρήστες');
  await page.goto(BASE + '/web/#/users');
  const reg = `select[aria-label="Ταμείο ${USER}"]`;
  await page.waitForSelector(reg);
  ok((await page.$eval(reg, (s) => s.selectedOptions[0].text)).startsWith(REG1), 'the users: the register of the cashier');
  await page.selectOption(reg, { label: (await page.$$eval(`${reg} option`, (o, c) => o.find((x) => x.text.startsWith(c)).text, REG2)) });
  await page.click(`tr:has(${reg}) button:has-text("Αποθήκευση")`);
  await page.waitForFunction((s) => document.querySelector('#toast').textContent.includes('Αποθηκεύτηκε'), reg);
  ok((await page.$eval(reg, (s) => s.selectedOptions[0].text)).startsWith(REG2), 'the users: the cashier moved to the other register');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/users.png', fullPage: true });
  // the cashier: only its register in the till, opened on it; its store at the top
  const p2 = await (await browser.newContext()).newPage();
  p2.on('pageerror', (e) => errors.push(String(e)));
  await login(p2, USER);
  ok(!(await p2.$$eval('#nav a', (as) => as.map((a) => a.textContent))).includes('Χρήστες'), 'a cashier: no Χρήστες');
  ok((await p2.textContent('#who')).includes('Test κατάστημα'), 'a cashier: its store at the top');
  await p2.goto(BASE + '/web/#/pos');
  await p2.waitForSelector('select[aria-label="Ταμείο"]');
  const regs = await p2.$$eval('select[aria-label="Ταμείο"] option', (o) => o.map((x) => x.value));
  ok(regs.length === 1 && regs[0] === REG2, 'the till of a cashier: only its register: ' + regs.join(','));
  ok(errors.length === 0, 'no errors in the pages: ' + errors.join(' | '));
  await browser.close();
  console.log(failed ? `== places FAILED (${failed})` : '== places OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('FAIL ' + e); process.exit(1); });
