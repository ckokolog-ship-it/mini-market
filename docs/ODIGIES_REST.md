# Η υπηρεσία REST (`api/`, `mm-api.jar`)

Βήμα 7 του πλάνου: τα δεδομένα του mini market ως JSON, για τις σελίδες web (βήμα 8) και το Android της απογραφής (βήμα 9).

- **Τι είναι:** Java 17 ή νεότερη, με τον `HttpServer` του JDK και JDBC (ojdbc11, UCP). Είναι ένα jar, όπως το `propo-api` του PROPO.
- **Η βάση:** συνδέεται με το **wallet** των φορμών, το alias `MM_DB`, οπότε δεν υπάρχει κωδικός σε αρχείο ή σε όρισμα. Ό,τι γράφει περνά από το `MM_CORE` και το `MM_LEDGER`, άρα τα νούμερα είναι τα ίδια με των φορμών και των reports.
- **Login (βήμα 7α):** χρήστες και ρόλοι στη βάση (`MM_AUTH`). Κάθε κλήση θέλει το token του login, εκτός από το `health`.

## Εκκίνηση (Windows)

**Maven δεν χρειάζεται.** Στον φάκελο `api` υπάρχει το **Maven Wrapper** (`mvnw.cmd`), που κατεβάζει μόνο του το Maven την πρώτη φορά. Αρκεί η Java 17 (το JDK που έχεις για τις φόρμες).

1. **Μία φορά, ο πρώτος χρήστης (διαχειριστής).** Από τον φάκελο `db`, με `NLS_LANG=GREEK_GREECE.AL32UTF8`:
   ```bat
   sqlplus mm/<κωδικός>@localhost:1522/FREEPDB1 @CREATE_MM_USER.sql
   ```
   - **Τι ρωτά:** όνομα χρήστη (λατινικά, π.χ. `chris`), ονοματεπώνυμο, ρόλο (`ADMIN`) και κωδικό δύο φορές.
   - **Ο κωδικός:** δεν φαίνεται όταν τον γράφεις, και δεν γράφεται πουθενά. Στη βάση μένει μόνο το hash του. Θέλει τουλάχιστον 10 χαρακτήρες, με γράμματα και ψηφία.
2. **Εκκίνηση.** Από τον φάκελο `api`:
   ```bat
   cd C:\Users\chris\eclipse-workspace\mini-market\api
   powershell -ExecutionPolicy Bypass -File run_api.ps1
   ```
   - **Την πρώτη φορά:** χτίζει το `target\mm-api.jar` με το `mvnw.cmd`, κατεβάζοντας το Maven και τον driver της Oracle (λίγα λεπτά).
   - **Μετά από `git pull`:** `run_api.ps1 -Build` για να ξαναχτιστεί.
   - **Ρυθμίσεις:** θύρα **8090** (`-Port` για άλλη)· σταματά με Ctrl+C.
3. **Δοκιμή:** στον browser, `http://127.0.0.1:8090/api/health` → `{"status":"ok","db":"ok"}`.

**Από το δίκτυο** (π.χ. τα κινητά της απογραφής): `run_api.ps1 -Bind 0.0.0.0`.
- **Πριν:** το login είναι πια υποχρεωτικό για όλα, εκτός από το `health`.
- **Προσοχή:** είναι απλό HTTP, χωρίς κρυπτογράφηση. Μόνο σε δίκτυο που εμπιστεύεσαι, όπως το WiFi του μαγαζιού ή το Tailscale, και ποτέ ανοιχτό στο Internet.
- **Το firewall των Windows** θα ρωτήσει για τη θύρα.

**Σε άλλο PC** (όχι αυτό με τις φόρμες), χρειάζεται μόνο Java 17. Στον φάκελο του jar:
- αντιγράφεις τον φάκελο `…\forms_domain\config\fmwconfig\forms_wallet` και το `tnsnames.ora` του ίδιου φακέλου (με το `MM_DB`) σε έναν φάκελο, π.χ. `C:\mm_wallet`·
- τρέχεις `run_api.ps1 -TnsAdmin C:\mm_wallet`.

**Προσοχή στο wallet:** όποιος το έχει συνδέεται στη βάση ως `mm`, οπότε φύλαξέ το όπως έναν κωδικό. Στο `tnsnames.ora` το host πρέπει να είναι το όνομα ή η IP του PC της βάσης, όχι `localhost`.

