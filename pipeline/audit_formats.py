"""Parser coverage audit across the whole btcmap-data history.

Answers "can we backtest on this?" — the repo has five different issue-body families, so a
backtest is only as good as the parser's coverage of each. Samples pages spread evenly
across the repo's history, classifies every body, and reports per-family extraction rates.

Usage:
    python3 audit_formats.py [--pages 40] [--per-page 50]
"""

from __future__ import annotations

import argparse
import collections
import json
import time
import urllib.request

from evidence import GITEA, http_json, parse_submission

UA = "HermesAgent/1.0"


def total_issues() -> int:
    req = urllib.request.Request(f"{GITEA}?state=all&limit=1", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as response:
        return int(response.headers.get("X-Total-Count") or 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=40)
    ap.add_argument("--per-page", type=int, default=50)
    ap.add_argument("--json-out", default="reports/parser-coverage.json")
    args = ap.parse_args()

    total = total_issues()
    per_page = args.per_page
    last_page = max(1, total // per_page)
    step = max(1, last_page // args.pages)
    pages = list(range(1, last_page + 1, step))[: args.pages]
    print(f"repo issues: {total} ({last_page} pages of {per_page}); sampling {len(pages)} pages: {pages[:6]}…")

    families = collections.Counter()
    coverage = collections.defaultdict(lambda: collections.Counter())
    dates = collections.defaultdict(lambda: [None, None])
    field_examples = collections.defaultdict(dict)
    sampled = 0

    for page in pages:
        try:
            items = http_json(f"{GITEA}?state=all&limit={per_page}&page={page}&sort=created&order=desc") or []
        except Exception as exc:
            print(f"page {page} failed: {exc}")
            continue
        for it in items:
            sub = parse_submission(it)
            sampled += 1
            family = sub["body_format"]
            families[family] += 1
            for field_name in ("name", "address", "lat", "category", "website"):
                coverage[family][field_name] += 1 if sub.get(field_name) not in (None, "") else 0
            created = (it.get("created_at") or "")[:10]
            if created:
                d = dates[family]
                d[0] = min(filter(None, [d[0], created]))
                d[1] = max(filter(None, [d[1], created]))
            for field_name in ("name", "address"):
                if sub.get(field_name) and len(field_examples[family]) < 3:
                    field_examples[family].setdefault(field_name, str(sub[field_name])[:70])
        time.sleep(0.25)

    print(f"\nsampled {sampled} issues across the history\n")
    header = f"{'format':<22}{'n':>6}{'share':>8}{'name':>8}{'addr':>8}{'coords':>8}{'cat':>7}{'site':>7}   first→last"
    print(header)
    print("-" * len(header))
    for family, n in families.most_common():
        c = coverage[family]
        def pct(field_name):
            return f"{100 * c[field_name] / max(1, n):.0f}%"
        first, last = dates[family]
        print(f"{family:<22}{n:>6}{100 * n / max(1, sampled):>7.0f}%{pct('name'):>8}{pct('address'):>8}"
              f"{pct('lat'):>8}{pct('category'):>7}{pct('website'):>7}   {first}→{last}")

    print("\nfield examples per family:")
    for family in families:
        print(f"  {family}: {json.dumps(field_examples[family])}")

    json.dump({"total_issues": total, "sampled": sampled,
               "families": dict(families),
               "coverage": {k: dict(v) for k, v in coverage.items()},
               "range": {k: v for k, v in dates.items()}},
              open(args.json_out if args.json_out.startswith("/") else args.json_out, "w"), indent=1)
    print(f"\n-> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
