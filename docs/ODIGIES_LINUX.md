# Το mini market στο Linux (forms1)

Η μεταφορά από τα Windows στον server **forms1**: Oracle Linux 9.8, `192.168.178.200`, `forms1.home.lan`. Εκεί υπάρχουν ήδη:
- η βάση Oracle 26ai Free (`FREEPDB1`, θύρα 1521)·
- τα Forms και τα Reports 14.1.2 (domain `forms_domain`, θύρες 9001 και 9012).

Το στήσιμο του server είναι στο [ORACLE_FORMS.md του PROPOApplication](https://github.com/ckokolog-ship-it/PROPOApplication/blob/main/docs/ORACLE_FORMS.md).

## Με μια ματιά

| Τι | Στα Windows | Στο forms1 |
|---|---|---|
| Βάση | Oracle 26ai Free, `localhost:1522/FREEPDB1` | Oracle 26ai Free, `forms1.home.lan:1521/FREEPDB1` (υπηρεσία `oracle-free-26ai`) |
| Wallet (`MM_DB`, χωρίς κωδικό) | `forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm` | `tools/linux/mm_wallet.sh` |
| mm-api και σελίδες web | υπηρεσία Windows (`install_service.ps1`) | υπηρεσία systemd `mm-api` (`api/install_service.sh`), `http://192.168.178.200:8090/` |
| Backup κάθε βράδυ | εργασία Windows (`backup.ps1 -Install`) | systemd timer `mm-backup` (`db/backup.sh --install`), στο `/u01/app/oracle/mm_backup` |
| Φόρμες | `build_forms.ps1` → `C:\forms_dev` | `forms/build_forms.sh` → ο φάκελος του `FORMS_PATH` |
| Reports | `build_reports.ps1` → `C:\reports_dev` | `reports/build_reports.sh` → `/u01/app/oracle/reports` |
| Ο φάκελος του repo | `C:\Users\chris\eclipse-workspace\mini-market` | `/u01/app/oracle/mini-market` (του χρήστη `oracle`) |

**Η σειρά:**
1. Πρώτα στήνεις τα πάντα στο forms1, με ένα **δοκιμαστικό** αντίγραφο των δεδομένων (βήματα 1–9).
2. Τη μέρα της αλλαγής (§10) παίρνεις το τελικό backup από τα Windows και το περνάς στο forms1.
3. Τα ταμεία και τα κινητά γυρνούν στη νέα διεύθυνση.
4. Τα Windows μένουν για λίγες μέρες ως εφεδρεία.

Συνδέεσαι με **MobaXterm**, SSH στο `192.168.178.200`, ως `chris`. Όπου γράφει «ως oracle»: `sudo -iu oracle`.

## 1. Ο κώδικας στο forms1

Ως `oracle`:

```bash
cd /u01/app/oracle
git clone https://github.com/ckokolog-ship-it/mini-market.git
cd mini-market
git config credential.helper store       # ο κωδικός του GitHub κρατιέται για τα επόμενα git pull
```

Το repo είναι ιδιωτικό, οπότε το `git clone` ζητά:
- **όνομα:** `ckokolog-ship-it`·
- **κωδικό:** ένα **token** του GitHub, όχι τον κωδικό του λογαριασμού.

Το token το φτιάχνεις στο GitHub: *Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token*. Ρυθμίσεις:
- **Repository access:** μόνο το `mini-market`·
- **Permissions:** *Contents: Read-only*.

Το `credential.helper store` το κρατά στο `~/.git-credentials` του `oracle`, που το διαβάζει μόνο αυτός.

Αν το `git` δεν υπάρχει: `sudo dnf -y install git` (ως `chris`).

## 2. Ο χρήστης MM στη βάση (μία φορά)

Ως `oracle`:

```bash
cd /u01/app/oracle/mini-market/db
export ORACLE_HOME=/opt/oracle/product/26ai/dbhomeFree PATH=/opt/oracle/product/26ai/dbhomeFree/bin:$PATH
export NLS_LANG=GREEK_GREECE.AL32UTF8
sqlplus system@forms1.home.lan/FREEPDB1 @CREATE_USER.sql                  # ο κωδικός του MM: τον διαλέγεις τώρα
sqlplus sys@forms1.home.lan/FREEPDB1 as sysdba @GRANT_CRYPTO.sql          # τα PIN των καρτών
sqlplus sys@forms1.home.lan/FREEPDB1 as sysdba @GRANT_BACKUP.sql          # το backup
```

Κάθε `sqlplus` ζητά τον κωδικό του `system` ή του `sys`, δηλαδή αυτόν του `configure` της βάσης.

## 3. Το wallet: το `MM_DB` χωρίς κωδικό (μία φορά)

Ως `oracle`:

```bash
/u01/app/oracle/mini-market/tools/linux/mm_wallet.sh
```

**Το `mkstore` ζητά:**
- τον κωδικό του **wallet**: είναι το ίδιο wallet με τα παιχνίδια του PROPO (`forms_wallet.sh`), άρα ο ίδιος κωδικός·
- τον κωδικό του **MM**, δύο φορές.

**Τι φτιάχνει:**
- το `MM_DB` στα `tnsnames.ora` και `sqlnet.ora` του domain·
- το `[mm]` στο `formsweb.cfg`·
- το κλειδί `mm` στο `cgicmd.dat` των Reports·
- το `NLS_LANG` με ελληνικά στο `default.env`, αν δεν υπάρχει.

Στο τέλος δοκιμάζει ότι το `/@MM_DB` συνδέει. Μετά, μία φορά, ως `chris`:

```bash
sudo systemctl restart weblogic-forms      # 5–10 λεπτά
```

Από εδώ και πέρα, όλα συνδέονται με `/@MM_DB` και χωρίς κωδικό: η βάση από το τερματικό, οι φόρμες, τα reports, το mm-api και το backup.

## 4. Η βάση

Ως `oracle`:

```bash
cd /u01/app/oracle/mini-market/db
export ORACLE_HOME=/opt/oracle/product/26ai/dbhomeFree PATH=/opt/oracle/product/26ai/dbhomeFree/bin:$PATH
export TNS_ADMIN=/u01/app/oracle/config/domains/forms_domain/config/fmwconfig
export NLS_LANG=GREEK_GREECE.AL32UTF8
sqlplus /@MM_DB @INSTALL.sql                # χωρίς demo: τα δεδομένα έρχονται από τα Windows (βήμα 5)
```

Γράφει στο τέλος `== MM INSTALL OK`.

> **Για ευκολία:** τα τρία `export` του `TNS_ADMIN`, του `ORACLE_HOME` και του `PATH` μπορούν να μπουν στο `~/.bash_profile` του `oracle`. Ο οδηγός του PROPO έχει ήδη ένα (§12).

## 5. Τα δεδομένα από τα Windows

**Στα Windows** (PowerShell ως διαχειριστής), ένα backup τώρα:

```bat
cd C:\Users\chris\eclipse-workspace\mini-market\db
powershell -ExecutionPolicy Bypass -File backup.ps1
```

Γράφει `== C:\mm_backup\mm_<ημερομηνία>_<ώρα>.dmp`. Το αντιγράφεις στο forms1, από το ίδιο PowerShell, με το `scp` των Windows:

```bat
scp C:\mm_backup\mm_20261121_2130.dmp chris@192.168.178.200:/tmp/
```

(ή με μεταφορά στο αριστερό πάνελ του MobaXterm).

**Στο forms1**, ως `chris`:

```bash
sudo /u01/app/oracle/mini-market/db/backup.sh --restore /tmp/mm_20261121_2130.dmp
```

Γράφεις `RESTORE` για επιβεβαίωση. Το script:
1. κρατά πρώτα ένα backup αυτού που υπάρχει τώρα·
2. σβήνει τα αντικείμενα του MM·
3. φορτώνει το αρχείο με `impdp`·
4. ξαναμεταγλωττίζει.

Μετά ξανατρέχεις το `INSTALL.sql` του βήματος 4, χωρίς να χαθεί τίποτα. Έτσι η βάση φτάνει στην έκδοση του repo, αν τα Windows ήταν πιο πίσω. Τέλος, έλεγχος:

```bash
echo "select count(*) from mm_check;" | sqlplus -s /@MM_DB       # 0: όλα συμφωνούν
rm /tmp/mm_20261121_2130.dmp                                     # (έχει και τα PIN: όχι στο /tmp)
```

Μετά το restore δουλεύουν όλα όπως στα Windows:
- οι χρήστες του μαγαζιού, με τους κωδικούς τους·
- τα PIN των καρτών, με το κλειδί τους·
- οι ρυθμίσεις: επικεφαλίδα της απόδειξης, myDATA, πόντοι.

## 6. Το mm-api και οι σελίδες web

Ως `chris`:

```bash
sudo dnf -y install java-21-openjdk-devel || true     # (το JDK 21 της Oracle υπάρχει ήδη: ORACLE_FORMS.md §3)
sudo /u01/app/oracle/mini-market/api/install_service.sh
```

**Τι κάνει:**
- χτίζει το jar ως `oracle`, με το `./mvnw`· την πρώτη φορά κατεβάζει το Maven, οπότε θέλει internet·
- το βάζει στο `/u01/app/oracle/mm-api`·
- φτιάχνει την υπηρεσία **`mm-api`**, που ξεκινά μετά τη βάση από το `/u01/app/oracle/scripts/mm-api.sh` (για το SELinux, όπως τα Forms), και ξαναξεκινά μόνη της αν σταματήσει· αν αποτύχει 5 φορές σε 10 λεπτά σταματά να προσπαθεί, και το `journalctl -u mm-api` λέει γιατί·
- περιμένει το `/api/health`.

Στο τέλος γράφει `{"status":"ok","db":"ok"}`.

**Από τα Windows:** `http://192.168.178.200:8090/`, με σύνδεση όπως πριν.

| Θέλω να ... | Εντολή (ως `chris`) |
|---|---|
| δω την κατάσταση | `systemctl status mm-api` |
| δω το log | `journalctl -u mm-api -n 100` |
| επανεκκίνηση | `sudo systemctl restart mm-api` |
| ενημέρωση μετά από `git pull` | `sudo /u01/app/oracle/mini-market/api/install_service.sh` |

## 7. Οι φόρμες

Ως `oracle`:

```bash
cd /u01/app/oracle/mini-market/forms
./build_forms.sh
```

Περνά το `MM_TEXT.sql` (τα ελληνικά των φορμών) και μετά φτιάχνει κάθε φόρμα: XML → `.fmb` → `.fmx`, στον φάκελο του `FORMS_PATH`. Γράφει `== done: MM_MENU MM_LOGIN ...`.

**Από τα Windows, με το FSAL:**

```bat
java -jar C:\forms\frmsal.jar -url "http://forms1.home.lan:9001/forms/frmservlet?config=mm&form=MM_MAIN" -t 10000
```

## 8. Τα reports

Ως `oracle`, από το MobaXterm με X11-forwarding: το `rwconverter` θέλει οθόνη, όπως το Reports Builder.

```bash
cd /u01/app/oracle/mini-market/reports
./build_reports.sh
sqlplus /@MM_DB @../db/SET_REPORTS_URL.sql http://forms1.home.lan:9012 PDF     # πού ανοίγουν οι φόρμες τα reports
```

- **Έλεγχος:** `http://forms1.home.lan:9012/reports/rwservlet?mm&report=MM_SALES.rdf&destype=cache&desformat=PDF`.
- **Τα ελληνικά στο PDF:** είναι οι γραμματοσειρές του `WLS_REPORTS` (`REPORTS_FONT_DIRECTORY`, `TK_FONTALIAS`), όπως τις έχει ήδη στήσει ο οδηγός του PROPO (§13).

## 9. Το backup κάθε βράδυ

Ως `chris`:

```bash
sudo /u01/app/oracle/mini-market/db/backup.sh --install
# με αντίγραφο και σε άλλο δίσκο, όταν είναι συνδεδεμένος:
sudo /u01/app/oracle/mini-market/db/backup.sh --install --copy-to /mnt/usb/mm_backup
```

- **Πότε:** κάθε μέρα στις 23:15 (`--at`), και στην επόμενη εκκίνηση αν ο server ήταν κλειστός.
- **Τι κρατά:** τα 14 τελευταία αρχεία (`--keep`), στο `/u01/app/oracle/mm_backup`, που το διαβάζει μόνο ο `oracle`.
- **Πού το βλέπεις:** η σελίδα του προϊσταμένου ειδοποιεί, όπως και στα Windows, αν το τελευταίο backup είναι παλιό ή απέτυχε.

| Θέλω να ... | Εντολή |
|---|---|
| ένα backup τώρα | ως `oracle`: `/u01/app/oracle/mini-market/db/backup.sh` |
| δω τα τελευταία | `/u01/app/oracle/mini-market/db/backup.sh --status` |
| επαναφορά | `sudo /u01/app/oracle/mini-market/db/backup.sh --restore /u01/app/oracle/mm_backup/<αρχείο>.dmp` |
| σταματήσει το χρονοδιάγραμμα | `sudo /u01/app/oracle/mini-market/db/backup.sh --uninstall` |

Ένα backup σε άλλο μηχάνημα είναι καλή ιδέα, π.χ. ένα `scp` κάθε εβδομάδα στα Windows ή σε δίσκο USB: αν χαλάσει ο δίσκος του forms1, χάνονται και τα backup του.

## 10. Η μέρα της αλλαγής

Όταν τα βήματα 1–9 δουλεύουν με το δοκιμαστικό αντίγραφο:

1. **Στα Windows:** κλείνεις τις φόρμες και σταματάς το mm-api (`install_service.ps1 -Uninstall`), ώστε να μη γίνει καμία πώληση εκεί.
2. **Στα Windows:** `backup.ps1` και `scp` του αρχείου στο forms1 (βήμα 5).
3. **Στο forms1:** `backup.sh --restore` με αυτό το αρχείο, και `INSTALL.sql` ξανά (βήμα 5).
4. **Ταμεία, κινητά, αφίσα:**
   - στα ταμεία (browser): η νέα διεύθυνση `http://192.168.178.200:8090/`·
   - στο Android: στο πεδίο «Η διεύθυνση του μαγαζιού» → `192.168.178.200:8090`·
   - η αφίσα με το QR των παραγγελιών: ξανά από τις «Παραγγελίες» → «Αφίσα με QR», με τη νέα διεύθυνση.
5. **Στα Windows**, όταν όλα δουλεύουν στο forms1:
   - `backup.ps1 -Uninstall` (σταματά το βραδινό backup εκεί)·
   - η βάση των Windows μένει μερικές μέρες ως εφεδρεία, χωρίς να γράφει κανείς σε αυτήν.

## Ενημέρωση μετά από merge (στο forms1)

Ως `oracle`, εκτός από όσα γράφουν `sudo`:

```bash
cd /u01/app/oracle/mini-market
./db/backup.sh                                       # 0. ένα backup πριν
git pull && git diff --stat ORIG_HEAD HEAD           # 1. ο κώδικας: τι άλλαξε
(cd db && sqlplus /@MM_DB @INSTALL.sql)              # 2. db/
sudo ./api/install_service.sh                        # 3. api/ (ως chris)
(cd forms && ./build_forms.sh)                       # 4. forms/ ή db/MM_TEXT.sql
(cd reports && ./build_reports.sh)                   # 5. reports/ (με ssh -X)
```

Όπως και στα Windows ([ODIGIES_ENIMEROSI.md](ODIGIES_ENIMEROSI.md)), όποιο βήμα δεν χρειάζεται μπορεί να παραλειφθεί, αλλά όλα μπορούν να τρέξουν ξανά χωρίς πρόβλημα.

## Όταν κάτι στραβώνει

| Μήνυμα | Αιτία | Λύση |
|---|---|---|
| `ORA-12578` ή `ORA-01017` με `/@MM_DB` | λείπει το wallet, ή άλλαξε ο κωδικός του MM | `tools/linux/mm_wallet.sh` ξανά: με το `MM_DB` ήδη μέσα, ζητά τον νέο κωδικό |
| `no wallet with MM_DB` (install_service.sh) | δεν έτρεξε το βήμα 3 | το βήμα 3 |
| `MM may not use DATA_PUMP_DIR` | δεν έτρεξε το `GRANT_BACKUP.sql` | το βήμα 2 |
| `Unable to access jarfile /u01/app/oracle/mm-api/mm-api.jar` (`mm-api`, «restart counter» που ανεβαίνει) | SELinux: η `java` που ξεκινά κατευθείαν από το systemd δεν διαβάζει το jar στο `/u01` | `sudo .../api/install_service.sh` ξανά: ξεκινά πλέον από το `/u01/app/oracle/scripts/mm-api.sh` (ετικέτα `bin_t`, όπως τα Forms). Έλεγχος: `ls -laZ /u01/app/oracle/mm-api /u01/app/oracle/scripts` |
| `status=203/EXEC` στο `mm-backup` | ετικέτα SELinux | `sudo restorecon -Rv /u01/app/oracle/scripts` |
| `?????` αντί για ελληνικά στις φόρμες | `NLS_LANG` του `default.env` χωρίς ελληνικά | `AMERICAN_GREECE.AL32UTF8` στο `default.env`, και `sudo systemctl restart weblogic-forms` |
| `REP-3000` στο `build_reports.sh` | χωρίς οθόνη | MobaXterm με X11-forwarding (`echo $DISPLAY` → `localhost:10.0`) |
| Τα ταμεία δεν φτάνουν το `:8090` | το firewalld τρέχει | `sudo firewall-cmd --permanent --add-port=8090/tcp && sudo firewall-cmd --reload` (το `install_service.sh` το κάνει μόνο του, αν το firewalld τρέχει όταν τρέχει αυτό) |
