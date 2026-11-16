// scan.js -- the camera as a scanner: a barcode (EAN-13, Code 128 ...) or a QR code of the labels (the
// address of an item: its code). The decoder of the system (BarcodeDetector, Chrome on Android) when
// there, else ZXing (zxing.min.js, loaded the first time). The camera needs a secure page: the app
// (http://localhost of the phone), or https, or this computer (http://localhost); not http://<ip>.

const FORMATS = ['ean_13', 'ean_8', 'code_128', 'code_39', 'upc_a', 'upc_e', 'qr_code'];
let zxing = null;

export function canScan() {
  return !!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

// what a QR of a label says (http://.../web/#/item/CODE): the code; anything else as it is
export function codeOf(text) {
  const m = /#\/item\/([^?#/]+)\s*$/.exec(String(text || '').trim());
  return m ? decodeURIComponent(m[1]) : String(text || '').trim();
}

function loadZxing() {
  if (window.ZXing) return Promise.resolve(window.ZXing);
  if (!zxing) {
    zxing = new Promise((ok, bad) => {
      const s = document.createElement('script');
      s.src = 'zxing.min.js';
      s.onload = () => ok(window.ZXing);
      s.onerror = () => { zxing = null; bad(new Error('Δεν φορτώθηκε ο αναγνώστης της κάμερας')); };
      document.head.append(s);
    });
  }
  return zxing;
}

async function detector() {
  if ('BarcodeDetector' in window) {
    try {
      const have = await window.BarcodeDetector.getSupportedFormats();
      const want = FORMATS.filter((f) => have.includes(f));
      if (want.length) {
        const d = new window.BarcodeDetector({ formats: want });
        return async (video) => {
          const r = await d.detect(video);
          return r.length ? r[0].rawValue : null;
        };
      }
    } catch (e) { /* ZXing then */ }
  }
  const Z = await loadZxing();
  const hints = new Map();
  hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.EAN_8, Z.BarcodeFormat.CODE_128,
    Z.BarcodeFormat.CODE_39, Z.BarcodeFormat.UPC_A, Z.BarcodeFormat.UPC_E, Z.BarcodeFormat.QR_CODE]);
  hints.set(Z.DecodeHintType.TRY_HARDER, true);
  const reader = new Z.MultiFormatReader();
  reader.setHints(hints);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  return async (video) => {
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return null;
    canvas.width = w;
    canvas.height = h;
    ctx.drawImage(video, 0, 0, w, h);
    const lum = new Z.HTMLCanvasElementLuminanceSource(canvas);
    try {
      return reader.decode(new Z.BinaryBitmap(new Z.HybridBinarizer(lum))).getText();
    } catch (e) {
      return null;                                     // nothing in this frame
    }
  };
}

// the camera in a window of its own until a code is read (its text), or "Κλείσιμο" (null)
export function scanOnce() {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.setAttribute('playsinline', '');
    video.muted = true;
    const box = document.createElement('div');
    box.className = 'scanner';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-label', 'Σάρωση με την κάμερα');
    const hint = document.createElement('p');
    hint.textContent = 'Στόχευσε το barcode ή το QR';
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = 'Κλείσιμο';
    const frame = document.createElement('div');
    frame.className = 'scanner-frame';
    frame.append(video);
    box.append(frame, hint, close);
    document.body.append(box);
    let stream = null;
    let done = false;
    const end = (value, error) => {
      if (done) return;
      done = true;
      if (stream) stream.getTracks().forEach((t) => t.stop());
      box.remove();
      document.removeEventListener('keydown', esc);
      if (error) reject(error); else resolve(value);
    };
    const esc = (ev) => { if (ev.key === 'Escape') end(null); };
    document.addEventListener('keydown', esc);
    close.addEventListener('click', () => end(null));
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
        });
        if (done) { stream.getTracks().forEach((t) => t.stop()); return; }
        video.srcObject = stream;
        await video.play();
        const read = await detector();
        const tick = async () => {
          if (done) return;
          let text = null;
          try { text = await read(video); } catch (e) { text = null; }
          if (text) {
            if (navigator.vibrate) navigator.vibrate(60);
            end(text);
          } else setTimeout(tick, 150);
        };
        tick();
      } catch (e) {
        end(null, new Error(e && e.name === 'NotAllowedError' ? 'Η κάμερα δεν επιτράπηκε' : 'Δεν άνοιξε η κάμερα: ' + (e && e.message)));
      }
    })();
  });
}
