#!/bin/bash
# Install Synapse on the BTC Map VPS for the triage bot.
#
# Idempotent: safe to re-run. Nothing here touches the existing btcmap services —
# it adds /opt/synapse, /etc/matrix-synapse, a systemd unit, and one Caddy vhost.
#
# The server name is the one thing that cannot be changed after federation starts
# (changing server_name later orphans every account), so it is a parameter:
#
#   ./install-synapse.sh matrix.btcmap.org
#
set -euo pipefail

SERVER_NAME="${1:-matrix.btcmap.org}"
CONF=/etc/matrix-synapse
DATA=/var/lib/matrix-synapse
VENV=/opt/synapse/venv
SYNAPSE_USER=synapse

echo "== server name: $SERVER_NAME"

if ! id "$SYNAPSE_USER" >/dev/null 2>&1; then
  useradd --system --home "$DATA" --create-home --shell /usr/sbin/nologin "$SYNAPSE_USER"
  echo "   created user $SYNAPSE_USER"
fi

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  echo "   created venv"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet --upgrade matrix-synapse
echo "   synapse $("$VENV/bin/python" -c 'import synapse; print(synapse.__version__)')"

mkdir -p "$CONF" "$DATA/media_store"
if [ ! -f "$CONF/homeserver.yaml" ]; then
  "$VENV/bin/python" -m synapse.app.homeserver \
    --server-name "$SERVER_NAME" \
    --config-path "$CONF/homeserver.yaml" \
    --data-directory "$DATA" \
    --generate-config --report-stats=no >/dev/null
  echo "   generated homeserver.yaml"
else
  echo "   homeserver.yaml already present — leaving it alone"
fi

# Post-generation settings. Every one of these is deliberate:
#   * SQLite: one bot account and one room needs nothing else; no Postgres to maintain.
#   * listeners on loopback only: Caddy terminates TLS and is the only public face.
#   * registration off: accounts are made with the shared secret, never by the public.
python3 - "$CONF/homeserver.yaml" "$SERVER_NAME" <<'PY'
import sys, secrets, re
path, server_name = sys.argv[1], sys.argv[2]
text = open(path).read()

def set_key(text, key, value):
    if re.search(rf"^{key}:", text, re.M):
        return re.sub(rf"^{key}:.*$", f"{key}: {value}", text, count=1, flags=re.M)
    return text.replace("server_name: " + server_name, f"server_name: {server_name}\n{key}: {value}", 1)

settings = {
    "public_baseurl": f"https://{server_name}/",
    "enable_registration": "false",
    "suppress_key_server_warning": "true",
    "serve_server_wellknown": "false",
    "registration_shared_secret": f'"{secrets.token_urlsafe(32)}"',
    "macaroon_secret_key": f'"{secrets.token_urlsafe(32)}"',
    "form_secret": f'"{secrets.token_urlsafe(32)}"',
    "media_store_path": "/var/lib/matrix-synapse/media_store",
}
for key, value in settings.items():
    if key == "form_secret" and re.search(r"^form_secret:", text, re.M):
        text = re.sub(r"^form_secret:.*$", f"form_secret: {value}", text, count=1, flags=re.M)
        continue
    if key == "macaroon_secret_key" and re.search(r"^macaroon_secret_key:", text, re.M):
        text = re.sub(r"^macaroon_secret_key:.*$", f"macaroon_secret_key: {value}", text, count=1, flags=re.M)
        continue
    text = set_key(text, key, value)

# listener: client + federation on loopback, Caddy in front
text = re.sub(
    r"listeners:\n(?:  -.*\n(?:      .*\n)*)+",
    "listeners:\n"
    "  - port: 8008\n"
    "    tls: false\n"
    "    bind_addresses: ['127.0.0.1']\n"
    "    type: http\n"
    "    x_forwarded: true\n"
    "    resources:\n"
    "      - names: [client, federation, media]\n"
    "        compress: false\n",
    text, count=1)

# SQLite lives with the data, not next to the config
text = re.sub(r"^    database: \S+$", "    database: /var/lib/matrix-synapse/homeserver.db", text,
              count=1, flags=re.M)
open(path, "w").write(text)
print("   config updated (public_baseurl, sqlite, loopback listener, secrets, registration off)")
PY

chown -R "$SYNAPSE_USER":"$SYNAPSE_USER" "$CONF" "$DATA" "$VENV"

cat >/etc/systemd/system/matrix-synapse.service <<EOF
[Unit]
Description=Matrix Synapse homeserver ($SERVER_NAME)
After=network-online.target

[Service]
Type=notify
User=$SYNAPSE_USER
WorkingDirectory=$DATA
ExecStart=$VENV/bin/python -m synapse.app.homeserver --config-path $CONF/homeserver.yaml
Restart=always
RestartSec=5
TimeoutStartSec=120
# hardening: the process only ever needs its own data + config
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA
ReadOnlyPaths=$CONF

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now matrix-synapse.service
sleep 6
systemctl is-active matrix-synapse.service

echo "== loopback check =="
curl -s -m 10 http://127.0.0.1:8008/_matrix/client/versions | head -c 120; echo

echo "== caddy vhost =="
if ! grep -q "^$SERVER_NAME {" /etc/caddy/Caddyfile; then
  cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-$(date +%Y%m%dT%H%M%S)"
  cat >>/etc/caddy/Caddyfile <<EOF

$SERVER_NAME {
	reverse_proxy 127.0.0.1:8008
}
EOF
  echo "   added vhost block"
else
  echo "   vhost already present"
fi
caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 && systemctl reload caddy && echo "   caddy reloaded (cert renews as soon as DNS points here)"
