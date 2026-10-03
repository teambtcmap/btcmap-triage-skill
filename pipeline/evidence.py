"""Phase 1 evidence collector for BTC Map submission triage.

Read-only. For each Gitea location-submission it assembles one JSON bundle:
  - what the submission claims (parsed from the issue body)
  - whether the merchant is already on BTC Map / OSM near those coordinates
  - whether their own website corroborates them and mentions bitcoin
  - whether it duplicates another open submission

Bundles are cached by issue number so re-runs are free and later signals (Kagi
enrichment/search) can be layered on without repeating the fetches.

Usage:
    python3 evidence.py --limit 250 [--with-kagi] [--workers 4]
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "HermesAgent/1.0 (btcmap triage; https://btcmap.org)"
GITEA = "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues"
BTCMAP = "https://api.btcmap.org/v4"
HERE = Path(__file__).resolve().parent
CACHE = HERE / "evidence-cache.json"
ISSUES = HERE / "issues.json"
KAGI_TOKEN_FILE = Path(os.environ.get("KAGI_TOKEN_FILE", "~/.config/btcmap/kagi.token")).expanduser()

BTC_RE = re.compile(r"(?i)\b(bitcoin|btc|lightning|satoshi|sats|zap|lnurl)\b")

# Bump when a parser or probe changes meaning: cached bundles below this version are refetched,
# so a fixed parse cannot leave stale "empty record" evidence in the cache.
PARSER_VERSION = 5

# Five body families exist in this repo's history (see the triage skill's
# references/EXAMPLE_ISSUES.md for full samples). Every field therefore accepts a list of
# aliases, first non-empty wins — a backtest that only reads the current layout silently
# drops most of the history.
FIELD_ALIASES = {
    "submission_id": (r"^Id: *(.+)$",),
    "origin": (r"^Origin: *(.+)$",),
    "name": (r"^Name \(local\): *(.+)$", r"^Merchant name: *(.+)$", r"^Community name: *(.+)$", r"^Name: *(.+)$"),
    "name_en": (r"^Name \(English\): *(.+)$",),
    "category": (r"^Category: *(.+)$", r"^Type: *(.+)$"),
    "address": (r"^Address: *(.+)$", r"^Location: *(.+)$"),
    "opening_hours": (r"^Opening hours: *(.+)$",),
    "website": (r"^Website: *(.+)$",),
    "payment_methods": (r"^Payment methods: *(.+)$",),
    "contact": (r"^Contact: *(.+)$",),
    "phone": (r"^Phone: *(.+)$",),
    "notes": (r"^Notes: *(.+)$", r"^Description: *(.+)$", r"^Details \(if applicable\): *(.+)$"),
    "currency_tag": (r"^currency:XBT=(.+)$",),
    "lat_field": (r"^Lat: *(-?\d+\.?\d*)$",),
    "lon_field": (r"^Long: *(-?\d+\.?\d*)$",),
    "coordinates": (r"^Coordinates: *(-?\d+\.?\d*), *(-?\d+\.?\d*)$",),
    "osm_edit": (r"^(?:OSM|Edit link|Merchant location): *(https?://\\S+)$",),
    "verified_by": (r"^How did you verify this\?: *(.+)$",),
    "current_correct": (r"^Current information correct: *(.+)$",),
}
COORD_RES = (
    re.compile(r"openstreetmap\.org/#map=\d+/(-?\d+\.?\d*)/(-?\d+\.?\d*)"),
    re.compile(r"openstreetmap\.org/edit#map=\d+/(-?\d+\.?\d*)/(-?\d+\.?\d*)"),
    # verification issues carry no Lat/Long line, only a btcmap.org/map deep link
    re.compile(r"btcmap\.org/map#\d+/(-?\d+\.?\d*)/(-?\d+\.?\d*)"),
)


def http_json(url: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode() or "null")


def http_text(url: str, timeout: float = 10.0, limit: int = 120_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status, response.read(limit).decode(errors="replace"), response.geturl()


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def similar(a: str, b: str) -> float:
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    at, bt = {t for t in re.split(r"\W+", a) if len(t) > 2}, {t for t in re.split(r"\W+", b) if len(t) > 2}
    overlap = len(at & bt) / max(1, min(len(at), len(bt))) if at and bt else 0.0
    return round(max(ratio, overlap), 3)


def detect_format(body: str, parsed: dict) -> str:
    """Which of the historical body families this is — recorded so coverage can be reported per format."""
    if "Merchant name:" in body:
        return "webform-verification" if "Current information correct:" in body else "webform-submission"
    if "Community name:" in body:
        return "webform-community"
    if "Name (local):" in body:
        return "machine-modern"
    if "Extra fields:" in body:
        return "machine-legacy"
    if "Origin:" in body:
        return "machine-unknown"
    return "unknown"


def parse_submission(it: dict) -> dict:
    body = (it.get("body") or "").replace("\r", "")
    out = {"number": it["number"], "title": it["title"], "state": it["state"],
           "labels": [l["name"] for l in it.get("labels", [])],
           "created_at": it.get("created_at"), "url": it.get("html_url")}
    for key, patterns in FIELD_ALIASES.items():
        out[key] = None
        for pattern in patterns:
            m = re.search(pattern, body, re.M)
            if m:
                out[key] = (m.group(1) or "").strip() or None
                if m.lastindex and m.lastindex > 1:
                    out["coordinates"] = [float(m.group(1)), float(m.group(2))]
                break
    # Legacy bodies (pre-2026-09) say "Name:" and carry the details as a raw JSON block after
    # "Extra fields:". Parsing only the modern layout silently dropped name/address/website for
    # 98 of 243 submissions, which made them look like empty records to the judge.
    if not out.get("name"):
        m = re.search(r"^Name: *(.+)$", body, re.M)
        out["name"] = m.group(1).strip() if m else None
    extra = {}
    m = re.search(r"^Extra fields:\s*$", body, re.M)
    if m:
        brace = body.find("{", m.end())
        if brace != -1:
            depth, end = 0, None
            for i, ch in enumerate(body[brace:], start=brace):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end:
                try:
                    extra = json.loads(body[brace:end]) or {}
                except Exception:
                    extra = {}
    if isinstance(extra, dict):
        for field_name, key in (("address", "address"), ("phone", "phone"), ("website", "website"),
                                ("contact", "contact"), ("notes", "notes"),
                                ("payment_methods", "payment_methods"), ("opening_hours", "opening_hours")):
            if not out.get(field_name) and isinstance(extra.get(key), str):
                out[field_name] = extra[key].strip() or None
        if not out.get("name_en") and isinstance(extra.get("name:en"), str):
            out["name_en"] = extra["name:en"]
    out["extra_fields"] = extra if isinstance(extra, dict) else {}
    coords = out.get("coordinates") if isinstance(out.get("coordinates"), list) else None
    if coords is None and out.get("lat_field") and out.get("lon_field"):
        coords = [float(out["lat_field"]), float(out["lon_field"])]
    if coords is None:
        for rx in COORD_RES:
            m = rx.search(body)
            if m:
                coords = [float(m.group(1)), float(m.group(2))]
                break
    out["lat"], out["lon"] = (coords or [None, None])
    out["body_format"] = detect_format(body, out)
    tags = re.findall(r"^([a-zA-Z0-9:_]+)=(.*)$", body, re.M)
    out["osm_tags"] = {k: v for k, v in tags}
    return out


def btc_map_check(sub: dict) -> dict:
    """Is this merchant already on BTC Map, and what is nearby?"""
    result = {"nearby": [], "name_matches": [], "errors": []}
    try:
        if sub.get("lat") is not None:
            url = f"{BTCMAP}/places/search?lat={sub['lat']}&lon={sub['lon']}&radius_km=0.25"
            nearby = http_json(url) or []
            result["nearby"] = [
                {"id": e.get("id"), "name": e.get("name"), "osm_id": e.get("osm_id"),
                 "distance_m": round(haversine_m(sub["lat"], sub["lon"], e["lat"], e["lon"])),
                 "verified": (e.get("tags") or {}).get("survey:date") or (e.get("tags") or {}).get("check_date")}
                for e in nearby if e.get("lat") is not None
            ][:8]
    except Exception as exc:
        result["errors"].append(f"radius: {exc}")
    name = sub.get("name") or sub.get("title", "").split("] ")[-1]
    try:
        found = http_json(f"{BTCMAP}/places/search?radius_km=50&name={urllib.parse.quote(name)}") or []
        for e in found[:5]:
            dist = round(haversine_m(sub["lat"], sub["lon"], e["lat"], e["lon"])) if sub.get("lat") is not None and e.get("lat") is not None else None
            result["name_matches"].append({"name": e.get("name"), "distance_m": dist,
                                           "similarity": similar(name, e.get("name") or ""),
                                           "verified": (e.get("tags") or {}).get("survey:date")})
    except Exception as exc:
        result["errors"].append(f"name: {exc}")
    return result


def _signals_from_text(text: str, sub: dict) -> dict:
    lower = text.lower()
    name = (sub.get("name") or "").lower()
    name_tokens = [t for t in re.split(r"\W+", name) if len(t) > 3]
    phone_digits = re.sub(r"\D", "", sub.get("phone") or "")
    addr_tokens = [t for t in re.split(r"\W+", (sub.get("address") or "").lower()) if len(t) > 4 and not t.isdigit()]
    return {
        "mentions_btc": sorted({m.group(0).lower() for m in BTC_RE.finditer(text)})[:8],
        "name_on_site": bool(name_tokens) and any(t in lower for t in name_tokens),
        "phone_on_site": bool(phone_digits) and phone_digits[-7:] in re.sub(r"\D", "", text),
        "address_on_site": bool(addr_tokens) and sum(1 for t in addr_tokens if t in lower) >= max(1, len(addr_tokens) // 3),
    }


def website_check(sub: dict, use_extract: bool = True) -> dict:
    """Read the merchant's own site twice: a direct fetch (full HTML, instant, free) and Kagi
    Extract (clean markdown; reads pages that block a plain fetch).

    Measured on 40 submissions: Extract alone succeeded on 25, the direct fetch on 35, and the
    two together cover the most ground — Extract rescued 4 pages the fetch could not read at all
    and found a bitcoin signal in 1 the fetch missed, while the fetch kept raw-HTML tokens
    (e.g. `btc` in markup) that markdown drops. Signals are therefore UNIONed, with the source
    of each recorded, rather than one replacing the other.
    """
    url = (sub.get("website") or "").split()[0] if sub.get("website") else ""
    if not url:
        return {"present": False, "reason": "no website in submission"}
    if not url.startswith("http"):
        url = "https://" + url

    result: dict = {"present": True, "url": url, "sources": {}}
    direct_text = ""
    try:
        status, html, final = http_text(url)
        text = re.sub(r"<[^>]+>", " ", html)
        direct_text = text
        result["sources"]["direct"] = {
            "reachable": True, "status": status, "final_url": final,
            "title": (re.search(r"(?is)<title[^>]*>(.*?)</title>", html) or [None, None])[1],
            **_signals_from_text(text, sub),
        }
    except urllib.error.HTTPError as exc:
        result["sources"]["direct"] = {"reachable": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        result["sources"]["direct"] = {"reachable": False, "error": str(exc)[:120]}

    if use_extract:
        out = kagi_extract(sub, url)
        if out.get("error"):
            result["sources"]["kagi_extract"] = {"reachable": False, "error": out["error"]}
        else:
            markdown = out.get("markdown") or ""
            result["sources"]["kagi_extract"] = {
                "reachable": bool(markdown.strip()), "chars": len(markdown),
                **_signals_from_text(markdown, sub),
            }

    # union the signals, remembering who found each one
    result["reachable"] = any(s.get("reachable") for s in result["sources"].values())
    result["reachable_via"] = [name for name, s in result["sources"].items() if s.get("reachable")]
    result["mentions_btc"] = sorted({w for s in result["sources"].values() for w in (s.get("mentions_btc") or [])})
    for field_name in ("name_on_site", "phone_on_site", "address_on_site"):
        sources = [name for name, s in result["sources"].items() if s.get(field_name)]
        result[field_name] = bool(sources)
        result[f"{field_name}_via"] = sources
    result["has_payment_contact"] = bool(result["mentions_btc"])
    if not result["reachable"]:
        result["errors"] = {name: s.get("error") for name, s in result["sources"].items() if s.get("error")}
    return result


def duplicate_check(sub: dict, others: list[dict]) -> dict:
    hits = []
    for other in others:
        if other["number"] == sub["number"]:
            continue
        sim = similar(sub.get("name") or sub["title"], other.get("name") or other["title"])
        dist = None
        if sub.get("lat") is not None and other.get("lat") is not None:
            dist = round(haversine_m(sub["lat"], sub["lon"], other["lat"], other["lon"]))
        if sim >= 0.6 or (dist is not None and dist < 60):
            hits.append({"number": other["number"], "name": other.get("name") or other["title"],
                         "similarity": sim, "distance_m": dist,
                         "origin": other.get("origin"), "labels": other["labels"]})
    hits.sort(key=lambda h: (-(h["similarity"] or 0), h["distance_m"] if h["distance_m"] is not None else 9e9))
    return {"possible_duplicates": hits[:5]}


MCP_URL = "https://mcp.kagi.com/mcp"


def _kagi_mcp_tool(name: str, arguments: dict, timeout: float = 60.0, cap: int = 900) -> dict:
    """Call Kagi's hosted MCP server (mcp.kagi.com).

    The v0 REST endpoints (/api/v0/search, /api/v0/enrich/web) reject this account's key
    with `401 {"code":2,"msg":"Unauthorized"}` and `meta.api_balance: null` for every auth
    style, and /api/v1/search 404s — the key authenticates only against the MCP server
    (Bearer, `kagimcp` 3.4.4), which exposes kagi_search_fetch and kagi_extract.
    """
    if not KAGI_TOKEN_FILE.exists():
        return {"skipped": f"no token at {KAGI_TOKEN_FILE}"}
    token = KAGI_TOKEN_FILE.read_text().strip()
    if not token:
        return {"skipped": f"token file {KAGI_TOKEN_FILE} is empty"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
    request = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream", "User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code} {exc.read()[:200].decode(errors='replace')}"}
    except Exception as exc:
        return {"error": str(exc)[:160]}
    body = raw.split("data: ", 1)[-1]
    try:
        parsed = json.loads(body)
    except Exception:
        return {"error": f"unparseable MCP reply: {raw[:120]}"}
    if parsed.get("error"):
        return {"error": json.dumps(parsed["error"])[:300], "tool": name}
    result = parsed.get("result") or {}
    content = result.get("content") or []
    text = content[0].get("text", "") if content else ""
    if result.get("isError"):
        # keep the server's own wording: "rate limited", "not found", "robots", etc.
        return {"error": re.sub(r"\s+", " ", text)[:300] or "isError with empty content", "tool": name}
    urls = re.findall(r"\*\*URL:\*\* *(\S+)", text)
    titles = re.findall(r"^### +(?:\[(.+?)\]|(.+))$", text, re.M)
    return {
        "tool": name,
        "is_error": bool(result.get("isError")),
        "result_count": len(urls) or len(titles),
        "top_urls": urls[:5],
        "excerpt": re.sub(r"\s+", " ", text)[:cap],
    }


def kagi_extract(sub: dict, url: str, cap: int = 60_000) -> dict:
    """Kagi Extract (MCP) — page content as clean markdown, for pages a plain fetch cannot read.

    Returns {"markdown": str} or {"error": ...}; the raw MCP text is capped at `cap` characters.
    """
    result = _kagi_mcp_tool("kagi_extract", {"url": url}, timeout=90.0, cap=cap)
    if result.get("error") or result.get("is_error"):
        return {"error": result.get("error") or "extract returned an error"}
    return {"markdown": result.get("excerpt") or "", "tool": "kagi_extract"}


def kagi_search(sub: dict) -> dict:
    """Kagi search (via the MCP server) — independent web presence for this business."""
    name = sub.get("name") or sub["title"].split("] ")[-1]
    where = sub.get("address") or ""
    return _kagi_mcp_tool("kagi_search_fetch", {"query": f"{name} {where}".strip()})


def kagi_enrich(sub: dict) -> dict:
    """Not available on this account: /api/v0/enrich/web 401s for our key. Kept so bundles
    record the gap explicitly rather than looking like an untried signal."""
    return {"skipped": "enrichment endpoint rejects this key; use kagi_search"}


def fetch_issues(state: str = "all", pages: int = 6, per_page: int = 50) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        url = f"{GITEA}?state={state}&limit={per_page}&page={page}&sort=created&order=desc"
        try:
            page_items = http_json(url) or []
        except Exception as exc:
            print(f"issue fetch page {page} failed: {exc}", file=sys.stderr)
            break
        out += page_items
        if len(page_items) < per_page:
            break
        time.sleep(0.3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--with-kagi", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--refresh-issues", action="store_true")
    args = ap.parse_args()

    if args.refresh_issues or not ISSUES.exists():
        issues = fetch_issues()
        ISSUES.write_text(json.dumps(issues, indent=1))
    else:
        issues = json.loads(ISSUES.read_text())
    print(f"issues on hand: {len(issues)}")

    subs = [parse_submission(i) for i in issues if "type/location-submission" in {l["name"] for l in i.get("labels", [])}]
    subs = subs[: args.limit]
    open_subs = [s for s in subs if "status/added" not in s["labels"] and "status/rejected" not in s["labels"]]
    print(f"location submissions: {len(subs)} ({len(open_subs)} without a terminal label)")

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    done = 0
    search_calls = enrich_calls = 0
    for sub in subs:
        key = str(sub["number"])
        entry = cache.get(key)
        if entry and entry.get("parser_version") != PARSER_VERSION:
            entry = None  # stale parse: rebuild rather than judge a half-empty record
        if entry and entry.get("fetched_at"):
            if not args.with_kagi or ("kagi_search" in entry and "kagi_enrich" in entry):
                continue
            # Cache hit and only Kagi is missing: add the paid signals alone, never re-fetch the free ones.
            if "kagi_search" not in entry:
                entry["kagi_search"] = kagi_search(sub)
                search_calls += 1
            if "kagi_enrich" not in entry:
                entry["kagi_enrich"] = kagi_enrich(sub)
                enrich_calls += 1
            done += 1
            time.sleep(args.sleep)
            continue
        bundle = {
            "submission": sub,
            "btc_map": btc_map_check(sub),
            "website": website_check(sub),
            "duplicates": duplicate_check(sub, subs),
            "parser_version": PARSER_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        if args.with_kagi:
            bundle["kagi_search"] = kagi_search(sub)
            search_calls += 1
            bundle["kagi_enrich"] = kagi_enrich(sub)
            enrich_calls += 1
        cache[key] = bundle
        done += 1
        if done % 10 == 0:
            CACHE.write_text(json.dumps(cache, indent=1))
            print(f"  {done} bundles fetched (issue #{sub['number']})", flush=True)
        time.sleep(args.sleep)
    CACHE.write_text(json.dumps(cache, indent=1))
    cost = search_calls * 0.012 + enrich_calls * 0.002
    print(f"done: {done} new/updated bundles, {len(cache)} cached -> {CACHE}")
    print(f"kagi this run: {search_calls} search ($12/1k) + {enrich_calls} enrich ($2/1k) = ${cost:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
