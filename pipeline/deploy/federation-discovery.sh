#!/bin/bash
# Federation discovery for matrix.btcmap.org.
#
# By default another server reaches ours on the server_name's port *8448*. Nothing listens
# there (nor should it — Caddy owns 443 and ufw allows only the ports we mean to serve), so
# federation must be delegated to :443 explicitly via .well-known/matrix/server. Without
# this, matrix.org would try 8448, fail, and the join would never complete even once DNS is
# in place.
set -euo pipefail
SERVER_NAME=matrix.btcmap.org
CADDYFILE=/etc/caddy/Caddyfile

cp "$CADDYFILE" "$CADDYFILE.bak-$(date +%Y%m%dT%H%M%S)"

python3 - "$CADDYFILE" "$SERVER_NAME" <<'PY'
import pathlib, re, sys
path, server = pathlib.Path(sys.argv[1]), sys.argv[2]
text = path.read_text()

block = f'''{server} {{
	# Federation discovery: point other homeservers at :443 (Caddy) instead of the default :8448
	handle /.well-known/matrix/server {{
		header Content-Type application/json
		respond `{{"m.server": "{server}:443"}}` 200
	}}
	handle /.well-known/matrix/client {{
		header Content-Type application/json
		respond `{{"m.homeserver": {{"base_url": "https://{server}"}}}}` 200
	}}
	reverse_proxy 127.0.0.1:8008
}}'''

pattern = re.compile(rf"^{re.escape(server)} \{{.*?^\}}$", re.M | re.S)
if pattern.search(text):
    text = pattern.sub(block, text, count=1)
    print("vhost updated with well-known handlers")
elif f"{server} {{" in text:
    print("vhost present but not rewritten — check manually")
else:
    text = text.rstrip("\n") + "\n\n" + block + "\n"
    print("vhost appended with well-known handlers")
path.write_text(text)
PY

caddy validate --config "$CADDYFILE" >/dev/null && echo "caddy config valid"
systemctl reload caddy
echo "reloaded"
echo "== ufw: are 80/443 allowed? =="
ufw status | grep -E "^(80|443)/tcp|^80,443" || echo "(no explicit rule — checking live listener instead)"
ss -lnt | awk '{print $4}' | grep -E ":(80|443)$"
