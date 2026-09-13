# Turing Hotel Italy — CSV configuration

## Files

- christian_compt_setup.csv contains one row for each configured agent in this scope.
- christian_compt_setup_50_humans.csv contains 60 agents; `50` remains its historical preset alias.
- christian_compt_setup_100_humans.csv contains 120 agents; `100` remains its historical preset alias.
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
- featherless_model_key: alias of the credential in the Featherless keys file; NA means that Featherless is not used. This is not an API secret.
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

The Featherless keys file has no header and contains one credential per row in `alias,key,capacity` format. The alias is referenced by `featherless_model_key`; the secret is never stored in a setup CSV. Capacity must be a positive integer. The configured aliases are `agent_standard`, `chat1`, `chat2`, `chat3`, and `chat4`.

The registered UNaIVERSE `node_name` is always `Agent Name (model_id)`, without the provider prefix: for example `Neo (gemma-4-31B-it)` instead of `Neo (google/gemma-4-31B-it)`. The complete model ID is still passed to the processor. This convention is shared by the terminal launcher and the optional local TUI.

## Selecting a setup

Place `account_key` and `FEATHERLESS_API_KEYS` in the project directory, then run:

```bash
python run.py
# Equivalent shorthand:
python run
```

This launches the default 24-agent setup (`20`), discovers the credentials,
uses the project's `.venv` automatically when present, and writes logs under
`logs/`. Existing agent sessions are reused. Launches are spaced 16 seconds apart.
The runtime dependencies (including UNaIVERSE) and GNU `screen` must already be
installed; the launcher does not install system packages.
The Featherless file may also be named `featherless_keys`, `featherles_keys`, or
`featherless_keys.txt` (searched in that order after `FEATHERLESS_API_KEYS`).
`account_ket` is accepted as a fallback for `account_key`.
Paths are resolved relative to the project directory for automatic discovery.
To select a larger setup without supplying credentials again, use
`python run.py --setup 50` or `python run.py --setup 100`.

Choose which providers to launch with `--provider`:

```bash
python run --provider claude
python run --provider codex
python run --provider featherless
python run --provider all
python run --setup 50 --provider featherless
```

The default is `all`. Selecting `claude` or `codex` requires only the UNaIVERSE account key plus the corresponding authenticated CLI;
the Featherless keys file is loaded only when selected agents use it. The filter
applies to launches and does not stop any agents already running.

All models receive the shared conversational instructions and their retained
transcript. There is no Qwen-specific message routing, request classification,
context selection, or corrective generation. Agents learn the situation from
received messages; the processor has no Turing Hotel rules or sender-role mapping.

The terminal launcher accepts the setup explicitly:

```bash
python run.py featherless_keys.txt UNAIVERSE_KEY --setup christian_compt_setup_50_humans.csv
python run.py featherless_keys.txt UNAIVERSE_KEY --setup christian_compt_setup_100_humans.csv
```

The same setups can be selected with the shorter aliases `20`, `50`, and `100`:

```bash
python run.py featherless_keys.txt --setup 50
python run.py featherless_keys.txt --setup 100
```

The local TUI asks for the UNaIVERSE account key only the first time and stores it in the Git-ignored `account_key` file in this repository directory, with owner-only permissions. Afterwards both the TUI and `run.py` reuse it, so the terminal key argument becomes optional:

```bash
python run.py featherless_keys.txt --setup christian_compt_setup_50_humans.csv
```

The TUI also includes a live operations register. Its header summarizes active,
waiting, generating, and failed agents. Each agent row shows its runtime phase
and retained-message count; the inspector exposes turn duration, policy wait,
Conversation counters, resets, evictions, the conservative context estimate,
model, policy, persona, and design cell. The retained `Conversation.history`
remains the main panel, with the latest processor input and completed output
beside it. Use Up/Down to choose an agent, Tab to move between panels, Page Up
and Page Down to scroll, and `q` to return to the launcher. Snapshots are
written atomically under the Git-ignored `logs/state/` directory and are never
used as processor input. Runtime errors are redacted before being exposed; API
and account credentials are never included in snapshots.

To stop all competition agents, across every setup and provider:

```bash
python close_all.py
```

This closes the current user's attached and detached `competition_agent_<id>`
screen sessions. It needs neither credentials nor Python packages. Other screen
sessions and saved logs are preserved. Use `python close_all.py --dry-run` to
preview the sessions. A failed stop is reported and returns a nonzero exit code.

To stop every `competition_agent_*` screen and relaunch the complete 24-agent setup with all model families:

