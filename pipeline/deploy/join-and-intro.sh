#!/bin/bash
# One command to run once matrix.btcmap.org resolves: prove the certificate and federation
# endpoints, join #btcmap-taggers, post the introduction, then post today's digest.
#
#   ./join-and-intro.sh              # check only: DNS, cert, federation endpoints, membership
#   ./join-and-intro.sh --post-intro # also join, introduce the bot, post the digest
set -euo pipefail
SERVER=matrix.btcmap.org
ROOM='#btcmap-taggers:matrix.org'
MODE="${1:-check}"
cd "$(dirname "$0")"

echo "== DNS =="
if ! getent hosts "$SERVER" >/dev/null; then
  echo "   $SERVER does not resolve yet — cannot join a federated room until it does."
  exit 1
fi
getent hosts "$SERVER" | sed 's/^/   /'

echo "== certificate + client API through Caddy =="
curl -s -o /dev/null -w "   https://$SERVER/_matrix/client/versions -> HTTP %{http_code}\n" \
  "https://$SERVER/_matrix/client/versions"
echo "== federation discovery (what other homeservers will read) =="
curl -s "https://$SERVER/.well-known/matrix/server"; echo
curl -s "https://$SERVER/.well-known/matrix/client"; echo

echo "== membership =="
if ! python3 matrix_post.py --check; then
  echo "   join failed — if the error is M_FORBIDDEN the room needs an invite from a taggers admin"
  exit 1
fi

if [ "$MODE" != "--post-intro" ]; then
  echo "check-only run: nothing posted"
  exit 0
fi

echo "== introduction =="
python3 matrix_post.py --text-file templates/room-intro.txt

echo "== digest =="
python3 digest.py --out reports/digest-$(date -u +%F).md >/dev/null
python3 matrix_post.py --text-file "reports/digest-$(date -u +%F).md"
echo "done"
