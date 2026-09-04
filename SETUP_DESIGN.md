# Calibration setup design

## Scaling rule

The original calibration uses 12 agents for approximately 20 active humans, or 0.6 agents per human. The two larger setups preserve that exposure density:

| Human target | Agents | Agent/human ratio | Agent share of all participants |
|---:|---:|---:|---:|
| 20 | 12 | 0.60 | 37.5% |
| 50 | 30 | 0.60 | 37.5% |
| 100 | 60 | 0.60 | 37.5% |

Preserving density makes scale the principal planned difference between deployments. The 30-agent set is nested inside the 60-agent set: the larger setup retains the same agent names and experimental assignments, then adds another 30 agents.

Agent names are unique character names drawn from the four Matrix feature films and, for the 60-agent setup, the Matrix anthology film *The Animatrix*. Names are labels only: they do not define a persona or alter the prompt condition.

Featherless credentials are referenced by aliases rather than embedded secrets. The original setup mapping is preserved as `chatA_1 → chat1`, `chatB_2 → chat2`, and `chatC_2 → chat3`. The 30-agent setup assigns 8 open-model agents to `agent_standard` and 4 to each `chat1`–`chat4`, matching one complete 24-agent credential allocation. The 60-agent setup doubles those counts while preserving the assignments of the nested 30-agent setup.

## Model matrix

The open-weight conditions form a family-by-capacity design. Claude Opus is retained as a separate closed-model reference and is not included in parameter-count comparisons.

| Code | Family | Capacity tier | Runtime model | Parameters | Featherless concurrency cost |
|---|---|---|---|---:|---:|
| QS | Qwen 3.5 | Small | `Qwen/Qwen3.5-2B` | 2B | 1 |
| GS | Gemma 4 | Small | `google/gemma-4-E2B-it` | 2.3B effective | 1 |
| QL | Qwen 3 | Large | `Qwen/Qwen3-32B` | 32.8B | 2 |
| GL | Gemma 4 | Large | `google/gemma-4-31B-it` | 30.7B | 2 |
| C | Claude | Closed reference | Claude Opus | Undisclosed | N/A |

The large models are closely matched in parameter count and operational cost. The small models are also in the same approximate capacity class: Qwen declares 2B parameters, while Gemma reports 2.3B effective parameters. Their architectures and parameter-accounting methods still differ, so analyses must treat `capacity_tier` as a planned categorical factor rather than a precise continuous parameter match.

Provider records used for the frozen model metadata: [Qwen3.5-2B](https://featherless.ai/models/Qwen/Qwen3.5-2B), [Qwen3-32B](https://featherless.ai/models/Qwen/Qwen3-32B), [Gemma4-E2B-it](https://featherless.ai/models/google/gemma-4-E2B-it), and [Gemma4-31B-it](https://featherless.ai/models/google/gemma-4-31B-it).

## Factor balance

Every model configuration is crossed with:

- `Static` and `Conversation dependent` timing policies;
- `persona` and `no_persona` prompt variants.

The 60-agent setup has 12 agents per model configuration and exactly three replicates in every model × policy × persona cell.

The 30-agent setup has six agents per model configuration. Each configuration has exactly three agents per policy and three per prompt variant. Because six is not divisible by the four policy × prompt cells, two cells have two replicates and two cells have one; the duplicated diagonal is alternated across model configurations. This preserves all principal-factor margins while keeping the original 0.6 agent/human ratio. Cell-level interaction estimates from this setup should use the recorded design matrix rather than assume equal cell counts.

The persona pool is reused as a controlled nuisance factor. In the 60-agent setup every persona occurs five times. In the 30-agent setup the six profiles occur either two or three times. `Not defined` remains an intentional experimental condition, not missing configuration data.

## Reproducibility

Each row records the runtime model ID, capacity tier, parameter count, concurrency cost, design cell, within-cell replicate, and deterministic launch-order seed. Row order is shuffled to avoid launching complete model groups in sequence:

- 50-human setup seed: `20260950`;
- 100-human setup seed: `20261000`.

The system prompt, sampling settings, timing-policy parameters, and conversation
retention algorithm are held constant across setups. Retention uses two bounds:
at most 100 messages and the runtime model context window. The first received
event is always retained; when either bound is exceeded, the oldest event in
the remaining tail is removed first.

Qwen and Gemma run with provider thinking disabled. In realtime hotel chats,
thinking could consume the entire output allowance without producing visible
content. Claude Opus retains the native behavior of the closed Claude Code
runtime and is therefore treated only as a closed-model reference, not as a
compute-matched condition in the open-weight family-by-capacity comparisons.

Context budgeting uses a common 32,768-token ceiling for every model condition.
This is the maximum currently exposed by Featherless for all Qwen and Gemma
configurations and is deliberately also imposed on Claude Opus, so additional
context capacity cannot become a model-family confound. Every condition reserves
the same 512 tokens for message templates and 8,192 tokens for the next output.
Since downloading model tokenizers at runtime would add a model-specific network
dependency, input length is conservatively estimated by UTF-8 byte count. The
same deterministic estimator is used in every experimental cell. Longer native
windows and Qwen's optional YaRN extension are intentionally not used.

Model availability and provider behavior should be recorded again on each
deployment date.

## Operational requirements

Launching every open-weight agent simultaneously requires 36 Featherless concurrency units in the 30-agent setup and 72 in the 60-agent setup, distributed across the supplied keys. The UNaIVERSE account must also permit the corresponding number of stable node names. The two setup files are intended for separate deployments, not simultaneous launch.
