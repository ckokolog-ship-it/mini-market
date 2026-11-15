// codes.js -- the barcodes and the QR codes of the labels, drawn here (no library from elsewhere: the
// pages take scripts from their own server only). The bars and the modules as data (tests/codes_check.mjs
// reads them back with a decoder), and as SVG for the page.
//
//   EAN-13      an item with a barcode of 13 digits and its right check digit
//   Code 128 B  any other code (latin letters, digits, - . / ...): the code of the item
//   QR          byte mode, error correction M, versions 1 to 10 (up to 213 bytes)

const SVG = 'http://www.w3.org/2000/svg';

// -- EAN-13 ----------------------------------------------------------------------------------------
const L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011'];
const R = L.map((p) => [...p].map((b) => (b === '1' ? '0' : '1')).join(''));
const G = R.map((p) => [...p].reverse().join(''));
const PARITY = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL'];

export function ean13Ok(code) {
  if (!/^\d{13}$/.test(String(code || ''))) return false;
  const d = [...code].map(Number);
  const sum = d.slice(0, 12).reduce((a, x, i) => a + x * (i % 2 ? 3 : 1), 0);
  return (10 - (sum % 10)) % 10 === d[12];
}

// the 95 modules of an EAN-13: 1 a bar, 0 a space
export function ean13Bars(code) {
  if (!ean13Ok(code)) throw new Error('not an EAN-13: ' + code);
  const d = [...code].map(Number);
  let s = '101';
  for (let i = 1; i <= 6; i += 1) s += (PARITY[d[0]][i - 1] === 'L' ? L : G)[d[i]];
  s += '01010';
  for (let i = 7; i <= 12; i += 1) s += R[d[i]];
  return s + '101';
}

// -- Code 128 (set B) ------------------------------------------------------------------------------
const C128 = ['11011001100', '11001101100', '11001100110', '10010011000', '10010001100', '10001001100', '10011001000',
  '10011000100', '10001100100', '11001001000', '11001000100', '11000100100', '10110011100', '10011011100', '10011001110',
  '10111001100', '10011101100', '10011100110', '11001110010', '11001011100', '11001001110', '11011100100', '11001110100',
  '11101101110', '11101001100', '11100101100', '11100100110', '11101100100', '11100110100', '11100110010', '11011011000',
  '11011000110', '11000110110', '10100011000', '10001011000', '10001000110', '10110001000', '10001101000', '10001100010',
  '11010001000', '11000101000', '11000100010', '10110111000', '10110001110', '10001101110', '10111011000', '10111000110',
  '10001110110', '11101110110', '11010001110', '11000101110', '11011101000', '11011100010', '11011101110', '11101011000',
  '11101000110', '11100010110', '11101101000', '11101100010', '11100011010', '11101111010', '11001000010', '11110001010',
  '10100110000', '10100001100', '10010110000', '10010000110', '10000101100', '10000100110', '10110010000', '10110000100',
  '10011010000', '10011000010', '10000110100', '10000110010', '11000010010', '11001010000', '11110111010', '11000010100',
  '10001111010', '10100111100', '10010111100', '10010011110', '10111100100', '10011110100', '10011110010', '11110100100',
  '11110010100', '11110010010', '11011011110', '11011110110', '11110110110', '10101111000', '10100011110', '10001011110',
  '10111101000', '10111100010', '11110101000', '11110100010', '10111011110', '10111101110', '11101011110', '11110101110',
  '11010000100', '11010010000', '11010011100', '1100011101011'];
const START_B = 104;
const STOP = 106;

export function code128Ok(text) {
  return /^[\x20-\x7e]{1,40}$/.test(String(text || ''));
}

export function code128Bars(text) {
  if (!code128Ok(text)) throw new Error('not for Code 128 B: ' + text);
  const values = [START_B, ...[...text].map((c) => c.charCodeAt(0) - 32)];
  const check = values.reduce((a, v, i) => a + v * (i || 1), 0) % 103;
  return [...values, check, STOP].map((v) => C128[v]).join('');
}

// -- QR, byte mode, error correction M -------------------------------------------------------------
const ECC_M = [0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26];       // ECC codewords of a block, by version
const BLOCKS_M = [0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5];              // its blocks

function rawModules(ver) {
  let r = (16 * ver + 128) * ver + 64;
  if (ver >= 2) {
    const n = Math.floor(ver / 7) + 2;
    r -= (25 * n - 10) * n - 55;
    if (ver >= 7) r -= 36;
  }
  return r;
}
const dataCodewords = (ver) => Math.floor(rawModules(ver) / 8) - ECC_M[ver] * BLOCKS_M[ver];

