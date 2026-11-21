#!/bin/bash
# backup.sh -- the backup of the database of the mini market on Linux (forms1, Oracle Linux 9), as backup.ps1
# on Windows: all of the schema MM (the items, the documents, the stock, the users, the cards with their PINs)
# with Data Pump (expdp), through the wallet of the domain (the alias MM_DB: no password anywhere).
#
#   ./backup.sh                                   a backup now (as oracle)
#   ./backup.sh --status                          the timer, the last backups
#   sudo ./backup.sh --install [--at 23:15] [--copy-to /mnt/usb/mm_backup] [--keep 14]
#                                                 every day (a systemd timer; a day the server was off: at
#                                                 its next start), and one now
#   sudo ./backup.sh --uninstall                  the timer removed (the backups stay)
#   sudo ./backup.sh --restore /path/mm_20261116_2315.dmp [--force]
#                                                 ALL the data of the mini market replaced with that backup
#                                                 (a .dmp of Windows too: the move from Windows to Linux)
#
# The files: /u01/app/oracle/mm_backup/mm_<date>_<time>.dmp (and its .log), the newest --keep (14) kept;
# with --copy-to (another disk) a copy there too, if it is mounted. The folder: oracle only (a backup has the
# PINs of the cards and their key). --restore: first a backup of what there is now (mm_before_restore_...),
# the service mm-api stopped meanwhile; close the Forms first.
# Once before, as SYS in FREEPDB1: GRANT_BACKUP.sql; and the wallet: tools/linux/mm_wallet.sh (MM_DB).
# The settings of the timer: /etc/mm-backup.conf (written by --install).
set -u
umask 077
HERE=$(cd "$(dirname "$0")" && pwd)
SELF=$HERE/$(basename "$0")
CONF=/etc/mm-backup.conf
# shellcheck disable=SC1090
[ -r "$CONF" ] && . "$CONF"
DIR=${MM_BACKUP_DIR:-/u01/app/oracle/mm_backup}
COPY_TO=${MM_BACKUP_COPY_TO:-}
KEEP=${MM_BACKUP_KEEP:-14}
AT=${MM_BACKUP_AT:-23:15}
DB_HOME=${DB_HOME:-/opt/oracle/product/26ai/dbhomeFree}
DOMAIN=${DOMAIN_HOME:-/u01/app/oracle/config/domains/forms_domain}
TNS=${MM_TNS_ADMIN:-$DOMAIN/config/fmwconfig}
ALIAS=${MM_ALIAS:-MM_DB}
OWNER=${MM_OWNER:-oracle}
SCRIPTS=${MM_SCRIPTS:-/u01/app/oracle/scripts}
UNITS=${MM_UNITS:-/etc/systemd/system}
API=mm-api
MODE=backup
RESTORE=
FORCE=
while [ $# -gt 0 ]; do
  case $1 in
    --status) MODE=status ;;
    --install) MODE=install ;;
    --uninstall) MODE=uninstall ;;
    --restore) MODE=restore; RESTORE=${2:?--restore <file.dmp>}; shift ;;
    --force) FORCE=1 ;;
    --at) AT=${2:?--at HH:MM}; shift ;;
    --copy-to) COPY_TO=${2:?--copy-to <folder>}; shift ;;
    --keep) KEEP=${2:?--keep <n>}; shift ;;
    --dir) DIR=${2:?--dir <folder>}; shift ;;
    -h|--help) sed -n '2,22p' "$SELF"; exit 0 ;;
    *) echo "== unknown: $1 (--help)"; exit 2 ;;
  esac
  shift
done
HISTORY=$DIR/backup_history.txt
export ORACLE_HOME=$DB_HOME TNS_ADMIN=$TNS NLS_LANG=AMERICAN_AMERICA.AL32UTF8
die() { echo "== $*" >&2; exit 1; }
me=$(id -un)

# the database work as oracle (the owner of the database and of its DATA_PUMP_DIR, and of the wallet);
# root (--install, --restore) runs the same script as oracle for it
as_owner() {
  if [ "$me" = "$OWNER" ]; then "$@"
  elif command -v runuser > /dev/null; then
    runuser -u "$OWNER" -- env ORACLE_HOME="$ORACLE_HOME" TNS_ADMIN="$TNS_ADMIN" NLS_LANG="$NLS_LANG" "$@"
  elif command -v sudo > /dev/null; then
    sudo -n -u "$OWNER" env ORACLE_HOME="$ORACLE_HOME" TNS_ADMIN="$TNS_ADMIN" NLS_LANG="$NLS_LANG" "$@"
  else                                  # (neither: su, the command quoted)
    su -s /bin/bash "$OWNER" -c "$(printf '%q ' env ORACLE_HOME="$ORACLE_HOME" TNS_ADMIN="$TNS_ADMIN" NLS_LANG="$NLS_LANG" "$@")"
  fi
}

