#!/bin/bash
# build_forms.sh -- on a Linux Forms server (forms1), as oracle: the forms of the mini market, XML ->
# .fmb (XML2Forms) -> .fmx (frmcmp_batch) in the first folder of FORMS_PATH of default.env.
#
#   ./build_forms.sh [user@db or /@MM_DB] [FORM ...]      (by default /@MM_DB, all of them)
#
# /@MM_DB: the wallet of the domain (PROPOApplication retro/oracle/linux/forms_wallet.sh, with the
# alias MM_DB of the user mm). MM_TEXT.sql first, with the sqlplus of the database and AL32UTF8.
set -u
cd "$(dirname "$0")" || exit 1
HERE=$(pwd)
USERID=${1:-/@MM_DB}
shift || true
FORMS=${*:-MM_MENU MM_MAIN MM_ITEMS MM_CUSTOMERS MM_SUPPLIERS MM_CARDS MM_RESERVATIONS MM_KITS MM_PROMOS MM_VARIANTS MM_INVOICES MM_PAYMENTS}
MW=${MW_HOME:-/u01/app/oracle/middleware}
DOMAIN=${DOMAIN_HOME:-/u01/app/oracle/config/domains/forms_domain}
DB_HOME=${ORACLE_HOME:-/opt/oracle/product/26ai/dbhomeFree}
export ORACLE_HOME=$MW
export TNS_ADMIN=$DOMAIN/config/fmwconfig

CP=
for j in frmxmltools.jar frmjdapi.jar xmlparserv2.jar xschema.jar; do
  f=$(find "$MW" -name $j 2>/dev/null | head -1)
  [ -n "$f" ] || { echo "$j: not found under $MW"; exit 1; }
  CP=$CP${CP:+:}$f
done
CMP=
for f in "$DOMAIN"/config/fmwconfig/components/FORMS/instances/*/bin/frmcmp_batch.sh "$MW/bin/frmcmp_batch.sh"; do
  [ -x "$f" ] && { CMP=$f; break; }
done
[ -n "$CMP" ] || { echo "frmcmp_batch.sh: not found"; exit 1; }
ENV=$(find "$DOMAIN" -name default.env 2>/dev/null | grep -v /tmp/ | head -1)
FP=$(grep '^FORMS_PATH=' "$ENV" 2>/dev/null | cut -d= -f2 | cut -d: -f1)
[ -d "$FP" ] || { echo "FORMS_PATH of default.env ($ENV): no folder"; exit 1; }

echo "== ../db/MM_TEXT.sql"
out=$(ORACLE_HOME=$DB_HOME NLS_LANG=GREEK_GREECE.AL32UTF8 "$DB_HOME/bin/sqlplus" -s "$USERID" @../db/MM_TEXT.sql < /dev/null)
echo "$out"
echo "$out" | grep -qE 'ORA-|SP2-' && { echo "== MM_TEXT.sql: not installed"; exit 1; }

done_=
for name in $FORMS; do
  cd "$HERE" || exit 1
  # MM_MENU: the menu module of all the forms (.mmb -> .mmx, module_type=menu)
  src=fmb; bin=fmx; type=form
  [ "$name" = MM_MENU ] && { src=mmb; bin=mmx; type=menu; }
  [ -f "$name.xml" ] || { echo "== $name: no $name.xml"; continue; }
  rm -f "$name.$src"
  echo "== $name.xml -> $name.$src"
  LD_LIBRARY_PATH=$MW/lib:${LD_LIBRARY_PATH:-} java -cp "$CP" oracle.forms.util.xmltools.XML2Forms OVERWRITE=YES "$name.xml"
  [ -f "$name.$src" ] || { echo "== no $name.$src: the messages above"; continue; }
  mv "$name.$src" "$FP"/
  cd "$FP" || exit 1
  rm -f "$name.$bin" "$name.err"
  "$CMP" module="$name.$src" userid="$USERID" module_type=$type compile_all=yes batch=yes
  if [ -f "$name.$bin" ]; then echo "== $FP/$name.$bin: OK"; done_="$done_ $name"
  else echo "== no $name.$bin: $FP/$name.err"; tail -30 "$name.err" 2>/dev/null; fi
done
echo "== done:$done_  -- frmservlet?config=mm&form=<FORM>"
