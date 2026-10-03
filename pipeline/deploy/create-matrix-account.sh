#!/bin/bash
# Create the BTC Map triage bot account on the local Synapse and store its access token.
#
# Runs on the btcmap VPS. The password is generated here and written only to
# ~/.config/btcmap/matrix.env (0600) — never printed, never in the transcript.
set -euo pipefail

USER_ID=btcmap-triage
CONF=/etc/matrix-synapse/homeserver.yaml
VENV=/opt/synapse/venv
OUT="$HOME/.config/btcmap/matrix.env"
BASE=http://127.0.0.1:8008

mkdir -p "$(dirname "$OUT")"
touch "$OUT"; chmod 600 "$OUT"

if grep -q '^MATRIX_ACCESS_TOKEN=' "$OUT" 2>/dev/null; then
  echo "token already stored — not creating a second account"
  exit 0
fi

PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

# Registration is disabled on the homeserver (deliberately), so the account is made with
# the registration shared secret — the admin path — not the public /register endpoint.
if sudo -u synapse "$VENV/bin/register_new_matrix_user" \
     -c "$CONF" -u "$USER_ID" -p "$PASSWORD" --no-admin "$BASE" >/tmp/register-bot.log 2>&1; then
  CREATED=yes
else
  CREATED=no
  echo "account creation reported a problem:"; sed -n '1,5p' /tmp/register-bot.log
fi

TOKEN="$(curl -s -m 15 -X POST "$BASE/_matrix/client/v3/login" \
  -H 'Content-Type: application/json' \
  -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"'"$USER_ID"'"},"password":"'"$PASSWORD"'"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')"

if [ -z "$TOKEN" ]; then
  echo "login failed — account may exist with a different password; see journal"
  exit 1
fi

cat >"$OUT" <<EOF
# BTC Map triage bot. Created $(date -u +%Y-%m-%dT%H:%M:%SZ) on matrix.btcmap.org
MATRIX_HOMESERVER=http://127.0.0.1:8008
MATRIX_PUBLIC_HOMESERVER=https://matrix.btcmap.org
MATRIX_USER_ID=@$USER_ID:matrix.btcmap.org
MATRIX_ACCESS_TOKEN=$TOKEN
MATRIX_PASSWORD=$PASSWORD
MATRIX_ROOM=#btcmap-taggers:matrix.org
EOF
chmod 600 "$OUT"

echo "account created: $CREATED"
echo "stored: $OUT"
echo "identity check:"
curl -s -m 10 "$BASE/_matrix/client/v3/account/whoami" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  user_id:", d.get("user_id"), "| device:", d.get("device_id"))'
