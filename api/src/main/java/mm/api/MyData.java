package mm.api;

import java.io.IOException;
import java.io.InputStream;
import java.io.StringReader;
import java.io.StringWriter;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.net.URL;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.TransformerException;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import javax.xml.transform.stream.StreamSource;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;

/**
 * myDATA of AADE: the invoices (1.1) and the credit notes (5.1 of an invoice sent, else 5.2) of the
 * sales, as the REST API of AADE for an ERP (docs/mydata, v1.0.12 of the XSD in resources/mydata):
 * the XML of a document (checked against the XSD before it goes), SendInvoices, its MARK, UID and QR
 * back into MM_DOC (mm_core.mydata_sent); CancelInvoice. The retail receipts go through the cash
 * register (ΦΗΜ) or a provider, not from here.
 *
 * <pre>
 *   GET  /api/docs/{id}/mydata          the XML that would go (text/xml), checked
 *   POST /api/docs/{id}/mydata          queued and sent now; the document back
 *   POST /api/docs/{id}/mydata/cancel   its cancellation at AADE (CancelInvoice), then cancel_doc
 * </pre>
 * The account (never in git): the file MM_MYDATA_CONFIG (default mydata.properties in the folder of the
 * service): url (default https://mydataapidev.aade.gr, the tests of AADE; the real one
 * https://mydatapi.aade.gr/myDATA), user, key. Without it nothing is sent: the documents wait (Q).
 * Every minute the documents waiting (Q, e.g. posted by a form with MYDATA_AUTO Y) are sent.
 * The shop: MM_SETTING MYDATA_AFM (its ΑΦΜ), MYDATA_BRANCH (0 the seat), MYDATA_VAT_EXEMPTION (the
 * cause, table 8.3, of a line of 0% VAT); db/SET_MYDATA.sql.
 */
final class MyData {
    static final String INV = "http://www.aade.gr/myDATA/invoice/v1.0";
    static final String ICLS = "https://www.aade.gr/myDATA/incomeClassificaton/v1.0";
    static final String DEV = "https://mydataapidev.aade.gr";
    // a sale of goods to a business (Πωλήσεις αγαθών Χονδρικές - Επιτηδευματιών), table 8.8 and 8.9
    static final String CATEGORY = "category1_1";
    static final String E3 = "E3_561_001";
    private static Schema schema;

    private MyData() {
    }

    record Config(String url, String user, String key) {
    }

    /** the account of the shop at AADE, or null: not set (nothing is sent) */
    static Config config() {
        Path f = Path.of(Main.env("MM_MYDATA_CONFIG", "mydata.properties"));
        if (!Files.isReadable(f)) {
            return null;
        }
        Properties p = new Properties();
        try (InputStream in = Files.newInputStream(f)) {
            p.load(in);
        } catch (IOException e) {
            return null;
        }
        String user = p.getProperty("user", "").trim();
        String key = p.getProperty("key", "").trim();
        if (user.isEmpty() || key.isEmpty()) {
            return null;
        }
        return new Config(p.getProperty("url", DEV).trim().replaceAll("/+$", ""), user, key);
    }

    private static synchronized Schema schema() throws SAXException {
        if (schema == null) {
            URL u = MyData.class.getResource("/mydata/InvoicesDoc-v1.0.12.xsd");
            SchemaFactory f = SchemaFactory.newInstance(XMLConstants.W3C_XML_SCHEMA_NS_URI);
            schema = f.newSchema(u);
        }
        return schema;
    }

    private static String setting(Connection c, String name) throws SQLException {
        Object v = Db.rows(c, "select max(value) v from mm_setting where name = ?", name).get(0).get("v");
        return v == null ? null : String.valueOf(v).trim();
    }

    private static Http.Fail fail(String text) {
        return new Http.Fail(400, "MM-189", "MM-189: " + text);
    }

