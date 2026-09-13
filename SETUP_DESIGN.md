# Calibration setup design

## Scaling and model allocation

On 2026-09-09, Haiku, Sonnet and Fable were added alongside the existing Opus agents in every setup. Each new Claude group copies the existing Opus group's persona and timing-policy assignments. Existing rows, IDs and Featherless key allocations are preserved. This expansion changes the previous 0.6 agents/human exposure density:

| Human target | Agents | Agents per Claude variant | Agent/human ratio |
|---:|---:|---:|---:|
| 20 | 24 | 4 | 1.20 |
| 50 | 48 | 6 | 0.96 |
| 100 | 96 | 12 | 0.96 |

The default setup retains Gemma 4 31B and Qwen3.5 2B as its open-model conditions. The two larger setups contain all four open-model conditions. The 48-agent set remains nested in the 96-agent set by agent name and experimental assignment.

Original names are character labels from the Matrix films and The Animatrix. New Claude agents use the corresponding Opus agent name with a Haiku, Sonnet or Fable suffix. Names do not define private personas. New IDs add 1000, 2000 or 3000 to the corresponding Opus ID; existing IDs stay stable.

## Model matrix

Open models form the family-by-capacity comparison. Closed models are separate reference conditions, without parameter-count matching.

| Code | Family | Capacity tier | Runtime model | Parameters | Featherless concurrency cost |
|---|---|---|---|---|---:|
| QS | Qwen 3.5 | Small | `Qwen/Qwen3.5-2B` | 2B | 1 |
| GS | Gemma 4 | Small | `google/gemma-4-E2B-it` | 2.3B effective | 1 |
| QL | Qwen 3.5 | Large | `Qwen/Qwen3.5-27B` | 27B | 2 |
| GL | Gemma 4 | Large | `google/gemma-4-31B-it` | 30.7B | 2 |
| C | Claude Opus | Closed reference | `opus` | Undisclosed | N/A |
| CH | Claude Haiku | Closed reference | `haiku` | Undisclosed | N/A |
| CS | Claude Sonnet | Closed reference | `sonnet` | Undisclosed | N/A |
| CF | Claude Fable | Closed reference | `claude-fable-5-1` | Undisclosed | N/A |

Claude CSV labels and model IDs are `Claude Opus`, `Claude Haiku`, `Claude Sonnet`, and `Claude Fable`; the runtime selector map in utils.py translates them to the CLI values above. Haiku, Sonnet and Opus use existing Claude Code aliases, whose resolved versions can change. Fable is explicitly selected as 5.1, following [Anthropic's CLI documentation](https://support.claude.com/en/articles/11940350-claude-code-model-configuration). Account access has not been validated by these offline checks. Record resolved model versions for each deployment.

On 2026-09-09, Qwen3-32B was replaced by Qwen3.5-27B to match the small model's generation. Capacity tiers are categorical: parameter accounting and architectures differ between families.

## Factor balance and reproducibility

Every model is crossed with Static / Conversation dependent timing and persona / no_persona prompts. The default setup has one replicate per cell. The 96-agent setup has three replicates per cell for each of its eight models. The 48-agent setup has six rows per model: three per timing policy and three per persona condition, with one or two replicates per crossed cell. The three new Claude groups reproduce the Opus cell allocation exactly.

Persona values and literal Not defined markers are preserved. The original persona pool remains unchanged; adding Claude groups changes its aggregate frequencies. Open-model key allocations are unchanged: the 48-agent setup uses 8 agents on agent_standard and 4 on each chat1–chat4; the 96-agent setup doubles these counts. Claude rows use NA and require no Featherless key.

Original row order and seeds (20260950 and 20261000) are retained. Added Claude rows follow their corresponding Opus row in Haiku, Sonnet, Fable order; the expanded order is deterministic but has not been reshuffled. New design cells use CH, CS or CF prefixes and preserve the source replicate ID. Future comparisons must account for the changed exposure density and launch ordering.

The system prompt, sampling settings, timing-policy parameters, and conversation
retention algorithm are held constant across setups. Retention uses two bounds:
at most 15 messages for every model (changed on 2026-09-09), and the runtime
model context window. The count includes received messages and the agent's own
replies: the first event is retained plus up to 14 recent events. When either
bound is exceeded, the oldest event in the remaining tail is removed first.
The 15-message limit is an experimental recency window, not a validated model
of human memory. System instructions and the private persona remain outside
this message count. Existing running processes need a restart to use this limit.

Qwen and Gemma run with provider thinking disabled. In realtime hotel chats,
thinking could consume the entire output allowance without producing visible
content. All four Claude variants retain the native behavior of the closed Claude Code
runtime and are therefore treated only as closed-model references, not as a
compute-matched condition in the open-weight family-by-capacity comparisons.

Context budgeting uses a common 32,768-token ceiling for every model condition.
This is the maximum currently exposed by Featherless for all Qwen and Gemma
configurations and is deliberately also imposed on all Claude variants, so additional
context capacity cannot become a model-family confound. Every condition reserves
the same 512 tokens for message templates and 8,192 tokens for the next output.
Since downloading model tokenizers at runtime would add a model-specific network
dependency, input length is conservatively estimated by UTF-8 byte count. The
same deterministic estimator is used in every experimental cell. Longer native
windows and Qwen's optional YaRN extension are intentionally not used.

Model availability and provider behavior should be recorded again on each
deployment date.

As of 2026-09-07, all processors use the shared turn builder in `prompts.py` by default
to frame their input with explicit
transcript boundaries, identifies `Tu (questo agente):` as previously sent replies, places the
internal clock before the transcript, and ends with a short next-message
instruction. This applies to Qwen, Gemma, and all Claude processors. The history
retention rules, sampling settings, and output allowance are unchanged; the added
instructions are included in context budgeting. This is a shared prompt
format change and must be recorded when comparing runs before and after it.
Offline tests verify input construction, not an improvement in generated replies.
The frame contains no world-specific sender names, room rules, or identity parsing.

The shared behavioural prompt also clarifies world agnosticism for every model:
agents start without assumptions about the environment or purpose of the encounter,
then learn from received context. Explicit announcements are not denied, but do not
become instructions to narrate the agent's response construction. This shared prompt
revision must also be recorded when comparing runs before and after it.
World managers are described only as a contextual role in this shared prompt,
without a fixed sender label or assumptions about a particular world's protocol.

On 2026-09-08, the experimental focused-context path was removed. All models
use the shared conversational framing without model-specific routing,
classification, selected context, or corrective generation. This preserves the
intended world-agnostic behavior: knowledge of the setting comes from received
messages. Model-specific API configuration and output transport handling remain.

## Operational requirements

The optional `--qwen-2b-behaviour compact` launcher setting selects the compressed
general conversational instructions for Qwen 2B only. It defaults to `full`.
Persona fields and their literal `Not defined` markers are preserved; retention,
sampling and the shared turn frame are unchanged. The choice is a prompt
condition and must be recorded when comparing runs. A 24-generation isolated
comparison did not establish a reliable quality improvement.

Launching every open-weight agent simultaneously requires 36 Featherless concurrency units in the 30-agent setup and 72 in the 60-agent setup, distributed across the supplied keys. The UNaIVERSE account must also permit the corresponding number of stable node names. The two setup files are intended for separate deployments, not simultaneous launch.

On 2026-09-08, conversation rendering was aligned with the competition starter
kit commit `11387e9`: local replies use `Tu (questo agente)` and unnamed events
keep their original text without a `?:` prefix. The shared transcript guide was
updated accordingly. Local context budgets and snapshot monitoring are retained.
