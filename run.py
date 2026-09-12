import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Normal relaunches must not be rejected because a previous process was still
# marked alive by the root server.
os.environ.setdefault("NODE_IGNORE_ALIVE", "1")

WORLD = "jolly-mayer/TuringHotelItaly"
ROOT = Path(__file__).resolve().parent
SETUP_FILE = ROOT / "christian_compt_setup.csv"
SETUP_FILES = {
    "20": SETUP_FILE,
    "50": ROOT / "christian_compt_setup_50_humans.csv",
    "100": ROOT / "christian_compt_setup_100_humans.csv",
}
LOGS_DIR = ROOT / "logs"
STATE_DIR = LOGS_DIR / "state"
ACCOUNT_KEY_FILE = ROOT / "account_key"
FEATHERLESS_KEY_FILENAMES = (
    "FEATHERLESS_API_KEYS",
    "featherless_keys",
    "featherles_keys",
    "featherless_keys.txt",
)
from utils import CLAUDE_MODEL_SELECTORS

DEFAULT_MODEL_IDS = {
    "Gemma 4 31B": "google/gemma-4-31B-it",
    "Gemma 4 E2B": "google/gemma-4-E2B-it",
    "Qwen 3.5 27B": "Qwen/Qwen3.5-27B",
    "Qwen 3.5 2B": "Qwen/Qwen3.5-2B",
    "Claude Opus": "Claude Opus",
    "Claude Haiku": "Claude Haiku",
    "Claude Sonnet": "Claude Sonnet",
    "Claude Fable": "Claude Fable",
}


def load_account_key():
    key_file = ACCOUNT_KEY_FILE
    if not key_file.exists():
        key_file = ROOT / "account_ket"
    try:
        return key_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def resolve_featherless_keys(filename=None):
    if filename is not None:
        return Path(filename).expanduser().resolve()
    for name in FEATHERLESS_KEY_FILENAMES:
        candidate = ROOT / name
        if candidate.is_file():
            return candidate
    raise ValueError(
        "missing Featherless keys: place FEATHERLESS_API_KEYS or featherless_keys "
        f"in {ROOT}, or pass the file path"
    )


def use_local_python():
    """Reuse the project's installed dependencies without manual activation."""
    venv = ROOT / ".venv"
    python = venv / "bin" / "python"
    if python.is_file() and Path(sys.prefix).resolve() != venv.resolve():
        os.execv(str(python), [str(python), str(ROOT / "run.py"), *sys.argv[1:]])


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


def state_file_for(config):
    return STATE_DIR / f"agent_{config['id']}.json"


def run_agent(config, featherless_key, unaiverse_key):
    from unaiverse.agent import Agent
    from unaiverse.networking.node.node import Node

    from policies import build_policy
    from processors.gemma import GemmaAgent
    from processors.opus import OpusAgent
    from processors.haiku import HaikuAgent
    from processors.sonnet import SonnetAgent
    from processors.fable import FableAgent
    from processors.qwen import QwenAgent
    from prompts import build_system_prompt

    llm = config["llm"]
    model_id = model_id_for(config)
    prompt = build_system_prompt(config)
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
            model=model_id or "Qwen/Qwen3.5-2B",
            cost=int(cost_value or 1),
        )
    elif llm in CLAUDE_MODEL_SELECTORS:
        classes = {"Claude Haiku": HaikuAgent, "Claude Sonnet": SonnetAgent,
                   "Claude Opus": OpusAgent, "Claude Fable": FableAgent}
        if model_id != llm:
            raise ValueError(f"Unsupported Claude model ID: {model_id}")
        processor = classes[llm](prompt, "medium")
    else:
        raise ValueError(f"Unsupported model configuration: {llm}")

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


def running_session_names():
    result = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    names = set()
    for line in result.stdout.splitlines():
        fields = line.strip().split()
        if not fields or "." not in fields[0]:
            continue
        name = fields[0].split(".", 1)[1]
        if "(Detached)" in line or "(Attached)" in line:
            names.add(name)
    return names