## Χωρίς παράθυρο: Windows service ή Docker

Το `run_api.ps1` τρέχει όσο είναι ανοιχτό το παράθυρό του. Για να τρέχει μόνιμα, υπάρχουν δύο τρόποι, με την ίδια θύρα. Τρέχει **ένας από τους δύο** κάθε φορά.

### Windows service (προτείνεται για το PC του μαγαζιού)

Σε **PowerShell ως διαχειριστής** (δεξί κλικ, «Εκτέλεση ως διαχειριστής»):

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\api
powershell -ExecutionPolicy Bypass -File install_service.ps1
```

- **Τι κάνει:** χτίζει το jar και το αντιγράφει στο `api\service`. Εγκαθιστά το service **«Mini market API»** (`mm-api`, φαίνεται στο `services.msc`) και το ξεκινά. Στο τέλος δείχνει την απάντηση του `/api/health`.
- **Η εκκίνηση:**
  - ξεκινά με τα Windows (λίγο μετά την εκκίνηση), **χωρίς να συνδεθεί κανείς**·
  - αν υπάρχει το service της βάσης `OracleServiceFREE`, περιμένει πρώτα εκείνο·
  - αν πέσει, ξαναξεκινά μόνο του σε 10, 30 και 60 δευτερόλεπτα.
- **Logs:** `api\service\logs\mm-api.out.log` και `mm-api.err.log`. Κρατιούνται 5 αρχεία των 10 MB.
- **Firewall:** με `-Bind 0.0.0.0` (η προεπιλογή εδώ) ανοίγει η θύρα 8090 μόνο για **ιδιωτικό** δίκτυο (κανόνας «mm-api 8090»). Με `-Bind 127.0.0.1` ακούει μόνο το ίδιο το PC.
- **Ο runner:** το service τρέχει μέσω του **WinSW 2.12.0** (MIT, github.com/winsw/winsw). Την πρώτη φορά κατεβαίνει, και αν το SHA-256 του δεν είναι το αναμενόμενο, δεν χρησιμοποιείται.
- **Μετά από `git pull`:** τρέχεις ξανά το ίδιο. Σταματά το service, χτίζει το νέο jar, και το ξεκινά.
- **Οι άλλες εντολές:**
  - `install_service.ps1 -Status`: πώς είναι, και το `/api/health`·
  - `install_service.ps1 -Uninstall`: αφαιρεί το service και τον κανόνα του firewall.
- Τρέχει ως `LocalSystem` και διαβάζει το wallet του domain, όπως το `run_api.ps1`.

### Docker

Με το **Docker Desktop** ανοιχτό:

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\api
powershell -ExecutionPolicy Bypass -File run_docker.ps1
```

- **Τι κάνει:** χτίζει το jar, και το `Dockerfile` του προσθέτει μόνο ένα Java runtime. Ξεκινά το container `mm-api` (`docker-compose.yml`), που ξαναξεκινά μαζί με το Docker.
- **Η βάση:**
  - το wallet του domain μπαίνει στο container μόνο για ανάγνωση·
  - το `tnsnames.ora` του domain αντιγράφεται στο `api\docker\tns`, και ένα `localhost` γίνεται `host.docker.internal` (το PC).
- **Ασφάλεια:** το container τρέχει ως απλός χρήστης (όχι root), και το Docker ελέγχει την υγεία του με το `/api/health`.
- **Οι άλλες εντολές:** `run_docker.ps1 -Logs` (τα logs) και `run_docker.ps1 -Down` (σταμάτημα).
- **Προσοχή:** το Docker Desktop ξεκινά μόνο όταν **συνδεθεί κάποιος στα Windows** (Settings, General, «Start Docker Desktop when you sign in»). Μετά από διακοπή ρεύματος, το mm-api δεν ξεκινά μέχρι να κάνει κάποιος login. Γι' αυτό, για το PC του μαγαζιού, προτείνεται το service.
- Αν τρέχει το service, το `run_docker.ps1` σταματά με μήνυμα: πρώτα `install_service.ps1 -Uninstall`.

## Login και ρόλοι

| Ρόλος | Τι μπορεί |
|---|---|
| `CASHIER` (ταμίας) | είδη, απογραφές (λίστα, σάρωση) |
| `MANAGER` (προϊστάμενος) | και πελάτες, προμηθευτές, καρτέλες, reports, νέα απογραφή, καταχώριση ή ακύρωσή της |
| `ADMIN` (διαχειριστής) | όλα |

