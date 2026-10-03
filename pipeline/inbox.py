"""Read merchant/submitter replies from bot@btcmap.org and match them to Gitea issues.

Read-only by default. Uses BODY.PEEK so inspecting the mailbox never marks mail as read —
whoever looks at it next sees the same unread state.

Matching is by the trailer our outreach email carries ("issue #NNNNN"), falling back to the
business name against the evidence cache, so a reply that quotes the message still matches.

    python3 inbox.py                     # new mail only, matched and summarised
    python3 inbox.py --all               # every message in INBOX, matched
    python3 inbox.py --apply             # also comment the reply onto the matched Gitea issue
    python3 inbox.py --apply --promote   # ...and move an affirmative reply to confidence/high
"""

from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import json
import pathlib
import re
import ssl
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EMAIL_ENV = pathlib.Path("~/.config/btcmap/email.env").expanduser()
GITEA_TOKEN = pathlib.Path("~/.config/btcmap/gitea.token").expanduser()
GITEA_API = "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data"
CACHE = HERE / "evidence-cache.json"
STATE = HERE / "reports" / "inbox-state.json"
SENT_LOG = HERE / "reports" / "outreach-sent.jsonl"
ISSUE_RE = re.compile(r"issue #(\d+)")

AFFIRMATIVE = re.compile(
    r"(?i)\b(yes|yep|we do|we accept|correct|that's right|confirm(ed)?|go ahead)\b")
NEGATIVE = re.compile(r"(?i)\b(no|nope|we don'?t|not any ?more|stopped|never|remove|stop)\b")


def settings() -> dict[str, str]:
    values = {}
    for line in EMAIL_ENV.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def fetch(mail: imaplib.IMAP4_SSL, uid: bytes) -> email.message.Message:
    status, data = mail.uid("FETCH", uid, "(BODY.PEEK[])")
    return email.message_from_bytes(data[0][1])


def body_text(message: email.message.Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(errors="replace")
                except Exception:
                    continue
        return ""
    try:
        return message.get_payload(decode=True).decode(errors="replace")
    except Exception:
        return str(message.get_payload())


# Automated mail must never be treated as a human reply. A Zoho sign-in notice matched
# issue #25242 by containing the words "United Kingdom" — the business-name fallback alone is
# too loose, so matching now requires either our trailer or a sender we actually emailed.
AUTOMATED_SENDER = re.compile(r"(?i)^(no-?reply|do-?not-?reply|welcome|notifications?|mailer-daemon|"
                              r"postmaster|bounce|automated|alerts?)@")
AUTOMATED_SUBJECT = re.compile(r"(?i)(new (sign-?in|login)|login activity|welcome to zoho|"
                               r"security alert|verify your|password (reset|changed)|"
                               r"out of office|undeliverable)")
GENERIC_NAMES = {"united kingdom", "the bitcoin", "bitcoin", "test", "shop", "store", "market"}


def is_automated(sender: str, subject: str) -> bool:
    return bool(AUTOMATED_SENDER.match(sender or "")) or bool(AUTOMATED_SUBJECT.search(subject or ""))


def emailed_addresses() -> set[str]:
    if not SENT_LOG.exists():
        return set()
    return {json.loads(line)["to"].lower() for line in SENT_LOG.read_text().splitlines() if line.strip()}


def match_issue(subject: str, text: str, cache: dict, sender: str) -> tuple[int | None, str]:
    """Match a reply to an issue: our own trailer first, then a name match — but only from a
    sender we have actually written to, and never on a generic name."""
    haystack = f"{subject}\n{text}"
    m = ISSUE_RE.search(haystack)
    if m:
        return int(m.group(1)), "trailer reference"
    if sender.lower() not in emailed_addresses():
        return None, "unmatched (sender not on the outreach log)"
    lowered = haystack.lower()
    for key, bundle in cache.items():
        name = ((bundle.get("submission") or {}).get("name") or "").strip()
        if len(name) >= 8 and name.lower() not in GENERIC_NAMES and name.lower() in lowered:
            return int(key), f"business name ({name})"
    return None, "unmatched"


def verdict(text: str) -> str:
    if AFFIRMATIVE.search(text) and not NEGATIVE.search(text):
        return "affirmative"
    if NEGATIVE.search(text) and not AFFIRMATIVE.search(text):
        return "negative"
    return "ambiguous"


def gitea(method: str, path: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        GITEA_API + path, data=data, method=method,
        headers={"Authorization": f"token {GITEA_TOKEN.read_text().strip()}",
                 "User-Agent": "HermesAgent/1.0", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return response.status, (json.loads(body) if body.strip() else None)
    except Exception as exc:
        return 0, str(exc)[:200]


def label_id(name: str) -> int | None:
    for page in range(1, 20):
        status, labels = gitea("GET", f"/labels?limit=50&page={page}")
        if not isinstance(labels, list) or not labels:
            break
        for label in labels:
            if label["name"] == name:
                return label["id"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--promote", action="store_true")
    args = ap.parse_args()

    cfg = settings()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()

    context = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(cfg["EMAIL_IMAP_HOST"], int(cfg.get("EMAIL_IMAP_PORT", 993)),
                             ssl_context=context)
    mail.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])
    mail.select("INBOX", readonly=True)
    typ, data = mail.uid("SEARCH", None, "ALL")
    uids = data[0].split()
    print(f"INBOX: {len(uids)} message(s); {len(uids) - len(seen)} new")

    new_seen = set(seen)
    found = 0
    for uid in uids:
        key = uid.decode()
        if key in seen and not args.all:
            continue
        message = fetch(mail, uid)
        sender = email.utils.parseaddr(message.get("From", ""))[1]
        subject = message.get("Subject", "(no subject)")
        text = body_text(message)
        if is_automated(sender, subject):
            new_seen.add(key)
            continue  # automated mail is not a reply and is never matched to an issue
        issue, how = match_issue(subject, text, cache, sender)
        opinion = verdict(text)
        found += 1
        print("\n" + "=" * 70)
        print(f"from    : {sender}\nsubject : {subject}\ndate    : {message.get('Date')}")
        print(f"issue   : #{issue} [{how}]   verdict: {opinion}")
        excerpt = " ".join(text.split())[:400]
        print(f"body    : {excerpt}")
        if args.apply and issue:
            comment = (f"**Reply received by email** from `{sender}` — read as **{opinion}**.\n\n"
                       f"Subject: {subject}\n\n> " + "\n> ".join(
                           " ".join(text.split())[i:i + 300] for i in range(0, min(len(text), 900), 300)))
            status, _ = gitea("POST", f"/issues/{issue}/comments", {"body": comment})
            print(f"   comment on #{issue}: HTTP {status}")
            if args.promote and opinion == "affirmative":
                lid = label_id("confidence/high")
                if lid:
                    status, _ = gitea("POST", f"/issues/{issue}/labels", {"labels": [lid]})
                    print(f"   promoted to confidence/high: HTTP {status}")
        new_seen.add(key)

    mail.logout()
    if not args.all:
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(sorted(new_seen)))
    print(f"\n{found} message(s) reported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