# a script of SQL*Plus through the wallet; its lines back. Any SP2- or ORA- line: an error
sql() {
  local out
  out=$(printf 'whenever sqlerror exit failure\nset heading off feedback off pagesize 0 linesize 400 trimout on\n%s\nexit\n' "$1" |
        as_owner "$DB_HOME/bin/sqlplus" -s -L "/@$ALIAS" 2>&1) || { echo "SQL*Plus /@$ALIAS: $(echo "$out" | tr '\n' ' ')" >&2; return 1; }
  if echo "$out" | grep -qE '^(SP2-|ORA-|ERROR)'; then echo "SQL*Plus /@$ALIAS: $(echo "$out" | tr '\n' ' ')" >&2; return 1; fi
  echo "$out" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$' || true   # (no lines: fine)
}

# the folder of DATA_PUMP_DIR (where expdp writes, on the side of the database)
pump_dir() {
  local d
  d=$(sql "select directory_path from all_directories where directory_name = 'DATA_PUMP_DIR';") || return 1
  [ -n "$d" ] || { echo "MM may not use DATA_PUMP_DIR: GRANT_BACKUP.sql as SYS first" >&2; return 1; }
  as_owner test -d "$d" || { echo "DATA_PUMP_DIR is $d: no such folder on this computer" >&2; return 1; }
  echo "$d"
}

# the database told how the backup went (mm_core.backup_done: the pages of a manager warn when the last
# good one is old or the last one failed); never an error of its own (the database may be the problem)
state() {
  local t
  t=$(printf '%s' "$2" | tr '\n\r' '  ' | sed "s/'/''/g" | cut -c1-380)
  sql "exec mm_core.backup_done('$1', '$t')
commit;" > /dev/null || echo "== [!] the state of the backup not written to the database"
}

history() { echo "$(date '+%Y-%m-%d %H:%M')  $1" >> "$HISTORY"; }

# Data Pump: expdp or impdp with a file of parameters (the wallet: userid=/@MM_DB); 0 done, 2 done with
# errors (an import: see its log), 1 failed
pump() {
  local tool=$1; shift
  local par out
  par=$(as_owner mktemp /tmp/mm_pump.XXXXXX.par) || return 1
  { echo "userid=/@$ALIAS"; printf '%s\n' "$@"; } | as_owner tee "$par" > /dev/null
  out=$(as_owner "$DB_HOME/bin/$tool" "parfile=$par" 2>&1)
  as_owner rm -f "$par"
  if echo "$out" | grep -qE 'completed with [0-9]+ error'; then return 2; fi
  if echo "$out" | grep -q 'successfully completed'; then return 0; fi
  echo "$out" | tail -15 | sed 's/^/   /' >&2
  return 1
}

new_dir() { as_owner mkdir -p "$1" && as_owner chmod 700 "$1"; }

# the newest $KEEP backups kept (by count, not by days: a server off for weeks keeps its last ones)
remove_old() {
  # shellcheck disable=SC2012
  ls -1t "$1"/mm_2*.dmp 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r f; do
    as_owner rm -f "$f" "${f%.dmp}.log"
  done
}