1. **Login:** `POST /api/auth/login` με `{"username": "...", "password": "..."}`. Απαντά με `token` (64 χαρακτήρες), `role` και `expires` (σε 12 ώρες).
2. **Μετά:** σε κάθε κλήση το header `Authorization: Bearer <token>`.
3. **Τέλος:** `POST /api/auth/logout`, ή αυτόματα μετά από 12 ώρες.
4. **Ποιος είμαι:** `GET /api/auth/me`.

Ασφάλεια:
- **Λάθος κωδικός:** 5 λάθος στη σειρά κλειδώνουν τον λογαριασμό για 15 λεπτά. Το ξεκλείδωμα, από διαχειριστή: `exec mm_auth.unlock('όνομα')` και `commit`.
- **Τέλος συνεδριών:** ένας νέος κωδικός, νέος ρόλος ή απενεργοποίηση τερματίζουν αμέσως όλες τις συνεδρίες του χρήστη.
- **Διαχειριστής:** μένει πάντα τουλάχιστον ένας ενεργός.
- **Τι κρατά η βάση:** τον κωδικό μόνο ως PBKDF2-HMAC-SHA256 (100.000 γύροι, δικό του salt), και το token μόνο ως SHA-256. Το `MM_AUTH_LOG` γράφει κάθε login, αποτυχία και αλλαγή, ποτέ κωδικό.

Από SQL (ως `mm`), μέχρι να υπάρξει φόρμα χρηστών:
```sql
exec mm_auth.set_role('maria', 'MANAGER')
exec mm_auth.set_active('maria', 'N')
exec mm_auth.unlock('maria')
commit;
```
Νέος χρήστης ή νέος κωδικός: `CREATE_MM_USER.sql`, που ρωτά τον κωδικό κρυφά.

## Τα endpoints

Επιστρέφουν JSON σε UTF-8, και όλα θέλουν token (πάνω). Οι ημερομηνίες γράφονται `ΕΕΕΕ-ΜΜ-ΗΗ`. Ένα διάστημα δίνεται με `?from=&to=`, και αν λείπει, είναι από την 1η Ιανουαρίου έως σήμερα.

