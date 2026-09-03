"""Read-only live conversation monitor for locally launched agents."""

import json
import time
from datetime import datetime

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.filters import has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, RadioList, TextArea

from run import node_name_for, running_session_names, state_file_for


MONITOR_STYLE = Style.from_dict(
    {
        "root": "bg:#07110d #d9e7df",
        "header": "bg:#0c2119 #66f2a3 bold",
        "header.meta": "bg:#0c2119 #9db7aa",
        "panel": "bg:#0d1b16 #d9e7df",
        "frame.border": "#285b45",
        "frame.label": "#63d9d2 bold",
        "radio": "#a9c2b5",
        "radio-selected": "bg:#173a2c #effff6 bold",
        "radio-checked": "#66f2a3",
        "status.running": "#66f2a3 bold",
        "status.stopped": "#60766b",
        "metadata.label": "#78958a",
        "metadata.value": "#e0eee7",
        "empty": "#78958a italic",
        "footer": "bg:#10241b #8ba398",
        "footer.key": "bg:#244b39 #e9fff3 bold",
    }
)


def load_snapshot(config):
    """Load a complete atomic snapshot, returning None before the first turn."""
    try:
        payload = json.loads(state_file_for(config).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("history"), list):
        return None
    return payload


def _visible_events(text):
    return (text or "").replace("\x1e", "\n\n── evento successivo ──\n\n").strip()


def render_history(snapshot):
    if not snapshot or not snapshot["history"]:
        return "Nessun messaggio nella Conversation.history di questo agente."

    rendered = []
    for index, message in enumerate(snapshot["history"], start=1):
        if message.get("mine"):
            speaker = "AGENTE"
        else:
            speaker = message.get("speaker") or "EVENTO"
        text = _visible_events(message.get("text", "")) or "—"
        indented = text.replace("\n", "\n    ")
        rendered.append(f"{index:03}  {speaker}\n    {indented}")
    return "\n\n".join(rendered)


def _set_text(area, value):
    if area.text == value:
        return
    area.buffer.set_document(
        Document(value, cursor_position=len(value)),
        bypass_readonly=True,
    )


