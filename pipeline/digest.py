"""Render the daily triage digest for the #btcmap-taggers room.

Reads the audit trail and the score cache and prints one message: counts by band, the
low-confidence list (candidates for closing), the high-confidence ones ready to prepare for
OpenStreetMap, and anything the runner could not read.

Posting is deliberately not implemented here — the Matrix account does not exist yet, so
this renders to stdout/file for review first.

    python3 digest.py [--date YYYY-MM-DD] [--out file.md]
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
AUDIT = HERE / "reports" / "triage-audit.jsonl"
SCORES = HERE / "jev-scores.json"
ISSUES = HERE / "issues.json"
REPO = "https://gitea.btcmap.org/teambtcmap/btcmap-data/issues"
BAND_ORDER = ("confidence/high", "confidence/medium", "confidence/low")


def link(number: int) -> str:
    return f"[#{number}]({REPO}/{number})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    day = args.date or dt.date.today().isoformat()
    rows = [json.loads(line) for line in AUDIT.read_text().splitlines() if line.strip()]
    # dry-run rows are not triage activity: a public digest must only count what was written
    todays = [r for r in rows if (r.get("at") or "").startswith(day) and r.get("applied")]
    dry_count = sum(1 for r in rows if (r.get("at") or "").startswith(day) and not r.get("applied"))
    if not todays:
        # a quiet day is still a renderable digest — an empty file would look like a failure
        text = f"**BTC Map triage — {day}**\n\nNo submissions were triaged today."
        print(text)
        if args.out:
            pathlib.Path(args.out).write_text(text + "\n")
        return 0

    # a band change within the day collapses to the last decision per issue
    latest = {}
    for row in sorted(todays, key=lambda r: r.get("at") or ""):
        latest[row["issue"]] = row

    scores = json.loads(SCORES.read_text()) if SCORES.exists() else {}
    names = {int(k): (v.get("name") or "") for k, v in scores.items()}
    by_band = collections.defaultdict(list)
    for number, row in latest.items():
        by_band[row["label"]].append(number)

    lines = [f"**BTC Map triage — {day}**", ""]
    summary = " · ".join(f"{len(by_band.get(band, []))} {band.split('/')[1]}"
                         for band in BAND_ORDER if by_band.get(band))
    lines.append(f"{len(latest)} submission{'s' if len(latest) != 1 else ''} scored: {summary}")
    lines.append("")
    if dry_count:
        lines.append(f"_({dry_count} further dry-run scores excluded — no labels written.)_")
        lines.append("")

    for band, heading in (("confidence/low", "Looks like a personal or placeholder record — candidates to close"),
                          ("confidence/high", "Real businesses at a visitable address — ready to prepare for OpenStreetMap"),
                          ("confidence/medium", "Probably real, needs a human to confirm")):
        numbers = sorted(by_band.get(band, []))
        if not numbers:
            continue
        lines.append(f"**{heading}** ({len(numbers)})")
        for number in numbers:
            row = latest[number]
            name = names.get(number) or ""
            bit = f"{link(number)} {name}".strip()
            if band == "confidence/high":
                bit += " — no junk signal, not already mapped"
            lines.append(f"- {bit}")
        lines.append("")

    unreadable = [n for n in latest if not (scores.get(str(n), {}).get("answers"))]
    if unreadable:
        lines.append(f"_{len(unreadable)} issue(s) could not be scored and need a human: "
                     + ", ".join(link(n) for n in sorted(unreadable)) + "_")
        lines.append("")

    lines.append("Scored by Jev 1.13 (System One) from evidence gathered at run time; this is a "
                 "recommendation for a human triager, not a decision. Labels on each issue: "
                 "`confidence/high|medium|low`, `triaged/auto`.")

    text = "\n".join(lines)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n")
        print(f"-> {args.out}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