def session_is_running(session_name):
    return session_name in running_session_names()


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
    state_file = state_file_for(config)

    if session_is_running(session_name):
        print(f"{node_name} è già attivo nella sessione {session_name}.", flush=True)
        return True

    env = os.environ.copy()
    env["COMPETITION_AGENT_ID"] = config["id"]
    env["COMPETITION_UNAIVERSE_KEY"] = unaiverse_key
    env["COMPETITION_LOG_FILE"] = str(log_file)
    env["COMPETITION_STATE_FILE"] = str(state_file)
    env["COMPETITION_SETUP_FILE"] = str(Path(setup_file).resolve())
    env["NODE_IGNORE_ALIVE"] = "1"
    if featherless_key:
        env["COMPETITION_FEATHERLESS_KEY"] = featherless_key

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file.unlink(missing_ok=True)

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


def restart_agent(config, featherless_key, unaiverse_key, setup_file=SETUP_FILE):
    """Wait for the old screen session to disappear before reusing its identity."""
    session_name = f"competition_agent_{config['id']}"
    if session_is_running(session_name):
        if not stop_agent(config):
            return False
        for _ in range(40):
            if not session_is_running(session_name):
                break
            time.sleep(0.25)
        else:
            print(f"Cannot restart {node_name_for(config)}: session is still running.", flush=True)
            return False
    return launch_agent(config, featherless_key, unaiverse_key, setup_file)


def select_configs(configs, provider, agents=None):
    if provider == "claude":
        configs = [config for config in configs if config["llm"].startswith("Claude")]
    elif provider == "featherless":
        configs = [config for config in configs if config["featherless_model_key"] != "NA"]
    if not configs:
        raise ValueError(f"no agents match provider '{provider}'")
    if not agents:
        return configs

    selected_ids = set()
    for selector in agents:
        selector = selector.strip()
        matches = [config for config in configs if config["id"] == selector]
        if not matches:
            matches = [config for config in configs if config["agent_name"].casefold() == selector.casefold()]
        if not matches:
            raise ValueError(f"agent '{selector}' not found in the selected setup/provider; use --list")
        if len(matches) != 1:
            raise ValueError(f"ambiguous agent '{selector}'; select a unique ID")
        selected_ids.add(matches[0]["id"])
    return [config for config in configs if config["id"] in selected_ids]


def agent_label(config, sessions):
    status = "running" if f"competition_agent_{config['id']}" in sessions else "stopped"
    return (
        f"#{config['id']}  {node_name_for(config)} | {status} | "
        f"{config['policy_type']} | persona: {config['persona_info']}"
    )


def choose_menu(title, options, default=None):
    """A line-oriented menu that also works without a full-screen terminal."""
    print(f"\n{title}")
    default_number = None
    for number, (value, label) in enumerate(options, start=1):
        marker = " [default]" if value == default else ""
        print(f"{number}) {label}{marker}")
        if value == default:
            default_number = number
    print("0) Exit")
    while True:
        answer = input("Choice: ").strip()
        if not answer and default_number is not None:
            answer = str(default_number)
        if answer == "0":
            return None
        if answer.isascii() and answer.isdecimal() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][0]
        print(f"Enter a number from 0 to {len(options)}.")


def configure_interactively(args):
    args.action = choose_menu("What would you like to do?", [
        ("launch", "Launch agents (keep existing sessions)"),
        ("restart", "Restart agents (launch them if stopped)"),
        ("stop", "Stop agents"),
        ("list", "List configured agents and session status"),
    ], default=args.action)
    if args.action is None:
        return False
    setup_options = [(alias, f"Setup {alias}: {path.name}") for alias, path in SETUP_FILES.items()]
    if args.setup not in SETUP_FILES:
        setup_options.insert(0, (args.setup, f"Current setup: {args.setup}"))
    setup_options.append(("custom", "Another CSV file"))
    setup = choose_menu("Which configuration?", setup_options, default=args.setup)
    if setup is None:
        return False
    if setup == "custom":
        setup = input("CSV path (empty to exit): ").strip()
        if not setup:
            return False
    args.setup = setup
    args.provider = choose_menu("Which providers?", [
        ("all", "All providers"),
        ("claude", "Claude only"),
        ("featherless", "Featherless only"),
    ], default=args.provider)
    return args.provider is not None


