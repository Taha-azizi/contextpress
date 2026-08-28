# contextpress

Deterministic context compression for LLM chat, RAG, and agent pipelines.
Created and maintained by **[Taha Azizi](https://github.com/Taha-azizi)**.

**Write-up:** [Introducing contextpress](https://pub.towardsai.net/introducing-contextpress-the-python-library-that-refactors-your-llm-context-c57965617edb) — Towards AI (Medium)

---

## Project Status

> **Status: Stable for its original use case — maintained at a low cadence.**
>
> - **Built for a specific use case and provided as-is.** I will review bug fixes when time permits, but I am **not actively developing new features**.
> - **PRs are welcome**, but please expect a review cycle of **2–4 weeks**. If you need a feature immediately, **fork the repository** and iterate on your own timeline.
> - **License:** [Apache 2.0](LICENSE) — no warranty, no liability. See §7 (Disclaimer of Warranty) and §8 (Limitation of Liability) of the license for the legal text.
>
> For bug reports, please open a [GitHub issue](https://github.com/Taha-azizi/contextpress/issues) with a minimal reproduction. Feature requests may be closed with a pointer to fork.

---

## Install

```bash
pip install contextpress
```

If you cloned this repository:

```bash
pip install -e .
```

## 30-second quickstart

```python
from contextpress import ContextManager

# Default compression is "medium" (includes recency); see below.
cm = ContextManager(type="chat")
messages = [{"role": "user", "content": "Hello!"}]
compressed = cm.compress(messages, token_budget=2000)
```

No API keys are required for Tier 1. Passing **`token_budget`** turns on the **budget** stage; other stages follow the chosen **compression** preset (`low` / `medium` / `high`).

Pass **`return_stats=True`** to get a `CompressionResult` with `messages` and compression stats (token counts, stages run, turn deltas):

```python
result = cm.compress(messages, token_budget=2000, return_stats=True)
print(result.stats.tokens_saved, result.stats.stages_run)
compressed = result.messages
```

Check token count **before** compressing:

```python
before = cm.estimate_tokens(messages)
```

**Preview without changing messages** (0.4+):

```python
preview = cm.preview(messages, token_budget=500)
print(preview.stats.tokens_saved, preview.stats.warnings_emitted)
assert preview.messages == messages  # unchanged

if cm.fits_budget(messages, 4000):
    ...
```

**Compare presets** (0.5+):

```python
rows = cm.compare_presets(messages, token_budget=500)
for preset, stats in rows.items():
    print(preset, stats.tokens_saved, stats.token_savings_pct)
```

**Recommend a preset** (0.5.3+):

```python
preset = cm.recommend_preset(messages, token_budget=500)
out = cm.compress(messages, token_budget=500, compression=preset)
```

**Batch compress** (0.5.4+):

```python
results = cm.compress_many(list_of_conversations, token_budget=2000, return_stats=True)
```

**Async** (0.5+):

```python
out = await cm.compress_async(messages, token_budget=2000)
```

### Custom stages (0.3+)

Register a `BaseStrategy` and include it in `stages=`:

```python
from contextpress.strategies.base import BaseStrategy

class MyStage(BaseStrategy):
    def process(self, conversation):
        ...

cm.register_stage("my_stage", MyStage)
out = cm.compress(messages, stages=["filler", "my_stage", "budget"], token_budget=500)
```

### Minimal examples

```python
from contextpress import ContextManager

# Shortest useful call (default compression=medium, budget on because token_budget set)
out = ContextManager().compress(
    [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}],
    token_budget=500,
)

# Lighter pass: structure + lexical + filler + abbrev + alias + repetition (+ budget if set)
out = ContextManager(compression="low").compress(messages, token_budget=500)

# Full NLP pipeline for this call (+ budget if token_budget set)
out = ContextManager().compress(messages, token_budget=500, compression="high")

# Exact stages only (preset ignored); include "budget" if you pass token_budget and want enforcement
out = ContextManager().compress(
    messages,
    token_budget=500,
    stages=["filler", "repetition", "budget"],
)
```

### Runnable demo in this repo

After `pip install -e .`, run:

```bash
python try_compress.py
```

That script builds a long history and a tight `token_budget` so you can see turn and token counts drop (see comments at the top of `try_compress.py`).

## Context types

- **chat** — Typical back-and-forth dialogue. Filler removal, repetition deduplication, resolution collapsing, recency weighting, and token budgets are tuned for conversational flow.
- **rag_doc** — Document chunks or RAG context. Resolution is off; repetition compares all chunks; recency uses relevance to the latest user query instead of chat recency.
- **agent** — Tool-using or task-oriented threads. Resolution can trigger on a single high-confidence completion signal; filler rules preserve tool-related turns when markers are present. OpenAI Chat Completions ``tool_calls`` / ``role: tool`` (0.6.4+), Anthropic ``tool_use`` / ``tool_result`` content blocks (0.6.7+), and Gemini ``functionCall`` / ``functionResponse`` parts (0.6.8+) are first-class.

```python
ContextManager(type="chat")
ContextManager(type="rag_doc")
ContextManager(type="agent")
```

Runnable agent example: [`examples/agent_pipeline.py`](examples/agent_pipeline.py).
OpenAI tools example: [`examples/openai_tools_compress.py`](examples/openai_tools_compress.py).
Anthropic tools example: [`examples/anthropic_tools_compress.py`](examples/anthropic_tools_compress.py).
Gemini tools example: [`examples/gemini_tools_compress.py`](examples/gemini_tools_compress.py).
Low-preset wording stages: [`examples/low_abbrev_alias.py`](examples/low_abbrev_alias.py).

## Pipeline stages

1. **Structure** (0.6+) — Minifies JSON blobs (including markdown `` ```json `` fences, 0.6.5+) and tightens whitespace / repeated log lines inside non-system turns (stdlib only; great for agent tool payloads and RAG chunks).
2. **Lexical** (0.6.10+) — Replaces multi-token words with fewer-token near-synonyms from a frozen, encoding-specific dictionary (`utilisation` → `use`). Chat and agent only (off for `rag_doc`). Skips system turns, JSON blobs, `` ```json `` fences, and tool call/result turns. Only keeps a swap when the turn's token count falls. **On `low` / `medium` / `high` for chat and agent.** This **changes wording**, not just removes content — use judgment on tone-sensitive text. Encoding follows `ContextManager(model=...)` (`cl100k_base` by default, `o200k_base` for gpt-4o-class models). Rebuild dictionaries with `python scripts/build_lexical_dict.py`.

```python
# Exact stages (preset ignored); lexical/abbrev/alias are also on chat/agent presets
out = ContextManager().compress(
    messages,
    token_budget=500,
    stages=["lexical", "filler", "abbrev", "alias", "repetition", "budget"],
)
```

Runnable demo: [`examples/low_abbrev_alias.py`](examples/low_abbrev_alias.py).
3. **Filler** — Removes low-semantic filler words / empty hedges (aggressive discourse strip) and (in chat/agent) drops acknowledgement-only assistant turns. JSON and tool turns are left unmodified.
4. **Abbrev** (0.6.10+) — Replaces ~300 common long forms with shorter equivalents when that actually reduces tokens (`due to the fact that` → `because`, `in order to` → `to`, `application programming interface` → `API`). Chat/agent only (off for `rag_doc`). Skips system / JSON / tool turns. Some popular shortcuts (e.g. `for example` → `e.g.`) are skipped when they do not shrink BPE count.
5. **Alias** (0.6.10+) — Finds multi-word expressions that appear **3+ times** in the same chat, introduces them once as `Phrase (ABBR)`, then uses `ABBR` afterward (e.g. `Context Press (CP)` … `CP`). Chat/agent only. Skips system / JSON / tool turns. Reverts if the whole conversation would grow.
6. **Repetition** — TF-IDF cosine similarity; keeps the more recent of similar turns. Tool-call turns are not dropped (0.6.6+).
7. **Resolution** — Collapses agreed threads into a single `RESOLVED:` synthetic system turn (chat/agent only). Threads that still contain tool/JSON turns are left intact (0.6.6+).
8. **Trim** (0.6.10+) — Drops the middle of a long thread. Keeps the opening turns, the last three non-system turns, and any tool call/result groups that sat in the gap. Short chats are unchanged. Runs after resolution so completed threads can still collapse. **Not in the ``low`` preset**; ``medium`` / ``high``, or pass ``stages=`` that includes ``trim``.
9. **Recency** — Extractively compresses older turns (or low-relevance chunks in `rag_doc`) while preserving the latest context. JSON blobs, `` ```json `` fences, and tool turns are not summarized (0.6.6+).
10. **Budget** — Enforces a hard token limit with `tiktoken`, removing oldest turns first while protecting system prompts and recent turns. Assistant ``tool_calls`` and matching ``role: tool`` results are dropped together (0.6.4+); Anthropic ``tool_use``/``tool_result`` and Gemini ``functionCall``/``functionResponse`` pairs stay intact the same way (0.6.7+/0.6.8+).

**Cost estimate** (0.6+, approximate list prices for planning):

```python
est = cm.estimate_cost(messages, provider="openai", model="gpt-4o-mini", output_tokens=200)
print(est.total_cost_usd, est.to_dict())
```

**USD on compression stats** (0.6.1+, opt-in):

```python
cm = ContextManager(type="chat", model="gpt-4o-mini", cost_provider="openai")
result = cm.compress(messages, token_budget=2000, return_stats=True)
print(result.stats.estimated_input_cost_before_usd)
print(result.stats.estimated_input_cost_after_usd)
print(result.stats.estimated_cost_saved_usd)
# or attach later: result.stats.attach_cost(provider="anthropic", model="claude-haiku-4-5")
```

**Readable savings report** (0.6.2+):

```python
result = cm.compress(messages, token_budget=2000, return_stats=True)
print(result.summary())
# contextpress (chat, medium): 12 -> 8 turns, 842 -> 410 tokens (51.3% saved)
# stages: structure, filler, repetition, budget
# est. input cost: $0.000126 -> $0.000061 (saved $0.000065)   # when cost_provider set
```

**Assumed completion tokens** (0.6.3+, opt-in; output cost is unchanged by compression):

```python
cm = ContextManager(type="chat", model="gpt-4o-mini", cost_provider="openai", cost_output_tokens=200)
result = cm.compress(messages, token_budget=2000, return_stats=True)
print(result.summary())
# ...
# est. output cost: $0.000120 (200 tokens)
# est. total: $0.000246 -> $0.000181
```

LangChain-style message objects (``.type`` / ``.content``) round-trip through ``compress()``;
dropped turns keep their original object types. See `examples/langchain_roundtrip.py`.

See [`ROADMAP.md`](ROADMAP.md) for positioning vs heavier compression stacks and the 0.6.x plan.

## Tier 1 vs Tier 2 (classical NLP vs LLM)

| | **Tier 1** (always available) | **Tier 2** (optional) |
|---|-------------------------------|------------------------|
| **What** | Pipeline stages: structure, lexical, filler, abbrev, alias, repetition, trim, resolution, recency, budget | `LLMBackend`: semantic `deduplicate` + `summarize` after Tier 1 |
| **Where in code** | `contextpress/strategies/`, orchestrated by `pipeline.py` | `contextpress/llm/` (`base.py`, `adapters.py`) |
| **Techniques** | Rules, TF–IDF, cosine similarity, NLTK, Sumy extractive summarization, tiktoken | Your provider’s chat/completions API (you supply the client) |
| **API key** | None | Required for your chosen provider (OpenAI, Anthropic, …) |
| **Determinism** | Deterministic for a fixed input and settings | Non-deterministic (model sampling) |
| **How to enable** | Default: `ContextManager()` runs Tier 1 only | Pass `llm_backend=` (`OpenAIBackend`, **`ClaudeBackend`**, `GeminiBackend`, `OllamaBackend`, or custom `LLMBackend`) |

**Note:** `ContextManager(model="gpt-4")` is only for **tiktoken** encoding when counting tokens in the **budget** stage. It does **not** call that model unless you also pass **`llm_backend`**.

## Compression presets and custom stages

**Presets** (`low` / `medium` / `high`, default **`medium`**) control how many NLP stages run. Aliases: `light`→low, `med`/`mid`→medium, `max`→high.

| Preset | Non-budget stages enabled |
|--------|-----------------------------|
| **low** | structure, lexical, filler, abbrev, alias, repetition |
| **medium** | structure, lexical, filler, abbrev, alias, repetition, trim, recency |
| **high** | structure, lexical, filler, abbrev, alias, repetition, trim, resolution, recency |

The **budget** stage is separate: if you pass **`token_budget=<int>`**, the budget stage runs as well (unless you opt out with `disable=["budget"]` or omit `"budget"` from an explicit `stages=` list). If `token_budget` is `None`, the budget stage does not run.

Presets are **merged with the context profile** (for example, **resolution**, **lexical**, **abbrev**, and **alias** stay off for `rag_doc` even on `high`, unless you pass an explicit `stages=` list that includes those names).

```python
from contextpress import ContextManager

# Default strength is medium
cm = ContextManager(type="chat", compression="medium")

# Per-call preset
out = cm.compress(messages, token_budget=4000, compression="high")

# Full control: exact stages for this call (preset ignored)
out = cm.compress(
    messages,
    token_budget=4000,
    stages=["filler", "repetition", "budget"],
)

# Preset + skip one stage
out = cm.compress(messages, compression="high", disable=["resolution"])

# Change default for future calls
cm.set_compression("low")
```

## Optional LLM tier (Tier 2)

After **Tier 1** finishes, you can attach an **`LLMBackend`** for semantic compression.

**What it does**

1. Calls **`deduplicate(turn_texts)`** on non-system turns (your backend returns indices to **keep**; default adapters keep all).
2. If the combined transcript is long enough (default **1500** characters; set **`llm_min_input_chars=0`** to always run), calls **`summarize(transcript, max_tokens)`**.
3. **System turns are unchanged** in order and content. **All other turns are replaced** by a **single assistant** message whose content is the LLM summary (metadata includes `source: contextpress_llm_tier`). If the LLM call fails, the Tier 1 conversation is returned and a **warning** is emitted.

Optional constructor knobs: **`llm_min_input_chars`**, **`llm_max_summary_tokens`**, **`llm_mode`**.

**`llm_mode`** (0.3+): `replace_all` (default — dedupe then one summary turn), `dedupe_only` (dedupe, keep turns), `summarize_only` (append summary, keep turns).

**Install SDKs** (not bundled): `pip install openai`, `anthropic`, and/or **`ollama`** (for local Ollama), or `pip install "contextpress[llm]"` from this repo’s `pyproject.toml` to pull all optional LLM clients.

```python
from contextpress import ContextManager
from contextpress.llm.adapters import OpenAIBackend

backend = OpenAIBackend(model="gpt-4o-mini")  # uses OPENAI_API_KEY
cm = ContextManager(
    type="chat",
    llm_backend=backend,
    llm_min_input_chars=1000,
    llm_max_summary_tokens=1024,
)
out = cm.compress(messages, token_budget=4000)
```

**Runnable example** (requires `OPENAI_API_KEY`): [`examples/llm_tier_openai.py`](examples/llm_tier_openai.py).

```bash
pip install openai
set OPENAI_API_KEY=sk-...   # or export on Unix
python examples/llm_tier_openai.py
```

**Local Ollama (no cloud API key)** — install [Ollama](https://ollama.com), run `ollama serve`, pull a model (`ollama pull llama3.2`), then:

```python
from contextpress import ContextManager
from contextpress.llm.adapters import OllamaBackend

backend = OllamaBackend(model="llama3.2")  # optional: host="http://localhost:11434"
cm = ContextManager(type="chat", llm_backend=backend, llm_min_input_chars=500)
out = cm.compress(messages, token_budget=4000)
```

Runnable script: [`examples/llm_tier_ollama.py`](examples/llm_tier_ollama.py).

**Claude (Anthropic)** — `pip install anthropic`, set `ANTHROPIC_API_KEY`:

```python
from contextpress import ContextManager
from contextpress.llm.adapters import ClaudeBackend

backend = ClaudeBackend(model="claude-haiku-4-5")
cm = ContextManager(type="chat", llm_backend=backend, llm_min_input_chars=500)
out = cm.compress(messages, token_budget=4000)
```

Runnable script: [`examples/llm_tier_claude.py`](examples/llm_tier_claude.py).

**Gemini (Google)** — `pip install google-generativeai`, set `GOOGLE_API_KEY`:

```python
from contextpress import ContextManager
from contextpress.llm.adapters import GeminiBackend

backend = GeminiBackend(model_name="gemini-2.0-flash")
cm = ContextManager(type="chat", llm_backend=backend, llm_min_input_chars=500)
out = cm.compress(messages, token_budget=4000)
```

Runnable script: [`examples/llm_tier_gemini.py`](examples/llm_tier_gemini.py).

```bash
pip install ollama
ollama pull llama3.2
python examples/llm_tier_ollama.py
```

## Custom strategies

Subclass `contextpress.strategies.base.BaseStrategy`, implement `process(self, conversation) -> Conversation`, then fork `Pipeline._build_strategy` in a local subclass or contribute a factory that returns your strategy for a custom stage name. Stages must not mutate input turns; return new `Conversation` and `Turn` objects.

## Why contextpress

Long chat histories inflate token usage, bury important facts (lost-in-the-middle), and repeat stale or redundant content. `contextpress` trims noise, merges resolved threads, and enforces budgets with deterministic Tier 1 NLP so applications stay within context limits without extra services.

## Dependencies

- **nltk** — Tokenization, tagging, and light parsing for resolution and NLP helpers.
- **scikit-learn** — TF-IDF vectors and cosine similarity for repetition and RAG relevance.
- **sumy** — Extractive summarization for the recency stage.
- **tiktoken** — Token-accurate budgeting aligned with common model encodings.

## Research and citing

For academic use, cite this package in your paper’s software or methods section. A machine-readable citation file is provided as [`CITATION.cff`](CITATION.cff).

## Extension and growth

- **Stabilization audit** — See [`AUDIT.md`](AUDIT.md) for known contract gaps and the 0.5.5–0.5.8 backlog (refactors, fixtures, fixes).
- **Custom stages** — Subclass `contextpress.strategies.base.BaseStrategy` and plug in via a custom `Pipeline` subclass or future registry hooks.
- **Tier 2** — Implement `LLMBackend` (`summarize`, `deduplicate`) for provider-specific semantic compression; failures fall back to Tier 1.
- **Presets API** — `from contextpress.compression import VALID_STAGES, STAGE_ORDER` for tooling and experiments.
- **Profiles** — `configure(stage, ...)` adjusts aggressiveness per stage; `type="rag_doc"` vs `chat` changes dedup and recency behavior.

Invalid inputs are rejected early where practical: for example, `token_budget` must be a positive `int` or `None` (booleans are not accepted).

## Typing

The package includes `py.typed` (PEP 561) for static analysis in downstream projects.
