import csv
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).parent
HUMAN_BEHAVIOUR_FILE = ROOT / "human_behaviour.md"
PERSONAS_FILE = ROOT / "turing_personas.csv"

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
