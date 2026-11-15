// codes_check.mjs -- the bars and the QR modules of api/src/main/resources/web/codes.js for some texts,
// as JSON (tests/test_codes.py draws them and reads them back with a decoder)
import { copyFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// (a copy as .mjs: the file of the pages is a module of the browser, not of this folder)
const dir = mkdtempSync(join(tmpdir(), 'mmcodes-'));
const copy = join(dir, 'codes.mjs');
copyFileSync(fileURLToPath(new URL('../api/src/main/resources/web/codes.js', import.meta.url)), copy);
const codes = await import(pathToFileURL(copy).href);
rmSync(dir, { recursive: true, force: true });
const input = JSON.parse(process.argv[2]);
const out = {
  ean: input.ean.map((c) => ({ text: c, ok: codes.ean13Ok(c), bars: codes.ean13Ok(c) ? codes.ean13Bars(c) : null })),
  c128: input.c128.map((c) => ({ text: c, bars: codes.code128Bars(c) })),
  qr: input.qr.map((t) => ({ text: t, m: codes.qrMatrix(t).map((r) => r.map((x) => (x ? 1 : 0)).join('')) })),
};
console.log(JSON.stringify(out));
