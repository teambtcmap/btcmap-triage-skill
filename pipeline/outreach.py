"""Draft and (only when explicitly unlocked) send BTC Map verification emails.

Draft is the default. Sending needs BOTH `--send` and the presence of an approval file, so a
scheduled run or a mistyped flag cannot mail a real business by accident.

Who gets the email matters: the submission's `contact` field is usually the *submitter's*
address (someone who asked for the place to be added), not the merchant's. The submitter is
the safer first approach — they left an address expecting follow-up. Emailing the merchant
directly needs an address found on their own website, which the evidence stage records but
does not scrape contacts from.

    python3 outreach.py --issue 25465                 # draft, prints exactly what would send
    python3 outreach.py --issue 25465 --to merchant    # draft to the merchant's site contact, if known
    python3 outreach.py --issue 25465 --send           # only if the approval file exists
"""

from __future__ import annotations

import argparse
import email.message
import json
import pathlib
import smtplib
import ssl
import sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "templates" / "outreach-email.txt"
CACHE = HERE / "evidence-cache.json"
SENT_LOG = HERE / "reports" / "outreach-sent.jsonl"
EMAIL_ENV = pathlib.Path("~/.config/btcmap/email.env").expanduser()
APPROVAL = pathlib.Path("~/.config/btcmap/outreach-approved").expanduser()
GITEA_ISSUE = "https://gitea.btcmap.org/teambtcmap/btcmap-data/issues/{n}"
SIGNATURE = "BTC Map triage volunteers"


def settings() -> dict[str, str]:
    values = {}
    for line in EMAIL_ENV.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def recipient(bundle: dict, prefer: str) -> tuple[str | None, str]:
    sub = bundle["submission"]
    submitter = sub.get("contact")
    site = bundle.get("website") or {}
    if prefer == "submitter" and submitter and "@" in submitter:
        return submitter, "submitter (the address left with the submission)"
    if submitter and "@" in submitter and prefer == "merchant":
        # no merchant address is scraped by design; fall back with a note rather than guess
        return submitter, "submitter (no merchant address known — the site contact is not scraped)"
    if submitter and "@" in submitter:
        return submitter, "submitter"
    return None, f"no address (website {site.get('url') or 'none'})"


def render(bundle: dict, to: str) -> email.message.EmailMessage:
    sub = bundle["submission"]
    body = TEMPLATE.read_text()
    message = email.message.EmailMessage()
    message["From"] = f"BTC Map <{settings()['EMAIL_ADDRESS']}>"
    message["To"] = to
    message["Subject"] = body.splitlines()[0].replace("Subject: ", "").format(
        name=sub.get("name") or "your business")
    message["Reply-To"] = settings()["EMAIL_ADDRESS"]
    message["Date"] = email.utils.formatdate(localtime=True)
    message.set_content(body.split("\n", 1)[1].format(
        name=sub.get("name") or "",
        address=sub.get("address") or "",
        payment_methods=(sub.get("payment_methods") or "Bitcoin").replace(",", ", "),
        origin=sub.get("origin") or "unknown",
        submission_id=sub.get("submission_id") or "?",
        issue_number=sub.get("number"),
        signature=SIGNATURE,
    ).strip())
    return message


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--to", choices=["submitter", "merchant"], default="submitter")
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()

    bundle = (json.loads(CACHE.read_text())).get(str(args.issue))
    if not bundle:
        print(f"no evidence bundle for #{args.issue} — run triage_jev.py first")
        return 1

    to, why = recipient(bundle, args.to)
    if not to:
        print(f"cannot draft: {why}")
        return 1

    message = render(bundle, to)
    print(f"issue   : {GITEA_ISSUE.format(n=args.issue)}")
    print(f"to      : {to}  [{why}]")
    print(f"from    : {message['From']}")
    print(f"subject : {message['Subject']}")
    print("-" * 68)
    print(message.get_content().strip())
    print("-" * 68)

    if not args.send:
        print("draft only — nothing sent. Add --send once the wording is approved.")
        return 0
    if not APPROVAL.exists():
        print(f"refusing to send: {APPROVAL} does not exist.")
        print("  approve the wording first, then:  touch " + str(APPROVAL))
        return 1
    if SENT_LOG.exists():
        already = {json.loads(l)["issue"] for l in SENT_LOG.read_text().splitlines() if l.strip()}
        if args.issue in already:
            print(f"#{args.issue} was already emailed — not sending twice")
            return 0

    cfg = settings()
    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["EMAIL_SMTP_HOST"], int(cfg.get("EMAIL_SMTP_PORT", 587)), timeout=30) as server:
        server.starttls(context=context)
        server.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])
        server.send_message(message)
    SENT_LOG.parent.mkdir(exist_ok=True)
    with SENT_LOG.open("a") as handle:
        handle.write(json.dumps({"issue": args.issue, "to": to, "why": why,
                                 "subject": message["Subject"]}) + "\n")
    print(f"sent to {to}; logged in {SENT_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
