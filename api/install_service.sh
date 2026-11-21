#!/bin/bash
# install_service.sh -- the REST service and the pages of the mini market (mm-api.jar) as a service of
# systemd on Linux (forms1, Oracle Linux 9), as install_service.ps1 on Windows: it starts with the server,
# after the database, and again by itself if it stops. Through the wallet of the domain (the alias MM_DB,
# tools/linux/mm_wallet.sh): no password anywhere. As root:
#
#   sudo ./install_service.sh                     install, or update (the jar built again: after a git pull)
#   sudo ./install_service.sh --port 8090 --bind 0.0.0.0
#   sudo ./install_service.sh --no-build          the jar of target/ as it is
#   ./install_service.sh --status                 the service, and /api/health
#   sudo ./install_service.sh --uninstall
#
# The service: mm-api (systemctl status mm-api; its log: journalctl -u mm-api), run as oracle (the owner of
# the wallet), started by /u01/app/oracle/scripts/mm-api.sh (SELinux: bin_t, as the start of the forms). Its folder: /u01/app/oracle/mm-api (the jar it runs: a later build does not touch it). --bind
# 0.0.0.0 (the default): the network too (the tills, the phones), plain HTTP with the login of the pages:
# only a network you trust. firewalld, if it runs: the port opened. The build: ./mvnw as oracle (the first
# time it downloads Maven and the driver of Oracle: some minutes; the internet needed then).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
NAME=mm-api
PORT=8090
BIND=0.0.0.0
BUILD=1
MODE=install
OWNER=${MM_OWNER:-oracle}
HOME_DIR=${MM_API_HOME:-/u01/app/oracle/mm-api}
DOMAIN=${DOMAIN_HOME:-/u01/app/oracle/config/domains/forms_domain}
TNS=${MM_TNS_ADMIN:-$DOMAIN/config/fmwconfig}
UNITS=${MM_UNITS:-/etc/systemd/system}
SCRIPTS=${MM_SCRIPTS:-/u01/app/oracle/scripts}
while [ $# -gt 0 ]; do
  case $1 in
    --port) PORT=${2:?--port <n>}; shift ;;
    --bind) BIND=${2:?--bind <address>}; shift ;;
    --no-build) BUILD= ;;
    --status) MODE=status ;;
    --uninstall) MODE=uninstall ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "== unknown: $1 (--help)"; exit 2 ;;
  esac
  shift
done
die() { echo "== $*" >&2; exit 1; }

health() {
  local k r
  for k in $(seq 30); do
    if r=$(curl -fs --max-time 3 "http://127.0.0.1:$PORT/api/health"); then
      echo "== http://127.0.0.1:$PORT/api/health: $r"; return 0
    fi
    [ "$k" = 1 ] && echo "== waiting for the service (some seconds)"
    sleep 2
  done
  echo "== no answer on port $PORT yet: journalctl -u $NAME -n 50"
  return 1
}

if [ "$MODE" = status ]; then
  systemctl status $NAME --no-pager -n 5 2>/dev/null || echo "== the service $NAME is not installed"
  systemctl is-active --quiet $NAME && health
  exit 0
fi
[ "$(id -u)" = 0 ] || die "as root: sudo $0 $*"

if [ "$MODE" = uninstall ]; then
  systemctl disable --now $NAME 2>/dev/null
  rm -f "$UNITS/$NAME.service" "$SCRIPTS/$NAME.sh"
  systemctl daemon-reload
  if systemctl is-active --quiet firewalld; then
    firewall-cmd -q --permanent --remove-port="$PORT/tcp" 2>/dev/null && firewall-cmd -q --reload
  fi
  echo "== the service $NAME removed (its folder stays: $HOME_DIR)"
  exit 0
fi

# the JDK: 17 or later (the JDK 21 of the forms, ORACLE_FORMS.md 3)
JDK=${JAVA_HOME:-}
[ -x "${JDK:-}/bin/java" ] || JDK=$(find /usr/lib/jvm -maxdepth 1 -name "jdk-21*" 2>/dev/null | sort | tail -1)
[ -x "${JDK:-}/bin/java" ] || JDK=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")
[ -x "$JDK/bin/java" ] || die "no Java: JAVA_HOME=<a JDK 17 or later>"
[ -f "$TNS/forms_wallet/cwallet.sso" ] && grep -Eqs '^[[:space:]]*MM_DB[[:space:]]*=' "$TNS/tnsnames.ora" ||
  die "no wallet with MM_DB in $TNS: tools/linux/mm_wallet.sh first (as oracle)"

