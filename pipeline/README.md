# Jev-based triage pipeline

The current pipeline: evidence → Jev 1.13 (TypeSafe System One) → one label and one comment per
submission. It supersedes the scoring in `scripts/phase1_verify.py` / `phase2_verify.py` for new
work — those remain as reference for the weighted-check approach and the outreach templates.

Everything here is standard-library Python 3.11+. No dependencies, no build step.

## What it does, and deliberately does not

For each open submission it gathers what can actually be checked, then asks Jev for a judgement:

| stage | file | what it produces |
|---|---|---|
| evidence | `evidence.py` | BTC Map/OSM entries near the coordinates, the merchant's own website read twice, duplicates, optional Kagi search |
| judgement | `jev_client.py` | headless client for `/zen/v1/systemone`; typed questions in, values and probabilities out |
| routing | `triage_jev.py` | `confidence/high|medium|low` + `triaged/auto` + one comment showing the evidence |
| reporting | `digest.py`, `matrix_post.py` | the daily digest, posted to the taggers room |
| replies | `inbox.py`, `outreach.py` | merchant/submitter email: drafted, sent only when unlocked, replies matched back to issues |
| calibration | `score_backlog.py`, `audit_formats.py` | measures the scorer against the repo's own labels and reports parser coverage per body format |
| integrity | `reconcile_audit.py` | rebuilds the audit trail from Gitea if a run is killed mid-flight |

**It never closes, rejects or edits a submission, and it never touches OpenStreetMap.** One label and
one comment; every decision that matters stays with a human.

## Body formats

Five layouts exist across this repo's history, and a parser that reads only the current one loses most
of the corpus. Measured over 2,000 sampled issues (25,310 total):

| format | share | date range |
|---|---|---|
| machine-legacy (`Name:` + `Extra fields:` JSON) | **76%** | 2025-11-06 → 2026-09-13 |
| webform-submission (`Merchant name:`) | 12% | 2025-10-05 → 2026-08-25 |
| webform-verification | 9% | 2025-10-05 → 2026-10-03 |
| machine-modern (`Name (local):` + `Additional fields:`) | **2%** | 2026-10-02 → now |
| webform-community | 1% | – |

`evidence.py` reads all five and records `body_format` on every bundle, so results can be broken down
by layout. See `references/PARSING_PITFALLS.md` for the field-level traps.

## How well does it work?

Calibrated against the repo's own terminal labels — 243 submissions, all scored:

| group | n | mean | median |
|---|---|---|---|
| `status/added` | 69 | 0.716 | 0.750 |
| `status/rejected` | 110 | 0.397 | 0.394 |
| open / unlabelled | 64 | 0.478 | 0.522 |

Separation **AUC 0.887**, and 0.869 / 0.902 split by legacy / modern body format — the legacy parse
holds up, which matters because it is three quarters of the history. At threshold 0.30: 68/69 added
kept, 46/110 rejected dropped. Zero added submissions were called `close_as_junk`; zero rejected ones
were called `add_to_queue`.

**Two caveats, recorded because they limit what those numbers mean.**

1. **`status/rejected` is an outcome, not a verdict on authenticity.** Rejections are policy — no
   bitcoin evidence, a residential address, a duplicate, a service-only business. Every one of those is
   a real company, and the scorer agrees.
2. **The backtest leaks its labels.** Evidence is gathered *now*, so "already on BTC Map with a matching
   name nearby" is partly a consequence of the triage having happened (62 of 69 added have such a match).
   Treat the calibration as a check on the question design, not an accuracy claim. The live case —
   evidence gathered at submission time — is the unbiased one.

## Bands

| band | means |
|---|---|
| `confidence/high` | real business ≥0.70 at a visitable address, no junk signal, not already mapped |
| `confidence/medium` | probably real; a human should confirm |
| `confidence/low` | looks like a personal, placeholder or non-business record |

Bitcoin acceptance is reported separately and never gates the band. Requiring independent
corroboration of it put **zero** of 64 open submissions in the top band: a merchant's bitcoin
acceptance is rarely provable from outside their own submission, which is what the human and outreach
steps exist for.

## Safety rails

- `PAUSE` in this directory forces dry-run even when `--apply` is passed.
- Writing requires `--apply`; a scheduled run that lacks it cannot label anything.
- Outreach requires `--send` **and** an approval file, and records every send so an issue is never
  emailed twice.
- The audit trail is flushed and fsynced per issue, so a killed run cannot leave Gitea writes the
  trail lacks; `reconcile_audit.py` rebuilds anything lost.
- Apply deletes any previous `confidence/*` label before adding the new one, so a re-run cannot leave
  two contradictory bands.

## Running it

```bash
python3 triage_jev.py                       # dry run over open submissions
python3 triage_jev.py --limit 5 --apply     # label and comment on five
python3 digest.py                           # render today's digest
python3 inbox.py                            # new replies, matched to issues
python3 score_backlog.py                    # re-run the calibration
```

Credentials are read from `~/.config/btcmap/` (`gitea.token`, `kagi.token`, `zen.token`,
`email.env`, `matrix.env`), all mode 600. Nothing in this directory is committed with data in it —
caches and reports are git-ignored because they contain merchant contact details.

## Costs

Jev 1.13 paid is $0.042/1M input tokens and free to output: a full 243-submission pass costs
**$0.012**. The free id rate-limits at roughly 148 calls per burst, so batch work uses the paid id.
Kagi Extract is $4/1,000 pages and only runs for submissions carrying a website (~40 in 243). BTC Map
and OpenStreetMap lookups, and direct page fetches, are free.
