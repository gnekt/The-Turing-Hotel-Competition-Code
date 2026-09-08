"""Stop the current user's competition agent screen sessions."""

import argparse
import os
import re
import subprocess
import sys


SESSION_ID = re.compile(r"\d+\.competition_agent_\d+")


def screen_command(*args):
    return subprocess.run(
        ["screen", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "LC_ALL": "C"},
    )


def competition_sessions():
    result = screen_command("-ls")
    if result.returncode != 0 and "No Sockets found" not in result.stdout:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "screen -ls failed")
    sessions = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and SESSION_ID.fullmatch(fields[0]):
            if "(Attached)" in line or "(Detached)" in line:
                sessions.append(fields[0])
    return sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list sessions without stopping them")
    args = parser.parse_args(argv)

    try:
        sessions = competition_sessions()
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        print(f"Cannot list agent sessions: {error}", file=sys.stderr)
        return 1

    if not sessions:
        print("No competition agents are running.")
        return 0

    stopped = 0
    for session in sessions:
        if args.dry_run:
            print(f"Would stop {session}")
            continue
        try:
            result = screen_command("-S", session, "-X", "quit")
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "screen quit failed")
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
            print(f"Cannot stop {session}: {error}", file=sys.stderr)
            continue
        stopped += 1
        print(f"Stopped {session}", flush=True)

    if args.dry_run:
        print(f"Found {len(sessions)} competition agent sessions.")
        return 0
    print(f"Stopped {stopped}/{len(sessions)} competition agent sessions.")
    return 0 if stopped == len(sessions) else 1


if __name__ == "__main__":
    sys.exit(main())
