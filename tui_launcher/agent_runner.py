import csv
import os
import sys
import traceback

from run import SETUP_FILE, run_agent


def main():
    agent_id = os.environ.pop("COMPETITION_AGENT_ID")
    unaiverse_key = os.environ.pop("COMPETITION_UNAIVERSE_KEY")
    featherless_key = os.environ.pop("COMPETITION_FEATHERLESS_KEY", None)
    log_file = os.environ.pop("COMPETITION_LOG_FILE")

    output = open(log_file, "a", buffering=1, encoding="utf-8")
    os.dup2(output.fileno(), sys.stdout.fileno())
    os.dup2(output.fileno(), sys.stderr.fileno())

    with SETUP_FILE.open(newline="", encoding="utf-8") as file:
        config = next(row for row in csv.DictReader(file) if row["id"] == agent_id)

    print(f"[launcher] Starting {config['agent_name']} (PID {os.getpid()})", flush=True)
    try:
        run_agent(config, featherless_key, unaiverse_key)
    except BaseException:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