# a backup now; its file on stdout (the messages on stderr)
backup_now() {
  local prefix=${1:-mm} name pump file mb where=
  new_dir "$DIR" || die "the folder $DIR: not made"
  name=${prefix}_$(date +%Y%m%d_%H%M)
  echo "== expdp: $name.dmp (the schema of $ALIAS, consistent as of now)" >&2
  if ! pump=$(pump_dir) || ! pump expdp directory=DATA_PUMP_DIR "dumpfile=$name.dmp" "logfile=$name.log" \
       flashback_time=systimestamp reuse_dumpfiles=yes; then
    history "FAILED  $name  (expdp; its log in DATA_PUMP_DIR)"
    state N "expdp of $name failed (the log: DATA_PUMP_DIR/$name.log)"
    die "expdp failed: see $name.log in DATA_PUMP_DIR"
  fi
  for ext in dmp log; do
    as_owner cp -f "$pump/$name.$ext" "$DIR/$name.$ext" && as_owner rm -f "$pump/$name.$ext"
  done
  file=$DIR/$name.dmp
  mb=$(as_owner du -m "$file" | cut -f1)
  echo "== $file ($mb MB)" >&2
  if [ -n "$COPY_TO" ]; then
    if [ "$(readlink -f "$COPY_TO")" = "$(readlink -f "$DIR")" ]; then
      echo "== [!] --copy-to is the folder of the backups itself: no copy (another disk)" >&2
    elif [ -d "$(dirname "$COPY_TO")" ] && new_dir "$COPY_TO"; then
      as_owner cp -f "$file" "$DIR/$name.log" "$COPY_TO/" && where="  + $COPY_TO"
      remove_old "$COPY_TO"
      echo "== a copy: $COPY_TO" >&2
    else
      where="  (no copy: $COPY_TO not there)"
      echo "== [!] $COPY_TO is not there (the disk not mounted): only $DIR this time" >&2
    fi
  fi
  remove_old "$DIR"
  history "OK      $name.dmp  $mb MB$where"
  state Y "$name.dmp"
  echo "$file"
}

# all the objects of MM dropped (a few passes: views and packages first, then tables, sequences);
# nothing left, or it stops before the import
DROP_ALL="alter session set ddl_lock_timeout = 60;
declare
  n number;
begin
  for pass in 1 .. 3 loop
    for o in (select object_name, object_type from user_objects
              where object_type in ('PACKAGE', 'PROCEDURE', 'FUNCTION', 'VIEW', 'SYNONYM', 'TYPE', 'TABLE', 'SEQUENCE')
                and object_name not like 'BIN\$%' and object_name not like 'ISEQ\$\$%'
                and not (object_type = 'TABLE' and object_name like 'SYS\\_%' escape '\\')
              order by case object_type when 'TABLE' then 2 when 'SEQUENCE' then 3 else 1 end) loop
      begin
        execute immediate 'drop ' || o.object_type || ' \"' || o.object_name || '\"'
          || case o.object_type when 'TABLE' then ' cascade constraints purge' when 'TYPE' then ' force' end;
      exception when others then null;   -- gone already (a table with its sequence), or next pass
      end;
    end loop;
  end loop;
  select count(*) into n from user_objects
  where object_type in ('PACKAGE', 'VIEW', 'TABLE', 'SEQUENCE') and object_name not like 'ISEQ\$\$%';
  if n > 0 then
    raise_application_error(-20001, n || ' objects of MM still there (a Form open? close the Forms)');
  end if;
end;
/"

need_root() { [ "$me" = root ] || die "as root: sudo $SELF $*"; }
[ -x "$DB_HOME/bin/sqlplus" ] || die "not found: $DB_HOME/bin/sqlplus (DB_HOME=<the folder of the database>)"
[ -f "$TNS/tnsnames.ora" ] || die "no $TNS/tnsnames.ora: tools/linux/mm_wallet.sh first (MM_TNS_ADMIN=<the folder>)"

case $MODE in
status)
  if command -v systemctl > /dev/null && systemctl list-unit-files mm-backup.timer > /dev/null 2>&1; then
    systemctl list-timers mm-backup.timer --no-pager 2>/dev/null | head -3
    systemctl status mm-backup.service --no-pager -n 3 2>/dev/null | sed -n '1,3p;/Main PID\|Active/p'
  else
    echo "== the timer mm-backup is not installed (sudo $SELF --install)"
  fi
  if [ -r "$HISTORY" ] || as_owner test -r "$HISTORY"; then echo "== the last backups:"; as_owner tail -7 "$HISTORY" | sed 's/^/   /'
  else echo "== no backup yet in $DIR"; fi
  ;;
uninstall)
  need_root --uninstall
  systemctl disable --now mm-backup.timer 2> /dev/null
  rm -f "$UNITS/mm-backup.timer" "$UNITS/mm-backup.service" "$SCRIPTS/mm-backup.sh"
  systemctl daemon-reload
  echo "== the timer mm-backup removed (the backups stay in $DIR; $CONF stays)"
  ;;
