"""Phase 1 calibration: score the historical backlog with Jev and report how well it separates.

Reads the evidence bundles from evidence.py, asks Jev a fixed question set, and writes
reports/backlog-<date>.json plus a markdown report. Nothing is written to Gitea.

Ground truth is the repo's own terminal labels (status/added / status/rejected) — which
measure the OUTCOME of human triage, not authenticity. The report says so, and includes
an unlabelled/unresolved bucket rather than pretending every issue has a verdict.

Usage:
    python3 score_backlog.py [--limit 250] [--model jev-1.13] [--force]
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import hashlib
import statistics
import time
from pathlib import Path

from jev_client import FREE, PAID, BudgetExceeded, JevClient, expected_value

HERE = Path(__file__).resolve().parent
CACHE = HERE / "evidence-cache.json"
SCORES = HERE / "jev-scores.json"
REPORTS = HERE / "reports"

QUESTIONS = {
    "bitcoin_evidence": {
        "type": "noul",
        "instructions": (
            "Do the submission and the fetched evidence show that this business accepts bitcoin at "
            "this location? The submitter's own claim is not evidence: require corroboration from the "
            "website, an existing OSM/BTC Map entry, or an independent web result."
        ),
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
    "duplicate": {
        "type": "noul",
        "instructions": (
            "Does the evidence suggest this submission is a duplicate of an existing BTC Map/"
            "OpenStreetMap entry or of another open submission listed under POSSIBLE DUPLICATES?"
        ),
    },
    "real_business": {
        "type": "score",
        "instructions": (
            "How likely is this a genuine real-world trading business at the given address, as opposed "
            "to a personal record, placeholder, test entry or purely online listing? Judge the record "
            "itself (name, category, address plausibility, web presence) — do NOT require proof of "
            "bitcoin acceptance for this question, that is asked separately."
        ),
        "criteria": ["very unlikely", "unlikely", "uncertain", "likely", "very likely"],
    },
    "action": {
        "type": "choice",
        "instructions": "What should a BTC Map triager do with this issue?",
        "criteria": {
            "add_to_queue": "evidence is strong enough to prepare an OpenStreetMap edit for review",
            "needs_human_check": "ambiguous — a human must verify before acting",
            "close_as_junk": "not a real verifiable merchant: close without adding",
        },
    },
}


def summarise(bundle: dict) -> str:
    s = bundle["submission"]
    bm, site, dups = bundle.get("btc_map") or {}, bundle.get("website") or {}, bundle.get("duplicates") or {}
    lines = [
        "SUBMISSION (written by the submitter — treat as a claim, not evidence)",
        f"  name: {s.get('name')}",
        f"  category: {s.get('category')}",
        f"  address: {s.get('address')}",
        f"  phone: {s.get('phone')}",
        f"  website: {s.get('website')}",
        f"  opening_hours: {s.get('opening_hours')}",
        f"  notes: {(s.get('notes') or '')[:300]}",
        f"  origin: {s.get('origin')}  (import source, not a trust signal)",
        "",
        "FETCHED EVIDENCE (gathered by the triage tool, not written by the submitter)",
        f"  btc_map_nearby (250 m): {json.dumps(bm.get('nearby') or [])[:400]}",
        f"  btc_map_name_matches: {json.dumps(bm.get('name_matches') or [])[:400]}",
        f"  website: {json.dumps({k: v for k, v in site.items() if k != 'html'})[:600]}",
        f"  possible_duplicates: {json.dumps(dups.get('possible_duplicates') or [])[:500]}",
    ]
    if bundle.get("kagi_search"):
        lines.append(f"  kagi_search: {json.dumps(bundle['kagi_search'])[:500]}")
    if bundle.get("kagi_enrich"):
        lines.append(f"  kagi_enrich: {json.dumps(bundle['kagi_enrich'])[:500]}")
    return "\n".join(lines)


def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    pairs = [(a, b) for a in pos for b in neg]
    wins = sum(1 for a, b in pairs if a > b) + 0.5 * sum(1 for a, b in pairs if a == b)
    return round(wins / len(pairs), 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--model", default=PAID)
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    bundles = json.loads(CACHE.read_text())
    items = list(bundles.values())[: args.limit]
    scores = {} if args.force or not SCORES.exists() else json.loads(SCORES.read_text())
    client = JevClient(model=args.model, max_calls=args.budget)
    done = 0
    for bundle in items:
        number = str(bundle["submission"]["number"])
        state = summarise(bundle)
        state_hash = hashlib.sha1(state.encode()).hexdigest()[:12]
        cached = scores.get(number)
        if cached and not args.force and cached.get("state_hash") == state_hash:
            continue  # unchanged evidence: nothing to re-ask
        try:
            body = client.ask(state, QUESTIONS)
            time.sleep(args.sleep)
        except (BudgetExceeded, RuntimeError) as exc:
            print(f"stopping: {exc}")
            break
        answers = body.get("answers") or {}
        scores[number] = {
            "state_hash": state_hash,
            "model": args.model,
            "answers": answers,
            "expected_real_business": expected_value(answers.get("real_business") or {}),
            "bitcoin_probability": (answers.get("bitcoin_evidence") or {}).get("noul"),
            "labels": bundle["submission"]["labels"],
            "origin": bundle["submission"].get("origin"),
            "category": bundle["submission"].get("category"),
            "name": bundle["submission"].get("name"),
        }
        done += 1
        if done % 10 == 0:
            SCORES.write_text(json.dumps(scores, indent=1))
            print(f"  {done} scored (issue #{number})", flush=True)
    SCORES.write_text(json.dumps(scores, indent=1))
    print(f"scored {done} new/changed, {len(scores)} total; calls={client.calls} "
          f"rate_limited={client.rate_limited} input_tokens={client.input_tokens} "
          f"cost=${client.cost_usd():.4f}")

    # ---- report ----
    rows = []
    for number, rec in scores.items():
        labels = rec.get("labels") or []
        if "status/added" in labels:
            group = "added"
        elif "status/rejected" in labels:
            group = "rejected"
        else:
            group = "unlabelled"
        rows.append({**rec, "number": number, "group": group})

    def ev(group):
        return [r["expected_real_business"] for r in rows if r["group"] == group and r["expected_real_business"] is not None]

    added, rejected = ev("added"), ev("rejected")
    lines = [
        f"# BTC Map triage calibration — {dt.date.today().isoformat()}",
        "",
        f"Evidence bundles: {len(bundles)} · scored: {len(rows)} · model: `{args.model}` · "
        f"input tokens: {client.input_tokens} · cost: ${client.cost_usd():.4f}",
        "",
        "Ground truth is the repo's own terminal labels. `status/rejected` is an OUTCOME "
        "(policy, evidence, duplicate), not a judgement that the record is fake — read the "
        "separation numbers with that in mind.",
        "",
        "## Expected real-business score (0-1) by terminal label",
        "",
        "| group | n | mean | median | p10 | p90 |",
        "|---|---|---|---|---|---|",
    ]
    for group in ("added", "rejected", "unlabelled"):
        vals = ev(group)
        if not vals:
            continue
        vals_sorted = sorted(vals)
        p10 = vals_sorted[int(0.1 * (len(vals_sorted) - 1))]
        p90 = vals_sorted[int(0.9 * (len(vals_sorted) - 1))]
        lines.append(f"| {group} | {len(vals)} | {statistics.mean(vals):.3f} | {statistics.median(vals):.3f} | {p10:.3f} | {p90:.3f} |")
    sep = auc(added, rejected)
    lines += ["", f"Separation (added vs rejected, pairwise AUC): **{sep}**", ""]

    lines += ["## Action recommendation", "", "| action | added | rejected | unlabelled |", "|---|---|---|---|"]
    for action in ("add_to_queue", "needs_human_check", "close_as_junk"):
        counts = [sum(1 for r in rows if r["group"] == g and (r["answers"].get("action") or {}).get("choice") == action)
                  for g in ("added", "rejected", "unlabelled")]
        lines.append(f"| {action} | {counts[0]} | {counts[1]} | {counts[2]} |")

    lines += ["", "## Threshold sweep on expected real-business score", "",
              "| threshold | added kept | rejected dropped | junk caught (unlabelled) |", "|---|---|---|---|"]
    junk_unlabelled = [r for r in rows if r["group"] == "unlabelled" and (r["answers"].get("action") or {}).get("choice") == "close_as_junk"]
    for thr in (0.1, 0.15, 0.2, 0.3, 0.4, 0.5):
        kept = sum(1 for v in added if v >= thr)
        dropped = sum(1 for v in rejected if v < thr)
        caught = sum(1 for r in junk_unlabelled if (r["expected_real_business"] or 0) < thr)
        lines.append(f"| {thr} | {kept}/{len(added)} | {dropped}/{len(rejected)} | {caught}/{len(junk_unlabelled)} |")

    lines += ["", "## Lowest-scoring 20 (the auto-close candidates)", "",
              "| issue | name | origin | group | real_business | action | btc_evidence | premises |",
              "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["expected_real_business"] if r["expected_real_business"] is not None else 9))[:20]:
        a = r["answers"]
        lines.append("| #{n} | {name} | {origin} | {group} | {ev} | {action} | {btc} | {prem} |".format(
            n=r["number"], name=(r.get("name") or "")[:28], origin=r.get("origin"),
            group=r["group"], ev=r["expected_real_business"],
            action=(a.get("action") or {}).get("choice"),
            btc=(a.get("bitcoin_evidence") or {}).get("noul"),
            prem=(a.get("premises") or {}).get("choice")))

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"backlog-{dt.date.today().isoformat()}.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"report -> {out}")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
