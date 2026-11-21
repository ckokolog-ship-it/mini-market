# Ενημέρωση μετά από merge: όλες οι εντολές μαζί

Μετά από κάθε merge ενός PR, στο PC του μαγαζιού. Τα βήματα τρέχουν με αυτή τη σειρά. Όποιο δεν χρειάζεται για ένα PR μπορεί να παραλειφθεί, αλλά όλα μπορούν να τρέξουν ξανά χωρίς πρόβλημα.

Ο φάκελος του repo: `C:\Users\chris\eclipse-workspace\mini-market`. Στο Linux (forms1) οι ίδιες εντολές είναι στο τέλος του [ODIGIES_LINUX.md](ODIGIES_LINUX.md).

## 0. Backup της βάσης (PowerShell ως διαχειριστής)

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\db
powershell -ExecutionPolicy Bypass -File backup.ps1
```

Ένα backup πριν από κάθε αλλαγή της βάσης. Αν κάτι πάει στραβά: `backup.ps1 -Restore C:\mm_backup\<αρχείο>.dmp` (§14 του [ODIGIES_VASI.md](ODIGIES_VASI.md)).

## 1. Ο κώδικας

```bat
cd C:\Users\chris\eclipse-workspace\mini-market
git checkout main
git pull
git diff --stat ORIG_HEAD HEAD
```

Το τελευταίο δείχνει ποια αρχεία άλλαξαν, και από αυτό φαίνεται ποια βήματα χρειάζονται:

| Άλλαξε κάτι στο | Βήμα |
|---|---|
| `db/` | 2. Η βάση |
| `api/` (και οι σελίδες web, `api/src/main/resources/web`) | 3. Το mm-api |
| `forms/` | 4. Οι φόρμες |
| `reports/` | 5. Τα reports |

Αν άλλαξε το `forms/mkforms.py`, άλλαξε και το `db/MM_TEXT.sql`, που μπαίνει με το βήμα 2. Τότε χρειάζονται και τα δύο βήματα, 2 και 4.

## 2. Η βάση (Command Prompt, `cmd`)

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\db
set NLS_LANG=GREEK_GREECE.AL32UTF8
C:\app\chris\product\26ai\dbhomeFree\bin\sqlplus.exe mm@FREEPDB1 @INSTALL.sql
```

- Ζητά τον κωδικό του `mm`. Στο τέλος γράφει `== MM INSTALL OK`.
- **Χωρίς `demo`** στη βάση του μαγαζιού. Οι πίνακες που υπάρχουν μένουν όπως είναι: προστίθενται μόνο οι νέοι πίνακες και οι νέες στήλες, και ξαναγράφονται τα πακέτα και οι όψεις.
- Το `set` είναι εντολή του `cmd`. Στο PowerShell γράφεις `$env:NLS_LANG='GREEK_GREECE.AL32UTF8'`.
- Το `sqlplus` με πλήρη διαδρομή, γιατί το σκέτο `sqlplus` στο `PATH` είναι του Forms.

Μετά, ο έλεγχος ότι όλα συμφωνούν (καμία γραμμή = εντάξει):

```bat
C:\app\chris\product\26ai\dbhomeFree\bin\sqlplus.exe mm@FREEPDB1 @MM_CHECK.sql
```

## 3. Το mm-api και οι σελίδες web (PowerShell ως διαχειριστής)

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\api
powershell -ExecutionPolicy Bypass -File install_service.ps1
powershell -ExecutionPolicy Bypass -File install_service.ps1 -Status
```

- Το πρώτο σταματά το service, χτίζει το νέο jar και το ξαναξεκινά. Οι σελίδες web είναι μέσα στο jar.
- Το `-Status` δείχνει την απάντηση του `/api/health`.
- Στον browser, μία φορά **Ctrl+F5**, για να φορτώσει τη νέα σελίδα και όχι την παλιά από την cache. Το ίδιο και στο κινητό: ανανέωση της σελίδας.

Αν το mm-api τρέχει στο Docker και όχι ως service: `powershell -ExecutionPolicy Bypass -File run_docker.ps1` ([ODIGIES_REST.md](ODIGIES_REST.md)).

## 4. Οι φόρμες (μόνο αν άλλαξε το `forms/`)

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\forms
powershell -ExecutionPolicy Bypass -File build_forms.ps1
```

Γράφει τα `.fmx` στο `C:\forms_dev`. Οι ανοιχτές φόρμες πρέπει να κλείσουν πρώτα ([ODIGIES_FORMS.md](ODIGIES_FORMS.md)).

## 5. Τα reports (μόνο αν άλλαξε το `reports/`)

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\reports
powershell -ExecutionPolicy Bypass -File build_reports.ps1
```

Γράφει τα `.rdf` στο `C:\reports_dev` ([ODIGIES_REPORTS.md](ODIGIES_REPORTS.md)).

## Όλα μαζί, με μια ματιά

| # | Πού | Εντολή |
|---|---|---|
| 0 | PowerShell (διαχειριστής), `db` | `powershell -ExecutionPolicy Bypass -File backup.ps1` |
| 1 | repo | `git checkout main` · `git pull` · `git diff --stat ORIG_HEAD HEAD` |
| 2 | cmd, `db` | `set NLS_LANG=GREEK_GREECE.AL32UTF8` · `…\sqlplus.exe mm@FREEPDB1 @INSTALL.sql` · `@MM_CHECK.sql` |
| 3 | PowerShell (διαχειριστής), `api` | `powershell -ExecutionPolicy Bypass -File install_service.ps1` · `-Status` · Ctrl+F5 |
| 4 | PowerShell, `forms` | `powershell -ExecutionPolicy Bypass -File build_forms.ps1` |
| 5 | PowerShell, `reports` | `powershell -ExecutionPolicy Bypass -File build_reports.ps1` |