```bash
./run.sh featherless_keys.txt 20
./run.sh featherless_keys.txt 50
./run.sh featherless_keys.txt 100
```


### Model variants by setup

The base preset (`20`) launches 24 agents: four each for Gemma 4 31B, Qwen 3.5 2B, Claude Opus, Codex Sol, Codex Terra and Codex Luna. Each model covers both timing policies with and without a persona. Codex agents use IDs 101–112 and copy the existing Opus persona assignments (P5/P6). The `50` and `100` presets now contain 60 and 120 agents respectively, with 6 and 12 agents for each of the ten model variants, including Codex Sol, Terra and Luna. The aliases and CSV filenames are retained for compatibility; they do not indicate agent counts. Each Codex variant reproduces the corresponding Opus persona, timing-policy and replicate assignments. Fable is excluded from all presets. New rows are appended without changing the remaining identities or their relative launch order, with names suffixed by Sol/Terra/Luna, IDs offset from Opus by 4000/5000/6000, and design-cell prefixes CXS/CXT/CXL. The smaller preset remains nested in the larger by agent name and experimental assignment.

`--provider codex` selects all three Codex variants. They use `gpt-5.6-sol`, `gpt-5.6-terra` and `gpt-5.6-luna`, respectively, from the [official OpenAI model catalog](https://developers.openai.com/api/docs/models). Install the Codex CLI and authenticate with `codex login` using an account with access to these models. Each reply runs a fresh `codex exec` with medium reasoning effort and the shared prompt/transcript; only the final answer file is published. The CLI runs ephemerally in a temporary directory, ignores user configuration, disables shell and web search, and uses a read-only sandbox. The installed CLI must support `--ignore-user-config` and `--ephemeral`. See [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

Codex uses the same local 32768-token context budget, 8192-token response reserve and 80-message retention as the other processors. The reserve controls local input trimming; it does not impose a CLI output-token limit. CLI internal instructions are outside that estimate. Tests exercise configuration, routing and subprocess handling offline; live account/model access has not been tested.

`--provider claude` selects the configured Claude variants: Opus in the base preset, and Haiku, Sonnet and Opus in the larger presets. The Fable processor remains available for custom configurations. Haiku, Sonnet and Opus use the corresponding Claude Code aliases; Fable uses `claude-fable-5-1`. All four share the same 32768-token context budget, 8192-token output reserve, 80-message retention and conversation guides. Claude Code must be authenticated with access to each selected model. Configuration and routing are tested offline; account access is not implied.


All agents retain at most 80 conversation messages: the first received event plus up to 79 recent events, counting their own replies too. The shared context budget can evict older messages before that count is reached. System instructions and private persona fields are separate. This setting takes effect on the next agent launch.


The shared behaviour allows reactions as short as one word, incomplete sentences, direct disagreement and context-appropriate changes in length. It sets no word quota, greeting routine or mandatory politeness. Context continuity, attribution, private-persona constraints and factual grounding remain explicit. The final turn guide is intentionally short rather than repeating a detailed conversational script. Existing agents load revised instructions on restart.


### Sampling preset (2026-09-09)

Qwen uses temperature 0.9 (previously 0.6), top_p 0.95 and top_k 50 (previously 20). Gemma uses temperature 1.1 (previously 1.0), top_p 0.95 and top_k 80 (previously 64). Both now send repetition_penalty 1.05, a mild penalty on tokens already present in the prompt or output. Small and large sizes share the same family preset. This is an experimental diversity setting, not a demonstrated quality improvement; higher randomness can also reduce coherence. This sampling change preserved the then-current 30-message history and disabled thinking. Retention was subsequently increased to 80 messages on 2026-09-12.

The installed Claude Code CLI exposes no sampling temperature/top-p/repetition-penalty flags, so the four Claude variants retain the CLI's sampling behavior. All Claude variants explicitly pass `--effort medium` to the CLI. Changing Claude effort is not a replacement for sampling temperature. See [Featherless sampling parameters](https://featherless.ai/docs/completions) for API semantics. Restart existing agents to apply the new processor defaults.


Historical context check with the then-current 697-word behaviour and the supplied welcome (2026-09-09, before the behaviour additions and 80-message retention): the largest configured profile plus system/turn instructions and welcome uses 7140 units of the runner's conservative UTF-8-byte estimate. The 32768-token window reserves 8192 for output and 512 for framing, leaving an input budget of 24064. This is not an exact tokenizer count. With 29 additional synthetic 500-character ASCII messages, all 30 events fit (estimate 21814); with 1000-character messages, context eviction reduces the retained count below 30. The first event stays pinned. Claude Code's additional internal prompt is outside this local estimate.
