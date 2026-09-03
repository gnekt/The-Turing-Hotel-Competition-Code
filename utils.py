"""
this file is part of the Turing Hotel competition codebase, and contains utility functions and classes for managing conversations and interacting with the Claude language model.
"""

import json
import os
import re
import time
from collections import namedtuple
from pathlib import Path
import subprocess


EVENT_SEPARATOR = "\x1e"
DISPLAY_EVENT_SEPARATOR = "␞"
SPEAKER = r"^\*\*(.+?):\*\*\s?(.*)$"
RESET_PHRASES = (
    "nuova conversazione",
    "cancella contesto",
    "inizia una nuova chat",
    "new conversation",
    "clear context",
    "start a new chat",
)


def reset_on_phrase(event: str) -> bool:
    """Match the small Italian and English reset vocabulary."""
    event = event.casefold()
    return any(phrase in event for phrase in RESET_PHRASES)


DEFAULT_RESET_RULES = (reset_on_phrase,)

EXPERIMENT_CONTEXT_TOKENS = 32_768
EXPERIMENT_RESPONSE_RESERVE_TOKENS = 8_192
MODEL_CONTEXT_TOKENS = {
    # One common ceiling prevents context capacity from becoming an additional
    # model-family confound. It is the largest value supported by every runtime.
    "Qwen/Qwen3-0.6B": EXPERIMENT_CONTEXT_TOKENS,
    "Qwen/Qwen3-32B": EXPERIMENT_CONTEXT_TOKENS,
    "google/gemma-4-E2B-it": EXPERIMENT_CONTEXT_TOKENS,
    "google/gemma-4-31B-it": EXPERIMENT_CONTEXT_TOKENS,
    "Claude Opus": EXPERIMENT_CONTEXT_TOKENS,
}
CONTEXT_TEMPLATE_RESERVE_TOKENS = 512


def model_context_tokens(model: str) -> int:
    try:
        return MODEL_CONTEXT_TOKENS[model]
    except KeyError as error:
        raise ValueError(f"Unknown context window for model: {model}") from error

# speaker: sender name, or "" for an event with no name
# text:    event body with surrounding whitespace removed
# mine:    True when remember() stored the reply
Message = namedtuple("Message", "speaker text mine")


