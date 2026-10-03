#!/bin/sh
# Run one triage pass. DRY RUN BY DEFAULT.
#
#   ./run-triage.sh            # scores and prints; writes nothing
#   ./run-triage.sh --apply    # labels + comments on Gitea for real
#
# Two independent brakes:
#   1. no --apply means nothing is written, whatever else is configured
#   2. a file named PAUSE in this directory forces dry-run even WITH --apply
#      (touch PAUSE to stop a scheduled run mid-notice; rm PAUSE to resume)
set -eu

cd "$(dirname "$0")"
export BTCMAP_ZEN_KEY="$(cat "$HOME/.config/btcmap/zen.token")"

if [ -f PAUSE ]; then
  echo "PAUSE present: forcing dry run"
  set -- --limit 30
fi

exec python3 triage_jev.py --limit 30 "$@"