function gfMul(x, y) {
  let z = 0;
  for (let i = 7; i >= 0; i -= 1) {
    z = (z << 1) ^ ((z >>> 7) * 0x11d);
    z ^= ((y >>> i) & 1) * x;
  }
  return z;
}
function rsDivisor(degree) {
  const r = new Array(degree).fill(0);
  r[degree - 1] = 1;
  let root = 1;
  for (let i = 0; i < degree; i += 1) {
    for (let j = 0; j < r.length; j += 1) {
      r[j] = gfMul(r[j], root);
      if (j + 1 < r.length) r[j] ^= r[j + 1];
    }
    root = gfMul(root, 0x02);
  }
  return r;
}
function rsRemainder(data, div) {
  const res = div.map(() => 0);
  for (const b of data) {
    const f = b ^ res.shift();
    res.push(0);
    div.forEach((c, i) => { res[i] ^= gfMul(c, f); });
  }
  return res;
}

function alignPositions(ver) {
  if (ver === 1) return [];
  const n = Math.floor(ver / 7) + 2;
  const step = Math.ceil((ver * 4 + 4) / (n * 2 - 2)) * 2;
  const res = [6];
  for (let pos = ver * 4 + 10; res.length < n; pos -= step) res.splice(1, 0, pos);
  return res;
}

