#!/usr/bin/env python3
"""Read-only IMAP/SMTP credential probe for mailbox setup.

Answers one question: do these host/port/TLS/credential values actually work?
That way a failing client command can be attributed to the config rather than to
the mailbox.

Read-only: logs in over IMAP, lists folders, counts INBOX messages, and logs in
over SMTP without sending anything. The password is never printed - pass it via
--password-cmd (a shell command that writes it to stdout) or --password-file.

Usage:
  probe_mailbox.py --user you@example.com \
      --password-cmd 'cat ~/.config/protonmail/bridge-pass' \
      --imap-host 127.0.0.1 --imap-port 1143 --imap-tls none \
      --smtp-host 127.0.0.1 --smtp-port 1025

Exit code 0 only when every requested leg succeeds.
"""

from __future__ import annotations

import argparse
import imaplib
import smtplib
import ssl
import subprocess
import sys
from pathlib import Path


def resolve_password(args: argparse.Namespace) -> str:
    if args.password_cmd:
        out = subprocess.run(
            args.password_cmd, shell=True, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    if args.password_file:
        return Path(args.password_file).expanduser().read_text().strip()
    raise SystemExit("need --password-cmd or --password-file")


def tls_context() -> ssl.SSLContext:
    # Loopback bridges and self-signed endpoints are the normal case here.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def probe_imap(args: argparse.Namespace, password: str) -> bool:
    modes = [args.imap_tls] if args.imap_tls != "auto" else ["none", "starttls", "ssl"]
    last = None
    for mode in modes:
        try:
            if mode == "ssl":
                m = imaplib.IMAP4_SSL(args.imap_host, args.imap_port, ssl_context=tls_context())
            else:
                m = imaplib.IMAP4(args.imap_host, args.imap_port)
                if mode == "starttls":
                    m.starttls(tls_context())
            m.login(args.user, password)
            folders = [f.decode(errors="replace") for f in (m.list()[1] or [])]
            ok, data = m.select("INBOX")
            count = len(m.search(None, "ALL")[1][0].split()) if ok == "OK" else -1
            state = data[0].decode() if data and data[0] else "?"
            print(f"IMAP OK ({args.imap_host}:{args.imap_port}, encryption={mode})")
            print(f"  folders ({len(folders)}): " + "; ".join(folders[:12]))
            print(f"  INBOX: status={state} messages={count}")
            m.logout()
            return True
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            last = exc
            print(f"IMAP fail ({mode}): {type(exc).__name__}: {exc}")
    print(f"IMAP could not authenticate: {last}")
    return False


def probe_smtp(args: argparse.Namespace, password: str) -> bool:
    try:
        s = smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=15)
        s.ehlo()
        tls_note = ""
        if args.smtp_tls != "none":
            try:
                s.starttls(context=tls_context())
                s.ehlo()
                tls_note = "start-tls"
            except Exception as exc:  # noqa: BLE001
                print(f"  (starttls unavailable: {exc})")
        s.login(args.user, password)
        note = f", {tls_note}" if tls_note else ""
        print(f"SMTP OK ({args.smtp_host}:{args.smtp_port}{note}) - logged in, nothing sent")
        s.quit()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"SMTP fail: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--user", required=True, help="full login, usually the email address")
    p.add_argument("--password-cmd", help="shell command printing the password (preferred)")
    p.add_argument("--password-file", help="file containing the password")
    p.add_argument("--imap-host")
    p.add_argument("--imap-port", type=int, default=993)
    p.add_argument(
        "--imap-tls",
        choices=["auto", "none", "ssl", "starttls"],
        default="auto",
        help="loopback bridges speak plaintext: use 'none' (auto tries none, starttls, ssl)",
    )
    p.add_argument("--smtp-host")
    p.add_argument("--smtp-port", type=int, default=587)
    p.add_argument("--smtp-tls", choices=["none", "starttls"], default="starttls")
    p.add_argument("--no-smtp", action="store_true", help="skip the SMTP leg")
    args = p.parse_args()

    password = resolve_password(args)
    results = []
    if args.imap_host:
        results.append(probe_imap(args, password))
    if args.smtp_host and not args.no_smtp:
        results.append(probe_smtp(args, password))
    if not results:
        p.error("pass at least one of --imap-host / --smtp-host")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
