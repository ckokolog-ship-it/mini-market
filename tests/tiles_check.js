// tiles_check.js -- the buttons of the till in a real browser (Chromium, Playwright), from tests/test_tiles.py:
// a manager makes a group, puts two items in it, gives one a PLU, moves a tile; a cashier opens the Z, presses a
// tile, ×2 and a tile, types the PLU in the scan, sees the tabs; nothing written as HTML. BASE, MGR / CASHIER,
// PW, ITEM / ITEM_B (item codes), PLU (a free one), SHOTS (a folder for screenshots, or empty).
const { chromium } = require('playwright');

const { BASE, MGR, CASHIER, PW, ITEM, ITEM_B, PLU, SHOTS } = process.env;
let failed = 0;
function ok(cond, what) {
  console.log((cond ? 'ok   ' : 'FAIL ') + what);
  if (!cond) failed += 1;
}

async function login(page, user) {
  await page.goto(BASE + '/web/');
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(BASE + '/web/#/');
  await page.reload();
  await page.fill('input[name=username]', user);
  await page.fill('input[name=password]', PW);
  await page.click('button[type=submit]');
  await page.waitForSelector('#nav a', { state: 'attached' });
}

async function lines(page) {      // [item, quantity] of each line of the receipt
  return page.$$eval('main table tbody tr', (rs) => rs.map((r) => [r.cells[1].textContent, r.cells[2].textContent]));
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('dialog', (d) => d.accept());

  // the manager: the page of the buttons, in the menu
  await login(page, MGR);
  const nav = await page.$$eval('#nav a', (as) => as.map((a) => a.textContent));
  ok(nav.includes('Κουμπιά ταμείου'), 'the menu of a manager: Κουμπιά ταμείου');
  await page.goto(BASE + '/web/#/tiles');
  await page.waitForSelector('main h1:has-text("Κουμπιά ταμείου")');
  await page.waitForSelector('section.tile-group');
  const groupNames = await page.$$eval('section.tile-group input[aria-label^="Όνομα ομάδας"]', (x) => x.map((y) => y.value));
  ok(groupNames.includes('Καφέδες'), 'the groups of the demo: ' + groupNames.join(', '));
  await page.fill('input[name=group_name]', 'TST Γλυκά <b>x</b>');
  await page.click('form button:has-text("Νέα ομάδα")');
  const grp = 'section.tile-group:has(input[value="TST Γλυκά <b>x</b>"])';
  await page.waitForSelector(grp);
  ok((await page.$$(`${grp} b`)).length === 0, 'a name as text, never as HTML');
  for (const c of [ITEM, ITEM_B]) {
    await page.fill(`${grp} input[name=tile_code]`, c);
    await page.click(`${grp} button:has-text("Βάλε")`);
    await page.waitForFunction(([g, code]) => {
      const s = document.querySelector(g);
      return s && s.textContent.includes(code);
    }, [grp, c]);
  }
  const names = async () => page.$$eval(`${grp} .tile .tile-price`, (x) => x.map((y) => y.textContent.split(' ')[0]));
  ok((await names()).join(',') === [ITEM, ITEM_B].join(','), 'two tiles, in the order put');
  await page.click(`${grp} .tile:has-text("${ITEM}") button[aria-label^="Πιο μετά"]`);
  await page.waitForFunction(([g, first]) => {
    const t = document.querySelector(g + ' .tile .tile-price');
    return t && t.textContent.startsWith(first);
  }, [grp, ITEM_B]);
  ok((await names()).join(',') === [ITEM_B, ITEM].join(','), 'a tile moved after the next');
  await page.fill(`${grp} .tile:has-text("${ITEM}") input[aria-label^="PLU"]`, PLU);
  await page.press(`${grp} .tile:has-text("${ITEM}") input[aria-label^="PLU"]`, 'Tab');
  await page.waitForFunction((t) => document.querySelector('#toast').textContent.includes(t), `PLU ${PLU}`);
  ok(true, 'a PLU given');
  const swatch = await page.$eval(`${grp} .swatch`, (s) => getComputedStyle(s).backgroundColor);
  ok(swatch === 'rgb(139, 90, 43)', 'the color of the group: ' + swatch);
  if (SHOTS) await page.screenshot({ path: SHOTS + '/tiles.png', fullPage: true });
  // the options: their groups on the page, and on each tile which of them it has
  const optNames = await page.$$eval('section.opt-admin input[aria-label^="Όνομα επιλογών"]', (x) => x.map((y) => y.value));
  ok(optNames.join(',') === 'Μέγεθος,Ζάχαρη,Γάλα,Έξτρα', 'the options of the demo: ' + optNames.join(','));
  // by category: the coffees their four groups, the bougatsa none; the shot only for the coffees
  ok(await page.isChecked('input[aria-label="Μέγεθος: Freddo espresso"]') && await page.isChecked('input[aria-label="Ζάχαρη: Freddo espresso"]')
    && !(await page.isChecked('input[aria-label="Μέγεθος: Μπουγάτσα κρέμα"]')), 'a tile: the options of its category');
  ok(await page.isChecked('input[aria-label="Μέγεθος στην κατηγορία Καφές (πάγκος)"]')
    && !(await page.isChecked('input[aria-label="Μέγεθος στην κατηγορία Σνακ και γλυκά (πάγκος)"]')), 'a group: its categories');
  ok((await page.textContent('tr:has(input[aria-label="Όνομα: Έξτρα σφηνάκι"]) .only-for summary')) === 'Καφές (πάγκος)', 'an option only for a category');
  // the recipe of a coffee: its materials, its cost, what is left of its price; a material more, then out
  ok((await page.textContent('button[aria-label="Συνταγή: Freddo espresso"]')).startsWith('Συνταγή (2) · κόστος 0,42'),
    'a tile: its recipe and cost ' + await page.textContent('button[aria-label="Συνταγή: Freddo espresso"]'));
  await page.click('button[aria-label="Συνταγή: Freddo espresso"]');
  await page.waitForSelector('dialog.materials[open] table');
  const mats = await page.$$eval('dialog.materials tbody tr td:first-child', (x) => x.map((y) => y.textContent));
  ok(mats.length === 2 && mats[0].startsWith('RAW01') && mats[1].startsWith('RAW08'), 'the materials: ' + mats.join(' | '));
  ok((await page.textContent('dialog.materials')).includes('μένουν 2,08 €'), 'what is left of the price');
  await page.fill('dialog.materials input[name=material_code]', 'RAW10');
  await page.fill('dialog.materials input[name=material_qty]', '0.01');
  await page.click('dialog.materials button:has-text("Βάλε")');
  await page.waitForFunction(() => document.querySelectorAll('dialog.materials tbody tr').length === 3);
  ok(true, 'a material more');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/recipe.png' });
  await page.click('dialog.materials button[aria-label^="Έξω: Σιρόπι"]');
  await page.waitForFunction(() => document.querySelectorAll('dialog.materials tbody tr').length === 2);
  await page.click('dialog.materials button:has-text("Κλείσιμο")');
  await page.waitForSelector('dialog.materials', { state: 'detached' });
  ok(true, 'and out');
  await page.click('button[aria-label="Υλικά: Βρώμης"]');
  await page.waitForSelector('dialog.materials[open] table');
  const oat = await page.$$eval('dialog.materials tbody tr', (x) => x.map((y) => y.cells[0].textContent + ' ' + y.cells[1].querySelector('input').value));
  ok(oat.some((x) => x.startsWith('RAW04') && x.endsWith('-0.15')) && oat.some((x) => x.startsWith('RAW05') && x.endsWith('0.15')),
    'the materials of an option, signed: ' + oat.join(' | '));
  await page.keyboard.press('Escape');
  await page.waitForSelector('dialog.materials', { state: 'detached' });

  // the cashier: no page of the buttons; the till with them
  await login(page, CASHIER);
  ok(!(await page.$$eval('#nav a', (as) => as.map((a) => a.textContent))).includes('Κουμπιά ταμείου'), 'a cashier: not in the menu');
  await page.goto(BASE + '/web/#/pos');
  await page.waitForSelector('main h1:has-text("Ταμείο")');
  await page.selectOption('main select[aria-label="Ταμείο"]', { label: 'TST Test' }).catch(() => null);
  await page.waitForSelector('main button:has-text("Άνοιγμα Ζ")');
  ok(await page.isHidden('.tiles'), 'the Z closed: no buttons');
  await page.click('main button:has-text("Άνοιγμα Ζ")');
  await page.waitForSelector('.tiles:not([hidden]) .tile-tab');
  const tabs = await page.$$eval('.tile-tab', (x) => x.map((y) => y.textContent));
  ok(tabs.includes('Καφέδες') && tabs.includes('TST Γλυκά <b>x</b>'), 'the tabs of the groups: ' + tabs.join(' | '));
  await page.click('.tile-tab:has-text("TST Γλυκά")');
  ok((await page.getAttribute('.tile-tab:has-text("TST Γλυκά")', 'aria-selected')) === 'true', 'a tab chosen');
  await page.waitForSelector('.tile-grid button.tile');
  const tileNames = await page.$$eval('.tile-grid button.tile .tile-name', (x) => x.map((y) => y.textContent));
  ok(tileNames.length === 2, 'its two tiles: ' + tileNames.join(', '));
  await page.click('.tile-qty button:has-text("×2")');
  await page.click('.tile-grid button.tile >> nth=0');                              // ITEM_B ×2
  await page.waitForFunction((c) => [...document.querySelectorAll('main table tbody tr')].some((r) => r.textContent.includes(c)), ITEM_B);
  ok((await page.inputValue('input[name=qty]')) === '1', 'the quantity 1 again after the press');
  await page.fill('input[name=code]', PLU);
  await page.press('input[name=code]', 'Enter');
  await page.waitForFunction((c) => [...document.querySelectorAll('main table tbody tr')].some((r) => r.textContent.includes(c)), ITEM);
  const ls = await lines(page);
  ok(ls.length === 2 && ls[0][0].includes(ITEM_B) && ls[0][1] === '2' && ls[1][0].includes(ITEM) && ls[1][1] === '1',
    'the receipt: B ×2 by its button, A by its PLU: ' + JSON.stringify(ls));
  if (SHOTS) await page.screenshot({ path: SHOTS + '/pos_tiles.png', fullPage: true });
  // a coffee with options: the dialog, the default chosen, a choice of one, an extra, ×2; its line
  await page.click('.tile-tab:has-text("Καφέδες")');
  await page.click('.tile-grid button.tile:has-text("Freddo espresso")');
  await page.waitForSelector('dialog.options-dialog[open]');
  ok((await page.getAttribute('dialog button.opt:has-text("Μέτριος")', 'aria-pressed')) === 'true', 'the dialog: the default chosen');
  await page.click('dialog button.opt:has-text("Σκέτος")');
  ok((await page.getAttribute('dialog button.opt:has-text("Μέτριος")', 'aria-pressed')) === 'false'
    && (await page.getAttribute('dialog button.opt:has-text("Σκέτος")', 'aria-pressed')) === 'true', 'one of a group of one');
  await page.click('dialog button.opt:has-text("Έξτρα σφηνάκι")');
  await page.click('dialog button.opt:has-text("Κανέλα")');
  await page.click('dialog button[aria-label="Μία ακόμα"]');
  ok((await page.textContent('dialog .opt-price')).startsWith('6,00'), 'the price with the extras ×2: ' + await page.textContent('dialog .opt-price'));
  if (SHOTS) await page.screenshot({ path: SHOTS + '/options_dialog.png' });
  await page.click('dialog button:has-text("Βάλε στην απόδειξη")');
  await page.waitForSelector('dialog.options-dialog', { state: 'detached' });
  await page.waitForFunction(() => [...document.querySelectorAll('main .line-options')].some((x) => x.textContent.includes('Σφηνάκι') || x.textContent.includes('σφηνάκι')));
  const opt = await page.$$eval('main .line-options', (x) => x.map((y) => y.textContent));
  ok(opt.includes('Μονός, Σκέτος, Έξτρα σφηνάκι +0,50, Κανέλα'), 'the line with its options: ' + opt.join(' | '));
  // a double: its price; the chocolate: no shot, no sugar; the bougatsa: no dialog at all
  await page.click('.tile-grid button.tile:has-text("Cappuccino") >> nth=1');
  await page.waitForSelector('dialog.options-dialog[open]');
  await page.click('dialog button.opt:has-text("Διπλός")');
  ok((await page.textContent('dialog .opt-price')).startsWith('3,30'), 'a double cappuccino: ' + await page.textContent('dialog .opt-price'));
  await page.keyboard.press('Escape');
  await page.waitForSelector('dialog.options-dialog', { state: 'detached' });
  await page.click('.tile-grid button.tile:has-text("Σοκολάτα")');
  await page.waitForSelector('dialog.options-dialog[open]');
  const choco = await page.$$eval('dialog button.opt', (x) => x.map((y) => y.firstChild.textContent));
  ok(!choco.includes('Έξτρα σφηνάκι') && !choco.includes('Διπλός') && !choco.includes('Σκέτος') && choco.includes('Σαντιγί'),
    'the chocolate: its options only ' + choco.join(','));
  await page.keyboard.press('Escape');
  await page.waitForSelector('dialog.options-dialog', { state: 'detached' });
  const n0 = (await lines(page)).length;
  await page.click('.tile-tab:has-text("Σνακ")');
  await page.click('.tile-grid button.tile:has-text("Μπουγάτσα")');
  await page.waitForFunction((k) => document.querySelectorAll('main table tbody tr').length === k + 1, n0);
  ok(!(await page.$('dialog.options-dialog')), 'the bougatsa: straight into the receipt');
  await page.click('.tile-tab:has-text("Καφέδες")');
  // its PLU typed: the dialog too; Esc: nothing
  await page.fill('input[name=code]', '101');
  await page.press('input[name=code]', 'Enter');
  await page.waitForSelector('dialog.options-dialog[open]');
  ok(true, 'a PLU of a coffee: its dialog');
  await page.keyboard.press('Escape');
  await page.waitForSelector('dialog.options-dialog', { state: 'detached' });
  ok((await lines(page)).length === 4, 'Esc: nothing into the receipt');
  // the phone: the tiles in two columns at least, no page wider than the screen
  await page.setViewportSize({ width: 390, height: 844 });
  const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  ok(!wide, 'a phone: nothing wider than the screen');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/pos_tiles_phone.png', fullPage: false });
  // this device without the buttons: off, kept
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.uncheck('input[name=tiles_on]');
  ok(await page.isHidden('.tiles'), 'the buttons off on this device');
  await page.check('input[name=tiles_on]');
  // paid: its number at the counter, big, and in the last receipts
  await page.click('main button:has-text("Κάρτα (F8)")');
  await page.waitForSelector('.counter-no');
  const no = await page.textContent('.counter-no');
  ok(/^#\d+$/.test(no), 'paid: its number at the counter ' + no);
  ok((await page.textContent('main')).includes('Πάγκος'), 'the last receipts: their number');
  if (SHOTS) await page.screenshot({ path: SHOTS + '/pos_paid.png', fullPage: true });

  ok(errors.length === 0, 'no errors in the browser: ' + errors.join(' | '));
  await browser.close();
  console.log(failed ? `== tiles FAILED (${failed})` : '== tiles OK');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('FAIL ' + e.stack); process.exit(1); });
