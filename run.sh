#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 FEATHERLESS_KEYS_FILE [20|50|100]" >&2
    exit 2
fi

FEATHERLESS_KEYS_FILE="$(realpath -- "$1")"
SETUP="${2:-20}"

case "$SETUP" in
    20|50|100) ;;
    *)
        echo "Invalid setup: choose 20, 50, or 100." >&2
        exit 2
        ;;
esac

if [[ ! -s "$FEATHERLESS_KEYS_FILE" ]]; then
    echo "Featherless keys file is missing or empty: $FEATHERLESS_KEYS_FILE" >&2
    exit 1
fi

if [[ ! -s "$ROOT_DIR/account_key" ]]; then
    echo "Missing account_key: start the TUI once to save it." >&2
    exit 1
fi

mapfile -t sessions < <(
    screen -ls 2>/dev/null |
        sed -nE 's/^[[:space:]]*([0-9]+\.competition_agent_[0-9]+)[[:space:]].*/\1/p'
)

for session in "${sessions[@]}"; do
    echo "Stopping $session"
    screen -S "$session" -X quit
done

exec python "$ROOT_DIR/run.py" "$FEATHERLESS_KEYS_FILE" --setup "$SETUP"