| Endpoint | Τι δίνει |
|---|---|
| `/api/health` | αν ζει η υπηρεσία και η βάση |
| `/api/items?q=&limit=&offset=` | είδη: κωδικός, barcode, περιγραφή, κατηγορία, τιμές, απόθεμα, ελάχιστο. Το `q` ψάχνει σε περιγραφή, κωδικό ή barcode. Μία σελίδα, έως 500 γραμμές (προεπιλογή 50), και το `total` όλων |
| `/api/items/{barcode ή κωδικός}` | ένα είδος, όπως το βρίσκει το ταμείο, με ΦΠΑ, κόστος, δεσμευμένα, διαθέσιμα και διαθέσιμες κάρτες |
| `/api/customers?q=`, `/api/customers/{id}` | πελάτες· ένας με το **υπόλοιπό** του, την κάρτα πόντων (`card`), τους πόντους (`points`) και τις τελευταίες κινήσεις τους (`point_moves`) |
| `POST /api/customers/{id}/card` | κάρτα πόντων για έναν πελάτη που δεν έχει (MANAGER) |
| `/api/suppliers?q=`, `/api/suppliers/{id}` | προμηθευτές· ένας με το υπόλοιπό του |
| `/api/ledger/item/{id}`, `/api/ledger/customer/{id}`, `/api/ledger/supplier/{id}` | η **καρτέλα**: τίτλος, «από μεταφορά» (`open`), σύνολα (`debit`, `credit`), γενικό υπόλοιπο (`close`), και οι γραμμές με το προοδευτικό υπόλοιπο. Με `&limit=&offset=`, μία σελίδα κινήσεων: `total` (όλες), `carry_in` (τα σύνολα πριν από την πρώτη γραμμή της σελίδας: «από μεταφορά») και `carry_out` (με την τελευταία: «σε μεταφορά»). Έτσι το `carry_out` μιας σελίδας είναι το `carry_in` της επόμενης |
| `/api/reports/sales` | πωλήσεις ανά ημέρα |
| `/api/reports/vat` | ΦΠΑ ανά μήνα και συντελεστή |
| `/api/reports/min-stock` | είδη κάτω από το ελάχιστο απόθεμα |
| `POST /api/docs/from-min-stock` `{"supplier_id"}` | οι παραγγελίες στους προμηθευτές από το ελάχιστο απόθεμα: πρόχειρα δελτία παραλαβής (`mm_core.order_missing`)· `lines` πόσες γραμμές μπήκαν, `drafts` τα πρόχειρα (MANAGER) |
| `GET /api/chart?days=&to=` | το γράφημα πωλήσεων (7 έως 364 ημέρες, έως μια ημέρα· προεπιλογή 30 έως σήμερα): `days` (ανά ημέρα: `total`, `receipts`, `last_year` την ίδια μέρα της εβδομάδας πέρσι), `hours` (0-23: αποδείξεις λιανικής και ποσό), `sums` (`total`, `last_year`, `receipts`, `avg_receipt`) (MANAGER) |
| `GET /api/day?date=` | η σύνοψη μιας ημέρας (προεπιλογή σήμερα): `zs` τα Ζ των ταμείων, `sales`, `vat` ανά συντελεστή, `top` τα 10 είδη, `scratch` (δελτία, κέρδη), `orders`, `mydata` (`day` ανά κατάσταση, `waiting`, `failed`), `min_stock`, `backup` (MANAGER) |
| `GET /api/scratch` | τα σκρατς: οι εκδόσεις (είδος, δελτία ανά πακέτο, διαθέσιμα), τα πακέτα (δελτία, πουλημένα, μένουν), τα κέρδη ανά ημέρα (MANAGER) |
| `POST /api/scratch/games` `{"game", "code", "pack_size"}` | μια έκδοση (4 ψηφία) και το είδος της (με serials) |
| `POST /api/scratch/packs` `{"code", "count"}` | φόρτωση πακέτου: το barcode ενός δελτίου (14 ψηφία) ή έκδοση και πακέτο (11)· `loaded`: πόσα δελτία |
| `POST /api/scratch/returns` `{"code"}` | επιστροφή των απούλητων δελτίων ενός πακέτου (άκυρα, έξω από το απόθεμα)· `returned`: πόσα |
| `POST /api/pos/{ταμείο}/prize` `{"amount", "ticket"}` | κέρδος σκρατς από το συρτάρι (CASHIER)· η σάρωση ενός πουλημένου δελτίου στο `scan`: 409 `sold`, με την απόδειξη |
| `/api/backup` | το τελευταίο backup (`db/backup.ps1`): `state` (`OK`, `OLD` πάνω από 2 μέρες, `FAILED`, `NEVER`), `days`, `ok_at`, `ok_file`, `failed_at`, `error` (MANAGER) |
| `/api/reports/trial-items`, `trial-customers`, `trial-suppliers` `?from=&to=&all=1` | τα ισοζύγια: `rows` (`id`, `code`, `name`, `unit`, `open_bal`, `debit`, `credit`, `close_bal`) και `totals`· χωρίς `all=1` μόνο όσα έχουν κάτι |
| `GET /api/counts`, `GET /api/counts/{id}` | οι απογραφές (ανοιχτές και των 90 ημερών)· μία με τις γραμμές της (μετρήθηκαν, σύστημα, διαφορά, συσκευή) |
| `POST /api/counts` `{"name": "..."}` | νέα απογραφή (MANAGER) |
| `POST /api/counts/{id}/scan` `{"code", "qty", "mode", "device"}` | σάρωση από κινητό: barcode ή κωδικός, ποσότητα (1), `ADD` (προσθέτει) ή `SET` (ορίζει), συσκευή (αλλιώς ο χρήστης) |
| `POST /api/counts/{id}/post`, `.../cancel` | καταχώριση στο απόθεμα, ή ακύρωση (MANAGER) |
| `GET /api/pos` | **το ταμείο:** τα ταμεία, το καθένα με το ανοιχτό Ζ του (ή κανένα) |
| `GET /api/pos/{ταμείο}` | ένα ταμείο (π.χ. `T1`): το Ζ του (αποδείξεις, μετρητά, κάρτα, και τι έχει το συρτάρι), η απόδειξη που είναι ανοιχτή με τις γραμμές της, και οι 5 τελευταίες αποδείξεις. Όλα τα `POST` πιο κάτω επιστρέφουν το ίδιο |
| `POST /api/pos/{ταμείο}/open` `{"cash"}`, `.../close` | άνοιγμα Ζ με τα μετρητά του συρταριού· κλείσιμο Ζ, με τα σύνολά του στο `closed` |
| `POST /api/pos/{ταμείο}/cash` `{"amount", "note"}` | μετρητά που μπαίνουν (+) ή βγαίνουν (−) από το συρτάρι, με αιτιολογία |
| `POST /api/pos/{ταμείο}/scan` `{"code", "qty"}` | barcode ή κωδικός, με ποσότητα. Μια κάρτα κινητής μπαίνει μία φορά, η παλαιότερη· με serial, μπαίνει αυτή η κάρτα. Η πρώτη σάρωση ανοίγει την απόδειξη. Με κλειστό Ζ: 409 |
| `POST /api/pos/{ταμείο}/lines/{id}` `{"qty"}` | νέα ποσότητα μιας γραμμής· με 0 η γραμμή σβήνει |
| `GET /api/pos/{ταμείο}/receipt/{id}` | μια απόδειξη του ταμείου για εκτύπωση: επικεφαλίδα και υποσέλιδο, γραμμές, ΦΠΑ ανά συντελεστή, και οι κάρτες με το PIN τους, αν πουλήθηκαν σήμερα (στο `MM_PIN_LOG` με τον χρήστη της σύνδεσης) |
| `GET /api/pos/settings`, `POST /api/pos/settings` `{"header", "footer"}` | η επικεφαλίδα και το υποσέλιδο των αποδείξεων (`MM_SETTING`)· η αλλαγή: MANAGER |
| `POST /api/pos/{ταμείο}/void` | σβήνει την ανοιχτή απόδειξη (αν ήταν από παραγγελία, η παραγγελία ξαναείναι ανοιχτή) |
| `POST /api/pos/{ταμείο}/order` `{"id"}` | μια παραγγελία, όλη, στην απόδειξη. Αν υπάρχει άλλη απόδειξη με είδη: 409. Η απόδειξη δείχνει `deposit` και `due` (το πληρωτέο) |
| `POST /api/pos/{ταμείο}/customer` `{"code"}` | ο πελάτης της απόδειξης: η κάρτα του (και μια σάρωσή της στο `/scan`) ή το τηλέφωνό του· κενό: χωρίς πελάτη. Η απόδειξη δίνει `customer` (`card`, `points`, `earn`: όσους θα πάρει), `points_used`, `disc_amount` |
| `POST /api/pos/{ταμείο}/customer/new` `{"name", "phone"}` | νέος πελάτης με κάρτα πόντων, στην απόδειξη |
| `POST /api/pos/{ταμείο}/points` `{"points"}` | εξαργύρωση πόντων ως έκπτωση στην απόδειξη (0: καμία)· MM-191 κάτω από το ελάχιστο ή πάνω από όσους έχει ή από το ποσό. Το ταμείο δίνει και `points` (`per_euro`, `value`, `min`) |
| `GET /api/doc-types` | τα είδη παραστατικών, με το τι κάνει το καθένα (MANAGER, όπως και τα παρακάτω του γραφείου) |
| `GET /api/docs?type=&status=&q=&limit=&offset=`, `GET /api/docs/{id}` | τα παραστατικά εκτός από τις αποδείξεις, σε σελίδες· ένα με τις γραμμές του, και για τιμολόγιο τα δελτία του (`notes_in`), για δελτίο το τιμολόγιό του (`invoice_text`) |
| `GET /api/docs/notes?type=&customer_id=&supplier_id=` | τα καταχωρημένα δελτία χωρίς τιμολόγιο |
| `POST /api/docs` `{"doc_type", "customer_id" ή "supplier_id", "payment", "doc_date"}` ή `{"from_note", "doc_date"}` | νέο πρόχειρο· ή το πρόχειρο τιμολόγιο ενός δελτίου |
| `POST /api/docs/{id}/lines` `{"code", "qty", "price", "discount"}`, `.../lines/{line}` `{"qty", ...}` | γραμμή (σε πώληση, κάρτες με serials: οι παλαιότερες)· αλλαγή, με `qty` 0 σβήνει |
| `POST /api/docs/{id}/notes` `{"note_id"}` | κι άλλο δελτίο στο πρόχειρο τιμολόγιο |
| `POST /api/docs/{id}/post`, `.../cancel`, `.../delete`, `.../credit` | καταχώριση, ακύρωση, σβήσιμο πρόχειρου, επιστροφή (πρόχειρο δελτίο επιστροφής) |
| `GET /api/payments?kind=R\|P&q=`, `POST /api/payments` `{"kind", "partner_id", "amount", "method", "pay_date", "notes", "register"}`, `POST /api/payments/{id}/cancel` | εισπράξεις (R) και πληρωμές (P): η λίστα, νέα, ακύρωση |
| `GET /api/orders?status=O\|D\|C\|all&q=`, `GET /api/orders/{id}` | **οι παραγγελίες** (από προεπιλογή οι ανοιχτές)· μία με τις γραμμές της: ποσότητα, τιμή, τι μαζεύτηκε (`picked`), διαθέσιμα |
| `POST /api/orders` `{"name", "phone", "pickup_date", "notes", "customer_id"}` | νέα παραγγελία· ποιος την έγραψε κρατιέται από το login |
| `POST /api/orders/{id}/lines` `{"code", "qty", "mode"}` | είδος με barcode ή κωδικό: `ADD` (προσθέτει, προεπιλογή) ή `SET` (ορίζει, 0 = βγαίνει) |
| `POST /api/orders/{id}/pick` `{"item_id", "qty"}`, `.../ready` `{"ready"}` | τι μαζεύτηκε από μια γραμμή· «έτοιμη» (όλα μαζεύτηκαν) ή όχι |
| `POST /api/orders/{id}/cancel` `{"register"}` | ακύρωση· αν έχει προκαταβολή, επιστρέφεται από αυτό το ταμείο |
| `POST /api/orders/{id}/note` | δελτίο αποστολής (με πίστωση) για παραγγελία πελάτη χονδρικής, καταχωρημένο (MANAGER) |
| `GET /api/orders/new` | οι online παραγγελίες που περιμένουν επιβεβαίωση: `count`, `last_id`, `last_name` (η ειδοποίηση των σελίδων) |
| `POST /api/orders/{id}/confirm` | online παραγγελία πελάτη (`source` = `O`): επιβεβαιώθηκε με τηλέφωνο (`confirmed_at`) |
| `POST /api/pos/{ταμείο}/pay` `{"payment": "CASH" ή "CARD", "given"}` | καταχώριση: ο αριθμός, το σύνολο και τα ρέστα στο `paid`. Αν τα χρήματα που δόθηκαν δεν φτάνουν, απαντά 400 και δεν καταχωρίζεται τίποτα |

