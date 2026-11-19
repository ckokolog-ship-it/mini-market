# Αναφορά της βάσης

Φτιάχνεται αυτόματα από τη βάση και τα σχόλια του κώδικα (`tools/mkdocs.py`). Μην την αλλάζεις με το χέρι: άλλαξε το σχόλιο στο `db/*.sql` και τρέξε ξανά το script. Πώς στήνεται η βάση: [ODIGIES_VASI.md](ODIGIES_VASI.md)· η αρχιτεκτονική: [ARXITEKTONIKI.md](ARXITEKTONIKI.md).

## Περιεχόμενα

- [Πίνακες](#πίνακες) (52)
- [Όψεις](#όψεις) (25)
- [Πακέτα](#πακέτα) (9)
- [Triggers](#triggers) (20)
- [Είδη παραστατικών](#είδη-παραστατικών)
- [Λάθη MM-1xx](#λάθη-mm-1xx)

## Πίνακες

| Πίνακας | Τι κρατά |
|---|---|
| [`MM_AUDIT_LOG`](#mm_audit_log) | Το ιστορικό ενεργειών: πότε, ποιος, από πού (σελίδες, φόρμες, SQL), τι, σε τι, λεπτομέρειες «από → σε». Το γράφουν triggers. |
| [`MM_AUTH_LOG`](#mm_auth_log) | Οι συνδέσεις και οι αλλαγές των χρηστών: σύνδεση, λάθος κωδικός, κλείδωμα, αποσύνδεση, νέος χρήστης, κωδικός, ρόλος. Ποτέ ο ίδιος ο κωδικός. |
| [`MM_CASH_MOVE`](#mm_cash_move) | Οι κινήσεις χρημάτων ενός ταμείου μέσα σε ένα Ζ: αρχικό ταμείο, πωλήσεις, επιστροφές, προκαταβολές, μετρητά μέσα και έξω. |
| [`MM_CATEGORY`](#mm_category) | Οι κατηγορίες των ειδών. |
| [`MM_COLOR`](#mm_color) | Τα χρώματα των παραλλαγών (ρούχα, παπούτσια). |
| [`MM_COUNT`](#mm_count) | Οι απογραφές: μία αποθήκη, ανοιχτή, καταχωρημένη ή ακυρωμένη. Τα κινητά σαρώνουν, το γραφείο καταχωρίζει τις διαφορές στο απόθεμα. |
| [`MM_COUNT_LINE`](#mm_count_line) | Οι γραμμές μιας απογραφής: είδος, πόσα μετρήθηκαν, πόσα είχε το σύστημα στην πρώτη σάρωση, από ποια συσκευή. |
| [`MM_CUSTOMER`](#mm_customer) | Οι πελάτες: επωνυμία, ΑΦΜ (με έλεγχο ψηφίου), ΔΟΥ, στοιχεία επικοινωνίας, κάρτα και πόντοι. |
| [`MM_DOC`](#mm_doc) | Τα παραστατικά: πρόχειρο (D), καταχωρημένο (P) με αριθμό και κινήσεις αποθήκης, ακυρωμένο (C). Πελάτης ή προμηθευτής, ταμείο και Ζ, αποθήκη (και αποθήκη παραλαβής της ενδοδιακίνησης), σύνολα, myDATA, ποιος το έφτιαξε και ποιος το καταχώρισε. |
| [`MM_DOC_LINE`](#mm_doc_line) | Οι γραμμές των παραστατικών: είδος, ποσότητα, τιμή, εκπτώσεις, ΦΠΑ, σύνολα, ημερομηνία λήξης (στην παραλαβή). |
| [`MM_DOC_LINE_OPTION`](#mm_doc_line_option) | Οι επιλογές κάθε γραμμής, με το όνομα και την τιμή τους εκείνη τη στιγμή. |
| [`MM_DOC_TYPE`](#mm_doc_type) | Τα είδη παραστατικών: πώληση, αγορά ή εσωτερικό, τι κάνουν στο απόθεμα, στο υπόλοιπο και στον ΦΠΑ, ο επόμενος αριθμός, ο τύπος του myDATA. |
| [`MM_FIFO`](#mm_fifo) | Οι στρώσεις FIFO: κάθε είσοδος στο απόθεμα μιας αποθήκης, με το κόστος της, πόσα μένουν και την ημερομηνία λήξης της. |
| [`MM_FIFO_OUT`](#mm_fifo_out) | Τι πήρε κάθε έξοδος από κάθε στρώση FIFO, και με ποιο κόστος. Από εδώ βγαίνει το κόστος των πωλήσεων. |
| [`MM_GRANT`](#mm_grant) | Τα δικαιώματα: τι επιτρέπει ένας ρόλος σε μια οθόνη, ένα πεδίο ή μια ενέργεια (N, R, W). |
| [`MM_ITEM`](#mm_item) | Τα είδη: κωδικός, barcode, περιγραφή, κατηγορία, ΦΠΑ, μονάδα, τιμή λιανικής και χονδρικής, κόστος, απόθεμα, ελάχιστο, serials, σετ, παραλλαγές, όριο ανά πώληση. |
| [`MM_ITEM_MONTH`](#mm_item_month) | Τα σύνολα κάθε μήνα ανά είδος (είσοδοι και έξοδοι): οι καρτέλες παίρνουν από εδώ το «από μεταφορά». Τα κρατούν triggers. |
| [`MM_ITEM_OPTION`](#mm_item_option) | Ποιες ομάδες επιλογών έχει κάθε είδος. |
| [`MM_KIT_COMPONENT`](#mm_kit_component) | Η σύνθεση ενός καλαθιού ή σετ: ποια είδη και πόσα από το καθένα. |
| [`MM_LEDGER_ROW`](#mm_ledger_row) | Προσωρινές γραμμές για τα reports των καρτελών (μέσα στη συναλλαγή που τις τυπώνει). |
| [`MM_OBJECT`](#mm_object) | Το μενού: ομάδες και οθόνες, με σελίδα web και/ή φόρμα, όνομα, σειρά, ενεργό. |
| [`MM_OBJECT_ITEM`](#mm_object_item) | Τα πεδία και οι ενέργειες κάθε οθόνης, για τα δικαιώματα. |
| [`MM_OPTION`](#mm_option) | Οι επιλογές μιας ομάδας: όνομα, έξτρα τιμή με ΦΠΑ, προεπιλογή, σειρά. |
| [`MM_OPTION_GROUP`](#mm_option_group) | Οι ομάδες επιλογών του ταμείου (ζάχαρη, γάλα, έξτρα): μία ή όσες θέλεις, υποχρεωτική, σειρά. |
| [`MM_PARTNER_MONTH`](#mm_partner_month) | Τα σύνολα κάθε μήνα ανά πελάτη και προμηθευτή (χρέωση και πίστωση). Τα κρατούν triggers. |
| [`MM_PAYMENT`](#mm_payment) | Οι εισπράξεις από πελάτες και οι πληρωμές σε προμηθευτές· με ταμείο, και κίνηση στο Ζ του. |
| [`MM_PIN_LOG`](#mm_pin_log) | Κάθε φορά που φάνηκε το PIN μιας κάρτας κινητής: ποιος, πότε, ποια κάρτα. |
| [`MM_PIN_USER`](#mm_pin_user) | Οι χρήστες που επιτρέπεται να βλέπουν τα PIN. |
| [`MM_POINTS`](#mm_points) | Οι πόντοι των πελατών: όσοι κερδίζονται με κάθε απόδειξη και όσοι χρησιμοποιούνται ως έκπτωση. |
| [`MM_PROMO`](#mm_promo) | Οι προσφορές: έκπτωση %, N+M δώρο, πακέτο σε τιμή, έκπτωση στο σύνολο, με διάστημα και ενεργό. |
| [`MM_PROMO_ITEM`](#mm_promo_item) | Σε ποια είδη ή κατηγορίες ισχύει κάθε προσφορά. |
| [`MM_REGISTER`](#mm_register) | Τα ταμεία: κωδικός, όνομα, αποθήκη από την οποία πουλούν. |
| [`MM_RESERVATION`](#mm_reservation) | Οι κρατήσεις και οι online παραγγελίες: όνομα, τηλέφωνο, ημέρα παραλαβής, προκαταβολή, κατάσταση. |
| [`MM_RESERVATION_LINE`](#mm_reservation_line) | Οι γραμμές μιας κράτησης: είδος, ποσότητα, τιμή, πόσα μαζεύτηκαν. |
| [`MM_ROLE`](#mm_role) | Οι ρόλοι: του συστήματος (ταμίας, προϊστάμενος, διαχειριστής) και του μαγαζιού. |
| [`MM_SCRATCH_GAME`](#mm_scratch_game) | Οι εκδόσεις των σκρατς: το είδος με το οποίο πουλιούνται και πόσα δελτία έχει ένα πακέτο. |
| [`MM_SECRET`](#mm_secret) | Το κλειδί κρυπτογράφησης των PIN (το φτιάχνει το MM_PIN την πρώτη φορά). |
| [`MM_SERIAL`](#mm_serial) | Τα serials: κάρτες κινητής (με PIN κρυπτογραφημένο), δελτία σκρατς. Νέο, διαθέσιμο, δεσμευμένο, πουλημένο, άκυρο. |
| [`MM_SESSION`](#mm_session) | Οι συνδέσεις του REST: μόνο το SHA-256 του token, ο χρήστης, η λήξη. |
| [`MM_SETTING`](#mm_setting) | Οι ρυθμίσεις του μαγαζιού: διεύθυνση των reports, myDATA, ημέρες λήξεων, πόντοι, μέθοδος κόστους, backup, κεφαλίδα απόδειξης. |
| [`MM_SIZE`](#mm_size) | Τα μεγέθη των παραλλαγών, με τη σειρά τους. |
| [`MM_STOCK_MOVE`](#mm_stock_move) | Οι κινήσεις αποθήκης: κάθε αλλαγή του αποθέματος, ανά αποθήκη (παραστατικό, διόρθωση, απογραφή, συναρμολόγηση). |
| [`MM_SUPPLIER`](#mm_supplier) | Οι προμηθευτές, με τα ίδια στοιχεία με τους πελάτες. |
| [`MM_TILE`](#mm_tile) | Τα κουμπιά του ταμείου: ένα είδος σε μια ομάδα, με τη σειρά του. |
| [`MM_TILE_GROUP`](#mm_tile_group) | Οι ομάδες κουμπιών του ταμείου (καφέ): όνομα, χρώμα, σειρά, ενεργή. |
| [`MM_USER`](#mm_user) | Οι χρήστες: όνομα, ρόλος του επιπέδου, κωδικός (μόνο PBKDF2), ενεργός, κλείδωμα, κατάστημα και ταμείο. |
| [`MM_USER_ROLE`](#mm_user_role) | Οι ρόλοι κάθε χρήστη (πολλοί: το περισσότερο του καθενός). |
| [`MM_VAT`](#mm_vat) | Οι συντελεστές ΦΠΑ. |
| [`MM_WAREHOUSE`](#mm_warehouse) | Οι αποθήκες: η κεντρική και τα υποκαταστήματα. |
| [`MM_WAREHOUSE_MIN`](#mm_warehouse_min) | Το ελάχιστο απόθεμα κάθε είδους σε κάθε υποκατάστημα. |
| [`MM_Z`](#mm_z) | Τα Ζ των ταμείων: ανοιχτό ή κλειστό, με τα σύνολά τους. |
| [`MM_Z_VAT`](#mm_z_vat) | Τα σύνολα ΦΠΑ ενός κλειστού Ζ, ανά συντελεστή. |

### MM_AUDIT_LOG

Το ιστορικό ενεργειών: πότε, ποιος, από πού (σελίδες, φόρμες, SQL), τι, σε τι, λεπτομέρειες «από → σε». Το γράφουν triggers.

> the history of what was done (MM_AUDIT_LOG; MM_AUDIT.sql: by triggers on the tables, whatever did it: the pages, the forms, SQL): when, who (CLIENT_IDENTIFIER: the user of the pages or the forms; none: the user of the database), from where (MODULE: mm-api, the forms, SQL*Plus), what (ACTION), of what (REF_TYPE, REF_ID, REF_TEXT), detail

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `at` | TIMESTAMP(6) | όχι | systimestamp |  |  |
| `username` | VARCHAR2(64) | ναι |  |  |  |
| `source` | VARCHAR2(64) | ναι |  |  |  |
| `action` | VARCHAR2(30) | όχι |  |  |  |
| `ref_type` | VARCHAR2(20) | ναι |  |  |  |
| `ref_id` | NUMBER | ναι |  |  |  |
| `ref_text` | VARCHAR2(100) | ναι |  |  |  |
| `detail` | VARCHAR2(1000) | ναι |  |  |  |

### MM_AUTH_LOG

Οι συνδέσεις και οι αλλαγές των χρηστών: σύνδεση, λάθος κωδικός, κλείδωμα, αποσύνδεση, νέος χρήστης, κωδικός, ρόλος. Ποτέ ο ίδιος ο κωδικός.

> what happened: LOGIN, FAIL, LOCKED, LOGOUT, CREATE, PASSWORD, ROLE, ACTIVE (never a password)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `at` | DATE | όχι | sysdate |  |  |
| `username` | VARCHAR2(30) | ναι |  |  |  |
| `event` | VARCHAR2(10) | όχι |  |  |  |
| `client` | VARCHAR2(60) | ναι |  |  |  |

### MM_CASH_MOVE

Οι κινήσεις χρημάτων ενός ταμείου μέσα σε ένα Ζ: αρχικό ταμείο, πωλήσεις, επιστροφές, προκαταβολές, μετρητά μέσα και έξω.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `register_id` | NUMBER | όχι |  | FK → [`MM_REGISTER`](#mm_register) |  |
| `z_id` | NUMBER | όχι |  | FK → [`MM_Z`](#mm_z) |  |
| `move_at` | DATE | όχι | sysdate |  |  |
| `kind` | VARCHAR2(10) | όχι |  |  |  |
| `payment` | VARCHAR2(6) | όχι | 'CASH' |  |  |
| `amount` | NUMBER(12,2) | όχι |  |  |  |
| `doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `note` | VARCHAR2(200) | ναι |  |  |  |
| `reservation_id` | NUMBER | ναι |  | FK → [`MM_RESERVATION`](#mm_reservation) |  |
| `payment_id` | NUMBER | ναι |  | FK → [`MM_PAYMENT`](#mm_payment) |  |

- έλεγχος: `kind in ('OPEN', 'IN', 'OUT', 'SALE', 'REFUND', 'DEPOSIT')`
- έλεγχος: `payment in ('CASH', 'CARD')`

### MM_CATEGORY

Οι κατηγορίες των ειδών.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(60) | όχι |  |  |  |

- μοναδικό: `name`

### MM_COLOR

Τα χρώματα των παραλλαγών (ρούχα, παπούτσια).

> clothes and shoes: a model (MM_ITEM.IS_MODEL = 'Y': not sold, no stock) and its variants, each an item of its own (its code, barcode, stock) with PARENT_ID the model, a colour and/or a size

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `code` | VARCHAR2(10) | όχι |  |  |  |
| `name` | VARCHAR2(40) | όχι |  |  |  |

- μοναδικό: `code`

### MM_COUNT

Οι απογραφές: μία αποθήκη, ανοιχτή, καταχωρημένη ή ακυρωμένη. Τα κινητά σαρώνουν, το γραφείο καταχωρίζει τις διαφορές στο απόθεμα.

> the counts of the stock (stocktaking): phones scan the shelves, the office posts the count. SYSTEM_QTY: the stock when the item was first scanned; at the post the difference COUNTED_QTY - SYSTEM_QTY becomes a move ADJ (what was sold after the scan stays sold).

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(60) | όχι |  |  |  |
| `status` | VARCHAR2(1) | όχι | 'O' |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |
| `posted_at` | DATE | ναι |  |  |  |
| `notes` | VARCHAR2(400) | ναι |  |  |  |
| `warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) | a count of the stock is of one warehouse (what it finds, a move there) |

- έλεγχος: `(status = 'P' and posted_at is not null) or (status <> 'P' and posted_at is null)`
- έλεγχος: `status in ('O', 'P', 'C')`

### MM_COUNT_LINE

Οι γραμμές μιας απογραφής: είδος, πόσα μετρήθηκαν, πόσα είχε το σύστημα στην πρώτη σάρωση, από ποια συσκευή.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `count_id` | NUMBER | όχι |  | FK → [`MM_COUNT`](#mm_count) (on delete cascade) |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `counted_qty` | NUMBER(12,3) | όχι |  |  |  |
| `system_qty` | NUMBER(12,3) | όχι |  |  |  |
| `scanned_at` | DATE | όχι | sysdate |  |  |
| `device` | VARCHAR2(40) | ναι |  |  |  |

- μοναδικό: `count_id, item_id`
- έλεγχος: `counted_qty >= 0`

### MM_CUSTOMER

Οι πελάτες: επωνυμία, ΑΦΜ (με έλεγχο ψηφίου), ΔΟΥ, στοιχεία επικοινωνίας, κάρτα και πόντοι.

> customers and suppliers: the same shape. AFM: the Greek tax number, nine digits (its check digit: MM_CORE.AFM_OK, step 2)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `afm` | VARCHAR2(9) | ναι |  |  |  |
| `doy` | VARCHAR2(60) | ναι |  |  |  |
| `address` | VARCHAR2(120) | ναι |  |  |  |
| `phone` | VARCHAR2(20) | ναι |  |  |  |
| `email` | VARCHAR2(100) | ναι |  |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |
| `card` | VARCHAR2(20) | ναι |  |  |  |
| `points` | NUMBER(10) | όχι | 0 |  |  |

- μοναδικό: `afm`
- μοναδικό: `card`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `regexp_like(afm, '^[0-9]{9}$')`
- έλεγχος: `email like '_%@_%._%'`

### MM_DOC

Τα παραστατικά: πρόχειρο (D), καταχωρημένο (P) με αριθμό και κινήσεις αποθήκης, ακυρωμένο (C). Πελάτης ή προμηθευτής, ταμείο και Ζ, αποθήκη (και αποθήκη παραλαβής της ενδοδιακίνησης), σύνολα, myDATA, ποιος το έφτιαξε και ποιος το καταχώρισε.

> the documents: D draft (no number yet, can change), P posted (numbered, stock moved), C cancelled

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `doc_type` | VARCHAR2(3) | όχι |  | FK → [`MM_DOC_TYPE`](#mm_doc_type) |  |
| `doc_no` | NUMBER(10) | ναι |  |  |  |
| `doc_date` | DATE | όχι | trunc(sysdate) |  |  |
| `customer_id` | NUMBER | ναι |  | FK → [`MM_CUSTOMER`](#mm_customer) |  |
| `supplier_id` | NUMBER | ναι |  | FK → [`MM_SUPPLIER`](#mm_supplier) |  |
| `register_id` | NUMBER | ναι |  | FK → [`MM_REGISTER`](#mm_register) |  |
| `z_id` | NUMBER | ναι |  | FK → [`MM_Z`](#mm_z) |  |
| `status` | VARCHAR2(1) | όχι | 'D' |  |  |
| `payment` | VARCHAR2(6) | όχι | 'CASH' |  |  |
| `net` | NUMBER(12,2) | όχι | 0 |  |  |
| `vat` | NUMBER(12,2) | όχι | 0 |  |  |
| `total` | NUMBER(12,2) | όχι | 0 |  |  |
| `ref_doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) | a credit note: the invoice it credits |
| `notes` | VARCHAR2(400) | ναι |  |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |
| `deposit` | NUMBER(12,2) | όχι | 0 |  |  |
| `invoice_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `mydata_state` | VARCHAR2(1) | ναι |  |  |  |
| `mydata_mark` | NUMBER(20) | ναι |  |  |  |
| `mydata_uid` | VARCHAR2(40) | ναι |  |  |  |
| `mydata_qr` | VARCHAR2(1000) | ναι |  |  |  |
| `mydata_error` | VARCHAR2(1000) | ναι |  |  |  |
| `mydata_at` | DATE | ναι |  |  |  |
| `mydata_cancel_mark` | NUMBER(20) | ναι |  |  |  |
| `points_used` | NUMBER(10) | όχι | 0 |  |  |
| `disc_pct` | NUMBER(5,2) | όχι | 0 |  |  |
| `disc_amount` | NUMBER(12,2) | όχι | 0 |  |  |
| `disc_reason` | VARCHAR2(100) | ναι |  |  |  |
| `created_by` | VARCHAR2(64) | ναι |  |  |  |
| `posted_by` | VARCHAR2(64) | ναι |  |  |  |
| `warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) |  |
| `to_warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) | a transfer between two warehouses (Δελτίο ενδοδιακίνησης, DEN: side T): the warehouse it goes to |
| `reason` | VARCHAR2(10) | ναι |  |  | a consumption (DAN): why the goods went out: USE (used by the shop), DAMAGE, SAMPLE, EXPIRED |
| `ticket_no` | NUMBER(5) | ναι |  |  |  |

- έλεγχος: `deposit >= 0`
- έλεγχος: `disc_amount >= 0`
- έλεγχος: `disc_pct between 0 and 100`
- έλεγχος: `mydata_state in ('Q', 'S', 'E', 'X')`
- έλεγχος: `status = 'D' or doc_no is not null`
- έλεγχος: `customer_id is null or supplier_id is null`
- έλεγχος: `payment in ('CASH', 'CARD', 'CREDIT')`
- έλεγχος: `points_used >= 0`
- έλεγχος: `reason in ('USE', 'DAMAGE', 'SAMPLE', 'EXPIRED')`
- έλεγχος: `status in ('D', 'P', 'C')`
- έλεγχος: `total = net + vat`

### MM_DOC_LINE

Οι γραμμές των παραστατικών: είδος, ποσότητα, τιμή, εκπτώσεις, ΦΠΑ, σύνολα, ημερομηνία λήξης (στην παραλαβή).

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `doc_id` | NUMBER | όχι |  | FK → [`MM_DOC`](#mm_doc) (on delete cascade) |  |
| `line_no` | NUMBER(5) | όχι |  |  |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `qty` | NUMBER(12,3) | όχι |  |  |  |
| `price` | NUMBER(12,4) | όχι |  |  |  |
| `discount` | NUMBER(5,2) | όχι | 0 |  |  |
| `vat_code` | VARCHAR2(1) | όχι |  | FK → [`MM_VAT`](#mm_vat) |  |
| `vat_rate` | NUMBER(5,2) | όχι |  |  | the rate on the day of the document |
| `net` | NUMBER(12,2) | όχι | 0 |  |  |
| `vat` | NUMBER(12,2) | όχι | 0 |  |  |
| `total` | NUMBER(12,2) | όχι | 0 |  |  |
| `expires` | DATE | ναι |  |  | the points of the retail customers (κάρτα πελάτη, mm_core.post_doc): the card (its barcode, EAN-13 2990...) and the points now; a receipt: the points it used (as its discount) the date a line of goods received expires (a delivery note or an invoice of purchase that brings stock: DPA, TAD; mm_core.set_expiry); what is left of each: MM_EXPIRY (MM_REPORT.sql) |
| `promo_id` | NUMBER | ναι |  | FK → [`MM_PROMO`](#mm_promo) (on delete set null) |  |
| `promo_disc` | NUMBER(12,2) | όχι | 0 |  |  |
| `doc_disc` | NUMBER(12,2) | όχι | 0 |  |  |
| `options` | VARCHAR2(400) | ναι |  |  |  |

- μοναδικό: `doc_id, line_no`
- έλεγχος: `discount between 0 and 100`
- έλεγχος: `price >= 0`
- έλεγχος: `qty > 0`
- έλεγχος: `total = net + vat`

### MM_DOC_LINE_OPTION

Οι επιλογές κάθε γραμμής, με το όνομα και την τιμή τους εκείνη τη στιγμή.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `line_id` | NUMBER | όχι |  | PK FK → [`MM_DOC_LINE`](#mm_doc_line) (on delete cascade) |  |
| `option_id` | NUMBER | όχι |  | PK FK → [`MM_OPTION`](#mm_option) |  |
| `name` | VARCHAR2(40) | όχι |  |  |  |
| `price` | NUMBER(8,2) | όχι |  |  |  |

### MM_DOC_TYPE

Τα είδη παραστατικών: πώληση, αγορά ή εσωτερικό, τι κάνουν στο απόθεμα, στο υπόλοιπο και στον ΦΠΑ, ο επόμενος αριθμός, ο τύπος του myDATA.

> the kinds of documents: sale (S) or purchase (P), what they do to the stock (-1, 0, +1), their next number

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `code` | VARCHAR2(3) | όχι |  | PK |  |
| `name` | VARCHAR2(60) | όχι |  |  |  |
| `side` | VARCHAR2(1) | όχι |  |  |  |
| `stock_sign` | NUMBER(1) | όχι |  |  |  |
| `prices_incl_vat` | VARCHAR2(1) | όχι |  |  |  |
| `partner_needed` | VARCHAR2(1) | όχι |  |  |  |
| `next_no` | NUMBER(10) | όχι | 1 |  |  |
| `partner_sign` | NUMBER(1) | όχι | 0 |  | what a kind of document does (MM_BASE.sql): to the stock (STOCK_SIGN, above), to the balance of the customer or the supplier (PARTNER_SIGN: + an invoice, - a credit note, 0 a delivery note), to the VAT (VAT_SIGN: + an invoice or a receipt, - a credit note, 0 a delivery note); REF_TYPE: the kind of delivery note an invoice is made from (MM_CORE.INVOICE_FROM, ADD_NOTE). A delivery note, its invoice. |
| `vat_sign` | NUMBER(1) | όχι | 0 |  |  |
| `ref_type` | VARCHAR2(3) | ναι |  |  |  |
| `mydata_type` | VARCHAR2(5) | ναι |  |  | myDATA of AADE (the invoices and the credit notes of the sales, mm-api MyData.java): the kind of each document there (1.1, 5.1 ...); a document: its state (Q to be sent, S sent, E failed, X its cancellation sent), its MARK, UID and QR from AADE, the error of the last try |

- έλεγχος: `prices_incl_vat in ('Y', 'N')`
- έλεγχος: `next_no >= 1`
- έλεγχος: `partner_needed in ('Y', 'N')`
- έλεγχος: `partner_sign in (-1, 0, 1)`
- έλεγχος: `side in ('S', 'P', 'T')`
- έλεγχος: `stock_sign in (-1, 0, 1)`
- έλεγχος: `vat_sign in (-1, 0, 1)`

### MM_FIFO

Οι στρώσεις FIFO: κάθε είσοδος στο απόθεμα μιας αποθήκης, με το κόστος της, πόσα μένουν και την ημερομηνία λήξης της.

> FIFO (first in, first out): each move into the stock is a layer with its own cost (a receipt from a supplier: the net of its line by piece; any other: that of the newest layer of the item, else the cost of the item); each move out takes from the oldest layers first, at their costs (MM_FIFO_OUT: what each move took, and its cost). A move out with no stock left: a layer of shortage (QTY 0, LEFT_ below 0, at the cost of the newest), filled by the next move in. A cancellation (a move 'Ακύρωση' of a document) gives back to the layers what its line took (a sale), or takes out what is left of the layer it brought (a receipt). All of it can be built again from MM_STOCK_MOVE (mm_core.fifo_rebuild); MM_CHECK: LEFT_ adds up to STOCK

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `move_id` | NUMBER | ναι |  |  | the move that brought it (MM_STOCK_MOVE) |
| `doc_line_id` | NUMBER | ναι |  |  | and its line, if of a document |
| `in_at` | DATE | όχι |  |  |  |
| `qty` | NUMBER(12,3) | όχι |  |  |  |
| `unit_cost` | NUMBER(12,4) | όχι |  |  |  |
| `left_` | NUMBER(12,3) | όχι |  |  |  |
| `warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) |  |
| `expires` | DATE | ναι |  |  | the expiry of a layer: of the line of the receipt that brought it; a transfer: of the layer it came from |

### MM_FIFO_OUT

Τι πήρε κάθε έξοδος από κάθε στρώση FIFO, και με ποιο κόστος. Από εδώ βγαίνει το κόστος των πωλήσεων.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `fifo_id` | NUMBER | όχι |  | FK → [`MM_FIFO`](#mm_fifo) |  |
| `move_id` | NUMBER | όχι |  |  | the move that took it (a cancellation: given back, below 0) |
| `doc_line_id` | NUMBER | ναι |  |  |  |
| `qty` | NUMBER(12,3) | όχι |  |  |  |
| `cost` | NUMBER(14,4) | όχι |  |  |  |

### MM_GRANT

Τα δικαιώματα: τι επιτρέπει ένας ρόλος σε μια οθόνη, ένα πεδίο ή μια ενέργεια (N, R, W).

> what a role may do: with a screen (item null), with a field or an action of it. No row: a screen N; a field as its screen; an action allowed when its screen is W

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `role_id` | NUMBER | όχι |  | FK → [`MM_ROLE`](#mm_role) (on delete cascade) |  |
| `object_id` | NUMBER | όχι |  | FK → [`MM_OBJECT`](#mm_object) (on delete cascade) |  |
| `item_id` | NUMBER | ναι |  | FK → [`MM_OBJECT_ITEM`](#mm_object_item) (on delete cascade) |  |
| `lvl` | VARCHAR2(1) | όχι |  |  |  |

- έλεγχος: `lvl in ('N', 'R', 'W')`

### MM_ITEM

Τα είδη: κωδικός, barcode, περιγραφή, κατηγορία, ΦΠΑ, μονάδα, τιμή λιανικής και χονδρικής, κόστος, απόθεμα, ελάχιστο, serials, σετ, παραλλαγές, όριο ανά πώληση.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `code` | VARCHAR2(20) | όχι |  |  |  |
| `barcode` | VARCHAR2(14) | ναι |  |  |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `category_id` | NUMBER | όχι |  | FK → [`MM_CATEGORY`](#mm_category) |  |
| `vat_code` | VARCHAR2(1) | όχι |  | FK → [`MM_VAT`](#mm_vat) |  |
| `unit` | VARCHAR2(3) | όχι | 'PCS' |  |  |
| `price` | NUMBER(12,2) | όχι |  |  | retail, with VAT |
| `cost` | NUMBER(12,4) | όχι | 0 |  | last purchase, net |
| `min_stock` | NUMBER(12,3) | όχι | 0 |  |  |
| `stock` | NUMBER(12,3) | όχι | 0 |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |
| `serial_tracked` | VARCHAR2(1) | όχι | 'N' |  |  |
| `kit` | VARCHAR2(1) | όχι | 'N' |  |  |
| `max_per_sale` | NUMBER(12,3) | ναι |  |  |  |
| `is_model` | VARCHAR2(1) | όχι | 'N' |  |  |
| `parent_id` | NUMBER | ναι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `color_id` | NUMBER | ναι |  | FK → [`MM_COLOR`](#mm_color) |  |
| `size_id` | NUMBER | ναι |  | FK → [`MM_SIZE`](#mm_size) |  |
| `wholesale_price` | NUMBER(12,4) | ναι |  |  |  |
| `plu` | NUMBER(5) | ναι |  |  |  |

- μοναδικό: `barcode`
- μοναδικό: `code`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `regexp_like(barcode, '^([0-9]{8}|[0-9]{12,14})$')`
- έλεγχος: `cost >= 0`
- έλεγχος: `kit in ('Y', 'N')`
- έλεγχος: `max_per_sale > 0`
- έλεγχος: `min_stock >= 0`
- έλεγχος: `is_model in ('Y', 'N')`
- έλεγχος: `plu between 1 and 99999`
- έλεγχος: `price >= 0`
- έλεγχος: `serial_tracked in ('Y', 'N')`
- έλεγχος: `unit in ('PCS', 'KG', 'L')`
- έλεγχος: `parent_id is null or color_id is not null or size_id is not null`
- έλεγχος: `wholesale_price >= 0`

### MM_ITEM_MONTH

Τα σύνολα κάθε μήνα ανά είδος (είσοδοι και έξοδοι): οι καρτέλες παίρνουν από εδώ το «από μεταφορά». Τα κρατούν triggers.

> the totals of each month (MM_MONTHS.sql: kept by triggers): the ledgers take what was before a period from them, not from every move since the first one. MM_ITEM_MONTH: the stock in and out of an item in a month (from MM_STOCK_MOVE). Reservable, as MM_ITEM.STOCK: two tills that sell the same item do not wait for each other.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `item_id` | NUMBER | όχι |  | PK FK → [`MM_ITEM`](#mm_item) |  |
| `month` | DATE | όχι |  | PK |  |
| `qty_in` | NUMBER(14,3) | όχι | 0 |  |  |
| `qty_out` | NUMBER(14,3) | όχι | 0 |  |  |

- έλεγχος: `month = trunc(month, 'MM')`

### MM_ITEM_OPTION

Ποιες ομάδες επιλογών έχει κάθε είδος.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `item_id` | NUMBER | όχι |  | PK FK → [`MM_ITEM`](#mm_item) (on delete cascade) |  |
| `group_id` | NUMBER | όχι |  | PK FK → [`MM_OPTION_GROUP`](#mm_option_group) (on delete cascade) |  |

### MM_KIT_COMPONENT

Η σύνθεση ενός καλαθιού ή σετ: ποια είδη και πόσα από το καθένα.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `kit_id` | NUMBER | όχι |  | PK FK → [`MM_ITEM`](#mm_item) (on delete cascade) |  |
| `component_id` | NUMBER | όχι |  | PK FK → [`MM_ITEM`](#mm_item) |  |
| `qty` | NUMBER(12,3) | όχι |  |  |  |

- έλεγχος: `qty > 0`
- έλεγχος: `kit_id <> component_id`

### MM_LEDGER_ROW

Προσωρινές γραμμές για τα reports των καρτελών (μέσα στη συναλλαγή που τις τυπώνει).

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `seq` | NUMBER | όχι |  |  |  |
| `kind` | VARCHAR2(1) | όχι |  |  |  |
| `ldate` | DATE | ναι |  |  |  |
| `doc_id` | NUMBER | ναι |  |  |  |
| `doc_text` | VARCHAR2(40) | ναι |  |  |  |
| `partner` | VARCHAR2(100) | ναι |  |  |  |
| `descr` | VARCHAR2(200) | ναι |  |  |  |
| `debit` | NUMBER | ναι |  |  |  |
| `credit` | NUMBER | ναι |  |  |  |
| `balance` | NUMBER | ναι |  |  |  |

### MM_OBJECT

Το μενού: ομάδες και οθόνες, με σελίδα web και/ή φόρμα, όνομα, σειρά, ενεργό.

> a group of the menu (G) or a screen (S): its page (route, e.g. #/items) and/or its form (MM_ITEMS)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `code` | VARCHAR2(30) | όχι |  |  |  |
| `kind` | VARCHAR2(1) | όχι |  |  |  |
| `parent_id` | NUMBER | ναι |  | FK → [`MM_OBJECT`](#mm_object) |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `route` | VARCHAR2(100) | ναι |  |  |  |
| `form` | VARCHAR2(30) | ναι |  |  |  |
| `sort_no` | NUMBER(5) | όχι | 0 |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- μοναδικό: `code`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `regexp_like(code, '^[A-Z][A-Z0-9_]{1,29}$')`
- έλεγχος: `kind in ('G', 'S')`

### MM_OBJECT_ITEM

Τα πεδία και οι ενέργειες κάθε οθόνης, για τα δικαιώματα.

> a field (F: e.g. the cost of an item) or an action (A: e.g. post a document) of a screen

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `object_id` | NUMBER | όχι |  | FK → [`MM_OBJECT`](#mm_object) (on delete cascade) |  |
| `kind` | VARCHAR2(1) | όχι |  |  |  |
| `code` | VARCHAR2(30) | όχι |  |  |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `sort_no` | NUMBER(5) | όχι | 0 |  |  |

- μοναδικό: `object_id, code`
- έλεγχος: `regexp_like(code, '^[A-Z][A-Z0-9_]{1,29}$')`
- έλεγχος: `kind in ('F', 'A')`

### MM_OPTION

Οι επιλογές μιας ομάδας: όνομα, έξτρα τιμή με ΦΠΑ, προεπιλογή, σειρά.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `group_id` | NUMBER | όχι |  | FK → [`MM_OPTION_GROUP`](#mm_option_group) (on delete cascade) |  |
| `name` | VARCHAR2(40) | όχι |  |  |  |
| `price` | NUMBER(8,2) | όχι | 0 |  |  |
| `is_default` | VARCHAR2(1) | όχι | 'N' |  |  |
| `sort_no` | NUMBER | όχι | 0 |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `is_default in ('Y', 'N')`
- έλεγχος: `price >= 0`

### MM_OPTION_GROUP

Οι ομάδες επιλογών του ταμείου (ζάχαρη, γάλα, έξτρα): μία ή όσες θέλεις, υποχρεωτική, σειρά.

> the options of an item at the till (a cafe: sugar, milk, extras): groups of options, one of them (pick O, e.g. Ζάχαρη: σκέτος / μέτριος / γλυκός; required: a line has one, its default if none chosen) or any of them (M, e.g. Έξτρα: σφηνάκι, σιρόπι); an option may cost more (price, with VAT, added to the price of the line); the groups of each item (MM_ITEM_OPTION). A line keeps the options chosen (MM_DOC_LINE_OPTION: name and price as they were) and their text (MM_DOC_LINE.OPTIONS, for the screens and the prints)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(40) | όχι |  |  |  |
| `pick` | VARCHAR2(1) | όχι | 'O' |  |  |
| `required` | VARCHAR2(1) | όχι | 'N' |  |  |
| `sort_no` | NUMBER | όχι | 0 |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `pick = 'O' or required = 'N'`
- έλεγχος: `pick in ('O', 'M')`
- έλεγχος: `required in ('Y', 'N')`

### MM_PARTNER_MONTH

Τα σύνολα κάθε μήνα ανά πελάτη και προμηθευτή (χρέωση και πίστωση). Τα κρατούν triggers.

> MM_PARTNER_MONTH: the debit and the credit of a customer (C) or a supplier (S) in a month (from the posted documents and the receipts and payments: MM_PARTNER_EVENT)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `kind` | VARCHAR2(1) | όχι |  | PK |  |
| `partner_id` | NUMBER | όχι |  | PK |  |
| `month` | DATE | όχι |  | PK |  |
| `debit` | NUMBER(14,2) | όχι | 0 |  |  |
| `credit` | NUMBER(14,2) | όχι | 0 |  |  |

- έλεγχος: `month = trunc(month, 'MM')`
- έλεγχος: `kind in ('C', 'S')`

### MM_PAYMENT

Οι εισπράξεις από πελάτες και οι πληρωμές σε προμηθευτές· με ταμείο, και κίνηση στο Ζ του.

> receipts from customers (R) and payments to suppliers (P): what settles the invoices on credit. CASH or CARD with a register: also a move IN/OUT of its open Z (MM_CASH_MOVE.PAYMENT_ID)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `kind` | VARCHAR2(1) | όχι |  |  |  |
| `customer_id` | NUMBER | ναι |  | FK → [`MM_CUSTOMER`](#mm_customer) |  |
| `supplier_id` | NUMBER | ναι |  | FK → [`MM_SUPPLIER`](#mm_supplier) |  |
| `pay_date` | DATE | όχι | trunc(sysdate) |  |  |
| `amount` | NUMBER(12,2) | όχι |  |  |  |
| `method` | VARCHAR2(6) | όχι | 'CASH' |  |  |
| `register_id` | NUMBER | ναι |  | FK → [`MM_REGISTER`](#mm_register) |  |
| `status` | VARCHAR2(1) | όχι | 'P' |  |  |
| `notes` | VARCHAR2(400) | ναι |  |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |

- έλεγχος: `amount > 0`
- έλεγχος: `kind in ('R', 'P')`
- έλεγχος: `method in ('CASH', 'CARD', 'BANK')`
- έλεγχος: `(kind = 'R' and customer_id is not null and supplier_id is null) or (kind = 'P' and supplier_id is not null and customer_id is null)`
- έλεγχος: `status in ('P', 'C')`

### MM_PIN_LOG

Κάθε φορά που φάνηκε το PIN μιας κάρτας κινητής: ποιος, πότε, ποια κάρτα.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `serial_id` | NUMBER | όχι |  | FK → [`MM_SERIAL`](#mm_serial) |  |
| `username` | VARCHAR2(60) | όχι |  |  |  |
| `shown_at` | DATE | όχι | sysdate |  |  |
| `reason` | VARCHAR2(20) | όχι |  |  |  |

- έλεγχος: `reason in ('REVEAL', 'RECEIPT')`

### MM_PIN_USER

Οι χρήστες που επιτρέπεται να βλέπουν τα PIN.

> who may see the PINs (until the login of step 7a: the name given to REVEAL_PIN, or the CLIENT_IDENTIFIER of the session), and every time a PIN was shown

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `username` | VARCHAR2(60) | όχι |  | PK |  |

### MM_POINTS

Οι πόντοι των πελατών: όσοι κερδίζονται με κάθε απόδειξη και όσοι χρησιμοποιούνται ως έκπτωση.

> the points of the retail customers: each receipt with a customer (its card scanned at the till) gives POINTS_PER_EURO points for each euro of its total (MM_SETTING; 0: no points), its points used are taken (each worth POINT_VALUE euros, as the discount of the receipt); a receipt cancelled, its moves back. MM_CUSTOMER.POINTS is the sum of its moves (MM_CHECK)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `customer_id` | NUMBER | όχι |  | FK → [`MM_CUSTOMER`](#mm_customer) |  |
| `doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `points` | NUMBER(10) | όχι |  |  |  |
| `move_at` | DATE | όχι | sysdate |  |  |
| `note` | VARCHAR2(100) | ναι |  |  |  |

### MM_PROMO

Οι προσφορές: έκπτωση %, N+M δώρο, πακέτο σε τιμή, έκπτωση στο σύνολο, με διάστημα και ενεργό.

> promotions, applied by MM_CORE.REPRICE to every draft sale, at each change: PCT     PCT % off the items or the categories of MM_PROMO_ITEM NM      buy BUY_QTY, get FREE_QTY free (the cheapest pieces), any mix of its items and categories BUNDLE  the items of MM_PROMO_ITEM, each QTY of it, for BUNDLE_PRICE together A line takes one promotion at most: bundles first, then N+M, then the best PCT.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `kind` | VARCHAR2(6) | όχι |  |  |  |
| `date_from` | DATE | όχι |  |  |  |
| `date_to` | DATE | όχι |  |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |
| `pct` | NUMBER(5,2) | ναι |  |  |  |
| `buy_qty` | NUMBER(5) | ναι |  |  |  |
| `free_qty` | NUMBER(5) | ναι |  |  |  |
| `bundle_price` | NUMBER(12,2) | ναι |  |  |  |

- μοναδικό: `name`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `date_to >= date_from`
- έλεγχος: `kind in ('PCT', 'NM', 'BUNDLE')`
- έλεγχος: `(kind = 'PCT' and pct > 0 and pct <= 100) or (kind = 'NM' and buy_qty >= 1 and free_qty >= 1) or (kind = 'BUNDLE' and bundle_price >= 0)`

### MM_PROMO_ITEM

Σε ποια είδη ή κατηγορίες ισχύει κάθε προσφορά.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `promo_id` | NUMBER | όχι |  | FK → [`MM_PROMO`](#mm_promo) (on delete cascade) |  |
| `item_id` | NUMBER | ναι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `category_id` | NUMBER | ναι |  | FK → [`MM_CATEGORY`](#mm_category) |  |
| `qty` | NUMBER(12,3) | όχι | 1 |  |  |

- έλεγχος: `(item_id is null) <> (category_id is null)`
- έλεγχος: `qty > 0`

### MM_REGISTER

Τα ταμεία: κωδικός, όνομα, αποθήκη από την οποία πουλούν.

> the cash registers, their Z (one open at a time) and the money in and out

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `code` | VARCHAR2(10) | όχι |  |  |  |
| `name` | VARCHAR2(60) | όχι |  |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |
| `warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) |  |

- μοναδικό: `code`
- έλεγχος: `active in ('Y', 'N')`

### MM_RESERVATION

Οι κρατήσεις και οι online παραγγελίες: όνομα, τηλέφωνο, ημέρα παραλαβής, προκαταβολή, κατάσταση.

> reservations (e.g. New Year cakes): a name and a phone, the day of the pickup, lines with the price of the day of the reservation. STATUS: O open (its quantities reserved), D delivered (DOC_ID: the receipt), C cancelled. The stock does not change until the delivery; MM_ITEM_AVAIL shows stock - reserved. A deposit goes into the cash register (MM_CASH_MOVE kind DEPOSIT) on its day.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `phone` | VARCHAR2(20) | όχι |  |  |  |
| `customer_id` | NUMBER | ναι |  | FK → [`MM_CUSTOMER`](#mm_customer) |  |
| `pickup_date` | DATE | όχι |  |  |  |
| `status` | VARCHAR2(1) | όχι | 'O' |  |  |
| `deposit` | NUMBER(12,2) | όχι | 0 |  |  |
| `doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `notes` | VARCHAR2(400) | ναι |  |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |
| `created_by` | VARCHAR2(30) | ναι |  |  | the orders (a reservation from the pages): who wrote it, when it was ready (picked), what of each line was picked |
| `ready_at` | DATE | ναι |  |  |  |
| `source` | VARCHAR2(1) | όχι | 'S' |  | an order of a customer from the page of the shop (/shop/, the WiFi of the shop): SOURCE 'O' (online; 'S' the staff), the token of its page of status (not its number: not to be guessed), when the shop confirmed it (a call to the phone given) |
| `public_token` | VARCHAR2(64) | ναι |  |  |  |
| `confirmed_at` | DATE | ναι |  |  |  |

- μοναδικό: `public_token`
- έλεγχος: `deposit >= 0`
- έλεγχος: `status <> 'D' or doc_id is not null`
- έλεγχος: `regexp_like(phone, '^[0-9+ ]{5,20}$')`
- έλεγχος: `source in ('S', 'O')`
- έλεγχος: `status in ('O', 'D', 'C')`

### MM_RESERVATION_LINE

Οι γραμμές μιας κράτησης: είδος, ποσότητα, τιμή, πόσα μαζεύτηκαν.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `reservation_id` | NUMBER | όχι |  | FK → [`MM_RESERVATION`](#mm_reservation) (on delete cascade) |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `qty` | NUMBER(12,3) | όχι |  |  |  |
| `price` | NUMBER(12,4) | όχι |  |  | with VAT |
| `picked` | NUMBER(12,3) | όχι | 0 |  |  |

- μοναδικό: `reservation_id, item_id`
- έλεγχος: `picked >= 0`
- έλεγχος: `price >= 0`
- έλεγχος: `qty > 0`

### MM_ROLE

Οι ρόλοι: του συστήματος (ταμίας, προϊστάμενος, διαχειριστής) και του μαγαζιού.

> the rights (MM_RIGHTS.sql): roles; the users in them (more than one: their rights together); the screens (a page of the web and/or a form of Oracle Forms) in the groups of the menu; the fields and the actions of a screen; what a role may do with each: N none, R read, W write (an action: W allowed)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `code` | VARCHAR2(30) | όχι |  |  |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `all_rights` | VARCHAR2(1) | όχι | 'N' |  |  |
| `system` | VARCHAR2(1) | όχι | 'N' |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- μοναδικό: `code`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `all_rights in ('Y', 'N')`
- έλεγχος: `regexp_like(code, '^[A-Z][A-Z0-9_]{1,29}$')`
- έλεγχος: `system in ('Y', 'N')`

### MM_SCRATCH_GAME

Οι εκδόσεις των σκρατς: το είδος με το οποίο πουλιούνται και πόσα δελτία έχει ένα πακέτο.

> the scratch tickets (σκρατς): bought in packs (e.g. 300 of 1 €), sold one by one. The barcode of a ticket: its game (έκδοση, 4 digits), its pack (7) and its number in the pack (3): 14 digits, its serial (MM_SERIAL) as well, so a scan at the till sells that very ticket. A game: the item it is sold as (an item with serials, e.g. «Σκρατς 1 €») and how many tickets a pack has (mm_core.load_pack)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `game` | VARCHAR2(4) | όχι |  | PK |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `pack_size` | NUMBER(3) | όχι | 300 |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |

- έλεγχος: `regexp_like(game, '^[0-9]{4}$')`
- έλεγχος: `pack_size between 1 and 999`

### MM_SECRET

Το κλειδί κρυπτογράφησης των PIN (το φτιάχνει το MM_PIN την πρώτη φορά).

> the key of the PINs (MM_PIN makes it the first time); nothing else reads it

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `name` | VARCHAR2(30) | όχι |  | PK |  |
| `value` | RAW(64) | όχι |  |  |  |

### MM_SERIAL

Τα serials: κάρτες κινητής (με PIN κρυπτογραφημένο), δελτία σκρατς. Νέο, διαθέσιμο, δεσμευμένο, πουλημένο, άκυρο.

> STATUS: N new (on a draft purchase), A available, R reserved (on a draft sale), S sold, X void PIN_ENC: the PIN encrypted (MM_PIN, AES-256); it shows only through MM_CORE.REVEAL_PIN

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `serial` | VARCHAR2(40) | όχι |  |  |  |
| `pin_enc` | RAW(64) | ναι |  |  |  |
| `status` | VARCHAR2(1) | όχι | 'A' |  |  |
| `in_doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `in_line_id` | NUMBER | ναι |  | FK → [`MM_DOC_LINE`](#mm_doc_line) |  |
| `out_doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `out_line_id` | NUMBER | ναι |  | FK → [`MM_DOC_LINE`](#mm_doc_line) |  |
| `created_at` | DATE | όχι | sysdate |  |  |
| `sold_at` | DATE | ναι |  |  |  |

- μοναδικό: `item_id, serial`
- έλεγχος: `status not in ('R', 'S') or out_line_id is not null`
- έλεγχος: `(status = 'S' and sold_at is not null and out_line_id is not null) or (status <> 'S' and sold_at is null)`
- έλεγχος: `status in ('N', 'A', 'R', 'S', 'X')`

### MM_SESSION

Οι συνδέσεις του REST: μόνο το SHA-256 του token, ο χρήστης, η λήξη.

> the sessions of the REST service: the token is given once, only its SHA-256 is kept here

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `token_hash` | RAW(32) | όχι |  | PK |  |
| `user_id` | NUMBER | όχι |  | FK → [`MM_USER`](#mm_user) (on delete cascade) |  |
| `client` | VARCHAR2(60) | ναι |  |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |
| `expires_at` | DATE | όχι |  |  |  |
| `last_seen` | DATE | όχι | sysdate |  |  |
| `revoked` | VARCHAR2(1) | όχι | 'N' |  |  |

- έλεγχος: `revoked in ('Y', 'N')`

### MM_SETTING

Οι ρυθμίσεις του μαγαζιού: διεύθυνση των reports, myDATA, ημέρες λήξεων, πόντοι, μέθοδος κόστους, backup, κεφαλίδα απόδειξης.

> the settings that differ from server to server, e.g. where the reports are (the button "Print" of the form MM_LEDGER): SET_REPORTS_URL.sql

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `name` | VARCHAR2(30) | όχι |  | PK |  |
| `value` | VARCHAR2(400) | ναι |  |  |  |

### MM_SIZE

Τα μεγέθη των παραλλαγών, με τη σειρά τους.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `size_group` | VARCHAR2(20) | όχι |  |  | e.g. CLOTHES (XS..XXL), SHOES (36..46) |
| `code` | VARCHAR2(10) | όχι |  |  |  |
| `sort_no` | NUMBER(5) | όχι | 0 |  |  |

- μοναδικό: `size_group, code`

### MM_STOCK_MOVE

Οι κινήσεις αποθήκης: κάθε αλλαγή του αποθέματος, ανά αποθήκη (παραστατικό, διόρθωση, απογραφή, συναρμολόγηση).

> the stock: every change of MM_ITEM.STOCK is a row here (a posted document, an adjustment, the first count)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) |  |
| `move_at` | DATE | όχι | sysdate |  |  |
| `kind` | VARCHAR2(4) | όχι |  |  |  |
| `qty` | NUMBER(12,3) | όχι |  |  |  |
| `doc_id` | NUMBER | ναι |  | FK → [`MM_DOC`](#mm_doc) |  |
| `doc_line_id` | NUMBER | ναι |  | FK → [`MM_DOC_LINE`](#mm_doc_line) |  |
| `note` | VARCHAR2(200) | ναι |  |  |  |
| `count_id` | NUMBER | ναι |  | FK → [`MM_COUNT`](#mm_count) |  |
| `unit_last` | NUMBER(12,4) | ναι |  |  | the cost by piece of the last purchase when a move was made (mm_core.fifo_apply): its cost when the shop counts its costs so (MM_SETTING COST_METHOD LAST) and not by FIFO |
| `warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) |  |

- έλεγχος: `(kind = 'DOC' and doc_id is not null) or (kind <> 'DOC' and doc_id is null)`
- έλεγχος: `kind in ('INIT', 'DOC', 'ADJ', 'ASM')`
- έλεγχος: `qty <> 0`

### MM_SUPPLIER

Οι προμηθευτές, με τα ίδια στοιχεία με τους πελάτες.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(100) | όχι |  |  |  |
| `afm` | VARCHAR2(9) | ναι |  |  |  |
| `doy` | VARCHAR2(60) | ναι |  |  |  |
| `address` | VARCHAR2(120) | ναι |  |  |  |
| `phone` | VARCHAR2(20) | ναι |  |  |  |
| `email` | VARCHAR2(100) | ναι |  |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- μοναδικό: `afm`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `regexp_like(afm, '^[0-9]{9}$')`
- έλεγχος: `email like '_%@_%._%'`

### MM_TILE

Τα κουμπιά του ταμείου: ένα είδος σε μια ομάδα, με τη σειρά του.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `group_id` | NUMBER | όχι |  | FK → [`MM_TILE_GROUP`](#mm_tile_group) (on delete cascade) |  |
| `item_id` | NUMBER | όχι |  | FK → [`MM_ITEM`](#mm_item) (on delete cascade) |  |
| `sort_no` | NUMBER | όχι | 0 |  |  |

- μοναδικό: `group_id, item_id`

### MM_TILE_GROUP

Οι ομάδες κουμπιών του ταμείου (καφέ): όνομα, χρώμα, σειρά, ενεργή.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `name` | VARCHAR2(40) | όχι |  |  |  |
| `color` | VARCHAR2(7) | όχι | '#6b7280' |  |  |
| `sort_no` | NUMBER | όχι | 0 |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `regexp_like(color, '^#[0-9a-fA-F]{6}$')`

### MM_USER

Οι χρήστες: όνομα, ρόλος του επιπέδου, κωδικός (μόνο PBKDF2), ενεργός, κλείδωμα, κατάστημα και ταμείο.

> the users of the shop (step 7a): the forms, the REST service and the web log in with them. ROLE: CASHIER (the till, the counts), MANAGER (and the office: invoices, ledgers, reports, counts posted), ADMIN (and the users). The password is never stored: PW_HASH = PBKDF2-HMAC-SHA256 of it with its own random salt (MM_AUTH); after 5 wrong ones in a row the user is locked for 15 minutes.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `username` | VARCHAR2(30) | όχι |  |  |  |
| `full_name` | VARCHAR2(100) | ναι |  |  |  |
| `role` | VARCHAR2(10) | όχι |  |  |  |
| `pw_hash` | RAW(32) | όχι |  |  |  |
| `pw_salt` | RAW(16) | όχι |  |  |  |
| `pw_iter` | NUMBER(7) | όχι |  |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |
| `failed` | NUMBER(3) | όχι | 0 |  |  |
| `locked_until` | DATE | ναι |  |  |  |
| `created_at` | DATE | όχι | sysdate |  |  |
| `pw_changed_at` | DATE | όχι | sysdate |  |  |
| `warehouse_id` | NUMBER | ναι |  | FK → [`MM_WAREHOUSE`](#mm_warehouse) (on delete set null) |  |
| `register_id` | NUMBER | ναι |  | FK → [`MM_REGISTER`](#mm_register) (on delete set null) |  |

- μοναδικό: `username`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `regexp_like(username, '^[a-z][a-z0-9._-]{2,29}$')`
- έλεγχος: `role in ('CASHIER', 'MANAGER', 'ADMIN')`

### MM_USER_ROLE

Οι ρόλοι κάθε χρήστη (πολλοί: το περισσότερο του καθενός).

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `user_id` | NUMBER | όχι |  | PK FK → [`MM_USER`](#mm_user) (on delete cascade) |  |
| `role_id` | NUMBER | όχι |  | PK FK → [`MM_ROLE`](#mm_role) (on delete cascade) |  |

### MM_VAT

Οι συντελεστές ΦΠΑ.

> VAT: the three Greek rates

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `code` | VARCHAR2(1) | όχι |  | PK |  |
| `rate` | NUMBER(5,2) | όχι |  |  |  |
| `descr` | VARCHAR2(40) | όχι |  |  |  |

- έλεγχος: `rate >= 0 and rate < 100`

### MM_WAREHOUSE

Οι αποθήκες: η κεντρική και τα υποκαταστήματα.

> the warehouses (αποθήκες): the main one (the central store, MAIN Y: one) and the branches; each move of the stock, each layer of FIFO, each document and register is of one (none: the main one)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `code` | VARCHAR2(10) | όχι |  |  |  |
| `name` | VARCHAR2(60) | όχι |  |  |  |
| `main` | VARCHAR2(1) | όχι | 'N' |  |  |
| `active` | VARCHAR2(1) | όχι | 'Y' |  |  |

- μοναδικό: `code`
- έλεγχος: `active in ('Y', 'N')`
- έλεγχος: `main in ('Y', 'N')`

### MM_WAREHOUSE_MIN

Το ελάχιστο απόθεμα κάθε είδους σε κάθε υποκατάστημα.

> the minimum stock of an item in a branch (the main one: MM_ITEM.MIN_STOCK); below it, goods sent from the central store (mm_core.transfer_missing: a draft DEN)

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `warehouse_id` | NUMBER | όχι |  | PK FK → [`MM_WAREHOUSE`](#mm_warehouse) (on delete cascade) |  |
| `item_id` | NUMBER | όχι |  | PK FK → [`MM_ITEM`](#mm_item) (on delete cascade) |  |
| `min_stock` | NUMBER(12,3) | όχι |  |  |  |

- έλεγχος: `min_stock > 0`

### MM_Z

Τα Ζ των ταμείων: ανοιχτό ή κλειστό, με τα σύνολά τους.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `id` | NUMBER | όχι | identity | PK |  |
| `register_id` | NUMBER | όχι |  | FK → [`MM_REGISTER`](#mm_register) |  |
| `z_no` | NUMBER(10) | όχι |  |  |  |
| `opened_at` | DATE | όχι | sysdate |  |  |
| `closed_at` | DATE | ναι |  |  |  |
| `status` | VARCHAR2(1) | όχι | 'O' |  |  |
| `docs` | NUMBER(10) | όχι | 0 |  |  |
| `net` | NUMBER(12,2) | όχι | 0 |  |  |
| `vat` | NUMBER(12,2) | όχι | 0 |  |  |
| `total` | NUMBER(12,2) | όχι | 0 |  |  |
| `cash` | NUMBER(12,2) | όχι | 0 |  |  |
| `card` | NUMBER(12,2) | όχι | 0 |  |  |
| `deposits` | NUMBER(12,2) | όχι | 0 |  |  |

- μοναδικό: `register_id, z_no`
- έλεγχος: `(status = 'O' and closed_at is null) or (status = 'C' and closed_at is not null and closed_at >= opened_at)`
- έλεγχος: `status in ('O', 'C')`
- έλεγχος: `total = net + vat`

### MM_Z_VAT

Τα σύνολα ΦΠΑ ενός κλειστού Ζ, ανά συντελεστή.

_Ορίζεται στο `db/MM_TABLES.sql`._

| Στήλη | Τύπος | Κενή | Προεπιλογή | Κλειδί | Σχόλιο του κώδικα |
|---|---|---|---|---|---|
| `z_id` | NUMBER | όχι |  | PK FK → [`MM_Z`](#mm_z) (on delete cascade) |  |
| `vat_code` | VARCHAR2(1) | όχι |  | PK FK → [`MM_VAT`](#mm_vat) |  |
| `net` | NUMBER(12,2) | όχι | 0 |  |  |
| `vat` | NUMBER(12,2) | όχι | 0 |  |  |
| `total` | NUMBER(12,2) | όχι | 0 |  |  |

- έλεγχος: `total = net + vat`

## Όψεις

Ό,τι δείχνουν οι σελίδες, οι φόρμες και τα reports βγαίνει από αυτές.

| Όψη | Τι δείχνει | Στήλες |
|---|---|---|
| `MM_AUDIT_ALL` | Το ιστορικό ενεργειών μαζί με τις συνδέσεις. | `id`, `at`, `username`, `source`, `action`, `ref_type`, `ref_id`, `ref_text`, `detail` |
| `MM_BACKUP_STATE` | Η κατάσταση του backup: OK, παλιό, απέτυχε, ποτέ. | `ok_at`, `ok_file`, `failed_at`, `error`, `days`, `state` |
| `MM_CHECK` | Ο έλεγχος της βάσης: κάθε γραμμή είναι κάτι που δεν συμφωνεί (απόθεμα, σύνολα, Ζ, FIFO, πόντοι, μήνες). Άδεια: όλα σωστά. | `what`, `id`, `detail` |
| `MM_CONSUMPTION` | Οι αναλώσεις (DAN) ανά αποθήκη, αιτία και είδος, με κόστος. | `doc_id`, `doc_no`, `day`, `warehouse_id`, `warehouse`, `warehouse_name`, `reason`, `item_id`, `code`, `name`, `unit`, `qty`, `cost_fifo`, `cost_last` |
| `MM_DOC_SERIALS` | Τα serials κάθε γραμμής παραστατικού. | `doc_id`, `doc_type`, `doc_no`, `line_id`, `line_no`, `code`, `name`, `serial`, `status` |
| `MM_EXPIRY` | Οι λήξεις: οι στρώσεις FIFO με ημερομηνία λήξης που έχουν ακόμα απόθεμα, ανά αποθήκη. | `item_id`, `code`, `name`, `unit`, `category`, `fifo_id`, `line_id`, `warehouse_id`, `warehouse`, `warehouse_name`, `expires`, `days_left`, `qty`, `left_`, `doc_id`, `doc_type`, `doc_no`, `doc_date`, `supplier` |
| `MM_FIFO_VALUE` | Η αξία του αποθέματος κάθε είδους με FIFO, και το κόστος της επόμενης εξόδου. | `item_id`, `code`, `name`, `unit`, `category`, `stock`, `last_cost`, `value`, `unit_cost`, `next_cost`, `value_last` |
| `MM_ITEM_AVAIL` | Το διαθέσιμο κάθε είδους: απόθεμα μείον όσα είναι δεσμευμένα σε κρατήσεις. | `item_id`, `code`, `name`, `stock`, `reserved`, `available` |
| `MM_ITEM_WAREHOUSE` | Ένα είδος σε κάθε αποθήκη (η φόρμα των ειδών): απόθεμα, ελάχιστο, όσα λείπουν, αξία FIFO, πρώτη λήξη. | `id`, `item_id`, `code`, `name`, `main`, `stock`, `min_stock`, `missing`, `value_`, `expires` |
| `MM_KIT_AVAIL` | Πόσα καλάθια ή σετ μπορούν να φτιαχτούν από το απόθεμα των ειδών τους. | `kit_id`, `code`, `name`, `ready`, `can_make` |
| `MM_MIN_STOCK` | Τα είδη κάτω από το ελάχιστο απόθεμα, με τον τελευταίο προμηθευτή. | `category`, `code`, `name`, `unit`, `stock`, `min_stock`, `missing`, `supplier`, `item_id`, `serial_tracked`, `supplier_id` |
| `MM_MOVE_COST` | Το κόστος κάθε κίνησης αποθήκης: FIFO και τελευταίας αγοράς. | `move_id`, `item_id`, `kind`, `doc_id`, `doc_line_id`, `move_at`, `qty`, `note`, `cost`, `cost_last` |
| `MM_PARTNER_EVENT` | Οι κινήσεις των πελατών και των προμηθευτών (παραστατικά, εισπράξεις, πληρωμές), για τις καρτέλες. | `kind`, `partner_id`, `ldate`, `debit`, `credit` |
| `MM_RESERVATION_NEED` | Πόσα χρειάζονται ακόμα οι ανοιχτές κρατήσεις. | `pickup_date`, `item_id`, `code`, `name`, `qty`, `reservations` |
| `MM_ROLE_RIGHT` | Το δικαίωμα κάθε ρόλου σε κάθε οθόνη, πεδίο και ενέργεια, όπως βγαίνει από τους κανόνες. | `role_id`, `object_id`, `object_code`, `item_id`, `item_code`, `kind`, `lv` |
| `MM_SALES_DAY` | Οι πωλήσεις κάθε ημέρας: αποδείξεις, τιμολόγια, πιστωτικά. | `day`, `alp_docs`, `alp_total`, `tpy_total`, `ppy_total`, `total` |
| `MM_SALES_DOC` | Οι πωλήσεις ανά παραστατικό: ημέρα, αποθήκη, ταμείο, ταμίας, καθαρά, σύνολο, κόστος. | `doc_id`, `day`, `doc_type`, `warehouse_id`, `register_id`, `posted_by`, `docs`, `net`, `total`, `cost_fifo`, `cost_last` |
| `MM_SCRATCH_PACK` | Τα πακέτα σκρατς: πόσα δελτία πουλήθηκαν και πόσα μένουν. | `game`, `pack`, `item_id`, `code`, `name`, `price`, `tickets`, `sold`, `left_`, `returned`, `loaded_at`, `last_sold` |
| `MM_SERIAL_CHECK` | Ο έλεγχος ότι το απόθεμα των ειδών με serials είναι όσα serials είναι διαθέσιμα. | `item_id`, `code`, `stock`, `available` |
| `MM_USER_MENU` | Το μενού κάθε χρήστη: οι οθόνες που μπορεί να δει, στις ομάδες τους. | `user_id`, `group_code`, `group_name`, `group_sort`, `code`, `name`, `route`, `form`, `sort_no`, `lvl` |
| `MM_USER_RIGHT` | Το δικαίωμα κάθε ενεργού χρήστη: το περισσότερο από τους ρόλους του. | `user_id`, `object_id`, `object_code`, `item_id`, `item_code`, `kind`, `lv`, `lvl` |
| `MM_VARIANT_GRID` | Οι παραλλαγές ενός μοντέλου σε πίνακα χρώμα × μέγεθος. | `model_id`, `model_code`, `model_name`, `item_id`, `code`, `barcode`, `color_code`, `color_name`, `size_group`, `size_code`, `sort_no`, `stock`, `reserved`, `available`, `price`, `active` |
| `MM_VAT_DAY` | Ο ΦΠΑ πωλήσεων και αγορών κάθε ημέρας, ανά συντελεστή. | `day`, `vat_code`, `vat_rate`, `s_net`, `s_vat`, `p_net`, `p_vat` |
| `MM_WAREHOUSE_MIN_STOCK` | Τα είδη κάτω από το ελάχιστο σε κάθε υποκατάστημα, με όσα έχει το κεντρικό. | `warehouse_id`, `warehouse`, `warehouse_name`, `item_id`, `code`, `name`, `unit`, `stock`, `min_stock`, `missing`, `central` |
| `MM_WAREHOUSE_STOCK` | Το απόθεμα κάθε είδους σε κάθε αποθήκη. | `item_id`, `warehouse_id`, `warehouse`, `warehouse_name`, `stock` |

## Πακέτα

Η προδιαγραφή κάθε πακέτου, όπως είναι γραμμένη στον κώδικα: οι διαδικασίες και οι συναρτήσεις του, με τα σχόλιά τους. Όλοι οι κανόνες είναι εδώ· οι φόρμες, οι σελίδες και το REST καλούν αυτά.

### MM_AUDIT

Το ιστορικό ενεργειών.

_`db/MM_AUDIT.sql`_

```
MM_AUDIT.sql -- the history of what was done (MM_AUDIT_LOG), by triggers on the tables: whatever did it (the pages,
the forms, SQL) is written. Run by INSTALL.sql, after the packages.

who:       CLIENT_IDENTIFIER of the session (the user of the pages, mm-api; of the forms, MM_UI), else the
user of the database (e.g. MM, from SQL*Plus)
from where: MODULE of the session (mm-api, the forms, SQL*Plus ...)
what:      a document posted, cancelled, a draft out; a Z opened, closed; money in and out of a
register; the stock corrected by hand; a count posted, cancelled; a payment, cancelled; an
item new, its name, prices, minimum, active; a customer, a supplier new or changed; a user new,
its role, active, place, password (never the password); the roles, their users, their rights;
the menu; the settings (no value of a key, a password, a token); a warehouse

In the transaction of what it writes: undone with it. MM_AUDIT_ALL: these and the logins (MM_AUTH_LOG).
Kept: mm_audit.purge(days) takes out what is older (e.g. 730: two years).
```

```sql
  procedure log(p_action varchar2, p_ref_type varchar2 default null, p_ref_id number default null,
                p_ref_text varchar2 default null, p_detail varchar2 default null);
  -- who is doing it: the user of the pages or the forms (CLIENT_IDENTIFIER), else of the database
  function who return varchar2;
  -- a change of a value for the detail: 'name: old → new' (nothing when the same)
  function diff(p_name varchar2, p_old varchar2, p_new varchar2) return varchar2;
  procedure purge(p_days number);
```

### MM_AUTH

Οι χρήστες και οι συνδέσεις: κωδικοί (PBKDF2), login, token, κλείδωμα, κατάστημα και ταμείο.

_`db/MM_AUTH.sql`_

```
MM_AUTH.sql -- the users of the shop and their logins (step 7a). Run by INSTALL.sql. Needs
DBMS_CRYPTO (GRANT_CRYPTO.sql, as SYS: the same grant as MM_PIN).

mm_auth.create_user('maria', 'Μαρία Π.', 'CASHIER', :password)     a user (ADMIN, MANAGER, CASHIER)
mm_auth.login('maria', :password, 'web', token, role, expires)       a session of 12 hours: its token
mm_auth.check(token, user_id, username, role)                         who it is (else MM-179)
mm_auth.logout(token)
set_password, set_role, set_active, unlock
mm_auth.set_place('maria', :store, :register)                       where she works (may_use: a register)

The password: PBKDF2-HMAC-SHA256, its own random salt of 16 bytes, C_ITER rounds (kept for each user:
more rounds later take effect at its next password). The token: 32 random bytes as 64 hex
characters, given once; only its SHA-256 is kept (MM_SESSION). 5 wrong passwords in a row: locked for
15 minutes. An unknown user costs the same time as a known one (no hint by the clock).
No commit here, as MM_CORE: except what a failed login leaves (its count, the log), which stays.
The errors: MM-174 .. MM-182.
```

```sql
  c_iter constant pls_integer := 100000;
  c_hours constant pls_integer := 12;

  function create_user(p_username varchar2, p_full_name varchar2, p_role varchar2,
                       p_password varchar2) return number;
  procedure set_password(p_username varchar2, p_password varchar2);
  procedure set_role(p_username varchar2, p_role varchar2);
  procedure set_active(p_username varchar2, p_active varchar2);
  procedure unlock(p_username varchar2);
  -- the place of a user: its store (a warehouse) and its register (of that store: a register given alone,
  -- its store too); null, null: everywhere. A cashier with a register works only on it; with a store,
  -- on the registers of it; a manager, on the registers of its store; an administrator, everywhere.
  procedure set_place(p_username varchar2, p_warehouse_id number, p_register_id number default null);
  -- may the user work on the register: Y or N
  function may_use(p_user_id number, p_register_id number) return varchar2;
  procedure login(p_username varchar2, p_password varchar2, p_client varchar2,
                  o_token out varchar2, o_role out varchar2, o_expires out date);
  procedure check_token(p_token varchar2, o_user_id out number, o_username out varchar2, o_role out varchar2);
  procedure logout(p_token varchar2);
  -- the password as stored (for the tests: the same in Python)
  function pbkdf2(p_password varchar2, p_salt raw, p_iter pls_integer) return raw;
```

### MM_CORE

Ο πυρήνας: παραστατικά, απόθεμα, FIFO, αποθήκες, ταμείο και Ζ, serials και PIN, σετ, προσφορές, παραλλαγές, εισπράξεις, κρατήσεις και παραγγελίες, απογραφές, myDATA, σκρατς, πόντοι, ελάχιστο.

_`db/MM_CORE.sql`_

```
MM_CORE.sql -- the rules of the mini market, in one package. Everything that writes goes through
here: the forms (Oracle Forms), the web pages and the phones (through a REST layer) call the same
procedures, so the three behave the same.

No COMMIT inside: the caller commits (a form at its save, the REST layer at the end of a call).
Errors: raise_application_error -20100 .. -20199, the text in Greek, the code first
("MM-104: ..."), so that a form or a web page can show it as it is.

MM_ITEM.STOCK is reservable: only "stock = stock +/- n where id = :id", and a SELECT in the
same transaction still sees the stock before the change (the change is applied at COMMIT).
```

```sql
  -- the check digits: 'Y' or 'N' (not boolean: Forms and SQL read them alike)
  function afm_ok(p_afm varchar2) return varchar2;
  function ean_ok(p_code varchar2) return varchar2;

  -- an item by barcode or by code, else by its short number (PLU, the buttons of the till); null if there is
  -- none (or it is inactive and p_active = 'Y')
  function find_item(p_code varchar2, p_active varchar2 default 'Y') return number;

  -- net, VAT and total of a line: the price with VAT (p_incl = 'Y') or without
  procedure amounts(p_price number, p_qty number, p_discount number, p_rate number, p_incl varchar2,
                    o_net out number, o_vat out number, o_total out number);

  -- the price a new line takes when none is given: retail with VAT (receipt), the wholesale price
  -- (invoice of sale; empty: the retail without its VAT), or the cost (purchase)
  function default_price(p_doc_type varchar2, p_item_id number) return number;

  -- the documents: a draft, its lines, then post (number, stock, cash) or cancel
  -- the warehouse of a document: the one given, else that of its register, else the main one
  function new_doc(p_doc_type varchar2, p_customer_id number default null, p_supplier_id number default null,
                   p_register_id number default null, p_payment varchar2 default 'CASH',
                   p_doc_date date default trunc(sysdate), p_warehouse_id number default null,
                   p_to_warehouse_id number default null) return number;
  function main_warehouse return number;              -- MM_WAREHOUSE MAIN Y
  -- a consumption (Δελτίο ανάλωσης, DAN): new_doc('DAN', p_warehouse_id => its warehouse), its lines as a
  -- transfer (at the cost of the layers), its reason (a draft): USE, DAMAGE, SAMPLE, EXPIRED (none: USE when
  -- posted); posted: out of its warehouse, no sale, no VAT, no profit; cancelled: back
  procedure set_reason(p_doc_id number, p_reason varchar2);
  -- a transfer (Δελτίο ενδοδιακίνησης, DEN): new_doc('DEN', p_warehouse_id => from, p_to_warehouse_id => to);
  -- its lines at the cost of each layer of FIFO they take in the warehouse it goes from (a line for each
  -- cost; no VAT; a price given is not taken); posted: its lines once more by the layers, out of the one,
  -- into the other with the same layers and costs; cancelled: back in both
  function add_line(p_doc_id number, p_item_id number, p_qty number,
                    p_price number default null, p_discount number default 0) return number;
  procedure update_line(p_line_id number, p_qty number, p_price number, p_discount number default 0);
  -- the date a line of goods received expires (a draft that brings stock from a supplier: DPA, TAD);
  -- null: none. What is left of them: MM_EXPIRY
  procedure set_expiry(p_line_id number, p_expires date);
  procedure delete_line(p_line_id number);
  procedure recalc(p_doc_id number);                     -- a draft sale: reprice first
  procedure reprice(p_doc_id number);                    -- the promotions and the discount of the document
  procedure set_doc_discount(p_doc_id number, p_pct number default 0, p_amount number default 0,
                             p_reason varchar2 default null);   -- on the whole document, with a reason
  procedure delete_doc(p_doc_id number);                 -- a draft only
  procedure set_payment(p_doc_id number, p_payment varchar2);  -- a draft: CASH, CARD (CREDIT not retail)
  function post_doc(p_doc_id number) return number;     -- returns the number of the document
  procedure cancel_doc(p_doc_id number);                 -- a posted one, while its Z is open
  -- the return of an invoice: a draft delivery note of return (DEP of a sale, DEA of a purchase) with its
  -- lines; posted, its credit note is made from it (invoice_from). Not an invoice with cards (MM-129)
  function credit_note(p_doc_id number) return number;
  -- an invoice (or a credit note) from posted delivery notes of one customer or supplier: its kind is
  -- the one whose REF_TYPE is the kind of the note; their lines into it; a note into one invoice only
  function invoice_from(p_note_id number, p_doc_date date default trunc(sysdate)) return number;  -- a new draft
  procedure add_note(p_invoice_id number, p_note_id number);            -- one more note into a draft

  -- the stock by hand
  procedure adjust_stock(p_item_id number, p_qty number, p_note varchar2, p_warehouse_id number default null);

  -- the cash register: one open Z at a time
  function open_z(p_register_id number, p_cash number default 0) return number;
  procedure cash_in_out(p_register_id number, p_amount number, p_note varchar2); -- + in, - out
  function open_z_of(p_register_id number) return number;  -- null when closed
  function close_z(p_register_id number) return number;    -- returns the id of the Z

  -- the cards with serial numbers (items with SERIAL_TRACKED = 'Y'); the PIN is kept encrypted
  function load_serial(p_item_id number, p_serial varchar2, p_pin varchar2 default null,
                       p_note varchar2 default null) return number;     -- straight to the stock (+1)
  function add_serial(p_line_id number, p_serial varchar2, p_pin varchar2 default null) return number;
                                                                         -- to a line of a draft purchase
  function sell_serial(p_doc_id number, p_item_id number default null,
                       p_serial varchar2 default null) return number;   -- the oldest available, or this one
  function sell_serials(p_doc_id number, p_item_id number, p_qty number) return number;
                                                                         -- p_qty of the oldest: how many
  procedure release_serial(p_serial_id number);                         -- back from a draft sale
  function reveal_pin(p_serial_id number, p_user varchar2 default null) return varchar2;
  function receipt_pin(p_serial_id number) return varchar2;             -- a card sold today

  -- baskets and sets (kits): what one has (p_qty 0: out), made before (assemble_kit; a negative
  -- quantity takes them apart), or sold before they are made (post_doc: the ready ones first)
  procedure set_component(p_kit_id number, p_component_id number, p_qty number);
  procedure assemble_kit(p_kit_id number, p_qty number, p_note varchar2 default null);
  function kit_cost(p_kit_id number) return number;

  -- promotions: PCT (% off), NM (buy N get M free), BUNDLE (items together for a price); their items
  -- or categories (promo_item: p_qty 0 out; a bundle: items only, with the quantity each)
  function new_promo(p_name varchar2, p_kind varchar2, p_from date, p_to date, p_pct number default null,
                     p_buy number default null, p_free number default null,
                     p_price number default null) return number;
  procedure promo_item(p_promo_id number, p_item_id number default null, p_category_id number default null,
                       p_qty number default 1);
  procedure promo_active(p_promo_id number, p_active varchar2);         -- 'Y' or 'N'

  -- clothes and shoes: a variant of a model (a colour and/or a size), an item of its own; the first one
  -- makes the item a model (not sold, no stock); model_price: the price to the model and its variants
  function make_variant(p_model_id number, p_color_id number default null, p_size_id number default null,
                        p_barcode varchar2 default null) return number;
  procedure model_price(p_model_id number, p_price number);

  -- receipts from customers and payments to suppliers (what settles the invoices on credit): CASH,
  -- CARD or BANK; with a register (CASH, CARD): a move of its open Z too
  function receive(p_customer_id number, p_amount number, p_method varchar2 default 'CASH',
                   p_date date default trunc(sysdate), p_register_id number default null,
                   p_notes varchar2 default null) return number;
  function pay(p_supplier_id number, p_amount number, p_method varchar2 default 'BANK',
               p_date date default trunc(sysdate), p_register_id number default null,
               p_notes varchar2 default null) return number;
  procedure cancel_payment(p_payment_id number);

  -- reservations (e.g. New Year cakes): a name, a phone, the day of the pickup; their quantities are
  -- reserved (MM_ITEM_AVAIL) until the delivery, a receipt that counts the deposit
  function new_reservation(p_name varchar2, p_phone varchar2, p_pickup_date date,
                           p_customer_id number default null, p_notes varchar2 default null,
                           p_created_by varchar2 default null) return number;
  -- an order (a reservation from the pages, of today or later): what of a line was picked (0 .. its
  -- quantity), the order ready or not; for a customer on credit, a delivery note instead of a receipt
  procedure pick(p_res_id number, p_item_id number, p_qty number);
  procedure set_ready(p_res_id number, p_ready varchar2 default 'Y');
  -- an order of a customer from the page of the shop: for today, its token (the page of its status), at
  -- most 3 open ones a phone (MM-188); confirmed by the shop (a call), or cancelled by the customer
  -- while not confirmed
  function online_order(p_name varchar2, p_phone varchar2, p_notes varchar2, p_token varchar2) return number;
  procedure confirm_order(p_res_id number);
  procedure cancel_online(p_token varchar2);
  function deliver_note(p_res_id number) return number;                -- a draft DAP of its lines
  procedure reserve(p_res_id number, p_item_id number, p_qty number, p_price number default null);  -- 0: out
  procedure take_deposit(p_res_id number, p_register_id number, p_amount number,
                         p_payment varchar2 default 'CASH');
  function deliver(p_res_id number, p_register_id number, p_payment varchar2 default 'CASH') return number;
  procedure cancel_reservation(p_res_id number, p_register_id number default null,
                               p_refund varchar2 default 'Y');

  -- the count of the stock: start, scan (from the phones), post
  function start_count(p_name varchar2, p_warehouse_id number default null) return number;   -- (none: the main one)
  function scan(p_count_id number, p_code varchar2, p_qty number default 1,
                p_mode varchar2 default 'ADD', p_device varchar2 default null) return number;
  procedure post_count(p_count_id number);
  procedure cancel_count(p_count_id number);

  -- myDATA of AADE (mm-api MyData.java sends them): a posted invoice or credit note of a sale to be
  -- sent (state Q); what AADE answered: sent (its MARK, UID, QR), failed (the error), its
  -- cancellation sent (X). MYDATA_AUTO Y in MM_SETTING: post_doc queues them by itself
  procedure mydata_queue(p_doc_id number);
  procedure mydata_sent(p_doc_id number, p_mark number, p_uid varchar2, p_qr varchar2);
  procedure mydata_failed(p_doc_id number, p_error varchar2);
  procedure mydata_cancelled(p_doc_id number, p_cancel_mark number);

  -- the scratch tickets (MM_SCRATCH_GAME): a game (έκδοση) and the item it is sold as, the tickets of a
  -- pack; a pack loaded from the barcode of one of its tickets (14 digits) or its game and pack (11):
  -- its tickets 000.. as serials (the barcode of each), into the stock; how many. A prize paid from the
  -- drawer of the till (a move out, «Κέρδος σκρατς»)
  procedure scratch_game(p_game varchar2, p_item_id number, p_pack_size number default 300);
  function load_pack(p_code varchar2, p_count number default null) return number;
  procedure scratch_prize(p_register_id number, p_amount number, p_ticket varchar2 default null);
  -- the tickets of a pack not sold, back to the supplier (the barcode of one of them, or game and pack):
  -- void (X), out of the stock in one move; how many. Not while one of them is in a receipt being written
  function return_pack(p_code varchar2) return number;

  -- an order to the suppliers from the minimum stock (MM_MIN_STOCK): for each supplier (the last one
  -- an item was bought from) a draft delivery note of purchase (DPA: that one, when there is a draft
  -- already) with what is missing (whole pieces), at the cost of the item; printed as an order, its
  -- quantities set when the goods come, then posted. Not the items with serials (loaded one by one), nor
  -- those without a supplier yet. How many lines went in
  function order_missing(p_supplier_id number default null) return number;

  -- the minimum stock of an item in a warehouse: the main one, MM_ITEM.MIN_STOCK; a branch,
  -- MM_WAREHOUSE_MIN (0: none). Below it in a branch (MM_WAREHOUSE_MIN_STOCK): goods from the central
  -- store, a draft DEN to the branch (that one, when there is a draft already) with what is missing
  -- (whole pieces), not more than the central store has; checked, posted when they leave. Not the items
  -- with serials, nor the sets. How many lines went in
  procedure set_min(p_warehouse_id number, p_item_id number, p_min number);
  function transfer_missing(p_warehouse_id number) return number;

  -- the points of the retail customers (MM_POINTS): a card for a customer (EAN-13 2990 + its id), the
  -- customer of a card; the customer of a draft receipt (null: none, its points not used); points used
  -- on it (0: none): at least POINTS_MIN, not more than it has, as the discount of the receipt
  -- (POINT_VALUE euros each). Posted: its points used taken, POINTS_PER_EURO for each euro given
  function new_card(p_customer_id number) return varchar2;
  function card_customer(p_card varchar2) return number;
  procedure set_doc_customer(p_doc_id number, p_customer_id number);
  procedure use_points(p_doc_id number, p_points number);

  -- FIFO (MM_FIFO, MM_FIFO_OUT): built by every move of the stock (stock_move); all of it again from
  -- the moves, of one item or of all (INSTALL.sql does it, after the demo rows)
  procedure fifo_rebuild(p_item_id number default null);

  -- the backup of the database (db/backup.ps1) says how it went: p_ok Y (p_text its file) or N (p_text
  -- the error); MM_BACKUP_STATE tells the pages when the last good one is too old
  procedure backup_done(p_ok varchar2, p_text varchar2);

  -- the buttons of the till (MM_TILE_GROUP, MM_TILE; errors MM-132): a group new (p_id null: at the end) or
  -- changed, out with its tiles; an item into a group (at its end; not a model, not inactive), a tile out;
  -- a group (p_kind G) or a tile (T) one place before (p_dir -1) or after (+1); the short number of an item
  -- (PLU, null: none): not the PLU, the code or the barcode of another item
  function tile_group_save(p_id number, p_name varchar2, p_color varchar2, p_active varchar2) return number;
  procedure tile_group_delete(p_id number);
  function tile_add(p_group_id number, p_item_id number) return number;
  procedure tile_delete(p_id number);
  procedure tile_move(p_kind varchar2, p_id number, p_dir number);
  procedure set_plu(p_item_id number, p_plu number);

  -- the options at the till (MM_OPTION_GROUP, MM_OPTION, MM_ITEM_OPTION; errors MM-132): a group new (p_id
  -- null) or changed (pick O one, M any; required: of a pick O), out with its options; an option new or
  -- changed (its price with VAT, >= 0; is_default: the one of its group, the others not), out (used on a
  -- receipt already: not, made inactive instead); a group (p_kind G) or an option (O) one place before or
  -- after; the groups of an item (p_on Y: in, N: out)
  function option_group_save(p_id number, p_name varchar2, p_pick varchar2, p_required varchar2,
                             p_active varchar2) return number;
  procedure option_group_delete(p_id number);
  function option_save(p_id number, p_group_id number, p_name varchar2, p_price number, p_default varchar2,
                       p_active varchar2) return number;
  procedure option_delete(p_id number);
  procedure option_move(p_kind varchar2, p_id number, p_dir number);
  procedure item_option(p_item_id number, p_group_id number, p_on varchar2);
  -- a line with its options (p_options: their ids, comma separated; null: none chosen): only the active
  -- options of the groups of the item, one of a group O; a required group without one: its default, else
  -- refused; the price of the line its price (default_price) and the extras; the options with the line
  -- (MM_DOC_LINE_OPTION) and their text (MM_DOC_LINE.OPTIONS: "Μέτριος, Βρώμης +0,30")
  function add_line_options(p_doc_id number, p_item_id number, p_qty number, p_options varchar2) return number;
  -- the number at the counter of a posted retail receipt with an item of the buttons of the till (MM_TILE):
  -- the next of the day (all the registers), once; null: none of them
  function counter_ticket(p_doc_id number) return number;
```

### MM_LEDGER

Οι καρτέλες ειδών, πελατών και προμηθευτών, και τα ισοζύγια.

_`db/MM_LEDGER.sql`_

```
MM_LEDGER.sql -- the ledgers (καρτέλες) of an item, a customer and a supplier for a period:
the balance before it (from the carry-over), its moves one by one with the running balance, the
totals of the period and the balance at its end. Run by INSTALL.sql.

select * from table(mm_ledger.item_rows(:item_id, :from, :to))           (the reports)
select * from table(mm_ledger.partner_rows('C', :customer_id, :from, :to))
mm_ledger.fill('I' / 'C' / 'S', id, from, to, open, debit, credit, close)  (the form MM_LEDGER:
the rows in MM_LEDGER_ROW, the totals out)
The first row (KIND O) is the carry-over, the others (M) the moves. The carry-over: the totals of the
months before the month of the period (MM_ITEM_MONTH, MM_PARTNER_MONTH: MM_MONTHS.sql) and the moves
of that month before its first day: a ledger of years ago as quick as one of today.
An item:     DEBIT in, CREDIT out, BALANCE the stock (every move of MM_STOCK_MOVE, by its hour).
A customer:  DEBIT the invoices, CREDIT the credit notes and the receipts; BALANCE what he owes.
A supplier:  CREDIT the invoices, DEBIT the credit notes and the payments; BALANCE what we owe.
A document paid at once (cash or card) has a second row, its money: it leaves the balance as it was.
Only what is posted: cancelled documents and payments are not in a ledger.

The reports (reports/MM_LEDGER_I, MM_LEDGER_P): report_rows, the moves with what was before each
one (PRIOR_*) and up to it (CUM_*): the first PRIOR_ of a page is its "from the carry-over" (από
μεταφορά), the last CUM_ and BALANCE its "to the carry-over" (σε μεταφορά); title and label: the
Greek of the report (its XML is ASCII).
```

```sql
  type t_row is record (
    seq       number,
    kind      varchar2(1),
    ldate     date,
    doc_id    number,
    doc_text  varchar2(40),
    partner   varchar2(100),
    descr     varchar2(200),
    debit     number,
    credit    number,
    balance   number);
  type t_rows is table of t_row;
  type t_rrow is record (
    seq            number,
    kind           varchar2(1),
    ldate          date,
    doc_text       varchar2(40),
    descr          varchar2(300),    -- the partner (or register) and the description
    debit          number,
    credit         number,
    balance        number,
    prior_debit    number,           -- the totals of the period before this row
    prior_credit   number,
    prior_balance  number,
    cum_debit      number,           -- ... with it
    cum_credit     number);
  type t_rrows is table of t_rrow;
  -- a row of a trial balance (ισοζύγιο): an item, a customer or a supplier, its totals as its ledger
  type t_trow is record (
    id         number,
    code       varchar2(40),     -- the code of an item, the ΑΦΜ of a customer or a supplier
    name       varchar2(200),
    unit       varchar2(10),
    open_bal   number,           -- from the carry-over (before p_from)
    debit      number,           -- the period
    credit     number,
    close_bal  number);          -- at the end of p_to
  type t_trows is table of t_trow;

  function item_rows(p_item_id number, p_from date, p_to date) return t_rows pipelined;
  -- p_kind: C a customer, S a supplier
  function partner_rows(p_kind varchar2, p_id number, p_from date, p_to date) return t_rows pipelined;
  -- p_what: I an item, C a customer, S a supplier
  procedure fill(p_what varchar2, p_id number, p_from date, p_to date,
                 p_open out number, p_debit out number, p_credit out number, p_close out number);
  -- the rows of a report: the moves (only the carry-over when there are none)
  function report_rows(p_what varchar2, p_id number, p_from date, p_to date) return t_rrows pipelined;
  -- the trial balance (ισοζύγιο) of the items (I), the customers (C) or the suppliers (S) for a period:
  -- one row each, with the totals of its ledger (fill) but not its moves; p_all 'N': only those with
  -- something (a carry-over, a move, a balance), 'Y': all. From the totals of the months (as the
  -- carry-over of a ledger): the balance as of a day = the months before its month + the moves of its
  -- days before it; a trial balance = that at p_from and after p_to, two half months of moves read
  function trial_rows(p_what varchar2, p_from date, p_to date, p_all varchar2 default 'N') return t_trows pipelined;
  -- 'Καρτέλα πελάτη: <name>' ...
  function title(p_what varchar2, p_id number) return varchar2;
  -- the words of the reports: DATE, DOC, DESCR, DEBIT, CREDIT, BALANCE (by p_what), FROM_CARRY,
  -- TO_CARRY, TOTALS, OPEN, CLOSE, PAGE, PERIOD, NONE
  function label(p_key varchar2, p_what varchar2 default null) return varchar2;
```

### MM_MONTHS

Τα σύνολα των μηνών (ξαναϋπολογισμός).

_`db/MM_MONTHS.sql`_

```
MM_MONTHS.sql -- the totals of each month, kept by triggers, for the ledgers (MM_LEDGER takes what
was before a period from them: one row a month, not every move since the first one). Run by
INSTALL.sql, which then builds them again from all the moves (rebuild: the moves of before).

MM_ITEM_MONTH     the stock in and out of an item a month       <- MM_STOCK_MOVE
MM_PARTNER_MONTH  the debit and credit of a customer / supplier <- MM_DOC (posted), MM_PAYMENT

Every change counts: a new row, a row changed (a date moved to another month, a document posted or
cancelled, its total, its partner) and a row deleted: what the row was is taken off, what it is now
is added. A posted document or payment is what its ledger shows (MM_PARTNER_EVENT).
MM_ITEM_MONTH is reservable (as MM_ITEM.STOCK): two tills that sell the same item in the same month do
not wait for each other; only the first move of an item in a month makes its row.
```

```sql
  -- a move (p_qty: + in, - out) added (p_sign 1) or taken off (-1)
  procedure item_move(p_item_id number, p_at date, p_qty number, p_sign number);
  procedure doc_change(p_doc_type varchar2, p_status varchar2, p_customer_id number, p_supplier_id number,
                       p_date date, p_payment varchar2, p_total number, p_sign number);
  procedure payment_change(p_kind varchar2, p_status varchar2, p_customer_id number, p_supplier_id number,
                           p_date date, p_amount number, p_sign number);
  -- all of it again from the moves, the documents and the payments (INSTALL.sql; no commit). In a
  -- transaction of its own: a row of MM_ITEM_MONTH changed (reservable) and not committed yet cannot
  -- be deleted (ORA-55754)
  procedure rebuild;
```

### MM_PIN

Η κρυπτογράφηση των PIN (AES-256).

_`db/MM_PIN.sql`_

```
MM_PIN.sql -- the PINs of the cards, encrypted: AES-256, CBC, PKCS5, a random IV for each PIN
(stored in front of it). The key: 32 random bytes in MM_SECRET, made the first time.
Needs EXECUTE on SYS.DBMS_CRYPTO (GRANT_CRYPTO.sql, as SYS). Without it this package is not valid
and only the PINs do not work; MM_CORE and the rest do.

What it protects: the PINs do not show in a SELECT, a report, an export of a table or a backup
read by someone without the key. A session of the owner MM can still read the key: the real
wall is the login (step 7a), where the users of the shop are not MM.
```

```sql
  function enc(p_pin varchar2) return raw;
  function dec(p_enc raw) return varchar2;
```

### MM_REPORT

Τα reports: πωλήσεις, ΦΠΑ, ελάχιστο απόθεμα.

_`db/MM_REPORT.sql`_

```
MM_REPORT.sql -- what the reports of sales, VAT and minimum stock read (reports/mkreports.py), and
their Greek words (the XML of a report is ASCII). Run by INSTALL.sql.

MM_SALES_DAY      the sales of each day: receipts (their number and total), invoices (and TDA), credit notes
MM_VAT_DAY        each day and VAT rate: net and VAT of the sales and of the purchases (a credit
note takes off)
MM_MIN_STOCK      the items under their minimum stock, with what is missing and the supplier of
their last purchase
Only what is posted (a cancelled receipt is not a sale).
```

```sql
  -- the title of a report: SALES, VAT, MIN_STOCK
  function title(p_report varchar2) return varchar2;
  -- 'Διάστημα: 01/01/2026 - 31/12/2026', or with no period 'Ημερομηνία: <today>'
  function period(p_from varchar2 default null, p_to varchar2 default null) return varchar2;
  -- the heading of a column, the words of the totals
  function label(p_key varchar2) return varchar2;
  -- a quantity as text: 12, 0,215 (no zeros after the point)
  function qty(p_qty number) return varchar2;
```

### MM_RIGHTS

Οι ρόλοι και τα δικαιώματα ανά οθόνη, πεδίο και ενέργεια, και το μενού.

_`db/MM_RIGHTS.sql`_

```
MM_RIGHTS.sql -- the rights of the users: roles, the screens of the menu (a page of the web and/or a form
of Oracle Forms), their fields and actions, what each role may do with them. Run by INSTALL.sql, after
MM_AUTH.sql (the tables: MM_TABLES.sql).

MM_ROLE         the roles: CASHIER, MANAGER, ADMIN (system: as before them) and the shop's own; a role
of all rights (ADMIN): everything, always
MM_USER_ROLE    the roles of a user (more than one: the most of each)
MM_OBJECT       the menu: its groups (G) and its screens (S), each with its page (route) and/or form
MM_OBJECT_ITEM  the fields (F) and the actions (A) of a screen
MM_GRANT        what a role may do: N none, R read, W write (an action: W allowed, else not)

The level of a user, for each screen, field, action (MM_USER_RIGHT): of each of its roles, the most.
Of a role: a screen, its grant (none: N); a field, its grant, not above its screen (none: as its
screen); an action, its grant when the screen is at least R (none: allowed when the screen is W).

mm_rights.lvl(user_id, 'ITEMS', 'COST')            N, R or W
mm_rights.can(user_id, 'DOCS', 'POST', 'W')        Y or N
mm_rights.need(user_id, 'ITEMS', null, 'W')        else MM-197
mm_rights.create_role('STORE_MGR', 'Υπεύθυνος καταστήματος'); mm_rights.copy_role('MANAGER', 'STORE_MGR')
mm_rights.set_grant('STORE_MGR', 'ITEMS', 'COST', 'N')        (null: the grant out)
mm_rights.add_user_role('nikos.r', 'STORE_MGR')

Once more (INSTALL.sql again): a screen, a field, a role, a grant that is there already stays as it is
(what the shop changed is kept); only what is new comes in. No commit in the package, as MM_CORE.
The errors: MM-197 (not allowed), MM-198 (the roles and the grants).
```

```sql
  function lvl(p_user_id number, p_object varchar2, p_item varchar2 default null) return varchar2;
  function can(p_user_id number, p_object varchar2, p_item varchar2 default null,
               p_level varchar2 default 'R') return varchar2;
  procedure need(p_user_id number, p_object varchar2, p_item varchar2 default null, p_level varchar2 default 'R');

  -- the roles: a new one (a code A-Z 0-9 _); its name, (not) active; out (not a system one); its grants
  -- from another one (all of them: what it had, replaced)
  function create_role(p_code varchar2, p_name varchar2, p_all_rights varchar2 default 'N') return number;
  procedure set_role(p_code varchar2, p_name varchar2, p_active varchar2 default 'Y');
  procedure drop_role(p_code varchar2);
  procedure copy_role(p_from varchar2, p_to varchar2);
  -- what a role may do with a screen (p_item null), a field or an action of it: N, R, W; null: the grant
  -- out (a screen: none; a field, an action: as its screen)
  procedure set_grant(p_role varchar2, p_object varchar2, p_item varchar2, p_level varchar2);
  -- the roles of a user
  procedure add_user_role(p_username varchar2, p_role varchar2);
  procedure drop_user_role(p_username varchar2, p_role varchar2);
  -- the menu: a group or a screen renamed, its place (its order; a screen: its group), (not) active (not
  -- the roles and the rights themselves: the way back to them)
  procedure set_object(p_code varchar2, p_name varchar2, p_sort number, p_group varchar2, p_active varchar2 default 'Y');
```

### MM_TEXT

Τα ελληνικά των φορμών (οι φόρμες είναι σε ASCII).

_`db/MM_TEXT.sql`_

```
MM_TEXT.sql -- made by forms/mkforms.py: the Greek of the forms (prompts, labels, titles,
messages), which the forms ask for when they open (XML2Forms does not carry Greek into a
form). UTF-8: run by INSTALL.sql, or by the build scripts with NLS_LANG ...AL32UTF8.
```

```sql
  function t(p_key varchar2) return varchar2;
```

## Triggers

| Trigger | Πίνακας | Πότε | Τι κάνει |
|---|---|---|---|
| `MM_CASH_MOVE_AUDIT` | `MM_CASH_MOVE` | after each row insert | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_COUNT_AUDIT` | `MM_COUNT` | after each row update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_CUSTOMER_AUDIT` | `MM_CUSTOMER` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_DOC_AUDIT` | `MM_DOC` | after each row update or delete | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_DOC_MONTH` | `MM_DOC` | after each row insert or update or delete | Κρατά τα σύνολα του μήνα των πελατών και των προμηθευτών. |
| `MM_DOC_WHO` | `MM_DOC` | before each row insert or update | Γράφει ποιος έφτιαξε και ποιος καταχώρισε το παραστατικό. |
| `MM_GRANT_AUDIT` | `MM_GRANT` | after each row insert or update or delete | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_ITEM_AUDIT` | `MM_ITEM` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_OBJECT_AUDIT` | `MM_OBJECT` | after each row update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_PAYMENT_AUDIT` | `MM_PAYMENT` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_PAYMENT_MONTH` | `MM_PAYMENT` | after each row insert or update or delete | Κρατά τα σύνολα του μήνα των πελατών και των προμηθευτών. |
| `MM_ROLE_AUDIT` | `MM_ROLE` | after each row insert or update or delete | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_SETTING_AUDIT` | `MM_SETTING` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_STOCK_MOVE_AUDIT` | `MM_STOCK_MOVE` | after each row insert | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_STOCK_MOVE_MONTH` | `MM_STOCK_MOVE` | after each row insert or update or delete | Κρατά τα σύνολα του μήνα των ειδών. |
| `MM_SUPPLIER_AUDIT` | `MM_SUPPLIER` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_USER_AUDIT` | `MM_USER` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_USER_ROLE_AUDIT` | `MM_USER_ROLE` | after each row insert or delete | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_WAREHOUSE_AUDIT` | `MM_WAREHOUSE` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |
| `MM_Z_AUDIT` | `MM_Z` | after each row insert or update | Γράφει στο ιστορικό ενεργειών (MM_AUDIT_LOG). |

## Είδη παραστατικών

`side`: S πώληση, P αγορά, T εσωτερικό (ενδοδιακίνηση, ανάλωση). Τα πρόσημα: απόθεμα, υπόλοιπο πελάτη/προμηθευτή, ΦΠΑ.

| Κωδικός | Όνομα | side | Απόθεμα | Υπόλοιπο | ΦΠΑ | Τιμές με ΦΠΑ | Θέλει πελάτη/προμηθευτή | Από δελτίο | myDATA |
|---|---|---|---|---|---|---|---|---|---|
| `DEA` | Δελτίο επιστροφής σε προμηθευτή | P | -1 | 0 | 0 | N | Y |  |  |
| `DPA` | Δελτίο παραλαβής | P | 1 | 0 | 0 | N | Y |  |  |
| `PAG` | Πιστωτικό τιμολόγιο αγοράς | P | 0 | -1 | -1 | N | Y | DEA |  |
| `TAD` | Τιμολόγιο - δελτίο παραλαβής | P | 1 | 1 | 1 | N | Y |  |  |
| `TAG` | Τιμολόγιο αγοράς | P | 0 | 1 | 1 | N | Y | DPA |  |
| `ALP` | Απόδειξη λιανικής πώλησης | S | -1 | 0 | 1 | Y | N |  |  |
| `DAP` | Δελτίο αποστολής | S | -1 | 0 | 0 | N | Y |  |  |
| `DEP` | Δελτίο επιστροφής από πελάτη | S | 1 | 0 | 0 | N | Y |  |  |
| `PPY` | Πιστωτικό τιμολόγιο πώλησης | S | 0 | -1 | -1 | N | Y | DEP | 5.1 |
| `TDA` | Τιμολόγιο - δελτίο αποστολής | S | -1 | 1 | 1 | N | Y |  | 1.1 |
| `TPY` | Τιμολόγιο πώλησης | S | 0 | 1 | 1 | N | Y | DAP | 1.1 |
| `DAN` | Δελτίο ανάλωσης | T | -1 | 0 | 0 | N | N |  |  |
| `DEN` | Δελτίο ενδοδιακίνησης | T | -1 | 0 | 0 | N | N |  |  |

## Λάθη MM-1xx

Κάθε κανόνας που δεν τηρείται σταματά με `ORA-20xxx: MM-1xx: μήνυμα`. Το REST τα επιστρέφει ως `400 {"error": "MM-1xx", "message": ...}` (το 177 και το 179 ως 401, το 178 ως 423).

| Κωδικός | Μηνύματα |
|---|---|
| MM-101 | Άγνωστο είδος παραστατικού |
| MM-102 | Το παραστατικό |
| MM-103 | Δεν υπάρχει παραστατικό |
| MM-104 | Το |
| MM-105 | Οι αγορές δεν περνούν από ταμείο |
| MM-106 | Δεν υπάρχει είδος |
| MM-107 | Το είδος |
| MM-108 | Δεν υπάρχει γραμμή |
| MM-109 | Το παραστατικό δεν έχει γραμμές |
| MM-110 | Η απόδειξη λιανικής θέλει ταμείο |
| MM-111 | Η απόδειξη λιανικής πληρώνεται με μετρητά ή κάρτα |
| MM-112 | Το ταμείο δεν έχει ανοιχτό Ζ |
| MM-113 | Ακυρώνεται μόνο καταχωρημένο παραστατικό |
| MM-114 | Το Ζ του παραστατικού έχει κλείσει: κάνε πιστωτικό<br>Το Ζ της έχει κλείσει: κάνε αντίστροφη κίνηση |
| MM-115 | Πιστωτικό γίνεται μόνο για καταχωρημένο τιμολόγιο |
| MM-116 | Η διόρθωση αποθέματος θέλει αιτιολογία |
| MM-117 | Δεν υπάρχει ενεργό ταμείο |
| MM-118 | Το ταμείο έχει ήδη ανοιχτό Ζ |
| MM-119 | Η κίνηση ταμείου θέλει ποσό και αιτιολογία |
| MM-120 | Υπάρχουν πρόχειρα παραστατικά στο ταμείο: καταχώρισέ τα ή σβήσε τα |
| MM-121 | Η απογραφή |
| MM-122 | Δεν υπάρχει απογραφή |
| MM-123 | Δεν βρέθηκε είδος με κωδικό |
| MM-124 | Λάθος ποσότητα<br>Λάθος τιμή<br>Λάθος ποσότητα ή τρόπος (ADD/SET) |
| MM-125 | Το είδος |
| MM-126 | Η ποσότητα ενός είδους με serials αλλάζει με τα serials |
| MM-127 | Το |
| MM-128 | Το |
| MM-129 | Το παραστατικό έχει κάρτες με serials: ακύρωσέ το (όσο το Ζ είναι ανοιχτό) |
| MM-130 | Από τις κάρτες αυτής της αγοράς έχουν πουληθεί ή δεσμευτεί |
| MM-131 | Τα είδη με serials δεν μετριούνται στην απογραφή: το απόθεμά τους είναι οι κάρτες τους |
| MM-132 | Η ομάδα κουμπιών θέλει όνομα<br>Το όνομα της ομάδας: ως 40 χαρακτήρες<br>Το χρώμα της ομάδας: #RRGGBB, π.χ. #8b5a2b<br>Ενεργή: Y ή N<br>Δεν υπάρχει ομάδα κουμπιών<br>Ένα μοντέλο δεν πουλιέται: βάλε μια παραλλαγή του |
| MM-133 | Το απόθεμα ενός είδους με serials αλλάζει με τα serials (load_serial) |
| MM-134 | Λάθος serial: 4 έως 40 γράμματα, ψηφία ή - |
| MM-135 | Λάθος PIN: 4 έως 20 ψηφία |
| MM-136 | Το serial |
| MM-137 | Τα serials φορτώνονται σε τιμολόγιο αγοράς |
| MM-138 | Οι κάρτες πουλιούνται με απόδειξη ή τιμολόγιο πώλησης |
| MM-139 | Δώσε είδος ή serial |
| MM-140 | Δεν υπάρχει διαθέσιμη κάρτα |
| MM-141 | Δεν υπάρχει κάρτα |
| MM-142 | Η κάρτα δεν είναι δεσμευμένη σε πρόχειρο |
| MM-143 | Δεν έχεις δικαίωμα να δεις το PIN |
| MM-144 | Το PIN τυπώνεται μόνο για κάρτα που πουλήθηκε σήμερα |
| MM-145 | Η κράτηση θέλει όνομα και τηλέφωνο |
| MM-146 | Η κράτηση |
| MM-147 | Η προκαταβολή ( |
| MM-148 | Η προκαταβολή θέλει θετικό ποσό, με μετρητά ή κάρτα |
| MM-149 | Η ημερομηνία παραλαβής δεν μπορεί να είναι στο παρελθόν |
| MM-150 | Δεν υπάρχει κράτηση<br>Δεν υπάρχει αυτή η παραγγελία |
| MM-151 | Η κράτηση δεν έχει είδη |
| MM-152 | Τα είδη με serials δεν μπαίνουν σε κράτηση |
| MM-153 | Καλάθι και είδη με serials δεν συνδυάζονται |
| MM-154 | Το |
| MM-155 | Το καλάθι δεν μπαίνει στον εαυτό του |
| MM-156 | Το είδος |
| MM-157 | Το |
| MM-158 | Η προσφορά θέλει όνομα και διάστημα ημερομηνιών<br>Λάθος προσφορά: PCT με 0-100%, NM με N και M, BUNDLE με τιμή<br>Υπάρχει ήδη προσφορά με όνομα<br>Ενεργή: Y ή N<br>Δεν υπάρχει προσφορά |
| MM-159 | Έκπτωση στο σύνολο γίνεται μόνο σε πώληση<br>Λάθος έκπτωση: 0 έως 100% ή θετικό ποσό<br>Η έκπτωση στο σύνολο θέλει αιτιολογία |
| MM-160 | Η προσφορά αφορά είδος ή κατηγορία (ένα από τα δύο)<br>Ένα πακέτο σε τιμή έχει είδη, όχι κατηγορίες |
| MM-161 | Το |
| MM-162 | Το |
| MM-163 | Το |
| MM-164 | Η παραλλαγή θέλει χρώμα ή μέγεθος<br>Δεν υπάρχει χρώμα<br>Δεν υπάρχει μέγεθος |
| MM-165 | Η παραλλαγή (ή ο κωδικός/barcode της) υπάρχει ήδη |
| MM-166 | Το είδος |
| MM-167 | Το ποσό πρέπει να είναι θετικό |
| MM-168 | Τρόπος: μετρητά, κάρτα ή έμβασμα |
| MM-170 | Δεν υπάρχει είσπραξη/πληρωμή<br>Η είσπραξη/πληρωμή έχει ήδη ακυρωθεί |
| MM-171 | Διάλεξε είδος, πελάτη ή προμηθευτή |
| MM-172 | Το διάστημα θέλει «από» και «έως», με το «από» πριν από το «έως» |
| MM-173 | Καρτέλα πελάτη (C) ή προμηθευτή (S)<br>Καρτέλα είδους (I), πελάτη (C) ή προμηθευτή (S)<br>Ισοζύγιο ειδών (I), πελατών (C) ή προμηθευτών (S) |
| MM-174 | Όνομα χρήστη: 3 έως 30 λατινικά γράμματα, ψηφία ή . _ -, από γράμμα |
| MM-175 | Ο κωδικός θέλει τουλάχιστον 10 χαρακτήρες, με γράμματα και ψηφία |
| MM-176 | Ρόλος: CASHIER (ταμίας), MANAGER (προϊστάμενος) ή ADMIN (διαχειριστής) |
| MM-177 | Λάθος όνομα χρήστη ή κωδικός |
| MM-178 | Ο λογαριασμός κλειδώθηκε για λίγα λεπτά, μετά από πολλούς λάθος κωδικούς |
| MM-179 | Χρειάζεται σύνδεση |
| MM-180 | Δεν υπάρχει χρήστης<br>Ενεργός: Y ή N |
| MM-181 | Πρέπει να μείνει τουλάχιστον ένας ενεργός διαχειριστής |
| MM-182 | Υπάρχει ήδη χρήστης |
| MM-183 | Το |
| MM-184 | Το<br>Το δελτίο<br>Το δελτίο είναι άλλου πελάτη ή προμηθευτή<br>Από το |
| MM-185 | Το δελτίο είναι στο |
| MM-186 | Το είδος δεν είναι στην παραγγελία<br>Μαζεύτηκαν από 0 έως |
| MM-187 | Δελτίο αποστολής μόνο για παραγγελία πελάτη (με ΑΦΜ)<br>Η παραγγελία έχει προκαταβολή: παράδοση με απόδειξη |
| MM-188 | Λάθος token παραγγελίας<br>Υπάρχουν ήδη 3 ανοιχτές παραγγελίες με αυτό το τηλέφωνο<br>Η παραγγελία επιβεβαιώθηκε από το μαγαζί: για ακύρωση, τηλεφώνησε στο μαγαζί |
| MM-189 | Το παραστατικό έχει διαβιβαστεί στο myDATA (MARK<br>Το<br>Διαβιβάζεται μόνο καταχωρημένο παραστατικό<br>Έχει ήδη διαβιβαστεί στο myDATA (MARK<br>Ο πελάτης του παραστατικού δεν έχει ΑΦΜ: το myDATA τον θέλει |
| MM-190 | Η έκδοση του σκρατς: 4 ψηφία (τα πρώτα του barcode)<br>Το είδος ενός σκρατς είναι είδος με serials (π.χ. «Σκρατς 1 €»)<br>Δελτία ανά πακέτο: από 1 έως 999<br>Το πακέτο: το barcode ενός δελτίου του (14 ψηφία) ή έκδοση και πακέτο (11 ψηφία)<br>Η έκδοση<br>Το πακέτο |
| MM-191 | Δεν υπάρχει πελάτης<br>Πελάτης με κάρτα μπαίνει μόνο σε απόδειξη λιανικής<br>Η απόδειξη δεν έχει πελάτη: σάρωσε την κάρτα του<br>Πόντοι: ακέραιος, 0 ή περισσότεροι<br>Εξαργύρωση από<br>Ο πελάτης έχει |
| MM-192 | Δεν υπάρχει γραμμή<br>Ημερομηνία λήξης μπαίνει στην παραλαβή από προμηθευτή (δελτίο παραλαβής, τιμολόγιο - δελτίο παραλαβής) |
| MM-193 | Δεν υπάρχει ενεργή αποθήκη<br>Δεν υπάρχει αποθήκη |
| MM-194 | Αιτία έχει μόνο το δελτίο ανάλωσης<br>Αιτία ανάλωσης: USE (ανάλωση), DAMAGE (φθορά), SAMPLE (δείγμα), EXPIRED (λήξη)<br>Η ενδοδιακίνηση και η ανάλωση δεν έχουν πελάτη, προμηθευτή ή ταμείο<br>Η ανάλωση δεν έχει αποθήκη παραλαβής<br>Η ενδοδιακίνηση θέλει άλλη ενεργή αποθήκη παραλαβής<br>Αποθήκη παραλαβής έχει μόνο η ενδοδιακίνηση |
| MM-195 | Το ελάχιστο απόθεμα δεν μπορεί να είναι αρνητικό<br>Το ελάχιστο από το κεντρικό: ένα ενεργό υποκατάστημα |
| MM-196 | Δεν υπάρχει ενεργό ταμείο<br>Το ταμείο του χρήστη πρέπει να είναι του καταστήματός του<br>Δεν υπάρχει ενεργό κατάστημα |
| MM-197 | Δεν επιτρέπεται: |
| MM-198 | Δεν υπάρχει ρόλος<br>Πρέπει να μείνει τουλάχιστον ένας ενεργός χρήστης με όλα τα δικαιώματα<br>Κωδικός ρόλου: 2 έως 30 λατινικά γράμματα, ψηφία ή _, από γράμμα<br>Ο ρόλος θέλει όνομα<br>Όλα τα δικαιώματα: Y ή N<br>Υπάρχει ήδη ρόλος |
| MM-199 | Το ιστορικό κρατιέται τουλάχιστον 30 ημέρες |

_Φτιάχτηκε στις 19/11/2026._
