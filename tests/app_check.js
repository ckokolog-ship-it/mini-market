// app_check.js -- the pages as the app of Android runs them (from tests/test_web.py): from another origin
// (APP, as http://localhost of the phone) with window.Capacitor, the REST service at the address of the
// shop (API: CORS); the camera a fake one (Chromium) showing the barcode of the bread (VIDEO, .y4m).
const { chromium } = require('playwright');

const { APP, API, BAD, MGR, PW, VIDEO, SHOTS } = process.env;
let failed = 0;
function ok(cond, what) {
  console.log((cond ? 'ok   ' : 'FAIL ') + what);
  if (!cond) failed += 1;
}

(async () => {
  const browser = await chromium.launch({
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--use-file-for-fake-video-capture=' + VIDEO],
  });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await ctx.grantPermissions(['camera'], { origin: APP });
  // what Capacitor puts in the page of the app
  await ctx.addInitScript(() => { window.Capacitor = { isNativePlatform: () => true }; });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error' && !/ERR_CONNECTION_REFUSED/.test(m.text())) errors.push(m.text()); });

  // the first time: the address of the shop; a wrong one, then the right one (without http://)
  await page.goto(APP + '/index.html');
  await page.waitForSelector('input[name=server]');
  ok(true, 'the app: asks the address of the shop');
  await page.fill('input[name=server]', BAD);                       // nothing listens there
  await page.click('button[type=submit]');
  await page.waitForSelector('main [role=alert]:not(:empty)');
  ok((await page.textContent('main [role=alert]')).includes('Δεν απαντά'), 'a wrong address: it says so');
  await page.fill('input[name=server]', API.replace('http://', ''));
  await page.click('button[type=submit]');
  await page.waitForSelector('input[name=username]');
  ok((await page.textContent('main')).includes('Μαγαζί: ' + API), 'the address kept, shown under the login');
  await page.fill('input[name=username]', MGR);
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
  ok(true, 'logged in through CORS');

  // the camera: the barcode of the bread, read (ZXing: no BarcodeDetector here), the item opened
  await page.goto(APP + '/index.html#/items');
  await page.waitForSelector('button.cam');
  await page.click('button.cam');
  await page.waitForSelector('.scanner video');
  ok(true, 'the camera opened');
  await page.waitForSelector('h1:has-text("Ψωμί")', { timeout: 20000 });
  ok(!(await page.$('.scanner')), 'read: the camera closed, the item of the barcode opened');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/app_item.png' });
  // into an order: the camera again, the bread into it
  await page.goto(APP + '/index.html#/orders');
  await page.fill('input[name=name]', 'Test app order');
  await page.fill('input[name=phone]', '6912345678');
  await page.click('button:has-text("Νέα παραγγελία")');
  await page.waitForSelector('form.scan button.cam');
  await page.click('form.scan button.cam');
  await page.waitForFunction(() => document.querySelector('main').textContent.includes('ART01'), null, { timeout: 20000 });
  ok(true, 'an order: the bread by the camera');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/app_order.png' });
  // the address again: another one logs out
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(APP + '/index.html');
  await page.click('a:has-text("αλλαγή")');
  await page.waitForSelector('input[name=server]');
  ok((await page.inputValue('input[name=server]')) === API.replace('http://', ''), 'the change of the address: the old one in it');
  ok(errors.length === 0, 'no error in the page: ' + errors.join(' | '));
  await browser.close();
  console.log(failed ? `== ${failed} FAILED` : '== app OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
