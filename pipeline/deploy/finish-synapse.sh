#!/bin/bash
# Finish the Synapse install: logging path, the settings the first pass missed, restart.
set -euo pipefail
CONF=/etc/matrix-synapse
DATA=/var/lib/matrix-synapse
SERVER_NAME=matrix.btcmap.org

python3 - "$CONF" "$SERVER_NAME" <<'PY'
import pathlib, re, sys, secrets
conf = pathlib.Path(sys.argv[1]); server_name = sys.argv[2]

# 1. logging: the generated config wrote /home/ubuntu/homeserver.log (ProtectHome blocks it)
logcfg = conf / f"{server_name}.log.config"
text = logcfg.read_text().replace("/home/ubuntu/homeserver.log", "/var/log/matrix-synapse/homeserver.log")
logcfg.write_text(text)
print("log file -> /var/log/matrix-synapse/homeserver.log")

# 2. the settings the first pass failed to add (server_name is quoted in the generated file,
#    so the anchor-based insert silently did nothing) — append them as real top-level keys.
hs = conf / "homeserver.yaml"
body = hs.read_text()
wanted = {
    "enable_registration": "false",
    "public_baseurl": f"https://{server_name}/",
    "suppress_key_server_warning": "true",
    "serve_server_wellknown": "false",
    "macaroon_secret_key": f'"{secrets.token_urlsafe(32)}"',
    "form_secret": f'"{secrets.token_urlsafe(32)}"',
}
added = []
for key, value in wanted.items():
    if re.search(rf"^{key}:", body, re.M):
        continue
    body = body.rstrip("\n") + f"\n{key}: {value}\n"
    added.append(key)
if not re.search(r"^registration_shared_secret:", body, re.M):
    body = body.rstrip("\n") + f'\nregistration_shared_secret: "{secrets.token_urlsafe(32)}"\n'
    added.append("registration_shared_secret")
hs.write_text(body)
print("added:", ", ".join(added) or "(nothing missing)")
PY

chown -R synapse:synapse "$CONF" "$DATA"

# 3. LogsDirectory gives the service a writable, correctly-owned /var/log/matrix-synapse
#    under ProtectSystem=strict, instead of loosening the hardening.
if ! grep -q "^LogsDirectory=" /etc/systemd/system/matrix-synapse.service; then
  sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$DATA\nLogsDirectory=matrix-synapse|" /etc/systemd/system/matrix-synapse.service
fi

# 4. validate before restarting — a broken config must never take the service down silently
/opt/synapse/venv/bin/python - <<'PY'
import yaml
cfg = yaml.safe_load(open("/etc/matrix-synapse/homeserver.yaml"))
assert cfg["server_name"] == "matrix.btcmap.org", cfg["server_name"]
assert cfg["enable_registration"] is False, cfg.get("enable_registration")
assert cfg["public_baseurl"].startswith("https://"), cfg.get("public_baseurl")
assert cfg["listeners"][0]["port"] == 8008, cfg["listeners"]
print("config validated: registration off, baseurl set, one loopback listener")
PY

systemctl daemon-reload
systemctl restart matrix-synapse
sleep 8
systemctl is-active matrix-synapse
echo "== loopback =="
curl -s -m 10 http://127.0.0.1:8008/_matrix/client/versions | head -c 120; echo
echo "== log =="
tail -3 /var/log/matrix-synapse/homeserver.log 2>/dev/null || journalctl -u matrix-synapse -n 3 --no-pager