**Η σελίδα των πελατών, χωρίς login** (`/shop/`, [ODIGIES_WEB.md](ODIGIES_WEB.md)):

| Endpoint | Τι |
|---|---|
| `GET /api/shop/info` | το όνομα του μαγαζιού (η πρώτη γραμμή της κεφαλίδας των αποδείξεων) |
| `GET /api/shop/categories` | οι κατηγορίες που έχουν είδη |
| `GET /api/shop/items?q=&category=&limit=&offset=` | `code`, `name`, `category`, `unit`, `price`, `available` (`Y`/`N`): μόνο ενεργά είδη με τιμή, χωρίς serial· όχι κόστος, όχι απόθεμα |
| `POST /api/shop/orders` `{"name", "phone", "notes", "lines": [{"code", "qty"}]}` | νέα παραγγελία για σήμερα: απαντά με τον κωδικό της (`token`, 48 χαρακτήρες) και την κατάστασή της. Έως 40 γραμμές, ποσότητα έως 99, 3 ανοιχτές ανά τηλέφωνο (`MM-188`), `MM_SHOP_ORDERS` αποστολές ανά διεύθυνση στα 10 λεπτά (429 `too_many`) |
| `GET /api/shop/orders/{token}` | `state`: `sent`, `confirmed`, `ready`, `delivered`, `cancelled`· οι γραμμές και το σύνολο |
| `POST /api/shop/orders/{token}/cancel` | ακύρωση από τον πελάτη, μόνο πριν από την επιβεβαίωση (`MM-188`) |

