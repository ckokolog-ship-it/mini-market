# Τα reports του mini market (Oracle Reports 14.1.2)

| Report | Τι | Παράμετροι |
|---|---|---|
| `MM_LEDGER_I` | Καρτέλα **είδους**: εισαγωγή, εξαγωγή, απόθεμα (3 δεκαδικά) | `P_KIND=I`, `P_ID`, `P_FROM`, `P_TO` |
| `MM_LEDGER_P` | Καρτέλα **πελάτη** (`P_KIND=C`) ή **προμηθευτή** (`P_KIND=S`): χρέωση, πίστωση, υπόλοιπο | `P_KIND`, `P_ID`, `P_FROM`, `P_TO` |

Οι ημερομηνίες γράφονται `ΗΗ/ΜΜ/ΕΕΕΕ`.

**Σε κάθε σελίδα:**
- **πάνω:** ο τίτλος (π.χ. «Καρτέλα πελάτη: … (ΑΦΜ …)»), το διάστημα, η σελίδα, οι επικεφαλίδες, και η γραμμή **«Από μεταφορά»**: τα σύνολα χρέωσης και πίστωσης και το υπόλοιπο πριν από την πρώτη γραμμή της σελίδας·
- **στη μέση:** οι κινήσεις, με το προοδευτικό υπόλοιπο·
- **κάτω:** η γραμμή **«Σε μεταφορά»**: τα ίδια, μαζί με την τελευταία γραμμή της σελίδας. Είναι το «Από μεταφορά» της επόμενης σελίδας.

**Μετά την τελευταία γραμμή:** «Σύνολα περιόδου», «Από προηγούμενη περίοδο» (το υπόλοιπο πριν από το διάστημα), και «Γενικό υπόλοιπο» (για είδος: «Τελικό απόθεμα»).

Τα νούμερα είναι τα ίδια με της φόρμας `MM_LEDGER`, γιατί έρχονται από τις ίδιες συναρτήσεις (`mm_ledger.report_rows`, `ODIGIES_VASI.md` §13).

## Πώς φτιάχνονται

Όπως οι φόρμες: το `reports/mkreports.py` γράφει το XML του report (`MM_LEDGER_I.xml`, `MM_LEDGER_P.xml`) σε ASCII. Τα ελληνικά (τίτλος, επικεφαλίδες, λέξεις) τα φέρνει το report από τη βάση όταν τρέχει, με τα `mm_ledger.title` και `mm_ledger.label`. Στα Windows, το `build_reports.ps1` τα κάνει `.rdf` με το `rwconverter`.

## Μία φορά (Windows)

Χρειάζεται ο Reports Server του PROPO (`docs/FORMS_REPORTS_ODIGOS.md` §10.5 του PROPOApplication), με ένα κλειδί ακόμα για τη βάση του mini market. Από το `retro\oracle\windows` του PROPOApplication, **ως διαχειριστής**:

```bat
reports_server.cmd -Alias MM_DB -Key mm -EnvId lottoEnv
```

- **Τι κάνει:** προσθέτει στο `cgicmd.dat` το κλειδί `mm: userid=/@MM_DB envid=lottoEnv %*`, δηλαδή το wallet του `forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm`, χωρίς κωδικό. Το κλειδί `lotto` μένει όπως ήταν.
- **Το περιβάλλον:** το `lottoEnv` είναι το ίδιο για τις δύο βάσεις (NLS_LANG, wallet, γραμματοσειρές).

Μετά, από τον φάκελο `db` του mini market:
```bat
sqlplus mm/<κωδικός>@localhost:1522/FREEPDB1 @SET_REPORTS_URL.sql http://192.168.178.165:9012 HTML
```

- **Τι γράφει:** στο `MM_SETTING` πού είναι ο Reports Server και σε ποια μορφή ανοίγουν τα reports.
- **Γιατί HTML:** στα Windows τα ελληνικά του PDF είναι ακόμα ανοιχτό θέμα (§10.2 του οδηγού του PROPO). Στο HTML βγαίνουν σωστά.

## Κάθε φορά που αλλάζουν

Από τον φάκελο `reports`:
```bat
powershell -ExecutionPolicy Bypass -File build_reports.ps1
```

- **Τι κάνει:** γράφει τα `C:\reports_dev\MM_LEDGER_I.rdf` και `MM_LEDGER_P.rdf`, και δείχνει το log του `rwconverter` (`C:\reports_dev\<όνομα>.log`).
- **Πριν:** μία φορά το `create_reptools.cmd` του PROPO, όπως για το Reports Builder.
- **Αν βγάλει λάθος (REP-…):** στείλε μου την έξοδο.

## Άνοιγμα

- **Από τη φόρμα `MM_LEDGER`:** δείξε μια καρτέλα και πάτα **«Εκτύπωση»**. Ανοίγει στον browser η ίδια καρτέλα, για το ίδιο διάστημα. Αν δεν έχει τρέξει το `SET_REPORTS_URL.sql`, η φόρμα το λέει.
- **Από τον browser:**
  ```
  http://192.168.178.165:9012/reports/rwservlet?mm&report=MM_LEDGER_P.rdf&destype=cache&desformat=HTML&P_KIND=C&P_ID=2&P_FROM=01/01/2026&P_TO=31/12/2026
  ```
