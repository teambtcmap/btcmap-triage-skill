"""Post the triage digest into a Matrix room as @btcmap-triage.

Reads ~/.config/btcmap/matrix.env (0600) for the homeserver, token and room. Joins the
room if it isn't already joined — the room lives on matrix.org, so this needs the
homeserver's federation to be up (DNS + certificate for matrix.btcmap.org).

    python3 matrix_post.py --text-file reports/digest-2026-10-03.md
    python3 matrix_post.py --check          # login, room resolution, membership only
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_FILE = pathlib.Path("~/.config/btcmap/matrix.env").expanduser()


def env() -> dict[str, str]:
    values = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def call(cfg: dict, method: str, path: str, payload=None, token: str | None = None, timeout: int = 30):
    url = cfg["MATRIX_HOMESERVER"].rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token or cfg['MATRIX_ACCESS_TOKEN']}",
        "Content-Type": "application/json", "User-Agent": "HermesAgent/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
            return response.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body[:200]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-file")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not ENV_FILE.exists():
        print(f"no {ENV_FILE} — run deploy/create-matrix-account.sh first")
        return 1
    cfg = env()
    room = cfg.get("MATRIX_ROOM", "#btcmap-taggers:matrix.org")

    status, who = call(cfg, "GET", "/_matrix/client/v3/account/whoami")
    print(f"whoami: {status} {who.get('user_id', who)}")
    if status != 200:
        return 1

    encoded = urllib.parse.quote(room, safe="")
    status, resolved = call(cfg, "GET", f"/_matrix/client/v3/directory/room/{encoded}")
    print(f"room resolve: {status} {resolved.get('room_id') or resolved}")
    room_id = resolved.get("room_id")
    if status != 200:
        print("  the room is on matrix.org — this needs federation (matrix.btcmap.org DNS + cert)")
        return 1

    status, joined = call(cfg, "GET", "/_matrix/client/v3/joined_rooms")
    in_room = room_id in (joined.get("joined_rooms") or [])
    print(f"membership: {'joined' if in_room else 'not joined'}")
    if not in_room:
        status, result = call(cfg, "POST", f"/_matrix/client/v3/join/{urllib.parse.quote(room_id, safe='')}", {})
        print(f"join: {status} {result if status != 200 else 'ok'}")
        if status != 200:
            print("  if this is M_FORBIDDEN the room needs an invite from a taggers admin")
            return 1
        in_room = True

    if args.check:
        return 0
    if not args.text_file:
        print("nothing to post: pass --text-file or --check")
        return 0

    text = pathlib.Path(args.text_file).read_text().strip()
    txn = __import__("hashlib").sha1(text.encode()).hexdigest()[:24]
    status, result = call(cfg, "PUT",
                          f"/_matrix/client/v3/rooms/{urllib.parse.quote(room_id, safe='')}"
                          f"/send/m.room.message/{txn}",
                          {"msgtype": "m.text", "body": text,
                           "format": "org.matrix.custom.html",
                           "formatted_body": f"<pre>{text}</pre>"})
    print(f"post: {status} event_id={result.get('event_id')}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
