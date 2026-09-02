# Turing Hotel Italy — CSV configuration

## Files

- christian_compt_setup.csv contains one row for each configured agent in this scope.
- christian_compt_setup_50_humans.csv contains 30 agents for approximately 50 active humans.
- christian_compt_setup_100_humans.csv contains 60 agents for approximately 100 active humans.
- SETUP_DESIGN.md records the scaling rule, factorial balance, model choices, and operational requirements.
- turing_personas.csv contains the reusable balanced persona pool for this scope.
- human_behaviour.md contains the shared human-like conversational behaviour used by every processor.
- prompts.py combines the shared behaviour with the optional persona at launch time.
- agent_runner.py is the tracked subprocess entry point used by the terminal launcher.
- policies/fixed_delay.py implements the `Static` timing condition.
- policies/read_and_type.py implements the `Conversation dependent` timing condition.

## Timing policies

Both timing policies act on `process`, before the processor reads the latest history and prepares its reply, and use the same 2–30 second support. This prevents a delayed, already-generated reply from ignoring messages received during the wait. `Static` samples uniformly with `FixedDelay(seconds=2.0, jitter=28.0)`, independently for every message. `Conversation dependent` uses `ReadAndType(read_cps=25.0, type_cps=6.0, think=2.0, min_delay=2.0, max_delay=30.0)`. The complete values are recorded in the setup CSV. These values are a pilot baseline: freeze and preregister them before the main data collection, and do not tune them after inspecting competition outcomes. Silence or turn selection is outside these two timing policies.
- In the original 12-agent setup, agents 1 (eliza), 2 (regolo), 15 (gold), and 16 (gold) are intentionally excluded.

## setup.csv fields

- id: numeric agent identifier from the configuration table.
- agent_name: unique Matrix-film character name assigned to the agent.
- competition_agnostic: whether the agent is marked as competition agnostic.
- llm: model used by the agent, or no for rule-based agents.
- featherless_model_key: identifier of the Featherless model or configuration to use; NA means that Featherless is not used. This is not an API secret.
- model_capacity: model capacity, or NA when it does not apply.
- model_id: exact provider model identifier passed to the processor when present.
- parameter_count: documented model size; closed models use Undisclosed.
- concurrency_cost: Featherless concurrency units required by one agent.
- model_details: model openness and implementation details.
- policy_type: Static or Conversation dependent.
- policy_details: additional policy information; empty means not specified.
- persona_info: yes or no, following the source configuration.
- persona_id: single foreign key identifying the persona assigned to the agent; it is empty for no-persona agents.
- prompt_variant: persona, no_persona, or NA when no prompt is used.
- design_cell: compact model × policy × persona condition identifier.
- replicate_id: replicate number within the design cell.
- design_seed: deterministic seed used to randomize launch order.

## personas.csv fields

- persona_id: stable identifier, from P1 to P6.
- nome, età, genere, città_paese, professione_studi, interessi, situazione_familiare, esperienze_personali, abitudini, altre_informazioni: persona attributes used to represent a coherent person.

## Special values

- NA means not applicable, for example because a rule-based agent does not use an LLM prompt.
- An empty field means that the configuration does not specify a value.
- Not defined is an internal technical marker used in the no-persona prompt. It is not a name, an identity, or a valid response. Agents must never output, repeat, translate, or disclose it.

## Linking the files

Use setup.csv as the main configuration. For rows with persona_info equal to yes, use persona_id as the single foreign key to retrieve the matching row in personas.csv. For rows with persona_info equal to no, persona_id is empty.

At runtime, prompts.py prepends human_behaviour.md for every model and appends the selected persona when present. The `no_persona` rows remain a separate experimental condition: every personal field is passed as `Not defined`, exactly as in the original setup, and the model is instructed not to expose that marker or invent a fixed biography.

## Balance of the persona dataset

The pool contains three women and three men, two personas in each age band (20s, 30s, and 40s), and two personas from each of the North, Centre, and South of Italy. The assignments are distributed across the model and policy groups so that persona attributes are not intentionally tied to one model or policy.

## CSV format

All files are UTF-8 CSVs using comma as the delimiter. Fields containing commas or line breaks are quoted. Use a standard CSV parser instead of splitting lines or commas manually.

The registered UNaIVERSE `node_name` is always `Agent Name (model_id)`, for example `Neo (google/gemma-4-31B-it)`. This convention is shared by the terminal launcher and the optional local TUI.

## Selecting a setup

The terminal launcher accepts the setup explicitly:

```bash
python run.py featherless_keys.txt UNAIVERSE_KEY --setup christian_compt_setup_50_humans.csv
python run.py featherless_keys.txt UNAIVERSE_KEY --setup christian_compt_setup_100_humans.csv
```
