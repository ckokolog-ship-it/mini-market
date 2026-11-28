#!/bin/bash
# deploy.sh -- on the server of k3s (k3s1), as root (sudo): mm-api of the mini market in the cluster (mm-api.yaml), its
# image localhost/mm/mm-api:<tag> (k3s/ship.sh took it to every node). The first time: the password of the user MM of
# the database asked (the Secret mm-db, never in a file of the repo); the account of myDATA, if ship.sh --mydata brought
# it, made the Secret mm-mydata (the file deleted). docs/ODIGIES_K3S.md.
#
#   sudo ./deploy.sh <tag>                   apply, and wait for the rollout
#   sudo ./deploy.sh <tag> --password        the password of MM asked again too
#   sudo ./deploy.sh --status                the pods (on which node), the service
#   sudo ./deploy.sh --undo                  back to the version before
#   sudo ./deploy.sh --delete                mm-api out of the cluster (the namespace; the database stays)
#
# The database: MM_DB_URL; by default the service mm_rw of Data Guard on db1 and db2 (bank: docs/ODIGIES_DG.md §14).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DG_URL='jdbc:oracle:thin:@(DESCRIPTION=(CONNECT_TIMEOUT=5)(TRANSPORT_CONNECT_TIMEOUT=3)(RETRY_COUNT=20)(RETRY_DELAY=3)(ADDRESS_LIST=(LOAD_BALANCE=off)(FAILOVER=on)(ADDRESS=(PROTOCOL=TCP)(HOST=192.168.178.221)(PORT=1521))(ADDRESS=(PROTOCOL=TCP)(HOST=192.168.178.222)(PORT=1521)))(CONNECT_DATA=(SERVICE_NAME=mm_rw)))'
DB_URL=${MM_DB_URL:-$DG_URL}
K="/usr/local/bin/k3s kubectl"
[ -x /usr/local/bin/k3s ] || K=kubectl
N=mm
die() { echo "== $*" >&2; exit 1; }
status() {
  $K -n $N get pods -o wide
  $K -n $N get svc mm-api
  echo "== the mini market: http://<any node>:8300/"
}
case ${1:-} in
  --status) status; exit 0 ;;
  --undo) $K -n $N rollout undo deploy/mm-api; $K -n $N rollout status deploy/mm-api --timeout=300s; status; exit 0 ;;
  --delete)
    read -rp "Το mm-api έξω από το cluster (namespace $N); (ναι/όχι) " ok
    [ "$ok" = ναι ] || [ "$ok" = nai ] || exit 1
    $K delete namespace $N; exit 0 ;;
  ''|-h|--help) sed -n '2,14p' "$0"; exit 0 ;;
esac
TAG=$1
[[ $TAG =~ ^[0-9a-f]{4,40}$ ]] || die "the tag: the commit that ship.sh wrote (e.g. 1a2b3c4)"
[ "$(id -u)" = 0 ] || [ -r /etc/rancher/k3s/k3s.yaml ] || die "as root: sudo $0 $*"
$K create namespace $N --dry-run=client -o yaml | $K apply -f - >/dev/null

if [ "${2:-}" = --password ] || ! $K -n $N get secret mm-db >/dev/null 2>&1; then
  read -rsp "Ο κωδικός του χρήστη MM της βάσης: " P1; echo
  read -rsp "Ξανά: " P2; echo
  [ -n "$P1" ] && [ "$P1" = "$P2" ] || die "empty, or not the same"
  # (from stdin: not in the arguments of a process, not in a file)
  printf '%s' "$P1" | $K -n $N create secret generic mm-db --from-file=password=/dev/stdin \
    --dry-run=client -o yaml | $K apply -f - >/dev/null
  unset P1 P2
  echo "== the Secret mm-db"
  $K -n $N rollout restart deploy/mm-api >/dev/null 2>&1 || true
fi
if [ -f "$HERE/mydata.properties" ]; then
  $K -n $N create secret generic mm-mydata --from-file=mydata.properties="$HERE/mydata.properties" \
    --dry-run=client -o yaml | $K apply -f - >/dev/null
  shred -u "$HERE/mydata.properties" 2>/dev/null || rm -f "$HERE/mydata.properties"
  echo "== the Secret mm-mydata (the file deleted)"
  $K -n $N rollout restart deploy/mm-api >/dev/null 2>&1 || true
fi

sed -e "s#@TAG@#$TAG#g" -e "s#@DB_URL@#$DB_URL#g" "$HERE/mm-api.yaml" | $K apply -f -
$K -n $N rollout status deploy/mm-api --timeout=300s
status
