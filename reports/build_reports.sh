#!/bin/bash
# build_reports.sh -- on forms1 (Oracle Linux 9, Reports 14.1.2), as oracle: the reports of the mini market,
# from the XML of the repo (mkreports.py) to the .rdf in the folder of the Reports Server (sourceDir of
# rwserver.conf: /u01/app/oracle/reports, ORACLE_FORMS.md 13), with rwconverter. As build_reports.ps1.
#
#   ./build_reports.sh                       all of them
#   ./build_reports.sh MM_LEDGER_P MM_SALES  some
#
# The connection: /@MM_DB, the wallet of the domain (tools/linux/mm_wallet.sh), no password. The log of each
# one: <OUT>/<name>.log. rwconverter is of the Reports Builder: it wants a screen (DISPLAY), as the Builder
# itself: from Windows, MobaXterm with X11-forwarding (ssh -X); a conversion with no screen: REP-3000.
set -u
cd "$(dirname "$0")" || exit 1
HERE=$(pwd)
REPORTS=${*:-MM_LEDGER_I MM_LEDGER_P MM_SALES MM_VAT MM_MIN_STOCK MM_TRIAL_I MM_TRIAL_C MM_TRIAL_S}
USERID=${USERID:-/@MM_DB}
D=${DOMAIN_HOME:-/u01/app/oracle/config/domains/forms_domain}
MW=${MW_HOME:-/u01/app/oracle/middleware}
OUT=${OUT:-/u01/app/oracle/reports}
die() { echo "== $*"; exit 1; }
[ "$(id -un)" = oracle ] || die "as oracle: sudo -iu oracle (with ssh -X: the screen), then this again"
[ -n "${DISPLAY:-}" ] || echo "== [!] no DISPLAY: rwconverter may stop with REP-3000 (MobaXterm: X11-forwarding, ssh -X)"

CONV=
for c in "$D/reports/bin/rwconverter.sh" "$MW/bin/rwconverter.sh" "$MW/bin/rwconverter"; do
  [ -x "$c" ] && { CONV=$c; break; }
done
[ -n "$CONV" ] || die "rwconverter: not in $D/reports/bin nor $MW/bin"
mkdir -p "$OUT" || die "the folder $OUT: not made"
export TNS_ADMIN=$D/config/fmwconfig
export NLS_LANG=AMERICAN_GREECE.AL32UTF8
grep -Eqs '^[[:space:]]*MM_DB[[:space:]]*=' "$TNS_ADMIN/tnsnames.ora" || die "no MM_DB in $TNS_ADMIN/tnsnames.ora: tools/linux/mm_wallet.sh first"

done_=
for r in $REPORTS; do
  name=$(echo "$r" | tr '[:lower:]' '[:upper:]')
  xml=$HERE/$name.xml
  [ -f "$xml" ] || die "no $xml: python3 mkreports.py"
  rdf=$OUT/$name.rdf
  log=$OUT/$name.log
  rm -f "$rdf" "$log"
  echo "== $name: $xml -> $rdf"
  (cd "$OUT" && "$CONV" batch=yes source="$xml" stype=xmlfile dest="$rdf" dtype=rdffile overwrite=yes \
     compile_all=yes userid="$USERID" logfile="$log")
  rc=$?
  [ -f "$log" ] && sed 's/^/   /' "$log"
  if [ ! -f "$rdf" ]; then
    # "Conversion ... canceled" with batch=yes, and the same XML fine with batch=no (MM_SALES on Windows,
    # the first time): once more so (its messages in windows, on the screen)
    echo "== $name: once more with batch=no"
    rm -f "$log"
    (cd "$OUT" && "$CONV" batch=no source="$xml" stype=xmlfile dest="$rdf" dtype=rdffile overwrite=yes \
       compile_all=yes userid="$USERID" logfile="$log")
    rc=$?
    [ -f "$log" ] && sed 's/^/   /' "$log"
  fi
  [ -f "$rdf" ] || die "$name: rwconverter $rc, no .rdf (the messages above, $log)"
  done_="$done_ $name"
done
echo "== OK:$done_ in $OUT"
echo "== the forms open them through SET_REPORTS_URL.sql (once): sqlplus /@MM_DB @../db/SET_REPORTS_URL.sql http://forms1.home.lan:9012 PDF"
echo "== one by hand: http://forms1.home.lan:9012/reports/rwservlet?mm&report=MM_SALES.rdf&destype=cache&desformat=PDF"
