#!/bin/bash
# mm_wallet.sh -- forms1 (Oracle Linux 9), as oracle: the mini market WITHOUT the password of the database
# anywhere, as forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm on Windows. For the forms, the reports,
# the service mm-api (api/install_service.sh) and the backup (db/backup.sh):
#   http://forms1.home.lan:9001/forms/frmservlet?config=mm&form=MM_MAIN
#   http://forms1.home.lan:9012/reports/rwservlet?mm&report=MM_SALES.rdf&destype=cache&desformat=PDF
# What it sets up (every file it changes is kept first as <file>.<date>.bak; run again: nothing twice):
#   1. the credential MM_DB = user mm of FREEPDB1 in the Oracle Wallet of the domain
#      (config/fmwconfig/forms_wallet; made if there is none). mkstore asks every password (the wallet's,
#      and mm's); none shows, none is written anywhere else;
#   2. MM_DB in tnsnames.ora, WALLET_LOCATION and SQLNET.WALLET_OVERRIDE in sqlnet.ora of the domain, and
#      TNS_ADMIN = that folder in default.env of the forms (and NLS_LANG with Greek, if it has none);
#   3. a section [mm] in formsweb.cfg: [standaloneapp] (FSAL) plus userid=/@MM_DB;
#   4. the key mm in cgicmd.dat of WLS_REPORTS: userid=/@MM_DB %*;
#   5. a check: /@MM_DB connects (sqlplus of the database), the page of config=mm carries no password.
# The same wallet as the games of PROPOApplication (forms_wallet.sh: LOTTO_DB): one more credential in it.
# Then, once, as chris: sudo systemctl restart weblogic-forms   (WLS_REPORTS reads sqlnet.ora at start)
set -u
D=${DOMAIN_HOME:-/u01/app/oracle/config/domains/forms_domain}
MW=${MW_HOME:-/u01/app/oracle/middleware}
DB_HOME=${DB_HOME:-/opt/oracle/product/26ai/dbhomeFree}
DBHOST=${DBHOST:-forms1.home.lan}
DBPORT=${DBPORT:-1521}
SERVICE=${SERVICE:-FREEPDB1}
DBUSER=${DBUSER:-mm}
ALIAS=${ALIAS:-MM_DB}
SECTION=${SECTION:-mm}
URL=${FORMS_URL:-http://forms1.home.lan:9001}
CFG=$D/config/fmwconfig
WALLET=$CFG/forms_wallet
STAMP=$(date +%Y%m%d-%H%M%S)
backup() { [ -f "$1" ] && cp -p "$1" "$1.$STAMP.bak"; return 0; }
die() { echo "== $*"; exit 1; }
[ "$(id -un)" = oracle ] || die "as oracle: sudo -iu oracle, then this again"

FWEB=$CFG/servers/WLS_FORMS/applications/formsapp_14.1.2/config/formsweb.cfg
FENV=$CFG/servers/WLS_FORMS/applications/formsapp_14.1.2/config/default.env
CGI=$CFG/servers/WLS_REPORTS/applications/reports_14.1.2/configuration/cgicmd.dat
for f in "$FWEB" "$FENV"; do [ -f "$f" ] || die "no $f (DOMAIN_HOME=<the domain of the forms>)"; done

# 1. the wallet and the credential
MK=${MKSTORE:-}
if [ -z "$MK" ]; then
  for c in "$MW/oracle_common/bin/mkstore" "$MW/bin/mkstore"; do [ -x "$c" ] && { MK=$c; break; }; done
fi
[ -n "$MK" ] || MK=$(find "$MW" -name mkstore -type f -perm -u+x 2>/dev/null | head -1)
[ -n "$MK" ] || die "mkstore: not found under $MW"
# mkstore is Java: JAVA_HOME of the user, else the JDK of the domain, else the JDK 21, else java of the PATH
if [ -z "${JAVA_HOME:-}" ] || [ ! -x "$JAVA_HOME/bin/java" ]; then
  JAVA_HOME=$(sed -n 's/^ *JAVA_HOME="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$D/bin/setDomainEnv.sh" 2>/dev/null | head -1)
  [ -x "${JAVA_HOME:-}/bin/java" ] || JAVA_HOME=$(find /usr/lib/jvm -maxdepth 1 -name "jdk-21*" 2>/dev/null | sort | tail -1)
  [ -x "${JAVA_HOME:-}/bin/java" ] || JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")
  [ -x "$JAVA_HOME/bin/java" ] || die "no Java for mkstore: export JAVA_HOME=<the JDK>"
  export JAVA_HOME
fi
(
  export ORACLE_HOME=$MW
  if [ ! -f "$WALLET/cwallet.sso" ]; then
    echo "== a new wallet in $WALLET (mkstore asks for a wallet password, twice)"
    mkdir -p "$WALLET" && chmod 700 "$WALLET"
    "$MK" -wrl "$WALLET" -create || die "the wallet was not created"
  fi
  echo "== is $ALIAS in the wallet? (mkstore asks for the wallet password)"
  out=/dev/null; [ -t 1 ] && out=/dev/tty        # (its prompt shown on a terminal)
  LIST=$("$MK" -wrl "$WALLET" -listCredential | tee "$out")
  if echo "$LIST" | grep -Eq "^[0-9]+: $ALIAS "; then
    echo "== $ALIAS is in the wallet: a new password for it (mkstore asks)"
    "$MK" -wrl "$WALLET" -modifyCredential "$ALIAS" "$DBUSER" || die "mkstore: not changed"
  else
    echo "== $ALIAS = $DBUSER in the wallet (mkstore asks for the password of $DBUSER, twice, then of the wallet)"
    "$MK" -wrl "$WALLET" -createCredential "$ALIAS" "$DBUSER" || die "mkstore: not stored"
  fi
) || exit 1
chmod 600 "$WALLET"/* 2>/dev/null

# 2. tnsnames.ora, sqlnet.ora, default.env
if ! grep -Eqs "^[[:space:]]*${ALIAS}[[:space:]]*=" "$CFG/tnsnames.ora"; then
  backup "$CFG/tnsnames.ora"
  printf '\n%s =\n  (DESCRIPTION = (ADDRESS = (PROTOCOL = TCP)(HOST = %s)(PORT = %s))\n    (CONNECT_DATA = (SERVICE_NAME = %s)))\n' \
    "$ALIAS" "$DBHOST" "$DBPORT" "$SERVICE" >> "$CFG/tnsnames.ora"
  echo "== $ALIAS in $CFG/tnsnames.ora"
fi
if ! grep -qs WALLET_LOCATION "$CFG/sqlnet.ora"; then
  backup "$CFG/sqlnet.ora"
  printf '\nWALLET_LOCATION = (SOURCE = (METHOD = FILE)(METHOD_DATA = (DIRECTORY = %s)))\nSQLNET.WALLET_OVERRIDE = TRUE\n' \
    "$WALLET" >> "$CFG/sqlnet.ora"
  echo "== the wallet in $CFG/sqlnet.ora"
fi
if ! grep -qx "TNS_ADMIN=$CFG" "$FENV"; then
  backup "$FENV"
  sed -i '/^TNS_ADMIN=/d' "$FENV"
  echo "TNS_ADMIN=$CFG" >> "$FENV"
  echo "== TNS_ADMIN=$CFG in default.env"
fi
# the Greek of the forms (MM_TEXT, from the database): a character set with Greek for the runtime; one there
# already: as it is (its value shown)
if ! grep -q '^NLS_LANG=' "$FENV"; then
  backup "$FENV"
  echo "NLS_LANG=AMERICAN_GREECE.AL32UTF8" >> "$FENV"
  echo "== NLS_LANG=AMERICAN_GREECE.AL32UTF8 in default.env (the Greek of the forms)"
else
  echo "== default.env: $(grep '^NLS_LANG=' "$FENV" | tail -1) (AL32UTF8 or EL8ISO8859P7: Greek; US7ASCII: ????)"
fi

# 3. formsweb.cfg: [mm] = [standaloneapp] + userid=/@MM_DB
backup "$FWEB"
awk -v sec="$SECTION" -v alias="$ALIAS" -v wallet="$WALLET" '
  { lines[NR] = $0 }
  END {
    cur = ""; n = 0; k = 0
    for (i = 1; i <= NR; i++) {
      l = lines[i]
      if (match(l, /^[[:space:]]*\[[^]]+\][[:space:]]*$/)) { cur = l; gsub(/^[[:space:]]*\[|\][[:space:]]*$/, "", cur) }
      if (cur == "standaloneapp" && l !~ /^[[:space:]]*\[/ && l !~ /^[[:space:]]*userid[[:space:]]*=/ && l !~ /^[[:space:]]*$/) base[++n] = l
      if (cur != sec) keep[++k] = l
    }
    while (k > 0 && keep[k] ~ /^[[:space:]]*$/) k--
    for (i = 1; i <= k; i++) print keep[i]
    print ""; print "[" sec "]"
    print "# the forms of the mini market; the password is in the wallet (" wallet ")"
    for (i = 1; i <= n; i++) print base[i]
    print "userid=/@" alias
  }' "$FWEB" > "$FWEB.new" && mv "$FWEB.new" "$FWEB"
echo "== [$SECTION] in formsweb.cfg: [standaloneapp] + userid=/@$ALIAS"

# 4. cgicmd.dat: the key of the reports
if [ -f "$CGI" ]; then
  backup "$CGI"
  grep -v "^[[:space:]]*${SECTION}[[:space:]]*:" "$CGI" > "$CGI.new"
  echo "$SECTION: userid=/@$ALIAS %*" >> "$CGI.new" && mv "$CGI.new" "$CGI"
  echo "== cgicmd.dat: $SECTION: userid=/@$ALIAS %*"
else
  echo "== no $CGI: the reports keep their userid"
fi

# 5. the checks: the database through the wallet; what the servlet sends for config=mm
if [ -x "$DB_HOME/bin/sqlplus" ]; then
  who=$(echo "select 'USER=' || user from dual;" | ORACLE_HOME=$DB_HOME TNS_ADMIN=$CFG "$DB_HOME/bin/sqlplus" -s -L "/@$ALIAS" 2>&1)
  if echo "$who" | grep -q "USER=$(echo "$DBUSER" | tr '[:lower:]' '[:upper:]')"; then echo "== /@$ALIAS connects: user $DBUSER"
  else echo "== [!] /@$ALIAS does not connect: $(echo "$who" | grep -m1 -E 'ORA-|SP2-')"; fi
fi
if page=$(curl -fs --max-time 20 "$URL/forms/frmservlet?config=$SECTION&form=MM_MAIN"); then
  if echo "$page" | grep -qi "userid=$DBUSER/"; then echo "== [!] the page carries userid=$DBUSER/...: check [$SECTION]"
  else echo "== the page of config=$SECTION: no password"; fi
else
  echo "== the servlet did not answer ($URL): check it after the restart"
fi
echo "== done. Once, as chris: sudo systemctl restart weblogic-forms"
echo "   forms:   $URL/forms/frmservlet?config=$SECTION&form=MM_MAIN   (FSAL)"
echo "   reports: http://forms1.home.lan:9012/reports/rwservlet?$SECTION&report=<name>.rdf&destype=cache&desformat=PDF"
