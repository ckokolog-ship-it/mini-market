# Το mini market στο k3s

Το `mm-api` (το REST, οι σελίδες web, τα ταμεία, τα κινητά) τρέχει και στο cluster k3s του δικτύου (k3s1 / k3s2 / k3s3:
`192.168.178.211` / `.212` / `.213`), δίπλα στην τράπεζα και στο PROPO, στο δικό του namespace `mm`. Τα Forms και τα
reports μένουν στο forms1 (WebLogic).

| | |
|---|---|
| Η σελίδα | **http://192.168.178.211:8300/** (ή .212, .213: όποιος κόμβος ζει) |
| Η βάση | το MMPDB στο Data Guard (`mm_rw`: db1 ή db2, όποιος είναι primary) |
| Αντίγραφα | 2 (ένα σβήνει, το άλλο απαντά· τα logins τα ελέγχει η βάση, οπότε απαντά όποιο κι αν ρωτηθεί) |

**Πρώτα το Data Guard:** το mini market πρέπει να έχει μετακομίσει στο MMPDB (repo `bank`, `docs/ODIGIES_DG.md` §14).

## Τι μπαίνει στο cluster

- **mm-api** σε 2 αντίγραφα, με τον χρήστη **MM** της βάσης. Ο κωδικός του είναι στο Secret `mm-db`: τον ζητά το
  `deploy.sh` και δεν γράφεται ποτέ σε αρχείο του repo. Στο forms1 το `mm-api` χρησιμοποιεί το wallet του domain· εδώ
  δεν υπάρχει wallet.
- **myDATA:** σε κάθε γύρο στέλνει **ένα μόνο** `mm-api` (κλείδωμα στη βάση: `MYDATA_SENDER` στο MM_SETTING), ακόμα
  κι αν τρέχουν 2 στο k3s και 1 στο forms1. Κανένα παραστατικό δεν φεύγει δύο φορές. Ο λογαριασμός του myDATA
  (`mydata.properties`) μπαίνει στο Secret `mm-mydata` (`ship.sh --mydata`)· χωρίς αυτόν τα παραστατικά περιμένουν (Q),
  όπως και στο forms1.
- Έξω φαίνεται μόνο στη θύρα **8300** κάθε κόμβου (ServiceLB του k3s). Η 80 μένει της τράπεζας, η 3000 του PROPO.

## Η πρώτη φορά

**1. forms1, ως chris** (έχει το κλειδί ssh των κόμβων· το repo εκεί όπου είναι):

```bash
sudo ~oracle/mini-market/k3s/ship.sh --mydata      # χωρίς --mydata αν δεν υπάρχει λογαριασμός myDATA
```

Χτίζει το jar (`./mvnw`) και το image (`localhost/mm/mm-api:<commit>`), το στέλνει σε κάθε κόμβο
(`k3s ctr images import`, χωρίς registry), αντιγράφει το `k3s/` στον k3s1 και γράφει την εντολή του βήματος 2.

**2. k3s1, ως chris:**

```bash
sudo ~/mm-k3s/deploy.sh <tag>
```

Ζητά τον κωδικό του χρήστη **MM** της βάσης (δύο φορές, δεν φαίνεται). Μετά: **http://192.168.178.211:8300/**.

## Μια νέα έκδοση

```bash
# forms1, ως oracle
cd ~/mini-market && git pull
# forms1, ως chris
sudo ~oracle/mini-market/k3s/ship.sh
# k3s1, ως chris
sudo ~/mm-k3s/deploy.sh <tag>
```

## Καθημερινά (k3s1)

| Εντολή | |
|---|---|
| `sudo ~/mm-k3s/deploy.sh --status` | τα pods (σε ποιον κόμβο) και η σελίδα |
| `sudo ~/mm-k3s/deploy.sh --undo` | πίσω στην προηγούμενη έκδοση |
| `sudo ~/mm-k3s/deploy.sh <tag> --password` | νέος κωδικός του MM |
| `sudo k3s kubectl -n mm logs deploy/mm-api` | τι λέει το mm-api (και το myDATA) |
| `sudo ~/mm-k3s/deploy.sh --delete` | το mm-api έξω από το cluster (η βάση μένει) |

## Και το forms1;

Το `mm-api` του forms1 (`systemctl status mm-api`, θύρα 8090) μπορεί να συνεχίσει να τρέχει: μιλά με την ίδια βάση,
και το myDATA το στέλνει ένα κάθε φορά. Αν θέλεις μόνο το k3s: `sudo systemctl disable --now mm-api` στο forms1, και τα
ταμεία και τα κινητά στη διεύθυνση `http://192.168.178.211:8300/`.
