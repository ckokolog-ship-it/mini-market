"""fake_aade.py -- a little AADE for the tests of myDATA (mm-api MyData.java): SendInvoices and
CancelInvoice as the documentation of AADE (docs/mydata), on a port of this computer. It keeps what it
got; its answer: Success with a new MARK, or what the test puts in MODE (an error of validation, an
HTTP error). The account it accepts: USER, KEY."""
import http.server
import re
import threading
import urllib.parse

USER, KEY = 'tst-user', 'tst-key'


class Aade:
    def __init__(self):
        self.got = []           # (path, headers, body)
        self.mode = 'ok'        # ok, invalid, http500
        self.mark = 400000000000000
        aade = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get('Content-Length') or 0)
                body = self.rfile.read(n).decode('utf-8') if n else ''
                aade.got.append((self.path, dict(self.headers), body))
                if self.headers.get('aade-user-id') != USER or self.headers.get('ocp-apim-subscription-key') != KEY:
                    return self.answer(401, '{"statusCode":401,"message":"Access denied due to invalid subscription key."}')
                if aade.mode == 'http500':
                    return self.answer(500, 'Internal Server Error')
                u = urllib.parse.urlparse(self.path)
                if u.path == '/SendInvoices':
                    if aade.mode == 'invalid':
                        return self.answer(200, response(
                            '<errors><error><message>Invalid counterpart vat number</message><code>104</code>'
                            '</error></errors><statusCode>ValidationError</statusCode>'))
                    aade.mark += 1
                    uid = ('%040X' % (aade.mark * 7919))[-40:]
                    qr = 'https://mydataapidev.aade.gr/TimologioQR/QRInfo?q=' + uid
                    return self.answer(200, response('<invoiceUid>%s</invoiceUid><invoiceMark>%d</invoiceMark>'
                                                     '<qrUrl>%s</qrUrl><statusCode>Success</statusCode>'
                                                     % (uid, aade.mark, qr)))
                if u.path == '/CancelInvoice':
                    mark = urllib.parse.parse_qs(u.query).get('mark', [''])[0]
                    if not re.fullmatch(r'\d+', mark):
                        return self.answer(400, 'mark')
                    aade.mark += 1
                    return self.answer(200, response('<cancellationMark>%d</cancellationMark>'
                                                     '<statusCode>Success</statusCode>' % aade.mark))
                return self.answer(404, 'no such method')

            def answer(self, code, text):
                b = text.encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/xml' if text.startswith('<') else 'text/plain')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = 'http://127.0.0.1:%d' % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()


def response(inner):
    return ('<?xml version="1.0" encoding="utf-8"?><ResponseDoc xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<response><index>1</index>%s</response></ResponseDoc>' % inner)
