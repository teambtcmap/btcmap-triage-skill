#!/bin/sh
# Post the daily digest to #btcmap-taggers. Prints to stdout until the Matrix
# account exists; once it does, swap the last line for the send call and set
# MATRIX_ROOM / MATRIX_TOKEN in ~/.config/btcmap/matrix.env.
set -eu
cd "$(dirname "$0")"
exec python3 digest.py --out "reports/digest-$(date -u +%F).md"