class Conversation:
    """Keep the first received event and rotate every later event in `keep - 1` slots.

    This retention policy is the starter kit's choice. It is not prescribed by
    the world, and competitors are free to implement conversation state in a
    different way, including by exploiting the demo inputs under ``prompts/``.
    Only the very first event is privileged: later manager messages, reset
    messages, participant messages, and local replies all share the same
    rotating tail.

    Args:
        keep: Total number of messages to retain, or 0 for no limit. The first
            message is fixed; later messages rotate through the other slots.
        speaker_pattern: Pattern with speaker and text groups, applied to each
            event. Unmatched events keep their full text with an empty speaker.
            Supply another pattern for worlds with a different format.
        me: Label used for local replies in the transcript.
        reset_rules: Callables that receive one raw event and return True when
            the rotating tail should be cleared. By default, common Italian and
            English requests to start a new conversation or clear context match.
        context_window_tokens: Maximum combined model context. Zero disables
            context-aware rotation.
        response_reserve_tokens: Context reserved for the next generation.
        system_prompt: Fixed prompt counted against the context budget.
        snapshot_file: Optional local JSON path used by read-only monitors. When
            omitted, ``COMPETITION_STATE_FILE`` is used if the launcher set it.

    A reset rule can be a simple heuristic, a regular-expression wrapper or a
    neural classifier. Conversation does not know which world produced the
    event. ``last_input`` and ``last_output`` expose the most recent completed
    processor turn to policies or other cooperating components.
    """

    def __init__(self, keep: int = 80, speaker_pattern: str = SPEAKER, me: str = "Io",
                 reset_rules=DEFAULT_RESET_RULES, snapshot_file=None,
                 context_window_tokens: int = 0, response_reserve_tokens: int = 0,
                 system_prompt: str = ""):
        self.keep = keep
        self.pattern = re.compile(speaker_pattern, re.S)
        self.me = me
        self.reset_rules = tuple(reset_rules)
        self.history: list[Message] = []
        self.last_input = ""
        self.last_output = ""
        self.context_window_tokens = context_window_tokens
        self.response_reserve_tokens = response_reserve_tokens
        self.system_prompt = system_prompt
        configured_snapshot = snapshot_file or os.environ.get("COMPETITION_STATE_FILE")
        self.snapshot_file = Path(configured_snapshot) if configured_snapshot else None
        self._publish_snapshot()

    def reset(self) -> None:
        """Clear the rotating slots while preserving the first message."""
        self._clear_tail()
        self._publish_snapshot()

    def _clear_tail(self) -> None:
        self.history[:] = self.history[:1]
        self.last_input = ""
        self.last_output = ""

    def add(self, sample: str) -> list[Message]:
        """Store one processor input and return its delivered events.

        Only ``EVENT_SEPARATOR`` divides events, so internal newlines remain in
        the text. Routing tags have already been removed by the guest role. If
        the speaker pattern does not match, the whole event is stored with an
        empty speaker. Empty messages are omitted from the history.
        """
        new = []
        for event in sample.split(EVENT_SEPARATOR):
            event = event.strip()
            if not event:
                continue

            # Clear the rotating tail first; the trigger is stored below.
            if any(rule(event) for rule in self.reset_rules):
                self._clear_tail()

            match = self.pattern.match(event)
            if match:
                speaker, text = match.group(1).strip(), match.group(2).strip()
            else:
                speaker, text = "", event   # Preserve the full unmatched event.
            message = Message(speaker=speaker, text=text, mine=False)
            new.append(message)
            self._store(message)
        self.last_input = sample
        self._publish_snapshot()
        return new

    def remember(self, text: str) -> None:
        """Store a local reply that the world will not echo through add()."""
        self.last_output = text.strip()
        self._store(Message(speaker="", text=self.last_output, mine=True))
        self._publish_snapshot()

    def discard_last_output(self) -> None:
        """Forget the latest local reply when a policy decides not to send it."""
        if self.history and self.history[-1].mine:
            self.history.pop()
        self.last_output = ""
        self._publish_snapshot()

    def _publish_snapshot(self) -> None:
        """Atomically expose this conversation to local monitoring tools."""
        if self.snapshot_file is None:
            return
        snapshot = {
            "updated_at": time.time(),
            "history": [message._asdict() for message in self.history],
            "last_input": self.last_input,
            "last_output": self.last_output,
        }
        temporary = self.snapshot_file.with_suffix(self.snapshot_file.suffix + ".tmp")
        try:
            self.snapshot_file.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            os.replace(temporary, self.snapshot_file)
        except OSError:
            # Observability must never interrupt the processor.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _store(self, message: Message) -> None:
        if not message.text:
            return

        # The first stored message is the fixed context anchor.
        if not self.history:
            self.history.append(message)
            return

        # With one slot, only the fixed first message fits.
        if self.keep == 1:
            return

        # Every later event rotates equally, regardless of its source or type.
        if self.keep and len(self.history) >= self.keep:
            self.history.pop(1)
        self.history.append(message)
        self._fit_context_window()

    def _fit_context_window(self) -> None:
        """Rotate the old tail until the next request fits conservatively.

        UTF-8 byte length is used as a tokenizer-independent upper-bound
        estimate. The first event and newest event are never split or altered.
        """
        if not self.context_window_tokens:
            return
        input_budget = (
            self.context_window_tokens
            - self.response_reserve_tokens
            - CONTEXT_TEMPLATE_RESERVE_TOKENS
        )
        if input_budget <= 0:
            raise ValueError("Model context leaves no room for processor input")
        while len(self.history) > 2 and self._estimated_input_tokens() > input_budget:
            self.history.pop(1)

    def _estimated_input_tokens(self) -> int:
        prompt = self.system_prompt
        transcript = self.transcript()
        if prompt and transcript:
            prompt += "\n"
        return len((prompt + transcript).encode("utf-8"))

    def last_message(self, mine: bool = False) -> Message | None:
        """Return the latest remote message, or a local one when mine=True."""
        for message in reversed(self.history):
            if message.mine == mine:
                return message
        return None

    def transcript(self, limit: int | None = None) -> str:
        """Render up to `limit` recent messages as `Speaker: text` entries.

        Local replies use `me`, and events without a sender use `?`. A limit
        of ``None`` or 0 includes the entire history. A positive limit still
        includes the fixed first message.
        """
        if not limit or len(self.history) <= limit:
            messages = self.history
        elif limit == 1:
            messages = self.history[:1]
        else:
            messages = self.history[:1] + self.history[-(limit - 1):]
        return "\n".join(f"{self.me if m.mine else (m.speaker or '?')}: {m.text}"
                         for m in messages)

    def as_messages(self, system: str = "", nudge: str = "") -> list[dict]:
        """Render the transcript as one neutral user message.

        ``mine`` selects only the local speaker label. It does not imply an API
        ``assistant`` role. Competitors who want role-based turns can implement
        that mapping in their own conversation manager.
        """
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})

        content = self.transcript()
        if nudge:
            content = f"{content}\n{nudge}" if content else nudge
        out.append({"role": "user", "content": content})
        return out



def call_claude_prompt(input: str, model: str = "sonnet", effort: str = "medium", timeout: int = 300) -> str:
    
    cmd = [
        "claude",
        "-p",                   
        "--output-format", "json",    
        "--model", model,
        "--max-turns", "1",            
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=input,             
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as e:
        raise RuntimeError(f"claude execution failed: {str(e)}") from e

    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {proc.stderr.strip()}")

    payload = json.loads(proc.stdout)

    if payload.get("is_error"):
        raise RuntimeError(f"errore dal run: {payload.get('result')}")

    return (payload.get("result") or "").strip()