install)
  need_root --install
  echo "$AT" | grep -qE '^[0-2][0-9]:[0-5][0-9]$' || die "--at HH:MM (e.g. 23:15)"
  file=$(backup_now) || exit 1
  # the settings, read by the script of the timer
  printf 'MM_BACKUP_DIR=%q\nMM_BACKUP_COPY_TO=%q\nMM_BACKUP_KEEP=%q\nMM_BACKUP_AT=%q\nDB_HOME=%q\nMM_TNS_ADMIN=%q\nMM_ALIAS=%q\n' \
    "$DIR" "$COPY_TO" "$KEEP" "$AT" "$DB_HOME" "$TNS" "$ALIAS" > "$CONF"
  chmod 644 "$CONF"
  # the script in the folder of the scripts of systemd (SELinux: bin_t there, ORACLE_FORMS.md 9)
  mkdir -p "$SCRIPTS"
  install -m 755 "$SELF" "$SCRIPTS/mm-backup.sh"
  command -v restorecon > /dev/null && restorecon -R "$SCRIPTS" 2> /dev/null
  cat > "$UNITS/mm-backup.service" <<END
[Unit]
Description=The backup of the database of the mini market (backup.sh, into $DIR)
After=oracle-free-26ai.service
Wants=oracle-free-26ai.service

[Service]
Type=oneshot
User=$OWNER
ExecStart=$SCRIPTS/mm-backup.sh
TimeoutStartSec=2h
END
  cat > "$UNITS/mm-backup.timer" <<END
[Unit]
Description=Every day at $AT: the backup of the mini market

[Timer]
OnCalendar=*-*-* $AT:00
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
END
  systemctl daemon-reload
  systemctl enable --now mm-backup.timer || die "the timer mm-backup did not start"
  echo "== the timer mm-backup: every day at $AT (and at the next start, if the server was off then); --status"
  ;;
restore)
  need_root --restore "$RESTORE"
  [ -f "$RESTORE" ] || die "no such file: $RESTORE"
  RESTORE=$(readlink -f "$RESTORE")
  echo "== ALL the data of the mini market will be replaced with $RESTORE"
  echo "   (first a backup of what there is now; close the Forms; the service mm-api is stopped meanwhile)"
  if [ -z "$FORCE" ]; then
    read -r -p 'Type RESTORE to go on: ' yes
    [ "$yes" = RESTORE ] || { echo "== nothing done"; exit 1; }
  fi
  before=$(backup_now mm_before_restore) || exit 1
  running=
  if command -v systemctl > /dev/null && systemctl is-active --quiet $API 2> /dev/null; then
    running=1; echo "== stop $API"; systemctl stop $API
  fi
  trap '[ -n "$running" ] && { echo "== start $API"; systemctl start $API; }' EXIT
  pump=$(pump_dir) || exit 1
  name=mm_restore_$(date +%Y%m%d_%H%M)
  # (a file of Windows: its owner and rights here are oracle's, so that the database reads it)
  cp -f "$RESTORE" "$pump/$name.dmp" && chown "$OWNER": "$pump/$name.dmp" && chmod 640 "$pump/$name.dmp" ||
    die "not copied into $pump"
  echo "== drop the objects of MM"
  sql "$DROP_ALL" > /dev/null || die "the objects of MM not dropped (the messages above): nothing imported"
  echo "== impdp $(basename "$RESTORE")"
  pump impdp directory=DATA_PUMP_DIR "dumpfile=$name.dmp" "logfile=$name.log"
  rc=$?
  rm -f "$pump/$name.dmp"
  [ $rc -eq 1 ] && die "impdp failed: see $pump/$name.log; what there was: sudo $SELF --restore $before"
  n=$(sql "exec dbms_utility.compile_schema(user, false)
select count(*) from user_objects where status <> 'VALID';" | tail -1)
  history "RESTORE $(basename "$RESTORE")  (before it: $(basename "$before"))  invalid objects: $n"
  state Y "$(basename "$before")"        # (the settings came back with the backup: the last good one again)
  [ $rc -eq 2 ] && echo "== [!] impdp: completed with errors, see $pump/$name.log"
  [ "${n:-0}" != 0 ] && echo "== [!] $n objects of MM not valid: INSTALL.sql again (the data stays)"
  echo "== restored from $RESTORE"
  echo "== if something is wrong: sudo $SELF --restore $before (what there was before)"
  ;;
backup)
  backup_now > /dev/null || exit 1
  ;;
esac