def execute(args):
    if args.tui and not configure_interactively(args):
        return 0
    setup_file = resolve_setup(args.setup)
    with setup_file.open(newline="", encoding="utf-8") as file:
        configs = list(csv.DictReader(file))
    if not configs:
        raise ValueError(f"setup is empty: {setup_file}")
    configs = select_configs(configs, args.provider, args.agent)

    if shutil.which("screen") is None:
        raise ValueError("GNU screen is required; install it before managing the agents")

    if args.action == "list":
        sessions = running_session_names()
        print(f"Setup: {setup_file}")
        for config in configs:
            print(agent_label(config, sessions))
        return 0

    if args.tui:
        sessions = running_session_names()
        options = [("all", f"All {len(configs)} selected agents")]
        options.extend((config["id"], agent_label(config, sessions)) for config in configs)
        selected = choose_menu(f"Which agents to {args.action}?", options)
        if selected is None:
            return 0
        if selected != "all":
            configs = select_configs(configs, "all", [selected])

    if args.action == "stop":
        stopped = 0
        for config in configs:
            if not session_is_running(f"competition_agent_{config['id']}"):
                print(f"{node_name_for(config)} is already stopped.")
                stopped += 1
            else:
                stopped += stop_agent(config)
        print(f"Stop completed: {stopped}/{len(configs)} sessions stopped.")
        return 0 if stopped == len(configs) else 1

    unaiverse_key = args.unaiverse_key or load_account_key()
    if not unaiverse_key:
        raise ValueError(
            f"missing UNaIVERSE account key: place account_key in {ROOT} "
            "or pass unaiverse_key"
        )

    keys = {}
    if any(config["featherless_model_key"] != "NA" for config in configs):
        keys = load_featherless_keys(resolve_featherless_keys(args.featherless_keys_file))

    # Validate every selected credential and identity before stopping any agent.
    for config in configs:
        featherless_key_for(config, keys)
        node_name_for(config)

    LOGS_DIR.mkdir(exist_ok=True)
    started = 0
    operation = restart_agent if args.action == "restart" else launch_agent
    for index, config in enumerate(configs):
        key = featherless_key_for(config, keys)
        started += operation(config, key, unaiverse_key, setup_file)
        if index < len(configs) - 1:
            time.sleep(16)

    print(f"Lancio completato: {started}/{len(configs)} sessioni attive.")
    return 0 if started == len(configs) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Launch and manage agents from a setup CSV. Default: launch all, keeping existing sessions.",
        epilog="Examples: python run.py --agent 3; python run.py --agent Neo --restart; python run.py --tui",
    )
    parser.add_argument(
        "featherless_keys_file",
        nargs="?",
        help="Featherless keys file; discovered in the project directory by default",
    )
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
    parser.add_argument(
        "--provider",
        choices=("claude", "featherless", "all"),
        default="all",
        help="which agents to manage; defaults to all",
    )
    parser.add_argument(
        "--agent",
        action="append",
        metavar="ID_OR_NAME",
        help="select an agent by ID or exact name (case-insensitive); repeat to select more",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--restart", dest="action", action="store_const", const="restart",
        help="restart selected agents, launching any that are stopped; without --agent, applies to all matches",
    )
    actions.add_argument(
        "--stop", dest="action", action="store_const", const="stop",
        help="stop selected agents; without --agent, applies to all matches (no credentials needed)",
    )
    actions.add_argument(
        "--list", dest="action", action="store_const", const="list",
        help="list configured agents and screen session status (no credentials needed)",
    )
    parser.set_defaults(action="launch")
    parser.add_argument("--tui", action="store_true", help="choose an operation with simple numbered menus")
    args = parser.parse_args(argv)
    if argv is None:
        use_local_python()
    try:
        return execute(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    except EOFError:
        print("\nCancelled.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted. Existing screen sessions remain running.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