    // 24% 1, 13% 2, 6% 3, 17% 4, 9% 5, 4% 6, 0% 7 (table 8.2)
    private static int vatCategory(BigDecimal rate) {
        return switch (rate.stripTrailingZeros().toPlainString()) {
            case "24" -> 1;
            case "13" -> 2;
            case "6" -> 3;
            case "17" -> 4;
            case "9" -> 5;
            case "4" -> 6;
            case "0" -> 7;
            default -> throw fail("ΦΠΑ " + rate + "%: δεν υπάρχει στο myDATA");
        };
    }

    private static String amount(BigDecimal v) {
        return v.setScale(2, RoundingMode.HALF_UP).toPlainString();
    }

    private static Element add(Document d, Node to, String ns, String name, Object text) {
        Element e = d.createElementNS(ns, name);
        if (text != null) {
            e.setTextContent(String.valueOf(text));
        }
        to.appendChild(e);
        return e;
    }

    private static void income(Document d, Element to, BigDecimal net) {
        Element ic = add(d, to, INV, "incomeClassification", null);
        add(d, ic, ICLS, "icls:classificationType", E3);
        add(d, ic, ICLS, "icls:classificationCategory", CATEGORY);
        add(d, ic, ICLS, "icls:amount", amount(net));
    }

    /** the XML of a document (InvoicesDoc of one invoice), checked against the XSD of AADE */
    static String xml(Connection c, long id) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, """
                select d.id, d.doc_type, d.doc_no, d.doc_date, d.status, d.payment, d.total, t.mydata_type,
                       t.name type_name, cu.afm, ref.mydata_mark ref_mark, ref.mydata_state ref_state
                from mm_doc d join mm_doc_type t on t.code = d.doc_type
                left join mm_customer cu on cu.id = d.customer_id
                left join mm_doc ref on ref.id = nvl(d.ref_doc_id,       -- (a credit note: the invoice of its note)
                    (select max(n.ref_doc_id) from mm_doc n where n.invoice_id = d.id))
                where d.id = ?""", id);
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such document: " + id);
        }
        Map<String, Object> doc = r.get(0);
        if (doc.get("mydata_type") == null) {
            throw fail("Το " + doc.get("type_name") + " δεν διαβιβάζεται από το μαγαζί στο myDATA");
        }
        if (!"P".equals(doc.get("status"))) {
            throw fail("Διαβιβάζεται μόνο καταχωρημένο παραστατικό");
        }
        if (doc.get("afm") == null) {
            throw fail("Ο πελάτης του παραστατικού δεν έχει ΑΦΜ: το myDATA τον θέλει");
        }
        String afm = setting(c, "MYDATA_AFM");
        if (afm == null || !afm.matches("[0-9]{9}")) {
            throw fail("Ο ΑΦΜ του μαγαζιού για το myDATA: MYDATA_AFM (db/SET_MYDATA.sql)");
        }
        String branch = setting(c, "MYDATA_BRANCH");
        String type = String.valueOf(doc.get("mydata_type"));
        Object refMark = "S".equals(doc.get("ref_state")) ? doc.get("ref_mark") : null;
        if ("5.1".equals(type) && refMark == null) {
            type = "5.2";                     // a credit note of no invoice sent: not correlated
        }
        List<Map<String, Object>> lines = Db.rows(c, """
                select l.line_no, i.code, i.name, i.unit, l.qty, l.net, l.vat, l.vat_rate
                from mm_doc_line l join mm_item i on i.id = l.item_id
                where l.doc_id = ? order by l.line_no""", id);
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setNamespaceAware(true);
            Document d = f.newDocumentBuilder().newDocument();
            Element root = d.createElementNS(INV, "InvoicesDoc");
            root.setAttributeNS(XMLConstants.XMLNS_ATTRIBUTE_NS_URI, "xmlns:icls", ICLS);
            d.appendChild(root);
            Element inv = add(d, root, INV, "invoice", null);
            Element issuer = add(d, inv, INV, "issuer", null);
            add(d, issuer, INV, "vatNumber", afm);
            add(d, issuer, INV, "country", "GR");
            add(d, issuer, INV, "branch", branch == null ? "0" : branch);
            Element cp = add(d, inv, INV, "counterpart", null);       // (in Greece: no name, AADE has it)
            add(d, cp, INV, "vatNumber", doc.get("afm"));
            add(d, cp, INV, "country", "GR");
            add(d, cp, INV, "branch", "0");
            Element h = add(d, inv, INV, "invoiceHeader", null);
            add(d, h, INV, "series", doc.get("doc_type"));
            add(d, h, INV, "aa", doc.get("doc_no"));
            add(d, h, INV, "issueDate", String.valueOf(doc.get("doc_date")).substring(0, 10));
            add(d, h, INV, "invoiceType", type);
            add(d, h, INV, "currency", "EUR");
            if (refMark != null) {
                add(d, h, INV, "correlatedInvoices", refMark);
            }
            BigDecimal total = (BigDecimal) doc.get("total");
            Element pm = add(d, inv, INV, "paymentMethods", null);
            Element pd = add(d, pm, INV, "paymentMethodDetails", null);
            add(d, pd, INV, "type", switch (String.valueOf(doc.get("payment"))) {    // table 8.12
                case "CASH" -> "3";
                case "CARD" -> "7";
                default -> "5";
            });
            add(d, pd, INV, "amount", amount(total));
            BigDecimal net = BigDecimal.ZERO;
            BigDecimal vat = BigDecimal.ZERO;
            String exemption = null;
            for (Map<String, Object> l : lines) {
                Element row = add(d, inv, INV, "invoiceDetails", null);
                add(d, row, INV, "lineNumber", l.get("line_no"));
                add(d, row, INV, "itemCode", l.get("code"));
                add(d, row, INV, "itemDescr", l.get("name"));
                add(d, row, INV, "quantity", ((BigDecimal) l.get("qty")).stripTrailingZeros().toPlainString());
                add(d, row, INV, "measurementUnit", switch (String.valueOf(l.get("unit"))) {   // table 8.13
                    case "KG" -> "2";
                    case "L" -> "3";
                    default -> "1";
                });
                BigDecimal n = (BigDecimal) l.get("net");
                BigDecimal v = (BigDecimal) l.get("vat");
                add(d, row, INV, "netValue", amount(n));
                int cat = vatCategory((BigDecimal) l.get("vat_rate"));
                add(d, row, INV, "vatCategory", cat);
                add(d, row, INV, "vatAmount", amount(v));
                if (cat == 7) {
                    if (exemption == null) {
                        exemption = setting(c, "MYDATA_VAT_EXEMPTION");
                    }
                    if (exemption == null) {
                        throw fail("Γραμμή με ΦΠΑ 0%: η αιτία εξαίρεσης για το myDATA, MYDATA_VAT_EXEMPTION (db/SET_MYDATA.sql)");
                    }
                    add(d, row, INV, "vatExemptionCategory", exemption);
                }
                income(d, row, n);
                net = net.add(n);
                vat = vat.add(v);
            }
            Element s = add(d, inv, INV, "invoiceSummary", null);
            add(d, s, INV, "totalNetValue", amount(net));
            add(d, s, INV, "totalVatAmount", amount(vat));
            for (String z : List.of("totalWithheldAmount", "totalFeesAmount", "totalStampDutyAmount",
                    "totalOtherTaxesAmount", "totalDeductionsAmount")) {
                add(d, s, INV, z, "0.00");
            }
            add(d, s, INV, "totalGrossValue", amount(net.add(vat)));
            income(d, s, net);
            StringWriter w = new StringWriter();
            var t = TransformerFactory.newInstance().newTransformer();
            t.setOutputProperty(OutputKeys.ENCODING, "UTF-8");
            t.setOutputProperty(OutputKeys.INDENT, "yes");
            t.setOutputProperty("{http://xml.apache.org/xslt}indent-amount", "2");
            t.transform(new DOMSource(d), new StreamResult(w));
            String xml = w.toString();
            try {
                schema().newValidator().validate(new StreamSource(new StringReader(xml)));
            } catch (SAXException e) {
                throw fail("Το XML δεν περνά το XSD της ΑΑΔΕ: " + e.getMessage());
            }
            return xml;
        } catch (ParserConfigurationException | TransformerException | IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** what AADE answered: Success with its MARK, UID, QR, or the errors */
    record Answer(boolean ok, Long mark, String uid, String qr, Long cancelMark, String error) {
    }

    static Answer answer(int status, String body) {
        if (status != 200) {
            return new Answer(false, null, null, null, null, "ΑΑΔΕ: HTTP " + status + " "
                    + body.replaceAll("\\s+", " ").trim().substring(0, Math.min(300, body.trim().length())));
        }
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            Document d = f.newDocumentBuilder().parse(new InputSource(new StringReader(body)));
            NodeList rs = d.getElementsByTagName("response");
            if (rs.getLength() == 0) {
                return new Answer(false, null, null, null, null, "ΑΑΔΕ: απάντηση χωρίς response");
            }
            Element r = (Element) rs.item(0);
            String code = text(r, "statusCode");
            if ("Success".equals(code)) {
                String m = text(r, "invoiceMark");
                String cm = text(r, "cancellationMark");
                return new Answer(true, m == null ? null : Long.valueOf(m), text(r, "invoiceUid"), text(r, "qrUrl"),
                        cm == null ? null : Long.valueOf(cm), null);
            }
            List<String> errs = new ArrayList<>();
            NodeList es = r.getElementsByTagName("error");
            for (int k = 0; k < es.getLength(); k++) {
                Element e = (Element) es.item(k);
                errs.add(text(e, "code") + ": " + text(e, "message"));
            }
            return new Answer(false, null, null, null, null, "ΑΑΔΕ " + code + ": " + String.join(" | ", errs));
        } catch (ParserConfigurationException | SAXException | IOException | NumberFormatException e) {
            return new Answer(false, null, null, null, null, "ΑΑΔΕ: απάντηση που δεν διαβάζεται: " + e.getMessage());
        }
    }

    private static String text(Element e, String name) {
        NodeList n = e.getElementsByTagName(name);
        return n.getLength() == 0 ? null : n.item(0).getTextContent().trim();
    }

    private static HttpResponse<String> call(Config cf, String path, String body) throws IOException {
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(cf.url() + path))
                .timeout(Duration.ofSeconds(60))
                .header("aade-user-id", cf.user())
                .header("ocp-apim-subscription-key", cf.key())
                .header("Content-Type", "application/xml");
        b = body == null ? b.POST(HttpRequest.BodyPublishers.noBody())
                : b.POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8));
        try {
            return HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(20)).build()
                    .send(b.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("interrupted");
        }
    }

    private static void proc(Connection c, String sql, Object... binds) throws SQLException {
        try (CallableStatement cs = c.prepareCall(sql)) {
            for (int k = 0; k < binds.length; k++) {
                if (binds[k] == null) {
                    cs.setNull(k + 1, Types.VARCHAR);
                } else {
                    cs.setObject(k + 1, binds[k]);
                }
            }
            cs.execute();
        }
    }

    /**
     * a document sent now (queued first): sent (S, its MARK) or failed (E, the error), committed. An
     * error of the document itself (no ΑΦΜ, no XSD): an Http.Fail, nothing sent
     */
    static Map<String, Object> send(Connection c, long id) throws SQLException {
        Config cf = config();
        String xml = xml(c, id);                    // (its own errors before anything)
        proc(c, "begin mm_core.mydata_queue(?); end;", id);
        c.commit();
        if (cf == null) {                           // it waits (Q), with why
            proc(c, "update mm_doc set mydata_error = ? where id = ?",
                    "Χωρίς λογαριασμό myDATA (mydata.properties): περιμένει", id);
            c.commit();
            return state(c, id);
        }
        Answer a;
        try {
            HttpResponse<String> r = call(cf, "/SendInvoices", xml);
            a = answer(r.statusCode(), r.body());
        } catch (IOException e) {
            a = new Answer(false, null, null, null, null, "ΑΑΔΕ: δεν απαντά (" + e.getMessage() + ")");
        }
        if (a.ok() && a.mark() != null) {
            proc(c, "begin mm_core.mydata_sent(?, ?, ?, ?); end;", id, a.mark(), a.uid(), a.qr());
        } else {
            proc(c, "begin mm_core.mydata_failed(?, ?); end;", id, a.error() == null ? "ΑΑΔΕ: χωρίς MARK" : a.error());
        }
        c.commit();
        return state(c, id);
    }

    /** its cancellation at AADE (CancelInvoice by its MARK), then the document cancelled here */
    static Map<String, Object> cancel(Connection c, long id) throws SQLException {
        Map<String, Object> s = state(c, id);
        if (!"S".equals(s.get("mydata_state"))) {
            throw fail("Ακυρώνεται στο myDATA μόνο παραστατικό που έχει διαβιβαστεί");
        }
        Config cf = config();
        if (cf == null) {
            throw fail("Χωρίς λογαριασμό myDATA (mydata.properties)");
        }
        Answer a;
        try {
            HttpResponse<String> r = call(cf, "/CancelInvoice?mark=" + s.get("mydata_mark"), null);
            a = answer(r.statusCode(), r.body());
        } catch (IOException e) {
            a = new Answer(false, null, null, null, null, "ΑΑΔΕ: δεν απαντά (" + e.getMessage() + ")");
        }
        if (!a.ok() || a.cancelMark() == null) {
            throw fail("Η ακύρωση στο myDATA απέτυχε: " + (a.error() == null ? "χωρίς MARK ακύρωσης" : a.error()));
        }
        proc(c, "begin mm_core.mydata_cancelled(?, ?); end;", id, a.cancelMark());
        c.commit();
        proc(c, "begin mm_core.cancel_doc(?); end;", id);
        c.commit();
        return state(c, id);
    }

    static Map<String, Object> state(Connection c, long id) throws SQLException {
        List<Map<String, Object>> r = Db.rows(c, """
                select id, status, mydata_state, mydata_mark, mydata_uid, mydata_qr, mydata_error, mydata_at,
                       mydata_cancel_mark
                from mm_doc where id = ?""", id);
        if (r.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such document: " + id);
        }
        return new LinkedHashMap<>(r.get(0));
    }

    /**
     * the turn to send, for this mm-api: a lock of the row MYDATA_SENDER of MM_SETTING (SELECT ... FOR UPDATE SKIP
     * LOCKED), held on its own connection while the documents are sent; another mm-api with it now: false, this
     * round skipped. More than one mm-api (k3s, forms1) never sends the same document twice.
     */
    static boolean takeTurn(Connection turn) throws SQLException {
        Db.exec(turn, """
                begin
                  merge into mm_setting s using (select 'MYDATA_SENDER' name from dual) v on (s.name = v.name)
                  when not matched then insert (name, value) values (v.name, 'the turn of a mm-api to send to myDATA');
                end;""");
        turn.commit();
        return !Db.rows(turn, "select name from mm_setting where name = 'MYDATA_SENDER' for update skip locked").isEmpty();
    }

    /** the documents waiting (Q), sent one by one (with an account): by the minute, from Main (with the turn) */
    static int sendWaiting(Connection c) throws SQLException {
        if (config() == null) {
            return 0;
        }
        int n = 0;
        for (Map<String, Object> r : Db.rows(c, "select id from mm_doc where mydata_state = 'Q' order by id fetch first 50 rows only")) {
            long id = ((BigDecimal) r.get("id")).longValue();
            try {
                send(c, id);
            } catch (Http.Fail e) {
                proc(c, "begin mm_core.mydata_failed(?, ?); end;", id, e.getMessage());
                c.commit();
            }
            n++;
        }
        return n;
    }
}
