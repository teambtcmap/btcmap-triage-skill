"""Reconcile the triage audit trail against what Gitea actually carries.

The first live run was killed mid-loop, so a few applies landed in Gitea without an audit
row (Python's buffered writes were lost with the process). This rebuilds those rows from
Gitea itself — the record of truth — and marks them `reconstructed`, so the trail shows
which entries came from the runner and which were recovered afterwards.

    python3 reconcile_audit.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
AUDIT = HERE / "reports" / "triage-audit.jsonl"
GITEA_API = "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data"
TOKEN = pathlib.Path("~/.config/btcmap/gitea.token").expanduser()


def gitea(path: str):
    request = urllib.request.Request(
        GITEA_API + path,
        headers={"Authorization": f"token {TOKEN.read_text().strip()}",
                 "User-Agent": "HermesAgent/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode()
        return json.loads(body) if body.strip() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    AUDIT.parent.mkdir(exist_ok=True)
    existing = []
    if AUDIT.exists():
        existing = [json.loads(line) for line in AUDIT.read_text().splitlines() if line.strip()]
    # an issue can legitimately hold a dry-run row and an applied row; only the applied one
    # proves Gitea was written to, so "already present" means "already has an applied row".
    by_issue = {row["issue"]: row for row in existing}
    applied_issues = {row["issue"] for row in existing if row.get("applied")}
    print(f"audit rows on file: {len(existing)} covering {len(by_issue)} issues "
          f"({len(applied_issues)} with an applied row)")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    recovered = 0
    added_issues = []
    for page in range(1, 4):
        items = gitea(f"/issues?state=open&limit=50&page={page}&type=issues")
        if not isinstance(items, list) or not items:
            break
        added_issues += items
    for issue in added_issues:
        names = {label["name"] for label in issue.get("labels", [])}
        if "triaged/auto" not in names:
            continue
        number = issue["number"]
        if number in applied_issues:
            continue
        band = next((n for n in names if n.startswith("confidence/")), "unknown")
        comments = gitea(f"/issues/{number}/comments") or []
        ours = [c for c in comments if c.get("body", "").startswith("**Automated triage**")]
        stamp = ours[-1]["created_at"] if ours else issue.get("updated_at")
        row = {"at": stamp, "issue": number, "label": band,
               "rationale": "reconstructed from the Gitea comment", "applied": True,
               "model": "unknown", "reconstructed": True}
        # recover the rationale from the comment header when it is there
        if ours:
            header = ours[-1]["body"].splitlines()[0]
            if "·" in header:
                row["rationale"] = header.split("—", 1)[-1].strip()[:200]
        existing.append(row)
        by_issue[number] = row
        applied_issues.add(number)
        recovered += 1

    existing.sort(key=lambda r: (r.get("at") or "", r["issue"]))
    AUDIT.write_text("\n".join(json.dumps(r) for r in existing) + "\n")
    print(f"recovered {recovered} rows from Gitea; audit now covers {len(applied_issues)} triaged issues "
          f"({dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