Παραδείγματα, από PowerShell:
```powershell
$t = (Invoke-RestMethod -Method Post http://127.0.0.1:8090/api/auth/login -ContentType 'application/json' `
      -Body (@{ username = 'chris'; password = (Read-Host 'Κωδικός') } | ConvertTo-Json)).token
Invoke-RestMethod http://127.0.0.1:8090/api/items?q=ψωμί -Headers @{ Authorization = "Bearer $t" }
```
Ο κωδικός ζητείται με το `Read-Host`, για να μη μείνει γραμμένος σε script ή στο ιστορικό.

Οι διευθύνσεις (με το token):
```
http://127.0.0.1:8090/api/items?q=ψωμί
http://127.0.0.1:8090/api/items/2000000000015
http://127.0.0.1:8090/api/ledger/customer/2?from=2026-01-01
http://127.0.0.1:8090/api/reports/vat?from=2026-10-01&to=2026-10-31
```

## myDATA της ΑΑΔΕ

Τα **τιμολόγια πώλησης** (TPY, TDA: τύπος **1.1**) και τα **πιστωτικά πώλησης** (PPY: **5.1** όταν το τιμολόγιο που πιστώνει έχει διαβιβαστεί, με το MARK του στο `correlatedInvoices`· αλλιώς **5.2**) διαβιβάζονται στο myDATA από το mm-api (`MyData.java`), όπως η τεκμηρίωση της ΑΑΔΕ για ERP (`docs/mydata`). Οι αποδείξεις λιανικής περνούν από τον φορολογικό μηχανισμό (ΦΗΜ) ή πάροχο, όχι από εδώ· τα δελτία και οι αγορές δεν διαβιβάζονται από το μαγαζί.

| Endpoint | Τι |
|---|---|
| `GET /api/docs/{id}/mydata` | `{"xml"}`: το XML που θα σταλεί (`InvoicesDoc`), ελεγμένο με τα XSD της ΑΑΔΕ (v1.0.12, `api/src/main/resources/mydata`) |
| `POST /api/docs/{id}/mydata` | διαβίβαση τώρα (`SendInvoices`): στο παραστατικό `mydata_state` `S` με `mydata_mark`, `mydata_uid`, `mydata_qr`, ή `E` με το `mydata_error` της ΑΑΔΕ |
| `POST /api/docs/{id}/mydata/cancel` | ακύρωση στην ΑΑΔΕ (`CancelInvoice` με το MARK: `mydata_cancel_mark`), μετά ακύρωση και εδώ |

**Τι μπαίνει στο XML:** εκδότης ο ΑΦΜ του μαγαζιού (`MYDATA_AFM`) και η εγκατάσταση (`MYDATA_BRANCH`, 0 η έδρα)· λήπτης ο ΑΦΜ του πελάτη (χωρίς επωνυμία: για ελληνικό ΑΦΜ τη βάζει η ΑΑΔΕ)· σειρά ο κωδικός του είδους (`TDA`), αριθμός ο αριθμός του· πληρωμή μετρητά 3, κάρτα 7, πίστωση 5· μία γραμμή για κάθε γραμμή του παραστατικού, με ΦΠΑ 24% 1, 13% 2, 6% 3, 0% 7 (με την αιτία εξαίρεσης `MYDATA_VAT_EXEMPTION`)· χαρακτηρισμός εσόδων `category1_1` (πώληση εμπορευμάτων) / `E3_561_001` (χονδρικές σε επιτηδευματίες). **Ο λογιστής** να επιβεβαιώσει τον χαρακτηρισμό και την αιτία εξαίρεσης.

**Οι ρυθμίσεις του μαγαζιού:** `db\SET_MYDATA.sql` (ΑΦΜ, εγκατάσταση, αυτόματη αποστολή `Y`/`N`, αιτία εξαίρεσης για 0%).

**Ο λογαριασμός στην ΑΑΔΕ** (όνομα χρήστη, subscription key): **ποτέ στο git**. Στο αρχείο `mydata.properties` στον φάκελο όπου τρέχει το mm-api (το service: `api\service\mydata.properties`), ή όπου δείχνει το `MM_MYDATA_CONFIG`:
```
url=https://mydataapidev.aade.gr
user=<όνομα χρήστη>
key=<subscription key>
```
Το `url` των δοκιμών είναι το προεπιλεγμένο· για τα πραγματικά: `https://mydatapi.aade.gr/myDATA`. Χωρίς το αρχείο δεν στέλνεται τίποτα: τα παραστατικά περιμένουν (`Q`), με το μήνυμα «Χωρίς λογαριασμό myDATA».

