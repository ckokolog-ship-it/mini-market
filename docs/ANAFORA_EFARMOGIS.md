# Αναφορά της εφαρμογής

Φτιάχνεται αυτόματα από τον κώδικα και τη βάση (`tools/mkdocs.py`): το REST, οι οθόνες και τα δικαιώματά τους, οι σελίδες web, οι φόρμες του Oracle, τα reports, τα tests. Η βάση: [ANAFORA_VASIS.md](ANAFORA_VASIS.md)· η αρχιτεκτονική: [ARXITEKTONIKI.md](ARXITEKTONIKI.md).

## Περιεχόμενα

- [Οθόνες και δικαιώματα](#οθόνες-και-δικαιώματα)
- [Η υπηρεσία REST](#η-υπηρεσία-rest)
- [Φόρμες του Oracle](#φόρμες-του-oracle)
- [Oracle Reports](#oracle-reports)
- [Tests](#tests)

## Οθόνες και δικαιώματα

Το μενού είναι στη βάση (`MM_OBJECT`): κάθε οθόνη είναι μια σελίδα web (`route`), μια φόρμα, ή και τα δύο, με τα ίδια δικαιώματα. N: τίποτα, R: ανάγνωση, W: αλλαγή. Οι ρόλοι του συστήματος όπως εγκαθίστανται· ο `ADMIN` έχει πάντα τα πάντα. Τα αλλάζει η σελίδα «Ρόλοι και δικαιώματα».

### Πωλήσεις

| Οθόνη | Σελίδα | Φόρμα | Ταμίας | Προϊστάμενος | Πεδία και ενέργειες |
|---|---|---|---|---|---|
| **Ταμείο** `POS` | `#/pos` | `MM_POS` | W | W | ενέργεια `OPEN_Z` Άνοιγμα Ζ (W/W)<br>ενέργεια `CLOSE_Z` Κλείσιμο Ζ (W/W)<br>ενέργεια `CASH` Μετρητά μέσα και έξω (W/W)<br>ενέργεια `VOID` Ακύρωση απόδειξης (W/W)<br>ενέργεια `PRIZE` Κέρδος σκρατς (W/W)<br>ενέργεια `WAREHOUSE` Αποθήκη του ταμείου (N/W)<br>ενέργεια `SETTINGS` Κεφαλίδα και υποσέλιδο αποδείξεων (N/W) |
| **Κουμπιά ταμείου** `TILES` | `#/tiles` |  | N | W | ενέργεια `PLU` Σύντομοι κωδικοί (PLU) (N/W) |
| **Παραγγελίες** `ORDERS` | `#/orders` |  | W | W | ενέργεια `CONFIRM` Επιβεβαίωση (W/W)<br>ενέργεια `CANCEL` Ακύρωση (W/W)<br>ενέργεια `NOTE` Δελτίο αποστολής (N/W) |
| **Κρατήσεις** `RESERVATIONS` |  | `MM_RESERVATIONS` | W | W | ενέργεια `CREATE` Νέα (W/W)<br>ενέργεια `DELIVER` Παράδοση (W/W)<br>ενέργεια `CANCEL` Ακύρωση (W/W) |
| **Προσφορές** `PROMOS` |  | `MM_PROMOS` | N | W | ενέργεια `CREATE` Νέα (N/W)<br>ενέργεια `ACTIVE` Ενεργή ή όχι (N/W) |

### Αποθήκη

| Οθόνη | Σελίδα | Φόρμα | Ταμίας | Προϊστάμενος | Πεδία και ενέργειες |
|---|---|---|---|---|---|
| **Είδη** `ITEMS` | `#/items` | `MM_ITEMS` | R | W | πεδίο `PRICE` Τιμή λιανικής (R/W)<br>πεδίο `WHOLESALE_PRICE` Χονδρική (R/W)<br>πεδίο `COST` Κόστος (N/W)<br>πεδίο `FIFO` Κόστος FIFO και στρώσεις (N/W)<br>πεδίο `STOCK` Απόθεμα (R/W)<br>πεδίο `MIN_STOCK` Ελάχιστο (R/W)<br>ενέργεια `CREATE` Νέο (N/W)<br>ενέργεια `DELETE` Διαγραφή (N/W) |
| **Ρούχα και παπούτσια** `VARIANTS` |  | `MM_VARIANTS` | N | W | ενέργεια `CREATE` Νέο (N/W) |
| **Καλάθια και σετ** `KITS` |  | `MM_KITS` | N | W | ενέργεια `ASSEMBLE` Συναρμολόγηση (N/W) |
| **Κάρτες κινητής** `CARDS` |  | `MM_CARDS` | N | W | πεδίο `PIN` PIN (N/W)<br>ενέργεια `LOAD` Φόρτωση (N/W) |
| **Ετικέτες** `LABELS` | `#/labels` |  | W | W |  |
| **Απογραφή** `COUNTS` | `#/counts` |  | W | W | ενέργεια `CREATE` Νέα (N/W)<br>ενέργεια `POST` Καταχώριση (N/W)<br>ενέργεια `CANCEL` Ακύρωση (N/W) |
| **Σκρατς** `SCRATCH` | `#/scratch` |  | N | W | ενέργεια `LOAD` Φόρτωση πακέτου (N/W)<br>ενέργεια `RETURN` Επιστροφή πακέτου (N/W)<br>ενέργεια `GAME` Εκδόσεις (N/W) |
| **Λήξεις** `EXPIRY` | `#/expiry` |  | N | W | ενέργεια `WITHDRAW` Απόσυρση (N/W) |
| **Αποθήκες** `WAREHOUSES` | `#/warehouses` |  | N | W | πεδίο `VALUE` Αξία (N/W)<br>ενέργεια `CREATE` Νέα (N/W)<br>ενέργεια `MIN` Ελάχιστο υποκαταστήματος (N/W)<br>ενέργεια `TRANSFER` Δελτίο από το κεντρικό (N/W) |

### Γραφείο

| Οθόνη | Σελίδα | Φόρμα | Ταμίας | Προϊστάμενος | Πεδία και ενέργειες |
|---|---|---|---|---|---|
| **Τιμολόγια και δελτία** `DOCS` | `#/docs` | `MM_INVOICES` | N | W | πεδίο `COST` Κόστος (N/W)<br>ενέργεια `CREATE` Νέο (N/W)<br>ενέργεια `POST` Καταχώριση (N/W)<br>ενέργεια `CANCEL` Ακύρωση (N/W)<br>ενέργεια `MYDATA` myDATA (N/W) |
| **Εισπράξεις και πληρωμές** `PAYMENTS` | `#/payments` | `MM_PAYMENTS` | N | W | ενέργεια `CREATE` Νέα (N/W)<br>ενέργεια `CANCEL` Ακύρωση (N/W) |
| **Πελάτες** `CUSTOMERS` | `#/partners/customers` | `MM_CUSTOMERS` | N | W | πεδίο `AFM` ΑΦΜ (N/W)<br>πεδίο `CONTACT` Τηλέφωνο, email, διεύθυνση (N/W)<br>πεδίο `BALANCE` Υπόλοιπο (N/W)<br>πεδίο `POINTS` Πόντοι (N/W)<br>ενέργεια `CREATE` Νέος (N/W)<br>ενέργεια `CARD` Κάρτα πόντων (N/W) |
| **Προμηθευτές** `SUPPLIERS` | `#/partners/suppliers` | `MM_SUPPLIERS` | N | W | πεδίο `AFM` ΑΦΜ (N/W)<br>πεδίο `CONTACT` Τηλέφωνο, email, διεύθυνση (N/W)<br>πεδίο `BALANCE` Υπόλοιπο (N/W)<br>ενέργεια `CREATE` Νέος (N/W) |
| **Καρτέλες** `LEDGERS` |  | `MM_LEDGER` | N | W |  |

### Αναφορές

| Οθόνη | Σελίδα | Φόρμα | Ταμίας | Προϊστάμενος | Πεδία και ενέργειες |
|---|---|---|---|---|---|
| **Σύνοψη ημέρας** `DAY` | `#/day` |  | N | R |  |
| **Γράφημα πωλήσεων** `CHART` | `#/chart` |  | N | R |  |
| **Πωλήσεις** `REP_SALES` | `#/reports/sales` |  | N | R |  |
| **Πωλήσεις ανά κατάστημα και ταμία** `REP_SALES_BY` | `#/reports/sales-by` |  | N | R |  |
| **ΦΠΑ** `REP_VAT` | `#/reports/vat` |  | N | R |  |
| **Ελάχιστο απόθεμα** `REP_MIN_STOCK` | `#/reports/min-stock` |  | N | W | ενέργεια `ORDER` Παραγγελίες σε προμηθευτές (N/W) |
| **Ισοζύγιο ειδών** `TRIAL_ITEMS` | `#/reports/trial-items` |  | N | R |  |
| **Ισοζύγιο πελατών** `TRIAL_CUSTOMERS` | `#/reports/trial-customers` |  | N | R |  |
| **Ισοζύγιο προμηθευτών** `TRIAL_SUPPLIERS` | `#/reports/trial-suppliers` |  | N | R |  |
| **Μικτό κέρδος** `PROFIT` | `#/reports/profit` |  | N | R |  |
| **Αναλώσεις** `REP_CONSUMPTION` | `#/reports/consumption` |  | N | R |  |
| **Αξία αποθήκης** `STOCK_VALUE` | `#/reports/stock-value` |  | N | W | ενέργεια `COST_METHOD` Τρόπος κοστολόγησης (N/W) |
| **Αναφορές PDF** `REPORTS_PDF` |  | `MM_REPORTS` | N | R |  |

### Διαχείριση

| Οθόνη | Σελίδα | Φόρμα | Ταμίας | Προϊστάμενος | Πεδία και ενέργειες |
|---|---|---|---|---|---|
| **Χρήστες** `USERS` | `#/users` | `MM_USERS` | N | N | ενέργεια `CREATE` Νέος (N/N)<br>ενέργεια `PASSWORD` Κωδικός (N/N)<br>ενέργεια `PLACE` Κατάστημα και ταμείο (N/N) |
| **Ρόλοι και δικαιώματα** `ROLES` | `#/roles` |  | N | N |  |
| **Ιστορικό ενεργειών** `AUDIT` | `#/audit` |  | N | N |  |

## Η υπηρεσία REST

Η υπηρεσία `mm-api` (Java, `api/`): `/api/...` σε JSON, με token από το login. Κάθε κλήση ελέγχεται με τα δικαιώματα (`Rights.java`). Οδηγίες: [ODIGIES_REST.md](ODIGIES_REST.md).

### Api.java

The endpoints (JSON). Dates in and out as YYYY-MM-DD; a period: ?from=&to= (from the 1st of January to today when not given). A login first (POST /api/auth/login): then "Authorization: Bearer <token>" on every call but /api/health. The roles: CASHIER (the items, the counts), MANAGER (and the customers, the suppliers, the ledgers, the reports, a count started, posted, cancelled), ADMIN (all).

```
  POST /api/auth/login {username, password}  its token (12 hours), role       (anyone)
  POST /api/auth/logout   GET /api/auth/me   the end of the session; who it is
  GET /api/auth/rights                       its menu and its rights (Rights: every call is checked by them)
  /api/health                                the service and its database   (anyone)
  /api/items?q=&limit=&offset=               the items (code, barcode, name, price, stock ...)
  /api/items/{barcode or code}               one item, as the till finds it, with what is reserved
  /api/customers?q=   /api/customers/{id}    the customers; one with its balance
  /api/suppliers?q=   /api/suppliers/{id}    the suppliers; one with its balance
  /api/ledger/{item|customer|supplier}/{id}  a ledger (MM_LEDGER): carry-over, moves, totals;
                                             with ?limit=&offset= a page of its moves, its carry_in, carry_out
  /api/reports/sales   /api/reports/vat   /api/reports/min-stock
  /api/scratch/...                           the scratch tickets in packs: see Scratch (MANAGER)
  /api/warehouses                            the warehouses (the main one first), what each has; an item: its
                                             stock in each. POST /api/warehouses {code, name}, /api/warehouses/{id}
                                             {name, active} (MANAGER)
  /api/warehouses/{id}                       a branch and its minimum stock: the items, what is missing,
                                             what the central store has; its drafts DEN. POST .../min
                                             {code, min} (0: none), POST .../transfer: what is missing,
                                             a draft DEN from the central store (MANAGER)
  /api/users   POST /api/users {username, full_name, role, password, warehouse_id, register_id}
  POST /api/users/{id} {full_name, role, active, password, unlock, warehouse_id, register_id}
                                             the users and where each works: its store, its register
                                             (mm_auth.set_place; the till: mm_auth.may_use) (ADMIN)
  /api/audit?from=&to=&user=&action=&q=&limit=&offset=   the history of what was done and the logins
                                             (MM_AUDIT_ALL), the newest first (AUDIT)
  /api/expiry?days=   POST /api/expiry/withdraw   the goods expiring, expired; one taken out (Expiry.java)
  /api/chart?to=&days=                       the charts of the sales: by day (and a year before), by hour
                                             (MANAGER, Chart.java)
  /api/day?date=                             the summary of a day: its Z, sales, VAT, items, scratch, orders,
                                             myDATA, minimum stock, backup (MANAGER, Day.java)
  /api/backup                              the last backup (db/backup.ps1): state OK, OLD, FAILED, NEVER (MANAGER)
  /api/reports/trial-items|trial-customers|trial-suppliers?from=&to=&all=1   the trial balances
  /api/reports/profit?from=&to=&method=   /api/reports/stock-value?method=   the gross profit, the value
                                             of the stock: FIFO or LAST (the cost of the last purchase)
  POST /api/reports/cost-method {method}     the way the shop counts its costs: FIFO or LAST
                                             (ισοζύγια): a row each with the totals of its ledger, no moves
  GET /api/counts   GET /api/counts/{id}      the counts of the stock; one with its lines
  POST /api/counts {name}                     a new count                    (MANAGER)
  POST /api/counts/{id}/scan {code, qty, mode ADD|SET, device}   a scan of a phone
  POST /api/counts/{id}/post   .../cancel     the count to the stock, or dropped (MANAGER)
  /api/pos/...                               the till: see Pos
  /api/orders/...                            the orders: see Orders
  /api/shop/...                              the page of the customers, no login: see Shop
  /api/docs/..., /api/doc-types, /api/payments/...   the office: invoices, notes, receipts (MANAGER): see Docs
```

### Chart.java

The charts of the sales (γράφημα πωλήσεων): the days of a period up to a day, each with the same day of a year before (364 days back: the same day of the week), the hours of the day, the totals. MANAGER.

```
  GET /api/chart?to=YYYY-MM-DD&amp;days=30   (to: default today; days 7 to 364)
    days     day, total (all the sales, MM_SALES_DAY), receipts, their total, last_year (the total then)
    hours    hour 0-23: the receipts of the period posted then, their total (less what came back)
    sums     total, last_year, receipts, their total, avg_receipt
```

### Day.java

The summary of a day (σύνοψη ημέρας), for a manager after the Z: in one answer what the pages show in many. MANAGER.

```
  GET /api/day?date=YYYY-MM-DD   (default today)
    zs        the Z of the registers on that day: receipts, total, cash, card, money in and out, drawer
    sales     the sales of the day (MM_SALES_DAY), vat its VAT by rate (MM_VAT_DAY)
    profit    its gross profit: revenue (net), cost (FIFO or LAST: COST_METHOD), profit
    top       the 10 items sold most (by value) out of the stock that day (less what came back)
    scratch   the scratch tickets sold and their value, the prizes paid
    orders    the orders written that day (online of them), the open ones now (online not confirmed)
    mydata    the invoices of the day to myDATA by state; waiting or failed now (any day)
    min_stock how many items are under their minimum now
    expiry    the receipts of goods expired (something left of them) and expiring in EXPIRY_DAYS, now
    backup    the state of the backup (MM_BACKUP_STATE)
```

### Db.java

The database: a pool of connections (UCP), the queries with bind variables, the rows as maps.

### Docs.java

The documents of the office (as the form MM_INVOICES: every kind but the retail receipts) and the receipts and payments (as MM_PAYMENTS), through MM_CORE. MANAGER and above.

```
  GET  /api/doc-types                            the kinds of documents (what each does)
  GET  /api/docs?type=&status=&q=&limit=&offset=  the documents, the last first
  GET  /api/docs/notes?type=&customer_id=&supplier_id=   the posted notes not in an invoice yet
  GET  /api/docs/{id}                            one: its lines; an invoice its notes, a note its invoice
  POST /api/docs {doc_type, customer_id|supplier_id, payment, doc_date, warehouse_id}   a new draft
  POST /api/docs {doc_type DEN, warehouse_id, to_warehouse_id}   a transfer between two warehouses (at cost)
  POST /api/docs {doc_type DAN, warehouse_id, reason}   a consumption: out of a warehouse at cost, for a reason
                                                 (USE, DAMAGE, SAMPLE, EXPIRED); POST /api/docs/{id}/reason {reason}
  POST /api/docs {from_note, doc_date}           a new draft invoice of a note (invoice_from)
  POST /api/docs/{id}/lines {code, qty, price, discount, expires}   a line (a card of a sale: qty of them);
                                                 expires YYYY-MM-DD: goods received (DPA, TAD)
  POST /api/docs/{id}/lines/{line} {qty, price, discount, expires}  a line changed; qty 0: out; expires
                                                 "" or null: none (only the fields given change)
  POST /api/docs/{id}/notes {note_id}            one more note into the draft invoice
  POST /api/docs/{id}/post | cancel | delete     posted (its number), cancelled, a draft deleted
  POST /api/docs/{id}/credit                     goods back: a draft return note of its lines
  POST /api/docs/from-min-stock {supplier_id}    the orders to the suppliers: drafts DPA of what is
                                                 under the minimum stock (mm_core.order_missing)
  GET  /api/docs/{id}/mydata                     the XML of myDATA (checked by the XSD of AADE)
  POST /api/docs/{id}/mydata  .../mydata/cancel  sent to myDATA now; cancelled there and here (MyData)
  GET  /api/payments?kind=R|P&q=&limit=&offset=  receipts (R) and payments (P)
  POST /api/payments {kind, partner_id, amount, method, pay_date, notes, register}
  POST /api/payments/{id}/cancel
```

### Expiry.java

The expiry of the goods (λήξεις): the date of each line of goods received (Docs: {expires}), what is left of it by FIFO (MM_EXPIRY of db/MM_REPORT.sql); those expiring in the next days or expired; what is left of one taken out of the stock (a move of the stock by hand). MANAGER.

```
  GET  /api/expiry?days=N&warehouse=CODE      expired, and expiring in N days (default MM_SETTING
                                              EXPIRY_DAYS, else 7): rows (each with its warehouse), days;
                                              of one warehouse (none: all)
  POST /api/expiry/withdraw {fifo_id, qty}    out of the stock of its warehouse (qty: default what is
                                              left of it); {line_id}: the first of that receipt
```

### Http.java

The answers (JSON, UTF-8) and the errors of the service.

### MyData.java

myDATA of AADE: the invoices (1.1) and the credit notes (5.1 of an invoice sent, else 5.2) of the sales, as the REST API of AADE for an ERP (docs/mydata, v1.0.12 of the XSD in resources/mydata): the XML of a document (checked against the XSD before it goes), SendInvoices, its MARK, UID and QR back into MM_DOC (mm_core.mydata_sent); CancelInvoice. The retail receipts go through the cash register (ΦΗΜ) or a provider, not from here. The account (never in git): the file MM_MYDATA_CONFIG (default mydata.properties in the folder of the service): url (default https://mydataapidev.aade.gr, the tests of AADE; the real one https://mydatapi.aade.gr/myDATA), user, key. Without it nothing is sent: the documents wait (Q). Every minute the documents waiting (Q, e.g. posted by a form with MYDATA_AUTO Y) are sent. The shop: MM_SETTING MYDATA_AFM (its ΑΦΜ), MYDATA_BRANCH (0 the seat), MYDATA_VAT_EXEMPTION (the cause, table 8.3, of a line of 0% VAT); db/SET_MYDATA.sql.

```
  GET  /api/docs/{id}/mydata          the XML that would go (text/xml), checked
  POST /api/docs/{id}/mydata          queued and sent now; the document back
  POST /api/docs/{id}/mydata/cancel   its cancellation at AADE (CancelInvoice), then cancel_doc
```

### Orders.java

The orders: a reservation (MM_RESERVATION) written from the pages, by a phone in the shop or on a call, its lines reserved (the stock "reserved" until it is delivered), picked from the shelves, ready, then at the till all of it into a receipt (POST /api/pos/{register}/order) or, for a customer on credit, a delivery note. CASHIER and above; the delivery note MANAGER.

```
  GET  /api/orders?status=O|D|C|all&q=          the orders (the open ones first by their day)
  GET  /api/orders/{id}                         one with its lines
  GET  /api/orders/new                          the orders of the customers not confirmed yet: count, last_id, last_name
  POST /api/orders {name, phone, customer_id, pickup_date, notes}   a new one (by whom: the login)
  POST /api/orders/{id}/lines {code, qty, mode ADD|SET}   an item in (ADD: one more of it), 0 out
  POST /api/orders/{id}/pick {item_id, qty}     what of a line was picked
  POST /api/orders/{id}/ready {ready}           ready (all picked) or not
  POST /api/orders/{id}/cancel {register}       cancelled (a deposit back through that register)
  POST /api/orders/{id}/note                    a delivery note, posted (MANAGER)
  POST /api/orders/{id}/confirm                 an order of a customer (the page /shop/) confirmed
```

### Pos.java

The till of the pages (as the form MM_POS): a register by its code, its Z, the draft receipt of the register (made at the first scan), its lines, paid by cash or card. Every call returns the state of the register, as the screen shows it. CASHIER and above.

```
  GET  /api/pos                              the registers the user may work on (mm_auth.may_use: its
                                             store, its register: mine Y), each with its open Z (or none);
                                             another register: 403 not_your_register
  GET  /api/pos/{register}                   its Z (with what it holds so far), the draft, the last receipts
  POST /api/pos/{register}/open {cash}       a Z opened, with the cash in the drawer
  POST /api/pos/{register}/close             the Z closed: its totals in "closed"
  POST /api/pos/{register}/cash {amount, note}   money in (+) or out (-) of the drawer
  GET  /api/pos/tiles                        the buttons of the till (Tiles: groups, tiles, the frequent)
  POST /api/pos/{register}/item {item_id, qty, options}   a button of the till: the item, as a scan of its
                                             code, with the options chosen (their ids; none: the defaults)
  POST /api/pos/{register}/scan {code, qty}  an item by barcode, code or short number (PLU) (a card of mobile: one, the
                                             oldest), or a card by its serial (a scratch ticket: its barcode)
  POST /api/pos/{register}/prize {amount, ticket}   a prize of a scratch ticket, paid from the drawer
  POST /api/pos/{register}/customer {code}   the customer of the receipt (points): its card (a scan of it
                                             at /scan works as well) or its phone; none: out of the receipt
  POST /api/pos/{register}/customer/new {name, phone}   a new customer with a card, into the receipt
  POST /api/pos/{register}/points {points}   points of its customer used on the receipt (0: none)
  POST /api/pos/{register}/warehouse {warehouse_id}   the warehouse its sales are from (MANAGER)
  POST /api/pos/{register}/lines/{id} {qty}  the quantity of a line (0: the line out)
  POST /api/pos/{register}/void              the draft out (an order in it: open again)
  POST /api/pos/{register}/order {id}        an order (Orders), all of its lines, into the receipt
  GET  /api/pos/{register}/receipt/{id}      a receipt of the register to print (80 mm): the header and
                                             the footer of the shop, its lines, its VAT, the PINs of
                                             its cards sold today (each print in MM_PIN_LOG, by whom)
  GET  /api/pos/settings                     the header and the footer of the receipts
  POST /api/pos/settings {header, footer}    (MANAGER)
  POST /api/pos/{register}/pay {payment CASH|CARD, given}   posted: its number, total, what was due
                                             (less a deposit of its order) and the change
```

### Rights.java

The rights of a user (MM_RIGHTS: its roles, the screens, their fields and actions) on the calls of the service: each call is a screen (read: R) or an action of it (W), checked before it runs (403 forbidden); the fields of a screen the user may not read: null in what it returns.

```
  GET /api/auth/rights      the menu of the user (its groups, their screens with a page) and its rights:
                            {"ITEMS": "R", "ITEMS.COST": "N", "POS.OPEN_Z": "W", ...}
```

### Roles.java

The roles, their rights and the menu (MM_RIGHTS), for the page «Ρόλοι και δικαιώματα»: the screen ROLES (read: R, a change: W; Rights).

```
  GET  /api/roles                            the roles: their users, how many grants
  POST /api/roles {code, name}               a new role (no rights yet)
  POST /api/roles/{code} {name, active}      renamed, (not) active
  POST /api/roles/{code}/copy {from}         the rights of another role (what it had: replaced)
  POST /api/roles/{code}/delete              out (not a role of the system)
  GET  /api/roles/{code}/grants              the menu with what the role may do: each screen, its fields and
                                             actions: grant (its row: N R W, or null) and lvl (what it comes to)
  POST /api/roles/{code}/grants {screen, item, level}   one grant (level null: its row out)
  POST /api/users/{id}/roles {roles: [code]} the roles of a user (Api)
  GET  /api/menu                             the menu: its groups and screens, the inactive ones too
  POST /api/menu/{code} {name, sort_no, group, active}   renamed, moved, (not) active
```

### Scratch.java

The scratch tickets (σκρατς): bought in packs (e.g. 300 of 1 €), sold one by one by the barcode of each ticket (its game 4 digits, its pack 7, its number 3: its serial too, MM_SCRATCH_GAME and mm_core.load_pack of db/MM_CORE.sql). MANAGER; a prize at the till: Pos (/api/pos/{register}/prize).

```
  GET  /api/scratch                         the games, the packs (tickets, sold, left), the prizes by day
  POST /api/scratch/games {game, code, pack_size}   a game (έκδοση) and the item it is sold as
  POST /api/scratch/packs {code, count}     a pack loaded: the barcode of one of its tickets (14 digits)
                                            or its game and pack (11); count: else the size of its game
  POST /api/scratch/returns {code}          its tickets not sold back to the supplier (void, out of the stock)
```

### Shop.java

The page of the shop for its customers (/shop/, the WiFi of the shop): no login. Only what a customer may see (the active items with their retail price and whether there are any: no cost, no stock, no cards with a PIN) and an order of a name and a phone, for today; the shop confirms it (a call) and it goes on as any order (Orders: picked, ready, the till). The page of its status by a token, not by its number. At most MM_SHOP_ORDERS orders (10) an address in 10 minutes; 40 lines, up to 99 of each.

```
  GET  /api/shop/info                        the name of the shop (the first line of the receipts)
  GET  /api/shop/categories                  the categories with items to order
  GET  /api/shop/items?q=&category=&limit=&offset=   the items: code, name, unit, price, available
  POST /api/shop/orders {name, phone, notes, lines: [{code, qty}]}   an order: its token
  GET  /api/shop/orders/{token}              its status, its lines, its total
  POST /api/shop/orders/{token}/cancel       cancelled, while the shop has not confirmed it
```

### Tiles.java

The buttons of the till (a cafe: coffees, juices, sweets without a barcode): groups of buttons, in each the items as tiles, and the short number of an item (PLU, typed at the till instead of a scan). Every rule is in mm_core (tile_group_save, tile_add, tile_move, set_plu ...); errors MM-132. The page: the recipe of each tile ("recipe", its cost by the last price of each material "recipe_cost"), the materials of each option ("components"). The till: each tile has the ids of its groups of options ("option_groups"), the groups with their active options in "options". The page: every group of options, its options, and the groups of each tile. Each POST returns the page again, as GET /api/tiles.

```
  GET  /api/pos/tiles                        the till: the active groups with their tiles (active items),
                                             and "frequent": the 8 tiles sold most in the last 7 days
  GET  /api/tiles                            the page Κουμπιά ταμείου: every group (and the inactive), its tiles
  POST /api/tiles/groups {name, color, active}           a new group, at the end
  POST /api/tiles/groups/{id} {name, color, active}      a group changed
  POST /api/tiles/groups/{id}/move {dir}     one place before (-1) or after (+1)
  POST /api/tiles/groups/{id}/delete         out, with its tiles
  POST /api/tiles/groups/{id}/tiles {code}   an item (its code, barcode or PLU) into the group, at its end
  POST /api/tiles/{id}/move {dir}            a tile one place before or after
  POST /api/tiles/{id}/delete                a tile out (the item stays)
  POST /api/tiles/plu {code, plu}            the PLU of an item (null: none)   (TILES: PLU)
  POST /api/tiles/options {name, pick, required, active}       a new group of options (pick O: one of
                                             them, M: any; required: a group O)
  POST /api/tiles/options/{id} {name, pick, required, active}  a group of options changed
  POST /api/tiles/options/{id}/move {dir}    /delete   (used on a receipt: not, inactive instead)
  POST /api/tiles/options/{id}/add {name, price, default}       an option into the group
  POST /api/tiles/option/{id} {name, price, default, active}    an option changed
  POST /api/tiles/option/{id}/move {dir}     /delete
  POST /api/tiles/item-options {code, group_id, on}   a group of options on an item (on: true) or off
  POST /api/tiles/recipe {code, component, qty}      the recipe of an item (a kit never assembled: a sale
                                             takes its materials): a material (its code) and how much
                                             of it (0: out)
  POST /api/tiles/option/{id}/component {component, qty}   the materials of an option: more (qty > 0)
                                             or less of one of the recipe (< 0); 0: out
```

### Web.java

The pages of the shop (step 8): index.html, app.js, codes.js (the barcodes and QR codes of the labels), scan.js and zxing.min.js (the camera as a scanner), app.css from the jar; and /shop/ (shop.html, shop.js: the page of the customers, no login) (resources/web), at http://host:8090/. They speak to /api/ with the token of their login. Only these files, only GET; a Content-Security-Policy of this server only (no script, style or connection elsewhere).

## Φόρμες του Oracle

Οι φόρμες φτιάχνονται από το `forms/mkforms.py` (XML → `.fmb` → `.fmx`, `build_forms.ps1`). Όλες έχουν το ίδιο πακέτο `UI` (`forms/MM_UI.pls`): τα triggers μόνο το καλούν. Οδηγίες: [ODIGIES_FORMS.md](ODIGIES_FORMS.md).

| Φόρμα | Τίτλος | Οθόνη | Blocks (πίνακας) | Κουμπιά |
|---|---|---|---|---|
| `MM_ITEMS` | Είδη | `ITEMS` | `ITEM` (MM_ITEM), `WS` (MM_ITEM_WAREHOUSE) |  |
| `MM_CUSTOMERS` | Πελάτες | `CUSTOMERS` | `PARTNER` (MM_CUSTOMER) |  |
| `MM_SUPPLIERS` | Προμηθευτές | `SUPPLIERS` | `PARTNER` (MM_SUPPLIER) |  |
| `MM_CARDS` | Κάρτες κινητής | `CARDS` | `CARD` (MM_ITEM), `SER` (MM_SERIAL) | Φόρτωσε, Δείξε PIN |
| `MM_RESERVATIONS` | Κρατήσεις | `RESERVATIONS` | `RES` (MM_RESERVATION), `RL` (MM_RESERVATION_LINE) | Νέα κράτηση, Βάλε / άλλαξε, Μαζεύτηκε, Προκαταβολή, Παράδοση (απόδειξη), Ακύρωση κράτησης, Έτοιμη / όχι, Δελτίο αποστολής |
| `MM_KITS` | Καλάθια και σετ | `KITS` | `KIT` (MM_ITEM), `KC` (MM_KIT_COMPONENT) | Βάλε / άλλαξε, Συναρμολόγησε (-: λύσε) |
| `MM_PROMOS` | Προσφορές | `PROMOS` | `PROMO` (MM_PROMO), `PI` (MM_PROMO_ITEM) | Νέα προσφορά, Ενεργή / ανενεργή, Βάλε / βγάλε |
| `MM_VARIANTS` | Ρούχα και παπούτσια | `VARIANTS` | `MODEL` (MM_ITEM), `VG` (MM_ITEM) | Τιμή σε όλες, Νέα παραλλαγή |
| `MM_INVOICES` | Τιμολόγια | `DOCS` | `DOC` (MM_DOC), `DL` (MM_DOC_LINE), `DS` (MM_SERIAL) | Νέο, Καταχώριση, Ακύρωση, Επιστροφή, Σβήσε πρόχειρο, Διαβίβαση myDATA, Από δελτίο, Βάλε γραμμή, Σβήσε τη γραμμή, Βάλε serial, Βγάλε serial |
| `MM_PAYMENTS` | Εισπράξεις και πληρωμές | `PAYMENTS` | `PAY` (MM_PAYMENT) | Καταχώριση, Ακύρωση |
| `MM_LEDGER` | Καρτέλες | `LEDGERS` | `LED` (MM_LEDGER_ROW) | Καρτέλα είδους, Καρτέλα πελάτη, Καρτέλα προμηθευτή, Εκτύπωση |
| `MM_POS` | Ταμείο λιανικής | `POS` | `PL` (MM_DOC_LINE) | Άνοιγμα Ζ, Κλείσιμο Ζ, Βάλε, Σβήσε τη γραμμή, Ακύρωση απόδειξης, Μετρητά, Κάρτα |
| `MM_REPORTS` | Αναφορές | `REPORTS_PDF` |  | Πωλήσεις ανά ημέρα (μήνες), ΦΠΑ πωλήσεων και αγορών, Ελάχιστο απόθεμα (σήμερα), Ισοζύγιο ειδών, Ισοζύγιο πελατών, Ισοζύγιο προμηθευτών, Καρτέλες (είδους, πελάτη, προμηθευτή), Παραγγελίες από το ελάχιστο απόθεμα |
| `MM_LOGIN` | Σύνδεση |  |  | Σύνδεση, Έξοδος |
| `MM_USERS` | Χρήστες | `USERS` | `USR` (MM_USER) | Νέος χρήστης, Νέος κωδικός (επιλεγμένου), Ρόλος (επιλεγμένου), Ενεργός / ανενεργός, Ξεκλείδωμα, Βλέπει PIN: ναι / όχι, Κατάστημα και ταμείο |
| `MM_MAIN` | Mini market |  |  | Είδη, Πελάτες, Προμηθευτές, Κάρτες κινητής, Κρατήσεις, Καλάθια και σετ, Προσφορές, Ρούχα και παπούτσια, Τιμολόγια, Εισπράξεις και πληρωμές, Καρτέλες, Αναφορές, Ταμείο λιανικής, Χρήστες, Αποσύνδεση, Έξοδος |

**Τα δικαιώματα μέσα στις φόρμες** (`FORM_RIGHTS`): F πεδίο (κρυφό χωρίς δικαίωμα, μόνο για ανάγνωση με R), B κουμπί (απενεργοποιημένο χωρίς το δικαίωμα).

| Φόρμα | Τι | Οθόνη.δικαίωμα | Item |
|---|---|---|---|
| `MM_ITEMS` | πεδίο | `ITEMS.PRICE` | `ITEM.PRICE` |
| `MM_ITEMS` | πεδίο | `ITEMS.WHOLESALE_PRICE` | `ITEM.WHOLESALE_PRICE` |
| `MM_ITEMS` | πεδίο | `ITEMS.COST` | `ITEM.COST` |
| `MM_ITEMS` | πεδίο | `ITEMS.MIN_STOCK` | `ITEM.MIN_STOCK` |
| `MM_ITEMS` | πεδίο | `ITEMS.STOCK` | `ITEM.STOCK` |
| `MM_ITEMS` | πεδίο | `ITEMS.STOCK` | `WS.STOCK` |
| `MM_ITEMS` | πεδίο | `ITEMS.STOCK` | `WS.MISSING` |
| `MM_ITEMS` | πεδίο | `ITEMS.MIN_STOCK` | `WS.MIN_STOCK` |
| `MM_ITEMS` | πεδίο | `ITEMS.COST` | `WS.VALUE_` |
| `MM_CUSTOMERS` | πεδίο | `CUSTOMERS.AFM` | `PARTNER.AFM` |
| `MM_CUSTOMERS` | πεδίο | `CUSTOMERS.AFM` | `PARTNER.DOY` |
| `MM_CUSTOMERS` | πεδίο | `CUSTOMERS.CONTACT` | `PARTNER.ADDRESS` |
| `MM_CUSTOMERS` | πεδίο | `CUSTOMERS.CONTACT` | `PARTNER.PHONE` |
| `MM_CUSTOMERS` | πεδίο | `CUSTOMERS.CONTACT` | `PARTNER.EMAIL` |
| `MM_SUPPLIERS` | πεδίο | `SUPPLIERS.AFM` | `PARTNER.AFM` |
| `MM_SUPPLIERS` | πεδίο | `SUPPLIERS.AFM` | `PARTNER.DOY` |
| `MM_SUPPLIERS` | πεδίο | `SUPPLIERS.CONTACT` | `PARTNER.ADDRESS` |
| `MM_SUPPLIERS` | πεδίο | `SUPPLIERS.CONTACT` | `PARTNER.PHONE` |
| `MM_SUPPLIERS` | πεδίο | `SUPPLIERS.CONTACT` | `PARTNER.EMAIL` |
| `MM_CARDS` | κουμπί (W) | `CARDS.LOAD` | `CTL.LOAD` |
| `MM_CARDS` | κουμπί (R) | `CARDS.PIN` | `CTL.PIN` |
| `MM_CARDS` | πεδίο | `CARDS.PIN` | `SER.PIN_SHOW` |
| `MM_CARDS` | πεδίο | `ITEMS.PRICE` | `CARD.PRICE` |
| `MM_RESERVATIONS` | κουμπί (W) | `RESERVATIONS.CREATE` | `CTL.NEWRES` |
| `MM_RESERVATIONS` | κουμπί (W) | `RESERVATIONS.DELIVER` | `CTL.DELIVER` |
| `MM_RESERVATIONS` | κουμπί (W) | `RESERVATIONS.CANCEL` | `CTL.CANCELRES` |
| `MM_RESERVATIONS` | πεδίο | `CUSTOMERS.CONTACT` | `RES.PHONE` |
| `MM_KITS` | κουμπί (W) | `KITS.ASSEMBLE` | `CTL.ASSEMBLE` |
| `MM_KITS` | πεδίο | `ITEMS.PRICE` | `KIT.PRICE` |
| `MM_KITS` | πεδίο | `ITEMS.COST` | `KIT.COST` |
| `MM_KITS` | πεδίο | `ITEMS.STOCK` | `KIT.STOCK` |
| `MM_PROMOS` | κουμπί (W) | `PROMOS.CREATE` | `CTL.NEWPROMO` |
| `MM_PROMOS` | κουμπί (W) | `PROMOS.ACTIVE` | `CTL.TOGGLE` |
| `MM_VARIANTS` | κουμπί (W) | `VARIANTS.CREATE` | `CTL.NEWVAR` |
| `MM_VARIANTS` | κουμπί (W) | `ITEMS.PRICE` | `CTL.MPRICE` |
| `MM_VARIANTS` | πεδίο | `ITEMS.PRICE` | `MODEL.PRICE` |
| `MM_VARIANTS` | πεδίο | `ITEMS.PRICE` | `VG.PRICE` |
| `MM_VARIANTS` | πεδίο | `ITEMS.STOCK` | `VG.STOCK` |
| `MM_INVOICES` | κουμπί (W) | `DOCS.CREATE` | `CTL.NEWDOC` |
| `MM_INVOICES` | κουμπί (W) | `DOCS.CREATE` | `CTL.CREDIT` |
| `MM_INVOICES` | κουμπί (W) | `DOCS.CREATE` | `CTL.FROMNOTE` |
| `MM_INVOICES` | κουμπί (W) | `DOCS.POST` | `CTL.POSTDOC` |
| `MM_INVOICES` | κουμπί (W) | `DOCS.CANCEL` | `CTL.CANCELDOC` |
| `MM_INVOICES` | κουμπί (W) | `DOCS.MYDATA` | `CTL.MYDATA` |
| `MM_PAYMENTS` | κουμπί (W) | `PAYMENTS.CREATE` | `CTL.NEWPAY` |
| `MM_PAYMENTS` | κουμπί (W) | `PAYMENTS.CANCEL` | `CTL.CANCELPAY` |
| `MM_POS` | κουμπί (W) | `POS.OPEN_Z` | `CTL.OPENZ` |
| `MM_POS` | κουμπί (W) | `POS.CLOSE_Z` | `CTL.CLOSEZ` |
| `MM_POS` | κουμπί (W) | `POS.VOID` | `CTL.VOIDREC` |
| `MM_REPORTS` | κουμπί (R) | `REP_SALES` | `CTL.RPT_SALES` |
| `MM_REPORTS` | κουμπί (R) | `REP_VAT` | `CTL.RPT_VAT` |
| `MM_REPORTS` | κουμπί (R) | `REP_MIN_STOCK` | `CTL.RPT_MIN` |
| `MM_REPORTS` | κουμπί (R) | `TRIAL_ITEMS` | `CTL.RPT_TRIAL_I` |
| `MM_REPORTS` | κουμπί (R) | `TRIAL_CUSTOMERS` | `CTL.RPT_TRIAL_C` |
| `MM_REPORTS` | κουμπί (R) | `TRIAL_SUPPLIERS` | `CTL.RPT_TRIAL_S` |
| `MM_REPORTS` | κουμπί (W) | `REP_MIN_STOCK.ORDER` | `CTL.ORDERMIN` |
| `MM_USERS` | κουμπί (W) | `USERS.CREATE` | `CTL.NEWUSER` |
| `MM_USERS` | κουμπί (W) | `USERS.PASSWORD` | `CTL.SETPW` |
| `MM_USERS` | κουμπί (W) | `ROLES` | `CTL.SETROLE` |
| `MM_USERS` | κουμπί (W) | `USERS.PLACE` | `CTL.SETPLACE` |

## Oracle Reports

Τα reports φτιάχνονται από το `reports/mkreports.py` (XML → `.rdf`, `build_reports.ps1`) και ανοίγουν σε PDF από τις φόρμες και τις σελίδες, μέσω του Reports Server. Οδηγίες: [ODIGIES_REPORTS.md](ODIGIES_REPORTS.md).

| Report | Από | Παράμετροι |
|---|---|---|
| `MM_LEDGER_I` | `mm_ledger.report_rows` (καρτέλα είδους) | P_KIND, P_ID, P_FROM, P_TO |
| `MM_LEDGER_P` | `mm_ledger.report_rows` (καρτέλα πελάτη ή προμηθευτή) | P_KIND, P_ID, P_FROM, P_TO |
| `MM_SALES` | `mm_sales_day` | P_FROM, P_TO |
| `MM_VAT` | `mm_vat_day` | P_FROM, P_TO |
| `MM_MIN_STOCK` | `mm_min_stock` | — |
| `MM_TRIAL_I` | `table(mm_ledger.trial_rows` | P_FROM, P_TO |
| `MM_TRIAL_C` | `table(mm_ledger.trial_rows` | P_FROM, P_TO |
| `MM_TRIAL_S` | `table(mm_ledger.trial_rows` | P_FROM, P_TO |

## Tests

Σε Python (`pytest`, `oracledb`), πάνω σε ζωντανή βάση· τα tests του REST ξεκινούν το `mm-api.jar`, και όσα του browser τρέχουν Chromium (Playwright). `MM_DSN=mm/<κωδικός>@localhost:1521/FREEPDB1 python -m pytest tests`.

| Αρχείο (tests) | Τι ελέγχει (από το σχόλιο του αρχείου) |
|---|---|
| `test_api.py` (17) | the REST service (api/, mm-api.jar) on a live database: it starts the jar on a free port of this computer, with MM_DSN, and asks it as a client would: a login first (its users: a manager and a cashier, tst...), then each call with its token; the roles; a count of the stock as the phones of step 9 will do it. |
| `test_audit.py` (3) | the history of what was done (MM_AUDIT_LOG, its triggers; MM_AUDIT_ALL with the logins): who (the user of the pages: mm-api tells the database; else the user of the database), from where, what, of what; undone with what failed; a value of a secret setting not written; the page «Ιστορικό ενεργειών» (AUDIT: an administrator; filters, pages); purge; in a browser (audit_check.js). |
| `test_auth.py` (6) | the users of the shop (MM_AUTH, step 7a): the password only as PBKDF2 (the same as Python's hashlib), the rules, login and its token, the lock after 5 wrong passwords, the end of a session (logout, a new password, a new role, inactive, expired), an administrator always left. |
| `test_codes.py` (3) | the barcodes and the QR codes of the labels (api/src/main/resources/web/codes.js), drawn as pictures and read back by a decoder (zxing-cpp): EAN-13 (and its check digit), Code 128 B, QR of every version 1 to 10 (latin, Greek: UTF-8). No database. |
| `test_consumption.py` (1) | the consumption note (Δελτίο ανάλωσης, DAN; mm_core.set_reason; MM_CONSUMPTION): goods out of a warehouse at the costs of the layers they take (FIFO), for a reason; no sale, no VAT; cancelled: back; the report of the consumptions; what is refused. |
| `test_core.py` (21) | the package MM_CORE (db/MM_CORE.sql) in a live database. |
| `test_day.py` (2) | the summary of a day (mm-api Day.java, GET /api/day): what a day at the till adds to it (the Z of the register, the sales, the VAT, the items sold most, a scratch prize); another day, empty; MANAGER only. |
| `test_db.py` (16) | the tables of the mini market (db/INSTALL.sql demo) in a live database. |
| `test_expiry.py` (2) | the expiry of the goods (MM_DOC_LINE.EXPIRES, mm_core.set_expiry, the view MM_EXPIRY; the REST of Expiry.java and the lines of Docs.java): an item received three times with dates, what is left of each by FIFO as it is sold, taken out, received again without a date; expired and expiring in N days; one taken out of the stock; what is refused. |
| `test_fifo.py` (2) | FIFO (MM_FIFO, MM_FIFO_OUT, mm_core.stock_move and fifo_rebuild, the views MM_FIFO_VALUE and MM_MOVE_COST): an item of its own bought twice at two costs, sold (the oldest first), the sale cancelled (its layers back), sold beyond its stock (a shortage at the cost of the item), bought again (the shortage filled first), the receipt cancelled; a return of a customer; built again from the moves, the same; MM_CHECK FIFO. |
| `test_forms.py` (35) | the forms of forms/mkforms.py, without the Forms: |
| `test_kits.py` (5) | baskets and sets (kits) in MM_CORE: what one has, made before (assemble_kit) or sold before they are made (post_doc: the ready ones first, the rest from the components), the cancel back exactly. |
| `test_ledger.py` (5) | the ledgers (MM_LEDGER): an item, a customer, a supplier for a period: the carry-over, the moves with the running balance, the totals, the balance at the end. |
| `test_months.py` (5) | the totals of the months (MM_MONTHS): kept by the triggers through every change (a document posted, cancelled, its date moved; a payment cancelled; a move moved or deleted), the same as MM_MONTHS.REBUILD from all the moves, and what the ledgers take from them (their carry-over) the same as from every move one by one. Two tills on the same item do not wait for each other (reservable). |
| `test_mydata.py` (2) | myDATA of AADE (mm-api MyData.java) against a little AADE of the tests (fake_aade.py): the XML of an invoice and of its credit note, checked against the XSD of AADE (xmllint) as well as by the service; sent (MARK, UID, QR into the document), an error of AADE, sent by itself (MYDATA_AUTO and the worker), cancelled at AADE then here; what is refused before anything goes. |
| `test_options.py` (3) | the options of an item at the till (a cafe: sugar, milk, extras): MM_OPTION_GROUP, MM_OPTION, MM_ITEM_OPTION, MM_DOC_LINE_OPTION and MM_DOC_LINE.OPTIONS; the rules of mm_core (option_group_save, option_save, option_delete, option_move, item_option, add_line_options; errors MM-132), the number at the counter (counter_ticket, MM_DOC.TICKET_NO); the REST (POST /api/pos/{register}/item with options, a scan with the defaults, the receipt and its ticket, /api/tiles/options...); the dialog in a browser (tests/tiles_check.js, with test_tiles.py). |
| `test_payments.py` (2) | receipts from customers and payments to suppliers (MM_CORE.RECEIVE, PAY, CANCEL_PAYMENT): the rules, the move of the register (CASH/CARD with a register), the cancel. |
| `test_places.py` (2) | where a user works (mm_auth.set_place, may_use; MM_USER.WAREHOUSE_ID, REGISTER_ID): its store and its register; the till of the pages only on the registers it may use (a cashier with a register: only that one; with a store: the registers of it; a manager: of its store; an administrator: all); the users in the pages (ADMIN): one made, changed (its place, role, active, password). |
| `test_points.py` (2) | the points of the retail customers (MM_POINTS; mm_core.new_card, card_customer, set_doc_customer, use_points, post_doc, cancel_doc): a card (EAN-13 2990...), a receipt of a customer gives points by its total, points used as the discount of a receipt (its VAT right), a receipt cancelled gives them back; what is refused. The settings POINTS_PER_EURO, POINT_VALUE, POINTS_MIN. |
| `test_promos.py` (9) | the promotions of MM_CORE.REPRICE on a draft sale, at each change: % off, buy N get M free (the cheapest pieces), a bundle for a price, one promotion a line (bundle, then N+M, then the best %), and the discount of the whole document spread by value (the VAT of each rate right). |
| `test_recipes.py` (4) | the recipes of the cafe: a coffee is a kit never assembled (MM_KIT_COMPONENT), each sale takes its materials by FIFO; the materials of an option (MM_OPTION_COMPONENT, mm_core.option_component): more of one (a shot of coffee) or less of one of the recipe (oat milk instead of the fresh), never below 0; a cancel gives them back exactly; the cost of the line its materials; the REST of the page (the recipe of a tile, its cost; the materials of an option). |
| `test_reports.py` (4) | the reports (reports/mkreports.py): the ledgers, sales, VAT, minimum stock; their XML (ASCII, every field with its source, every formula with its function, the summaries of a page only in the margin), and with MM_DSN their query and their words in the database, and the carry-over from page to page. |
| `test_reservations.py` (9) | the reservations of MM_CORE (e.g. New Year cakes): the quantities reserved, the deposit in the cash register on its day, the delivery with a receipt that takes only the rest, the cancel with the deposit back. |
| `test_rights.py` (3) | the rights (MM_RIGHTS): the roles of the system as the shop worked before them; the role of the level of a user kept with it (mm_auth.create_user, set_role); a role of the shop (made, a copy of another, its grants); a user in more than one role (the most of each); a field not above its screen; an action on a screen read only; the menu of a user; need (MM-197); what is refused (MM-198). |
| `test_rights_api.py` (2) | the rights (MM_RIGHTS) on the service and the pages: a role of the shop (only the items, without their prices; the documents read, posted but not made; the users without the administrators): its menu (/api/auth/rights), its calls (403), the fields it may not read (null), the customers through the documents without their tax numbers; in a browser (rights_check.js): its menu, the page of an item without its price, a page not allowed. |
| `test_roles_api.py` (2) | the page «Ρόλοι και δικαιώματα» on the service (Roles): a role made, its rights (the screen, a field, an action), copied from another, given to a user (its menu, its calls), renamed, not active, out; the menu renamed, moved, a screen not active (no one sees it), the roles kept in it; only with a right to the roles (an administrator); in a browser (roles_check.js). |
| `test_sales_by.py` (1) | the sales by store, register and cashier (MM_SALES_DOC; MM_DOC.CREATED_BY, POSTED_BY by the trigger of MM_AUDIT): who made and posted a receipt of the till of the pages; the report by each (the costs and the profit only with the right to the gross profit); the summary of the day; the cashier on the receipt. |
| `test_scratch.py` (1) | the scratch tickets in packs (MM_SCRATCH_GAME, mm_core.load_pack, scratch_prize; the REST of Scratch.java and the till): a game and its item; a pack loaded from the barcode of one of its tickets (game 4 digits, pack 7, ticket 3): its tickets as serials, the stock; at the till a scan sells that very ticket, a second scan says it is sold; a prize paid from the drawer; what is refused. |
| `test_serials.py` (11) | the cards of mobile phones (items with serial numbers) in MM_CORE, and their PINs (MM_PIN, encrypted). Needs EXECUTE on DBMS_CRYPTO (db/GRANT_CRYPTO.sql). |
| `test_tiles.py` (4) | the buttons of the till (a cafe: coffees, juices, sweets without a barcode): MM_TILE_GROUP, MM_TILE and MM_ITEM.PLU, the rules of mm_core (tile_group_save, tile_add, tile_move, tile_delete, set_plu, find_item by PLU; errors MM-132), the REST of Tiles.java (the page Κουμπιά ταμείου, the rights of TILES) and of the till (GET /api/pos/tiles, POST /api/pos/{register}/item): a receipt from the buttons, posted, the database still adding up (MM_CHECK); the pages in a browser (tests/tiles_check.js). |
| `test_transfer.py` (2) | the transfer between two warehouses (Δελτίο ενδοδιακίνησης, DEN; mm_core.new_doc with p_to_warehouse_id, add_line at cost, post_doc, cancel_doc; FIFO): bought at two costs into the main one, sent to a branch: its lines at the cost of each layer (x at a, y at b), no VAT; posted, out of the one and into the other with the same layers and costs; sold there at those costs; a transfer cancelled: back in both; FIFO built again, the same; not a sale (no profit, no VAT); what is refused. |
| `test_variants.py` (5) | clothes and shoes: a model and its variants (a colour and/or a size), each an item of its own; the model is not sold, counted, reserved or put in a basket; its price goes to its variants; a promotion on the model holds for its variants. |
| `test_warehouse.py` (4) | the warehouses (MM_WAREHOUSE; the warehouse of each move, layer of FIFO, document, register; mm_core.new_doc, stock_move, main_warehouse; the view MM_WAREHOUSE_STOCK; MM_CHECK FIFO_WH): the main one; a second one; a receipt into each, a sale from each (its register): the stock and the layers of each apart; FIFO built again, the same; what is refused. |
| `test_web.py` (2) | the pages of the mini market (api/src/main/resources/web) in a real browser: the jar of test_api.py, its manager and cashier; tests/web_check.js with Playwright (Chromium). |

_Φτιάχτηκε στις 19/11/2026._
