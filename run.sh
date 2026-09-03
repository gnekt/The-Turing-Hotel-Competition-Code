#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SETUP_FILE="$ROOT_DIR/christian_compt_setup.csv"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 FEATHERLESS_KEYS_FILE" >&2
    exit 2
fi

FEATHERLESS_KEYS_FILE="$(realpath -- "$1")"

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

exec python "$ROOT_DIR/run.py" "$FEATHERLESS_KEYS_FILE" --setup "$SETUP_FILE"