**Αυτόματα:** με `MYDATA_AUTO` = `Y`, ένα τιμολόγιο ή πιστωτικό πώλησης μπαίνει σε αναμονή μόλις καταχωρηθεί (και από τη φόρμα), και το mm-api στέλνει όσα περιμένουν κάθε λεπτό (`MM_MYDATA_EVERY` δευτερόλεπτα).

**Ακύρωση:** ένα διαβιβασμένο παραστατικό δεν ακυρώνεται εδώ πριν ακυρωθεί στην ΑΑΔΕ (MM-189): «Ακύρωση (και στο myDATA)».

## Λάθη

Ένα λάθος έρχεται ως JSON, `{"error": "...", "message": "..."}`:

| Κωδικός HTTP | Πότε |
|---|---|
| 400 | λάθος ημερομηνία ή αριθμός (`bad_date`, `bad_number`)· λάθος JSON (`bad_json`) ή πεδίο που λείπει (`missing`)· λάθος της βάσης `MM-1xx` με το ελληνικό μήνυμά του (π.χ. `MM-172` για λάθος διάστημα)· διαδρομή με `..` (`bad_path`) |
| 401 | χωρίς login (`auth_required`)· λάθος όνομα ή κωδικός (`MM-177`)· token που έληξε ή δεν ισχύει (`MM-179`) |
| 403 | ο ρόλος δεν φτάνει (`forbidden`) |
| 404 | δεν υπάρχει το είδος, το id ή το endpoint |
| 405 | οτιδήποτε άλλο εκτός από `GET` και `POST` |
| 413 | σώμα πάνω από 64 KB |
| 429 | πολλές online παραγγελίες από την ίδια διεύθυνση (`too_many`) |
| 423 | ο λογαριασμός κλειδώθηκε (`MM-178`) |
| 500 | άλλο λάθος της βάσης· τη λεπτομέρεια τη γράφει μόνο η κονσόλα της υπηρεσίας |

