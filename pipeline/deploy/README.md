# BTC Map triage — remote install (btcmap VPS)

**Nothing here runs on a schedule by default** — the timers are installed
*disabled* and the runner defaults to dry-run. This file says exactly what to turn on.

## What is here

```
~/btcmap-triage/
  triage_jev.py        one triage pass: evidence -> Jev 1.13 -> Gitea labels + one comment
  evidence.py          evidence collector (direct fetch + Kagi Extract unioned, BTC Map lookup, duplicates)
  jev_client.py        headless Jev client; reads the project Zen key first
  digest.py            renders the daily digest for a room
  reconcile_audit.py   rebuilds the audit trail from Gitea when a run is killed mid-flight
  score_backlog.py     calibration harness over the historical backlog
  audit_formats.py     body-format coverage audit (five layouts exist in this repo)
  run-triage.sh        wrapper: dry-run by default, PAUSE-aware
  run-digest.sh        wrapper for digest.py
  templates/           outreach email draft
  reports/             audit trail (JSONL) + rendered reports

~/.config/btcmap/      tokens, 0600: gitea.token, kagi.token, zen.token
~/.config/systemd/user btcmap-triage.{service,timer}, btcmap-digest.{service,timer}
```

## Enabling, deliberately

```sh
# 1. dry run by hand, read the output
~/btcmap-triage/run-triage.sh

# 2. real labels/comments for up to 30 open submissions
~/btcmap-triage/run-triage.sh --apply

# 3. only then, if you want it automatic (dry-run timer):
systemctl --user daemon-reload
systemctl --user enable --now btcmap-triage.timer
```

**Two brakes.** Without `--apply` nothing is written. And `touch ~/btcmap-triage/PAUSE`
forces dry-run even when `--apply` is passed — use it to stop a scheduled run without
disabling the timer. `rm PAUSE` resumes.

Automatic *writing* would need the timer to call `run-triage.sh --apply`; as installed it
does not. Change that line only if you want unattended writes.

## Kill switch for the whole install

```sh
systemctl --user disable --now btcmap-triage.timer btcmap-digest.timer
```

## Things that need credentials before they do anything

| Feature | Needs | State |
|---|---|---|
| Triage + labels | `~/.config/btcmap/{gitea,kagi,zen}.token` | in place, permissions 600 |
| Outreach email | mailbox IMAP/SMTP credentials | set in `~/.config/btcmap/email.env` |
| Daily digest in #btcmap-taggers | a Matrix account + access token | see Matrix below |

## Matrix

The bot account lives on this deployment's own homeserver (`install-synapse.sh`), which federates
with matrix.org so it can join the taggers room. Registration on matrix.org itself is closed
(`M_FORBIDDEN: Registration has been disabled. Only m.login.application_service registrations are
allowed`), which is why a self-hosted homeserver is the workable route:

```sh
sudo ./install-synapse.sh matrix.example.org    # homeserver, loopback listener, Caddy vhost
sudo ./finish-synapse.sh                        # logging path + settings the first pass misses
./create-matrix-account.sh                      # bot account + access token into ~/.config/btcmap/
./federation-discovery.sh                       # .well-known delegating federation to :443
./join-and-intro.sh                             # join the room, introduce the bot, post the digest
```

`federation-discovery.sh` matters more than it looks: by default a homeserver looks for its peers on
port **8448**, not 443, so without the `.well-known/matrix/server` delegation the join fails with a
timeout even when DNS and certificates are correct.

Room: `#btcmap-taggers:matrix.org` (`!ijZcvHZVEAtefLGwdo:matrix.org`).

## Costs, measured

* Jev 1.13 paid: **~$0.05 per 1,000 input tokens**; a full 243-submission pass costs
  **$0.012**. The free tier rate-limits at ~148 calls per burst, so batch work uses the paid id.
* Kagi Extract: $4/1,000 pages, called only for submissions that carry a website
  (~40 per 243). Kagi Search via the MCP server.
* Everything else (BTC Map API, OpenStreetMap lookups, direct page fetches) is free.
