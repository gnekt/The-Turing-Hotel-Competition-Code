import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).parent
HUMAN_BEHAVIOUR_FILE = ROOT / "human_behaviour.md"
PERSONAS_FILE = ROOT / "turing_personas.csv"
ITALY_TIMEZONE = ZoneInfo("Europe/Rome")
ITALIAN_WEEKDAYS = (
    "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"
)
ITALIAN_MONTHS = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)

PERSONA_FIELDS = (
    ("nome", "Nome"),
    ("età", "Età"),
    ("genere", "Genere"),
    ("città_paese", "Città o paese"),
    ("professione_studi", "Professione o percorso di studi"),
    ("interessi", "Interessi"),
    ("situazione_familiare", "Situazione familiare"),
    ("esperienze_personali", "Esperienze personali"),
    ("abitudini", "Abitudini"),
    ("altre_informazioni", "Altre informazioni personali"),
)


@lru_cache(maxsize=1)
def _human_behaviour():
    return HUMAN_BEHAVIOUR_FILE.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _personas():
    with PERSONAS_FILE.open(newline="", encoding="utf-8") as file:
        return {row["persona_id"]: row for row in csv.DictReader(file)}


def current_italian_context(now=None):
    """Build fresh calendar context for one model generation."""
    current = now.astimezone(ITALY_TIMEZONE) if now else datetime.now(ITALY_TIMEZONE)
    weekday = ITALIAN_WEEKDAYS[current.weekday()]
    month = ITALIAN_MONTHS[current.month - 1]
    timezone_name = current.tzname() or "ora italiana"
    return (
        "## Contesto temporale interno aggiornato\n"
        f"In Italia è {weekday} {current.day} {month} {current.year}, "
        f"ore {current:%H:%M:%S} ({timezone_name}).\n"
        "Usa questa informazione soltanto quando è pertinente. Non annunciarla "
        "automaticamente e non trattarla come un messaggio degli interlocutori."
    )


def build_system_prompt(config):
    """Combine the shared human behaviour with the agent's optional persona."""
    persona_id = config.get("persona_id", "").strip()
    if not persona_id:
        details = "\n".join(f"- {label}: Not defined" for _, label in PERSONA_FIELDS)
        return f"{_human_behaviour()}\n\n## Profilo privato — non divulgare\n\n{details}"

    try:
        persona = _personas()[persona_id]
    except KeyError as error:
        raise ValueError(f"Unknown persona_id: {persona_id}") from error

    details = "\n".join(f"- {label}: {persona[field]}" for field, label in PERSONA_FIELDS)
    return f"{_human_behaviour()}\n\n## Profilo privato — non divulgare\n\n{details}"


TRANSCRIPT_GUIDE = (
    "Segue lo storico in ordine cronologico. Le righe 'Io:' sono messaggi "
    "che hai già inviato, non testo da completare o ripetere. "
    "Ricava dal contenuto chi parla, a chi si rivolge e quali informazioni "
    "descrivono il contesto, senza presumere ruoli dal solo nome del mittente.\n"
)
REPLY_GUIDE = (
    "Scrivi adesso soltanto il tuo prossimo messaggio nella conversazione, "
    "senza prefissi. Reagisci all'ultimo scambio tenendo conto dello storico. "
    "Di norma bastano una o due frasi; a un saluto basta un saluto. "
    "Non riassumere il contesto se non serve e non spiegare come decidi "
    "cosa dire. Non inventare azioni o intenzioni degli altri. "
    "Non discutere quale ruolo devi interpretare e non chiedere agli "
    "interlocutori istruzioni su come conversare."
)


def build_turn_prompt(transcript: str) -> str:
    """Frame one conversation turn consistently for every model."""
    return (
        f"{current_italian_context()}\n\n"
        f"{TRANSCRIPT_GUIDE}\n"
        f"## Inizio storico\n{transcript}\n## Fine storico\n\n"
        f"{REPLY_GUIDE}"
    )


def budgeted_system_prompt(system_prompt: str) -> str:
    """Include fixed turn guides in the conversation context estimate.

    The existing template reserve covers clock context and section delimiters.
    This value is for budgeting only, not an additional provider system prompt.
    """
    return system_prompt + TRANSCRIPT_GUIDE + REPLY_GUIDE
