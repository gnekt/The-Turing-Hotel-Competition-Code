import argparse
import csv
import os
import subprocess
import sys
import time
from itertools import cycle
from pathlib import Path

# Normal relaunches must not be rejected because a previous process was still
# marked alive by the root server.
os.environ.setdefault("NODE_IGNORE_ALIVE", "1")

from unaiverse.agent import Agent
from unaiverse.networking.node.node import Node

from policies import build_policy
from processors.gemma import GemmaAgent
from processors.opus import OpusAgent
from processors.qwen import QwenAgent
from prompts import build_system_prompt


WORLD = "jolly-mayer/TuringHotelItaly"
SETUP_FILE = Path(__file__).with_name("christian_compt_setup.csv")
LOGS_DIR = Path(__file__).with_name("logs")


def run_agent(config, featherless_key, unaiverse_key):
    llm = config["llm"]
    prompt = build_system_prompt(config)

    if llm.startswith("Gemma"):
        processor = GemmaAgent(prompt, "medium", featherless_key)
    elif llm.startswith("Qwen"):
        processor = QwenAgent(prompt, "medium", featherless_key)
    else:
        processor = OpusAgent(prompt, "medium")

    agent = Agent(
        proc=processor,
        proc_inputs=["text"],
        proc_outputs=["text"],
        policy_filter=build_policy(config["policy_type"]),
    )
    node = Node(
        hosted=agent,
        unaiverse_key=unaiverse_key,
        node_name=config["agent_name"] or f"MyGuest{config['id']}",
        hidden=True,
        clock_delta=1.0 / 10.0,
    )
    node.run(join_world=WORLD)


def session_is_running(session_name):
    result = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        fields = line.strip().split()
        if not fields or "." not in fields[0]:
            continue
        name = fields[0].split(".", 1)[1]
        if name == session_name and ("(Detached)" in line or "(Attached)" in line):
            return True
    return False


def stop_agent(config):
    node_name = config["agent_name"] or f"MyGuest{config['id']}"
    session_name = f"competition_agent_{config['id']}"

    if not session_is_running(session_name):
        print(f"{node_name} non è attivo.", flush=True)
        return False

    result = subprocess.run(
        ["screen", "-S", session_name, "-X", "quit"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERRORE terminando {node_name}: {result.stderr.strip()}", flush=True)
        return False

    print(f"{node_name} terminato.", flush=True)
    return True


def launch_agent(config, featherless_key, unaiverse_key):
    node_name = config["agent_name"] or f"MyGuest{config['id']}"
    session_name = f"competition_agent_{config['id']}"
    log_file = LOGS_DIR / f"agent_{config['id']}.log"

    if session_is_running(session_name):
        print(f"{node_name} è già attivo nella sessione {session_name}.", flush=True)
        return True

    env = os.environ.copy()
    env["COMPETITION_AGENT_ID"] = config["id"]
    env["COMPETITION_UNAIVERSE_KEY"] = unaiverse_key
    env["COMPETITION_LOG_FILE"] = str(log_file)
    env["NODE_IGNORE_ALIVE"] = "1"
    if featherless_key:
        env["COMPETITION_FEATHERLESS_KEY"] = featherless_key

    result = subprocess.run(
        [
            "screen",
            "-dmS",
            session_name,
            sys.executable,
            "-u",
            "-m",
            "tui_launcher.agent_runner",
        ],
        cwd=SETUP_FILE.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERRORE avviando {node_name}: {result.stderr.strip()}", flush=True)
        return False

    time.sleep(1)
    if not session_is_running(session_name):
        print(f"ERRORE: {node_name} è terminato · controlla {log_file}", flush=True)
        return False

    print(f"{node_name} attivo · log: {log_file}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("featherless_keys_file")
    parser.add_argument("unaiverse_key")
    args = parser.parse_args()

    with open(args.featherless_keys_file, encoding="utf-8") as file:
        keys = cycle(line.strip() for line in file if line.strip())

    with SETUP_FILE.open(newline="", encoding="utf-8") as file:
        configs = list(csv.DictReader(file))

    LOGS_DIR.mkdir(exist_ok=True)
    started = 0
    for index, config in enumerate(configs):
        key = next(keys) if config["featherless_model_key"] != "NA" else None
        started += launch_agent(config, key, args.unaiverse_key)
        if index < len(configs) - 1:
            time.sleep(16)

    print(f"Lancio completato: {started}/{len(configs)} sessioni attive.")


if __name__ == "__main__":
    main()