const MASKS = [
  (x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, (x) => x % 3 === 0, (x, y) => (x + y) % 3 === 0,
  (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0, (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
  (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0, (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0];

// the modules of a QR of the text (UTF-8): rows of true (dark) and false
export function qrMatrix(text) {
  const bytes = [...new TextEncoder().encode(String(text))];
  let ver = 1;
  for (; ver <= 10; ver += 1) {
    if (4 + (ver < 10 ? 8 : 16) + 8 * bytes.length <= dataCodewords(ver) * 8) break;
  }
  if (ver > 10) throw new Error('too long for a QR of the labels: ' + bytes.length + ' bytes');
  // the bits: mode, length, the bytes, the end, the padding
  const bits = [];
  const put = (v, n) => { for (let i = n - 1; i >= 0; i -= 1) bits.push((v >>> i) & 1); };
  put(4, 4);
  put(bytes.length, ver < 10 ? 8 : 16);
  bytes.forEach((b) => put(b, 8));
  const cap = dataCodewords(ver) * 8;
  put(0, Math.min(4, cap - bits.length));
  put(0, (8 - (bits.length % 8)) % 8);
  for (let p = 0xec; bits.length < cap; p ^= 0xec ^ 0x11) put(p, 8);
  const data = [];
  for (let i = 0; i < bits.length; i += 8) data.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));
  // the error correction, the blocks interleaved
  const nb = BLOCKS_M[ver];
  const eccLen = ECC_M[ver];
  const raw = Math.floor(rawModules(ver) / 8);
  const nShort = nb - (raw % nb);
  const shortLen = Math.floor(raw / nb);
  const div = rsDivisor(eccLen);
  const blocks = [];
  for (let i = 0, k = 0; i < nb; i += 1) {
    const dat = data.slice(k, k + shortLen - eccLen + (i < nShort ? 0 : 1));
    k += dat.length;
    const ecc = rsRemainder(dat, div);
    if (i < nShort) dat.push(0);
    blocks.push(dat.concat(ecc));
  }
  const all = [];
  for (let i = 0; i < blocks[0].length; i += 1) {
    blocks.forEach((b, j) => { if (i !== shortLen - eccLen || j >= nShort) all.push(b[i]); });
  }
  // the patterns
  const size = ver * 4 + 17;
  const m = Array.from({ length: size }, () => new Array(size).fill(false));
  const fn = Array.from({ length: size }, () => new Array(size).fill(false));
  const set = (x, y, dark) => { m[y][x] = dark; fn[y][x] = true; };
  for (let i = 0; i < size; i += 1) {
    set(6, i, i % 2 === 0);
    set(i, 6, i % 2 === 0);
  }
  for (const [cx, cy] of [[3, 3], [size - 4, 3], [3, size - 4]]) {
    for (let dy = -4; dy <= 4; dy += 1) {
      for (let dx = -4; dx <= 4; dx += 1) {
        const d = Math.max(Math.abs(dx), Math.abs(dy));
        const x = cx + dx;
        const y = cy + dy;
        if (x >= 0 && x < size && y >= 0 && y < size) set(x, y, d !== 2 && d !== 4);
      }
    }
  }
  const ap = alignPositions(ver);
  ap.forEach((ax, i) => ap.forEach((ay, j) => {
    if ((i === 0 && j === 0) || (i === 0 && j === ap.length - 1) || (i === ap.length - 1 && j === 0)) return;
    for (let dy = -2; dy <= 2; dy += 1) for (let dx = -2; dx <= 2; dx += 1) set(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
  }));
  const format = (mask) => {
    const d = (0 << 3) | mask;                         // M: 00
    let rem = d;
    for (let i = 0; i < 10; i += 1) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    const b = ((d << 10) | rem) ^ 0x5412;
    const bit = (i) => ((b >>> i) & 1) === 1;
    for (let i = 0; i <= 5; i += 1) set(8, i, bit(i));
    set(8, 7, bit(6));
    set(8, 8, bit(7));
    set(7, 8, bit(8));
    for (let i = 9; i < 15; i += 1) set(14 - i, 8, bit(i));
    for (let i = 0; i < 8; i += 1) set(size - 1 - i, 8, bit(i));
    for (let i = 8; i < 15; i += 1) set(8, size - 15 + i, bit(i));
    set(8, size - 8, true);
  };
  format(0);                                            // (its place: not for the data)
  if (ver >= 7) {
    let rem = ver;
    for (let i = 0; i < 12; i += 1) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
    const b = (ver << 12) | rem;
    for (let i = 0; i < 18; i += 1) {
      const dark = ((b >>> i) & 1) === 1;
      const a = size - 11 + (i % 3);
      const c = Math.floor(i / 3);
      set(a, c, dark);
      set(c, a, dark);
    }
  }
  // the data, two columns at a time, up and down from the right
  let i = 0;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    for (let v = 0; v < size; v += 1) {
      for (let j = 0; j < 2; j += 1) {
        const x = right - j;
        const y = ((right + 1) & 2) === 0 ? size - 1 - v : v;
        if (!fn[y][x] && i < all.length * 8) {
          m[y][x] = ((all[i >>> 3] >>> (7 - (i & 7))) & 1) === 1;
          i += 1;
        }
      }
    }
  }
  // the mask with the lowest penalty
  let best = null;
  for (let k = 0; k < 8; k += 1) {
    const t = m.map((row, y) => row.map((dark, x) => (fn[y][x] ? dark : dark !== MASKS[k](x, y))));
    const p = penalty(t);
    if (!best || p < best.p) best = { k, t, p };
  }
  m.splice(0, size, ...best.t);
  format(best.k);
  return m;
}

// rules 1, 2 and 4 of the standard (runs, 2x2 blocks, the balance of dark and light)
function penalty(t) {
  const n = t.length;
  let p = 0;
  for (let pass = 0; pass < 2; pass += 1) {
    for (let a = 0; a < n; a += 1) {
      let run = 1;
      for (let b = 1; b < n; b += 1) {
        const cur = pass ? t[b][a] : t[a][b];
        const prev = pass ? t[b - 1][a] : t[a][b - 1];
        if (cur === prev) run += 1;
        else { if (run >= 5) p += run - 2; run = 1; }
      }
      if (run >= 5) p += run - 2;
    }
  }
  let dark = 0;
  for (let y = 0; y < n; y += 1) {
    for (let x = 0; x < n; x += 1) {
      if (t[y][x]) dark += 1;
      if (x < n - 1 && y < n - 1 && t[y][x] === t[y][x + 1] && t[y][x] === t[y + 1][x] && t[y][x] === t[y + 1][x + 1]) p += 3;
    }
  }
  return p + Math.floor(Math.abs(dark * 20 - n * n * 10) / (n * n)) * 10;
}

// -- as SVG ----------------------------------------------------------------------------------------
function svg(w, h, cls) {
  const e = document.createElementNS(SVG, 'svg');
  e.setAttribute('viewBox', `0 0 ${w} ${h}`);
  e.setAttribute('preserveAspectRatio', 'none');
  e.setAttribute('shape-rendering', 'crispEdges');
  e.setAttribute('class', cls);
  return e;
}
function rect(parent, x, y, w, h) {
  const r = document.createElementNS(SVG, 'rect');
  r.setAttribute('x', x);
  r.setAttribute('y', y);
  r.setAttribute('width', w);
  r.setAttribute('height', h);
  parent.append(r);
}

// the bars of a barcode (with its quiet zones of 10 modules)
export function barsSvg(bars) {
  const q = 10;
  const e = svg(bars.length + 2 * q, 40, 'bars');
  for (let i = 0; i < bars.length;) {
    if (bars[i] !== '1') { i += 1; continue; }
    let j = i;
    while (bars[j] === '1') j += 1;
    rect(e, q + i, 0, j - i, 40);
    i = j;
  }
  return e;
}

// a QR (with its quiet zone of 4 modules), a path of its dark modules
export function qrSvg(text) {
  const m = qrMatrix(text);
  const n = m.length + 8;
  const e = svg(n, n, 'qr');
  const path = document.createElementNS(SVG, 'path');
  let d = '';
  m.forEach((row, y) => row.forEach((dark, x) => { if (dark) d += `M${x + 4} ${y + 4}h1v1h-1z`; }));
  path.setAttribute('d', d);
  e.append(path);
  return e;
}

// the barcode of an item: its EAN-13, else its code in Code 128
export function itemBars(item) {
  if (ean13Ok(item.barcode)) return { kind: 'EAN-13', text: item.barcode, bars: ean13Bars(item.barcode) };
  return { kind: 'Code 128', text: item.code, bars: code128Bars(item.code) };
}
