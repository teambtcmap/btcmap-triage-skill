"""Live triage runner: score new BTC Map submissions and label them on Gitea.

Design decisions are taken from the calibration, not from the previous skill:

  * Evidence is gathered fresh at run time (the backtest's leaky signals warn against
    trusting anything reconstructed after the fact).
  * Two axes are reported separately — "is this a real business" and "does the evidence show
    bitcoin" — because conflating them made every thin-but-legitimate record look like junk.
  * The runner writes LABELS and ONE COMMENT. It never closes, rejects or edits anyone's work;
    every decision that matters stays with a human.
  * `already_mapped` is named explicitly so a redundant submission doesn't land in the human
    queue as if it needed investigation.

Idempotent: an issue carrying `triaged/auto` is skipped, so re-runs cost nothing.

    python3 triage_jev.py                 # dry run over the open backlog (default)
    python3 triage_jev.py --limit 5       # dry run, five issues
    python3 triage_jev.py --issue 25419   # dry run, one issue
    python3 triage_jev.py --apply         # actually label + comment
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import evidence as ev  # noqa: E402
from jev_client import PAID, BudgetExceeded, JevClient, expected_value  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
GITEA_API = "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data"
GITEA_TOKEN_FILE = pathlib.Path("~/.config/btcmap/gitea.token").expanduser()
CACHE = HERE / "evidence-cache.json"
SCORES = HERE / "jev-scores.json"
AUDIT = HERE / "reports" / "triage-audit.jsonl"
TRIAGED_LABEL = "triaged/auto"

QUESTIONS = {
    "real_business": {
        "type": "score",
        "instructions": (
            "How likely is this a genuine real-world trading business at the given address, as opposed "
            "to a personal record, placeholder, test entry or purely online listing? Judge the record "
            "itself — name, category, address plausibility, web presence. Do not require proof of "
            "bitcoin acceptance here; that is asked separately."
        ),
        "criteria": ["very unlikely", "unlikely", "uncertain", "likely", "very likely"],
    },
    "premises": {
        "type": "choice",
        "instructions": "What kind of premises is this submission about?",
        "criteria": {
            "business_premises": "a shop, office, venue or other place the public can visit",
            "private_residence": "a private home or personal address",
            "no_fixed_premises": "online-only, mobile or delivery, with no visitable location",
        },
    },
    "bitcoin_evidence": {
        "type": "noul",
        "instructions": (
            "Do the submission and the fetched evidence show that this business accepts bitcoin at this "
            "location? The submitter's own claim is not evidence: require corroboration from the website, "
            "an existing OpenStreetMap entry, or an independent web result."
        ),
    },
    "already_mapped": {
        "type": "noul",
        "instructions": (
            "Does the fetched evidence show this merchant is already mapped — an existing BTC Map or "
            "OpenStreetMap entry with a matching name at the same location?"
        ),
    },
    "duplicate": {
        "type": "noul",
        "instructions": (
            "Is this submission a duplicate of another open submission listed under POSSIBLE DUPLICATES?"
        ),
    },
    "action": {
        "type": "choice",
        "instructions": "What should a BTC Map triager do with this issue?",
        "criteria": {
            "add_to_queue": "evidence is strong enough to prepare an OpenStreetMap edit for review",
            "needs_human_check": "ambiguous — a human must verify before acting",
            "already_mapped": "the merchant is already on the map: nothing to add",
            "close_as_junk": "not a real verifiable merchant: close without adding",
        },
    },
}


# ---------------------------------------------------------------- gitea

def gitea(path: str, method: str = "GET", payload=None):
    token = GITEA_TOKEN_FILE.read_text().strip()
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        GITEA_API + path, data=data, method=method,
        headers={"Authorization": f"token {token}", "User-Agent": "HermesAgent/1.0",
                 "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return response.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:300]


def label_id(name: str) -> int | None:
    """Look a label id up by name. The repo carries 700+ labels, so page until found."""
    for page in range(1, 20):
        status, labels = gitea(f"/labels?limit=50&page={page}")
        if not isinstance(labels, list) or not labels:
            break
        for label in labels:
            if label["name"] == name:
                return label["id"]
    return None


# ---------------------------------------------------------------- scoring

def decide(answers: dict) -> tuple[str, str]:
    """(label, rationale). Bands from the calibration, with one deliberate change.

    Requiring independent bitcoin corroboration for the top band put ZERO of 64 open issues
    there — bitcoin acceptance is rarely provable from the outside, which is exactly what the
    human/outreach step is for. So the high band means "a real business at a visitable address
    that we have no junk signal for"; bitcoin evidence is reported alongside for the human.
    """
    score = expected_value(answers.get("real_business") or {}) or 0.0
    btc = (answers.get("bitcoin_evidence") or {}).get("noul") or 0.0
    premises = (answers.get("premises") or {}).get("choice")
    dupe = (answers.get("already_mapped") or {}).get("noul") or 0.0
    action = (answers.get("action") or {}).get("choice") or "needs_human_check"
    junkish = action == "close_as_junk" or premises == "private_residence"
    if junkish or score < 0.30:
        label = "confidence/low"
    elif score >= 0.70 and premises == "business_premises" and dupe < 0.5:
        label = "confidence/high"
    else:
        label = "confidence/medium"
    return label, (f"real_business {score:.2f} · bitcoin evidence {btc:.2f} · "
                   f"already mapped {dupe:.2f} · {premises} · {action}")


def evidence_lines(bundle: dict) -> list[str]:
    sub = bundle["submission"]
    bm = bundle.get("btc_map") or {}
    site = bundle.get("website") or {}
    dups = bundle.get("duplicates") or {}
    lines = []
    nearby = bm.get("nearby") or []
    if nearby:
        closest = sorted(nearby, key=lambda n: n.get("distance_m") or 9e9)[:3]
        lines.append("Existing BTC Map entries nearby: " + "; ".join(
            f"{n.get('name')} ({n.get('distance_m')} m, {n.get('osm_id')})" for n in closest))
    else:
        lines.append("Existing BTC Map entries nearby: none within 250 m")
    if site.get("present"):
        readers = ", ".join(site.get("reachable_via") or []) or "unreadable"
        bits = [f"reader: {readers}"]
        bits.append("mentions bitcoin" if site.get("mentions_btc") else "no bitcoin mention")
        if site.get("name_on_site"):
            bits.append("name confirmed on site")
        if site.get("address_on_site"):
            bits.append("address confirmed on site")
        if site.get("phone_on_site"):
            bits.append("phone confirmed on site")
        lines.append(f"Website {site.get('url')} — " + ", ".join(bits))
    else:
        lines.append("Website: none submitted")
    kagi = bundle.get("kagi_search") or {}
    if kagi.get("result_count"):
        urls = kagi.get("top_urls") or []
        lines.append(f"Kagi search: {kagi['result_count']} results"
                     + (f", top {urls[0]}" if urls else ""))
    if dups.get("possible_duplicates"):
        d = dups["possible_duplicates"][0]
        lines.append(f"Possible duplicate: #{d['number']} {d['name']} ({d['similarity']} name similarity)")
    return lines


def comment_body(bundle: dict, answers: dict, label: str, rationale: str, model: str) -> str:
    score = expected_value(answers.get("real_business") or {})
    btc = (answers.get("bitcoin_evidence") or {}).get("noul")
    mapped = (answers.get("already_mapped") or {}).get("noul")
    dup = (answers.get("duplicate") or {}).get("noul")
    premises = (answers.get("premises") or {}).get("choice")
    action = (answers.get("action") or {}).get("choice")
    meaning = {
        "confidence/high": "a real business at a visitable address, with no junk signal",
        "confidence/medium": "probably real — a human should confirm before it goes anywhere",
        "confidence/low": "looks like a personal, placeholder or non-business record",
    }[label]
    lines = [
        f"**Automated triage** — `{label}`: {meaning}.",
        "",
        f"Real business {score:.2f} · bitcoin evidence {btc:.2f} (submitted, not independently "
        f"confirmed) · already mapped {mapped:.2f} · duplicate {dup:.2f} · premises {premises} · "
        f"recommended action `{action}`",
        "",
        "Evidence gathered at run time:",
    ]
    lines += [f"- {line}" for line in evidence_lines(bundle)]
    lines += [
        "",
        f"_Model {model}; this is a recommendation for a human triager, not a decision. "
        "Labels: `confidence/high|medium|low`, `triaged/auto`._",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--issue", type=int, default=None)
    ap.add_argument("--apply", action="store_true", help="write labels + comments (default: dry run)")
    ap.add_argument("--model", default=PAID)
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--no-kagi", action="store_true")
    args = ap.parse_args()

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    scores = json.loads(SCORES.read_text()) if SCORES.exists() else {}
    client = JevClient(model=args.model, max_calls=args.budget)

    if args.issue:
        status, issue = gitea(f"/issues/{args.issue}")
        targets = [issue] if isinstance(issue, dict) else []
    else:
        targets = []
        for page in range(1, 5):
            status, raw = gitea(f"/issues?state=open&limit=50&page={page}&type=issues")
            if not isinstance(raw, list) or not raw:
                break
            targets += [i for i in raw if "type/location-submission" in {l["name"] for l in i.get("labels", [])}]
            if len(raw) < 50:
                break

    already = [i["number"] for i in targets if TRIAGED_LABEL in {l["name"] for l in i.get("labels", [])}]
    targets = [i for i in targets if i["number"] not in already][: args.limit]
    print(f"targets: {len(targets)} (skipped {len(already)} already carrying {TRIAGED_LABEL})")
    if not targets:
        return 0

    pause = HERE / "PAUSE"
    if args.apply and pause.exists():
        args.apply = False
        print(f"PAUSE file present ({pause}) — running in dry-run: no labels or comments will be written")

    AUDIT.parent.mkdir(exist_ok=True)
    audit = AUDIT.open("a")
    applied = 0
    for issue in targets:
        number = issue["number"]
        key = str(number)
        bundle = cache.get(key)
        if not bundle or bundle.get("parser_version") != ev.PARSER_VERSION:
            sub = ev.parse_submission(issue)
            bundle = {"submission": sub, "btc_map": ev.btc_map_check(sub),
                      "website": ev.website_check(sub), "duplicates": {"possible_duplicates": []},
                      "parser_version": ev.PARSER_VERSION,
                      "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()}
            if not args.no_kagi:
                bundle["kagi_search"] = ev.kagi_search(sub)
            cache[key] = bundle
            CACHE.write_text(json.dumps(cache, indent=1))
        try:
            body = client.ask(ev_summary(bundle), QUESTIONS)
        except (BudgetExceeded, RuntimeError) as exc:
            print(f"stopping: {exc}")
            break
        answers = body.get("answers") or {}
        label, rationale = decide(answers)
        comment = comment_body(bundle, answers, label, rationale, args.model)
        scores[key] = {"state_hash": None, "model": args.model, "answers": answers,
                       "expected_real_business": expected_value(answers.get("real_business") or {}),
                       "labels": [l["name"] for l in issue.get("labels", [])],
                       "name": bundle["submission"].get("name"),
                       "origin": bundle["submission"].get("origin"), "at": dt.datetime.now(dt.timezone.utc).isoformat()}
        SCORES.write_text(json.dumps(scores, indent=1))

        print(f"\n=== #{number} · {bundle['submission'].get('name')} → {label} ({rationale})")
        print(comment)
        if args.apply:
            # A band is a single value: clear any earlier confidence/* label first, or a re-run
            # that changes its mind leaves the issue carrying two contradictory bands.
            fresh = gitea(f"/issues/{number}")
            current = fresh[1].get("labels", []) if isinstance(fresh[1], dict) else []
            for existing in current:
                if existing["name"].startswith("confidence/"):
                    gitea(f"/issues/{number}/labels/{existing['id']}", "DELETE")
            s1, r1 = gitea(f"/issues/{number}/comments", "POST", {"body": comment})
            lid = label_id(label)
            s2, r2 = gitea(f"/issues/{number}/labels", "POST", {"labels": [lid]}) if lid else (0, "no id")
            tid = label_id(TRIAGED_LABEL)
            s3, r3 = gitea(f"/issues/{number}/labels", "POST", {"labels": [tid]}) if tid else (0, "no id")
            print(f"    applied: comment={s1} label={s2} triaged={s3}")
            applied += 1
            if s1 >= 400 or s2 >= 400:
                print(f"    !! write problem: {r1 if s1 >= 400 else ''} {r2 if s2 >= 400 else ''}")
        audit.write(json.dumps({"at": dt.datetime.now(dt.timezone.utc).isoformat(), "issue": number,
                                "label": label, "rationale": rationale, "applied": args.apply,
                                "model": args.model}) + "\n")
        audit.flush()  # a killed run must never leave Gitea writes that the audit trail lacks
        os.fsync(audit.fileno())
        time.sleep(0.4)
    audit.close()
    print(f"\napplied={applied} dry_run={not args.apply} calls={client.calls} cost=${client.cost_usd():.4f}")
    return 0


def ev_summary(bundle: dict) -> str:
    """State text handed to the judge — same shape the calibration used."""
    import score_backlog
    return score_backlog.summarise(bundle)


if __name__ == "__main__":
    raise SystemExit(main())
