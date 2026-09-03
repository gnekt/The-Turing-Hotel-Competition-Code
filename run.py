import argparse
import csv
import os
import subprocess
import sys
import time
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
ROOT = Path(__file__).parent
SETUP_FILE = ROOT / "christian_compt_setup.csv"
SETUP_FILES = {
    "20": SETUP_FILE,
    "50": ROOT / "christian_compt_setup_50_humans.csv",
    "100": ROOT / "christian_compt_setup_100_humans.csv",
}
LOGS_DIR = ROOT / "logs"
ACCOUNT_KEY_FILE = ROOT / "account_key"
DEFAULT_MODEL_IDS = {
    "Gemma 4 31B": "google/gemma-4-31B-it",
    "Gemma 4 E2B": "google/gemma-4-E2B-it",
    "Qwen 3 32B": "Qwen/Qwen3-32B",
    "Qwen 3 0.6B": "Qwen/Qwen3-0.6B",
    "Claude Opus": "Claude Opus",
}


def load_account_key():
    try:
        return ACCOUNT_KEY_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_account_key(account_key):
    ACCOUNT_KEY_FILE.parent.mkdir(exist_ok=True)
    ACCOUNT_KEY_FILE.write_text(account_key.strip() + "\n", encoding="utf-8")
    ACCOUNT_KEY_FILE.chmod(0o600)


def resolve_setup(value):
    return SETUP_FILES.get(str(value), Path(value)).expanduser().resolve()


def load_featherless_keys(filename):
    keys = {}
    with open(filename, newline="", encoding="utf-8") as file:
        for line_number, row in enumerate(csv.reader(file), start=1):
            if not row or not any(value.strip() for value in row):
                continue
            if len(row) != 3:
                raise ValueError(
                    f"invalid Featherless key row {line_number}: expected alias,key,capacity"
                )
            alias, secret, capacity_value = (value.strip() for value in row)
            if not alias or not secret:
                raise ValueError(f"invalid Featherless key row {line_number}: empty value")
            if alias in keys:
                raise ValueError(f"duplicate Featherless key alias: {alias}")
            try:
                capacity = int(capacity_value)
            except ValueError as error:
                raise ValueError(
                    f"invalid capacity for Featherless key alias: {alias}"
                ) from error
            if capacity <= 0:
                raise ValueError(f"capacity must be positive for Featherless key alias: {alias}")
            keys[alias] = {"secret": secret, "capacity": capacity}
    if not keys:
        raise ValueError("the Featherless keys file is empty")
    return keys


def featherless_key_for(config, keys):
    alias = config["featherless_model_key"]
    if alias == "NA":
        return None
    try:
        return keys[alias]["secret"]
    except KeyError as error:
        raise ValueError(f"missing Featherless key alias: {alias}") from error


def model_id_for(config):
    model_id = config.get("model_id", "").strip()
    if model_id:
        return model_id
    try:
        return DEFAULT_MODEL_IDS[config["llm"]]
    except KeyError as error:
        raise ValueError(f"unsupported model configuration: {config['llm']}") from error


def node_name_for(config):
    agent_name = config["agent_name"] or f"MyGuest{config['id']}"
    short_model_id = model_id_for(config).rsplit("/", 1)[-1]
    return f"{agent_name} ({short_model_id})"


def run_agent(config, featherless_key, unaiverse_key):
    llm = config["llm"]
    prompt = build_system_prompt(config)
    model_id = model_id_for(config)
    cost_value = config.get("concurrency_cost", "").strip()

    if llm.startswith("Gemma"):
        processor = GemmaAgent(
            prompt,
            "medium",
            featherless_key,
            model=model_id or "google/gemma-4-31B-it",
            cost=int(cost_value or 2),
        )
    elif llm.startswith("Qwen"):
        processor = QwenAgent(
            prompt,
            "medium",
            featherless_key,
            model=model_id or "Qwen/Qwen3-0.6B",
            cost=int(cost_value or 1),
        )
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
        node_name=node_name_for(config),
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
    node_name = node_name_for(config)
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


def launch_agent(config, featherless_key, unaiverse_key, setup_file=SETUP_FILE):
    node_name = node_name_for(config)
    session_name = f"competition_agent_{config['id']}"
    log_file = LOGS_DIR / f"agent_{config['id']}.log"

    if session_is_running(session_name):
        print(f"{node_name} è già attivo nella sessione {session_name}.", flush=True)
        return True

    env = os.environ.copy()
    env["COMPETITION_AGENT_ID"] = config["id"]
    env["COMPETITION_UNAIVERSE_KEY"] = unaiverse_key
    env["COMPETITION_LOG_FILE"] = str(log_file)
    env["COMPETITION_SETUP_FILE"] = str(Path(setup_file).resolve())
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
            "agent_runner",
        ],
        cwd=ROOT,
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
    parser.add_argument(
        "unaiverse_key",
        nargs="?",
        help="UNaIVERSE account key; defaults to ./account_key",
    )
    parser.add_argument(
        "--setup",
        default="20",
        help="setup alias (20, 50, 100) or CSV path; defaults to 20",
    )
    args = parser.parse_args()

    setup_file = resolve_setup(args.setup)
    unaiverse_key = args.unaiverse_key or load_account_key()
    if not unaiverse_key:
        parser.error(
            "missing UNaIVERSE account key: pass unaiverse_key or save it with the TUI"
        )

    try:
        keys = load_featherless_keys(args.featherless_keys_file)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    with setup_file.open(newline="", encoding="utf-8") as file:
        configs = list(csv.DictReader(file))

    try:
        for config in configs:
            featherless_key_for(config, keys)
    except ValueError as error:
        parser.error(str(error))

    LOGS_DIR.mkdir(exist_ok=True)
    started = 0
    for index, config in enumerate(configs):
        key = featherless_key_for(config, keys)
        started += launch_agent(config, key, unaiverse_key, setup_file)
        if index < len(configs) - 1:
            time.sleep(16)

    print(f"Lancio completato: {started}/{len(configs)} sessioni attive.")


if __name__ == "__main__":
    main()