## Ρυθμίσεις (μεταβλητές περιβάλλοντος)

| Μεταβλητή | Προεπιλογή | Τι |
|---|---|---|
| `MM_API_BIND` | `127.0.0.1` | η διεύθυνση όπου ακούει |
| `MM_API_PORT` | `8090` | η θύρα |
| `MM_DB_URL` | `jdbc:oracle:thin:/@MM_DB` | η βάση (το alias του wallet) |
| `MM_TNS_ADMIN` | — | ο φάκελος του `tnsnames.ora` (το `run_api.ps1` βάζει τον φάκελο του domain) |
| `MM_WALLET` | `MM_TNS_ADMIN\forms_wallet` | ο φάκελος του wallet |
| `MM_DB_USER`, `MM_DB_PASSWORD` | — | χωρίς wallet, μόνο για βάση δοκιμών (τα tests) |
| `MM_SHOP_ORDERS` | `10` | πόσες online παραγγελίες δέχεται από μία διεύθυνση στα 10 λεπτά |
| `MM_MYDATA_CONFIG` | `mydata.properties` | το αρχείο με τον λογαριασμό myDATA (url, user, key)· ποτέ στο git |
| `MM_MYDATA_EVERY` | `60` | κάθε πόσα δευτερόλεπτα στέλνονται όσα περιμένουν στο myDATA |
| `MM_API_CORS` | `http://localhost` | τα origins άλλων σελίδων που μπορούν να το καλούν (η εφαρμογή Android), με κόμματα· `none`: κανένα |

## Tests

Το `tests/test_api.py` ξεκινά το jar σε μια ελεύθερη θύρα, πάνω στη βάση του `MM_DSN`, και το ρωτά όπως ένας client. Ελέγχει:
- τα είδη, και ότι βρίσκονται με barcode ή κωδικό·
- ότι η καρτέλα κλείνει στο υπόλοιπο του πελάτη και στο απόθεμα του είδους·
- ότι τα reports συμφωνούν με τη βάση·
- τα λάθη, και ότι δέχεται μόνο `GET` και `POST`·
- το login, τους ρόλους (403), το logout·
- μια απογραφή από δύο «κινητά» ταμιών, που την καταχωρίζει ο προϊστάμενος.

Το `tests/test_auth.py` ελέγχει το `MM_AUTH` στη βάση:
- ότι ο κωδικός μένει μόνο ως PBKDF2, ίδιο με το `hashlib` της Python·
- τους κανόνες, και το κλείδωμα μετά από 5 λάθη·
- το τέλος των συνεδριών, και ότι μένει πάντα ένας διαχειριστής.

Αν δεν υπάρχει το jar, το χτίζει με `mvn`, αν υπάρχει.
