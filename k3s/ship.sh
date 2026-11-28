#!/bin/bash
# ship.sh -- on forms1, as root (sudo, from the user who has the ssh key of the nodes, e.g. chris): mm-api built
# (./mvnw as the owner of the repo), its image (api/Dockerfile, Docker) taken to the containerd of every node of k3s
# (no registry: ssh, k3s ctr images import -- k8s/node.sh of the bank gave that sudo), and the files of k3s/ to the
# first node; then the command to run there. docs/ODIGIES_K3S.md.
#
#   sudo ./k3s/ship.sh                       the nodes 192.168.178.211 .212 .213
#   sudo ./k3s/ship.sh --mydata              and the account of myDATA (the mydata.properties of the service here)
#   sudo ./k3s/ship.sh --no-build 192.168.178.211 192.168.178.212
#
# The tag: the commit (git rev-parse --short HEAD): every version its own, a rollout to it and back.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
MYDATA_FILE=${MM_MYDATA_FILE:-/u01/app/oracle/mm-api/mydata.properties}
BUILD=1
MYDATA=
NODES=()
for a in "$@"; do
  case $a in
    --no-build) BUILD= ;;
    --mydata) MYDATA=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) NODES+=("$a") ;;
  esac
done
[ ${#NODES[@]} -gt 0 ] || NODES=(192.168.178.211 192.168.178.212 192.168.178.213)
die() { echo "== $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "as root: sudo $0 $*"
U=${SUDO_USER:-root}
OWNER=$(stat -c %U "$ROOT")
TAG=$(runuser -u "$OWNER" -- git -C "$ROOT" rev-parse --short HEAD)
IMAGE=localhost/mm/mm-api:$TAG
command -v docker >/dev/null || die "no Docker on this machine"
ssh_n() { runuser -u "$U" -- ssh -o BatchMode=yes -o ConnectTimeout=10 "$@"; }

if [ -n "$BUILD" ]; then
  echo "== the jar (as $OWNER; the first time Maven downloads: some minutes)"
  runuser -u "$OWNER" -- bash -c "cd '$ROOT/api' && ./mvnw -q -B -DskipTests package"
  echo "== the image $IMAGE"
  docker build -q -f "$ROOT/api/Dockerfile" -t "$IMAGE" "$ROOT/api" >/dev/null
fi
docker image inspect "$IMAGE" >/dev/null 2>&1 || die "no image $IMAGE (without --no-build)"
TAR=$(mktemp /tmp/mm-api-XXXXXX.tar)
trap 'rm -f "$TAR"' EXIT
docker save -o "$TAR" "$IMAGE"
for n in "${NODES[@]}"; do
  echo "== to $n"
  ssh_n "$n" 'sudo -n /usr/local/bin/k3s ctr images import -' < "$TAR" >/dev/null
done

N1=${NODES[0]}
echo "== k3s/ to $N1:mm-k3s/"
ssh_n "$N1" 'mkdir -p mm-k3s'
for f in mm-api.yaml deploy.sh; do ssh_n "$N1" "cat > mm-k3s/$f" < "$HERE/$f"; done
ssh_n "$N1" 'chmod +x mm-k3s/deploy.sh'
if [ -n "$MYDATA" ]; then
  [ -f "$MYDATA_FILE" ] || die "no $MYDATA_FILE (MM_MYDATA_FILE=<the file of the account>)"
  echo "== the account of myDATA to $N1:mm-k3s/mydata.properties (deploy.sh makes it a Secret and deletes it)"
  ssh_n "$N1" 'umask 077 && cat > mm-k3s/mydata.properties' < "$MYDATA_FILE"
fi
echo "== now on $N1:  sudo ~/mm-k3s/deploy.sh $TAG"
