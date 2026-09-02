import csv
import time
from itertools import cycle

from prompt_toolkit.shortcuts import (
    checkboxlist_dialog,
    input_dialog,
    message_dialog,
    radiolist_dialog,
    yes_no_dialog,
)
from prompt_toolkit.styles import Style

from run import LOGS_DIR, SETUP_FILE, launch_agent, session_is_running, stop_agent


STYLE = Style.from_dict(
    {
        "dialog": "bg:#171b22",
        "dialog frame.label": "#8ab4f8 bold",
        "button": "bg:#303846 #e8eaed",
        "button.focused": "bg:#8ab4f8 #101318 bold",
        "radio-selected": "#8ab4f8 bold",
        "checkbox-selected": "#8ab4f8 bold",
    }
)


def load_configs():
    with SETUP_FILE.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def choose_action():
    return radiolist_dialog(
        title="Turing Hotel · Agent launcher",
        text="Cosa vuoi fare?",
        values=[
            ("launch", "Lancia agenti"),
            ("stop", "Termina agenti"),
        ],
        default="launch",
        ok_text="Continua",
        cancel_text="Esci",
        style=STYLE,
    ).run()


def model_name(llm):
    if llm.startswith("Gemma"):
        return "Gemma"
    if llm.startswith("Qwen"):
        return "Qwen"
    return "Claude Opus"


def choose_agents(configs):
    choice = radiolist_dialog(
        title="Turing Hotel · Agent launcher",
        text="Quali agenti vuoi lanciare?",
        values=[
            ("all", "Tutti gli agenti"),
            ("no_claude", "Tutti tranne Claude"),
            ("claude", "Solo Claude"),
            ("custom", "Selezione manuale"),
        ],
        default="all",
        ok_text="Continua",
        cancel_text="Esci",
        style=STYLE,
    ).run()

    if choice is None:
        return []
    if choice == "all":
        return configs
    if choice == "no_claude":
        return [config for config in configs if config["llm"] != "Claude Opus"]
    if choice == "claude":
        return [config for config in configs if config["llm"] == "Claude Opus"]

    selected_ids = checkboxlist_dialog(
        title="Selezione manuale",
        text="Spazio seleziona · Invio conferma",
        values=[
            (
                config["id"],
                f"#{config['id']:>2}  {config['agent_name']} ({model_name(config['llm'])})  "
                f"{config['policy_type']} · persona {config['persona_info']}",
            )
            for config in configs
        ],
        default_values=[config["id"] for config in configs],
        ok_text="Continua",
        cancel_text="Indietro",
        style=STYLE,
    ).run()
    if selected_ids is None:
        return choose_agents(configs)
    return [config for config in configs if config["id"] in selected_ids]


def ask_credentials(needs_featherless):
    keys = []
    if needs_featherless:
        keys_file = input_dialog(
            title="Credenziali Featherless",
            text="Percorso del file con una chiave per riga:",
            ok_text="Continua",
            cancel_text="Esci",
            style=STYLE,
        ).run()
        if not keys_file:
            return None, None
        try:
            with open(keys_file, encoding="utf-8") as file:
                keys = [line.strip() for line in file if line.strip()]
        except OSError as error:
            message_dialog(title="File non leggibile", text=str(error), style=STYLE).run()
            return ask_credentials(needs_featherless)
        if not keys:
            message_dialog(title="File vuoto", text="Non ho trovato chiavi Featherless.", style=STYLE).run()
            return ask_credentials(needs_featherless)

    unaiverse_key = input_dialog(
        title="Credenziali UNaIVERSE",
        text="UNaIVERSE key (non verrà mostrata):",
        password=True,
        ok_text="Continua",
        cancel_text="Esci",
        style=STYLE,
    ).run()
    return keys, unaiverse_key


def stop_agents(configs):
    active = [
        config
        for config in configs
        if session_is_running(f"competition_agent_{config['id']}")
    ]
    if not active:
        message_dialog(
            title="Nessun agente attivo",
            text="Non ci sono sessioni competition_agent aperte.",
            style=STYLE,
        ).run()
        return

    selected_ids = checkboxlist_dialog(
        title="Termina agenti",
        text="Seleziona le sessioni da terminare:",
        values=[
            (
                config["id"],
                f"#{config['id']:>2}  {config['agent_name']} ({model_name(config['llm'])})",
            )
            for config in active
        ],
        ok_text="Continua",
        cancel_text="Annulla",
        style=STYLE,
    ).run()
    if not selected_ids:
        return

    selected = [config for config in active if config["id"] in selected_ids]
    confirmed = yes_no_dialog(
        title="Conferma arresto",
        text=f"Terminare {len(selected)} agenti selezionati?",
        yes_text="Termina",
        no_text="Annulla",
        style=STYLE,
    ).run()
    if not confirmed:
        return

    stopped = sum(stop_agent(config) for config in selected)
    message_dialog(
        title="Arresto completato",
        text=f"Sessioni terminate: {stopped}/{len(selected)}.",
        style=STYLE,
    ).run()


def wait_before_next_agent(seconds=16):
    for remaining in range(seconds, 0, -1):
        print(f"\rProssimo agente tra {remaining:2} secondi...", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 40 + "\r", end="", flush=True)


def main():
    configs = load_configs()
    action = choose_action()
    if action == "stop":
        stop_agents(configs)
        return
    if action != "launch":
        return

    configs = choose_agents(configs)
    if not configs:
        return

    needs_featherless = any(config["featherless_model_key"] != "NA" for config in configs)
    keys, unaiverse_key = ask_credentials(needs_featherless)
    if keys is None or not unaiverse_key:
        return

    models = sorted({config["llm"] for config in configs})
    confirmed = yes_no_dialog(
        title="Conferma lancio",
        text=f"Agenti: {len(configs)}\nModelli: {', '.join(models)}\n\nAvviare ora?",
        yes_text="Avvia",
        no_text="Annulla",
        style=STYLE,
    ).run()
    if not confirmed:
        return

    key_pool = cycle(keys) if keys else None
    LOGS_DIR.mkdir(exist_ok=True)
    started = 0
    for index, config in enumerate(configs):
        featherless_key = next(key_pool) if config["featherless_model_key"] != "NA" else None
        started += launch_agent(config, featherless_key, unaiverse_key)
        if index < len(configs) - 1:
            wait_before_next_agent()

    print(f"\nLancio completato: {started}/{len(configs)} sessioni attive.", flush=True)
    print("La TUI può essere chiusa: gli agenti restano nelle sessioni screen.", flush=True)


if __name__ == "__main__":
    main()