JAR=$HERE/target/mm-api.jar
if [ -n "$BUILD" ]; then
  echo "== mvnw package, as $OWNER (the jar of the service)"
  runuser -u "$OWNER" -- env JAVA_HOME="$JDK" bash -c "cd '$HERE' && ./mvnw -q -B clean package -DskipTests" ||
    die "mvnw package failed (the messages above; the folder $HERE must be $OWNER's)"
fi
[ -f "$JAR" ] || die "no $JAR (without --no-build: it is built)"

# the service stopped while its jar changes; then the jar into its folder
systemctl is-active --quiet $NAME && { echo "== stop $NAME"; systemctl stop $NAME; }
GROUP=$(id -gn "$OWNER")
install -d -o "$OWNER" -g "$GROUP" -m 750 "$HOME_DIR"
install -o "$OWNER" -g "$GROUP" -m 640 "$JAR" "$HOME_DIR/mm-api.jar" || die "the jar not copied into $HOME_DIR"
runuser -u "$OWNER" -- test -r "$HOME_DIR/mm-api.jar" || die "$OWNER cannot read $HOME_DIR/mm-api.jar (ls -la $HOME_DIR)"
# the start through a script in the folder of the scripts of systemd (SELinux: bin_t there, ORACLE_FORMS.md 9):
# java started by systemd directly (its file not bin_t) stays in the domain of systemd, which may not read the
# jar under /u01 ("Unable to access jarfile"); from a bin_t script it runs unconfined, as the forms do
mkdir -p "$SCRIPTS"
cat > "$SCRIPTS/$NAME.sh" <<END
#!/bin/bash
# made by install_service.sh (mini market): the start of the service $NAME
exec "$JDK/bin/java" -Xmx512m -jar "$HOME_DIR/mm-api.jar"
END
chmod 755 "$SCRIPTS/$NAME.sh"
command -v restorecon > /dev/null && restorecon -R "$SCRIPTS" "$HOME_DIR" 2> /dev/null
cat > "$UNITS/$NAME.service" <<END
# made by install_service.sh: run it again to change it
[Unit]
Description=Mini market API (mm-api): the REST service and the pages, port $PORT ($BIND)
After=network-online.target oracle-free-26ai.service
Wants=network-online.target oracle-free-26ai.service
# (it fails again and again: it stops trying, journalctl -u $NAME says why)
StartLimitIntervalSec=10min
StartLimitBurst=5

[Service]
User=$OWNER
WorkingDirectory=$HOME_DIR
Environment=JAVA_HOME=$JDK
Environment=MM_TNS_ADMIN=$TNS
Environment=MM_WALLET=$TNS/forms_wallet
Environment=MM_DB_URL=jdbc:oracle:thin:/@MM_DB
Environment=MM_API_PORT=$PORT
Environment=MM_API_BIND=$BIND
ExecStart=$SCRIPTS/$NAME.sh
SuccessExitStatus=143
Restart=on-failure
RestartSec=10
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
END
systemctl daemon-reload
systemctl reset-failed $NAME 2> /dev/null
systemctl enable $NAME > /dev/null 2>&1
# the network: the port open, if firewalld runs (it does not on forms1: ORACLE_FORMS.md 2)
if [ "$BIND" != 127.0.0.1 ] && systemctl is-active --quiet firewalld; then
  firewall-cmd -q --permanent --add-port="$PORT/tcp" && firewall-cmd -q --reload && echo "== firewalld: $PORT/tcp open"
fi
systemctl start $NAME || die "the start failed: journalctl -u $NAME -n 50"
if health; then
  echo "== the service $NAME runs: http://$(hostname -f 2>/dev/null || hostname):$PORT/  (systemctl status $NAME)"
else
  journalctl -u $NAME -n 15 --no-pager 2> /dev/null | sed 's/^/   /'
  if command -v ausearch > /dev/null && ausearch -m avc -ts recent 2> /dev/null | grep -q "$NAME\\|java"; then
    echo "== [!] SELinux refused something (ausearch -m avc -ts recent): ls -laZ $SCRIPTS $HOME_DIR"
  fi
  exit 1
fi