class ConversationMonitor:
    def __init__(self, configs, setup_file):
        self.configs = configs
        self.by_id = {config["id"]: config for config in configs}
        self.setup_name = setup_file.name
        self.running = set()
        self.snapshot = None

        self.agent_list = RadioList(
            [
                (config["id"], self._agent_label(config))
                for config in configs
            ],
            default=configs[0]["id"],
            show_scrollbar=True,
        )
        self.history = TextArea(
            read_only=True,
            scrollbar=True,
            wrap_lines=True,
            style="class:panel",
        )
        self.last_input = TextArea(
            read_only=True,
            scrollbar=True,
            wrap_lines=True,
            style="class:panel",
        )
        self.last_output = TextArea(
            read_only=True,
            scrollbar=True,
            wrap_lines=True,
            style="class:panel",
        )

        self.header = Window(
            FormattedTextControl(self._header_text),
            height=3,
            style="class:header",
        )
        self.metadata = Window(
            FormattedTextControl(self._metadata_text),
            height=6,
            style="class:panel",
        )
        self.footer = Window(
            FormattedTextControl(self._footer_text),
            height=1,
            style="class:footer",
        )

    @property
    def selected(self):
        return self.by_id[self.agent_list.current_value]

    def _agent_label(self, config):
        session = f"competition_agent_{config['id']}"

        def label():
            running = session in self.running
            return FormattedText(
                [
                    ("class:status.running" if running else "class:status.stopped",
                     "● " if running else "○ "),
                    ("", f"{config['id']:>2}  {node_name_for(config)}"),
                ]
            )

        return label

    def _header_text(self):
        active = len(self.running)
        return FormattedText(
            [
                ("class:header", "  TURING HOTEL  /  CONVERSATION MONITOR\n"),
                ("class:header.meta", f"  Setup {self.setup_name}  ·  {active}/{len(self.configs)} agenti attivi\n"),
                ("class:header.meta", f"  Selezionato: {node_name_for(self.selected)}"),
            ]
        )

    def _metadata_text(self):
        config = self.selected
        session = f"competition_agent_{config['id']}"
        status = "ATTIVO" if session in self.running else "NON ATTIVO"
        if self.snapshot:
            updated = float(self.snapshot.get("updated_at", 0))
            age = max(0, int(time.time() - updated))
            timestamp = datetime.fromtimestamp(updated).strftime("%H:%M:%S")
            freshness = f"{timestamp} · {age}s fa"
            turns = str(len(self.snapshot["history"]))
        else:
            freshness = "in attesa del primo snapshot"
            turns = "0"
        persona = "definita" if config.get("persona_info") == "yes" else "non definita"
        return FormattedText(
            [
                ("class:metadata.label", " STATO       "),
                ("class:status.running" if status == "ATTIVO" else "class:status.stopped", status + "\n"),
                ("class:metadata.label", " MODELLO     "),
                ("class:metadata.value", config.get("model_id") or config.get("llm", "—")),
                ("", "\n"),
                ("class:metadata.label", " POLICY      "),
                ("class:metadata.value", config.get("policy_type", "—")),
                ("", "\n"),
                ("class:metadata.label", " PERSONA     "),
                ("class:metadata.value", persona),
                ("", "\n"),
                ("class:metadata.label", " HISTORY     "),
                ("class:metadata.value", turns + " messaggi"),
                ("", "\n"),
                ("class:metadata.label", " AGGIORNATO  "),
                ("class:metadata.value", freshness),
            ]
        )

    @staticmethod
    def _footer_text():
        return FormattedText(
            [
                ("", "  "), ("class:footer.key", " ↑↓ "), ("", " agente  "),
                ("class:footer.key", " Tab "), ("", " pannello  "),
                ("class:footer.key", " r "), ("", " aggiorna  "),
                ("class:footer.key", " q / Esc "), ("", " chiudi"),
            ]
        )

    def refresh(self):
        self.running = running_session_names()
        self.snapshot = load_snapshot(self.selected)
        _set_text(self.history, render_history(self.snapshot))
        if self.snapshot:
            last_input = _visible_events(self.snapshot.get("last_input"))
            last_output = _visible_events(self.snapshot.get("last_output"))
        else:
            last_input = last_output = ""
        _set_text(self.last_input, last_input or "Nessun input registrato.")
        _set_text(self.last_output, last_output or "Nessun output registrato.")

    def container(self):
        sidebar = Frame(
            self.agent_list,
            title=" AGENTI ",
            width=Dimension(min=25, preferred=36, max=52),
            style="class:panel",
        )
        conversation = Frame(
            self.history,
            title=" CONVERSATION.HISTORY ",
            style="class:panel",
        )
        inspector = HSplit(
            [
                Frame(self.metadata, title=" AGENTE ", style="class:panel"),
                Frame(self.last_input, title=" ULTIMO INPUT ", style="class:panel"),
                Frame(self.last_output, title=" ULTIMO OUTPUT ", style="class:panel"),
            ],
            width=Dimension(min=30, preferred=46),
        )
        return HSplit(
            [
                self.header,
                VSplit([sidebar, conversation, inspector], padding=1),
                self.footer,
            ],
            style="class:root",
        )


def show_dashboard(configs, setup_file):
    if not configs:
        return
    monitor = ConversationMonitor(configs, setup_file)
    bindings = KeyBindings()

    @bindings.add("q", eager=True)
    @bindings.add("escape", eager=True)
    def close(event):
        event.app.exit()

    @bindings.add("r", eager=True)
    def refresh(event):
        monitor.refresh()
        event.app.invalidate()

    @bindings.add("tab")
    def focus_next(event):
        event.app.layout.focus_next()

    @bindings.add("s-tab")
    def focus_previous(event):
        event.app.layout.focus_previous()

    @bindings.add("up", filter=has_focus(monitor.agent_list), eager=True)
    def previous_agent(event):
        monitor.agent_list._selected_index = max(
            0, monitor.agent_list._selected_index - 1
        )
        monitor.agent_list._handle_enter()
        monitor.refresh()
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(monitor.agent_list), eager=True)
    def next_agent(event):
        monitor.agent_list._selected_index = min(
            len(monitor.configs) - 1, monitor.agent_list._selected_index + 1
        )
        monitor.agent_list._handle_enter()
        monitor.refresh()
        event.app.invalidate()

    app = Application(
        layout=Layout(monitor.container(), focused_element=monitor.agent_list),
        key_bindings=bindings,
        style=MONITOR_STYLE,
        full_screen=True,
        mouse_support=True,
        enable_page_navigation_bindings=True,
        refresh_interval=1.0,
    )

    def refresh_before_render(_application):
        monitor.refresh()

    # ``pre_run_call`` was added to Application.run in newer prompt_toolkit
    # releases. The render event works across the versions used on our hosts;
    # refresh_interval above guarantees a new render every second.
    app.before_render += refresh_before_render
    monitor.refresh()
    app.run()
