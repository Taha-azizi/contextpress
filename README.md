# contextpress

[![PyPI version](https://img.shields.io/pypi/v/contextpress)](https://pypi.org/project/contextpress/)
[![Python versions](https://img.shields.io/pypi/pyversions/contextpress)](https://pypi.org/project/contextpress/)
[![License](https://img.shields.io/github/license/Taha-azizi/contextpress)](LICENSE)
[![PyPI downloads](https://img.shields.io/pypi/dm/contextpress)](https://pypi.org/project/contextpress/)

**Deterministic context compression for LLM chat, RAG, and agent pipelines** — trim token bloat before every model call.

- **Tier 1, no API key** — `ContextManager` runs deterministic NLP stages (structure, filler, repetition, recency, budget, …). Optional **Tier 2** via `llm_backend=` when you want semantic dedupe/summarize.
- **`chat` · `rag_doc` · `agent`** — profiles tune filler, resolution, recency, and tool-turn handling for dialogue, RAG chunks, and agent threads.
- **Measured tradeoffs** — **222** local workloads ([method](benchmarks/INFO_FIDELITY.md)): `low` **6.0%** token save / **1.6%** critical-fact loss; `medium` **22.7%** / **15.2%**; `high` **47.7%** / **27.3%** (weighted critical loss).

Created and maintained by **[Taha Azizi](https://github.com/Taha-azizi)**. **Write-up:** [Introducing contextpress](https://pub.towardsai.net/introducing-contextpress-the-python-library-that-refactors-your-llm-context-c57965617edb) (Towards AI).

## Install

```bash
pip install contextpress
```

**PyPI:** [pypi.org/project/contextpress](https://pypi.org/project/contextpress)

From a git clone:

```bash
pip install -e .
```

## API at a glance

| Need | Method |
|------|--------|
| Compress | `cm.compress(messages, token_budget=…)` |
| Token count | `cm.estimate_tokens(messages)` |
| Dry-run stats | `cm.preview(...)`, `cm.fits_budget(...)` |
| Pick a preset | `cm.compare_presets(...)`, `cm.recommend_preset(...)` |
| Batch / async | `cm.compress_many(...)`, `await cm.compress_async(...)` |

```python
from contextpress import ContextManager

cm = ContextManager(type="chat")  # or "rag_doc", "agent"
out = cm.compress(messages, token_budget=2000, return_stats=True)
print(out.stats.token_savings_pct, out.stats.stages_run)
```

Pass **`return_stats=True`** for `CompressionResult` (`messages`, token counts, stages). Default **`compression="medium"`**; **`token_budget`** enables the budget stage.

## Fidelity tradeoffs (0.6.14 study)

Deterministic factoid check on **222** local workloads (no LLM judge). Quote **mean token save** and **weighted critical-fact retention**. Full tables: [`benchmarks/INFO_FIDELITY.md`](benchmarks/INFO_FIDELITY.md).

| Preset | What runs | Tokens saved (mean) | Critical-fact loss | Facts kept |
|--------|-----------|--------------------:|-------------------:|-----------:|
| `low` | wording only | **6.0%** | **1.6%** | **98.4%** |
| `medium` | low + recency | **22.7%** | **15.2%** | **84.8%** |
| `high` | medium + trim + resolution | **47.7%** | **27.3%** | **72.7%** |

By context type (`ContextManager(type=…)`):

| Type | n | `low` save → fact loss | `medium` | `high` |
|------|--:|------------------------|----------|--------|
| **chat** | 202 | 5.9% → 1.6% | 23.5% → 22.6% | 50.8% → 45.0% |
| **rag_doc** (files) | 7 | 13.1% → 0.0% | 33.4% → 14.5% | 33.8% → 17.3% |
| **agent** (pretty tool JSON) | 5 | 11.3% → 2.7% | same (structure minify) | same |
| **agent tools** (Glaive) | 8 | 0.2% → 0.0% | 1.1% → 0.0% | 5.7% → 4.4% |

Typical chat (median fact loss): **0%** on `low`/`medium`, **33%** on `high`. Agents should stay on `low`; files get most of the win at `medium`; `high` is the long-chat lever.

### Study summary and methodology

- **Corpus:** 222 items × 3 presets (chats from public Hugging Face / GitHub-style threads, files stuffed into the prompt, agent tool JSON). Tier 1 only; no live LLM.
- **Tokens:** tiktoken counts before vs after compression (`token_budget=None` so budget truncation is not counted as “savings”).
- **Critical facts:** URLs, emails, paths, versions / decimals / 3+ digit numbers, ISO dates, `snake_case` / `CamelCase` ids from non-system turns. Retention uses token boundaries. **Weighted** loss pools facts across items (the headline); mean/median describe a typical item.
- **Soft loss:** `100 × (1 − TF-IDF cosine)` of the full thread (wording / dropped hedges — not the same as lost IDs).
- **Contracts:** system prompt unchanged; last-user keywords still present.
- **Limits:** this is not an LLM-as-judge of answer quality. It answers: *are the hard facts still in the prompt?* Re-run: `python -m benchmarks.info_fidelity` (see [`benchmarks/README.md`](benchmarks/README.md)).

---

## When to use / when not to use

**Use contextpress when**

- Chat history, RAG chunks, or pretty-printed tool JSON is eating the window every call.
- You want **deterministic**, offline, testable compression (Tier 1) before you pay for another model to summarize.
- You can pick a preset: `low` for wording, `medium` if older turns can be shortened, `high` if mid-thread can be dropped.

**Do not use it (or do not re-run it on the full prefix) when**

- **Prompt caching** is already paying off. OpenAI / Anthropic / Gemini caches are **exact prefix matches**. Re-compressing the **whole** history can rewrite earlier turns, bust the cache, and cost **more** than the ~6% `low` token cut. Compress the **uncached tail**, or compact **once** and append. See [Prompt caching](#prompt-caching-openai--anthropic--gemini) and `compare_cache_tradeoff()`.
- The thread is short (a two-line FAQ). Savings will be noise.
- You need **verbatim** quotes, legal/audit wording, or tone that lexical/abbrev must not touch — skip wording stages or use `stages=["structure"]` only.
- You need semantic “keep what the model would care about” — that is optional **Tier 2**, not Tier 1.

---

## Quickstart

No API keys are required for Tier 1. Pass **`token_budget=None`** unless you want the **budget** stage to enforce a hard cap.

**Sample before**

> In order to utilize the API effectively, due to the fact that rate limits apply, we should implement caching for the application programming interface calls we make on a daily basis.

**Sample after** (`low` preset — wording: structure, lexical, filler, abbrev, alias, repetition)

> To use the API effectively, because rate limits apply, we should implement caching for the API calls we make daily.

```python
from contextpress import ContextManager

messages = [
    {
        "role": "user",
        "content": (
            "In order to utilize the API effectively, due to the fact that "
            "rate limits apply, we should implement caching for the "
            "application programming interface calls we make on a daily basis."
        ),
    }
]

cm = ContextManager(type="chat", compression="low")
result = cm.compress(messages, token_budget=None, return_stats=True)
print(result.messages[0]["content"])
print(result.stats.token_savings_pct, result.stats.stages_run)
```

Default **`compression` is `"medium"`** (adds recency). Passing **`token_budget=<int>`** turns on **budget**.

```python
result = cm.compress(messages, token_budget=2000, return_stats=True)
print(result.stats.tokens_saved, result.stats.stages_run)
print(result.stats.elapsed_ms, result.stats.elapsed_ms_by_stage)
compressed = result.messages

before = cm.estimate_tokens(messages)
preview = cm.preview(messages, token_budget=500)
assert preview.messages == messages  # unchanged

rows = cm.compare_presets(messages, token_budget=500)
preset = cm.recommend_preset(messages, token_budget=500)
results = cm.compress_many(list_of_conversations, token_budget=2000, return_stats=True)
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

### Runnable demo in this repo

After `pip install -e .`:

```bash
python try_compress.py
python examples/quickstart_low.py
python examples/low_abbrev_alias.py
```

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
2. **Lexical** (0.6.10+) — Replaces multi-token words with fewer-token near-synonyms from a frozen, encoding-specific dictionary (`utilisation` → `use`). Chat and agent only (off for `rag_doc`). Skips system turns, JSON blobs, `` ```json `` fences, and tool call/result turns. Only keeps a swap when the turn's token count falls. **On `low` / `medium` / `high` for chat and agent.** This **changes wording**, not just removes content — use judgment on tone-sensitive text. Encoding follows `ContextManager(model=...)` (`cl100k_base` by default, `o200k_base` for gpt-4o-class models). Rebuild dictionaries with `python scripts/build_lexical_dict.py`. Same loader also powers opt-in ``contractions`` / ``wordy_phrases`` via ``dict_name`` / ``dict_path``.

```python
# Exact stages (preset ignored); lexical/abbrev/alias are also on chat/agent presets
out = ContextManager().compress(
    messages,
    token_budget=500,
    stages=["lexical", "filler", "abbrev", "alias", "repetition", "budget"],
)
```

Runnable demo: [`examples/low_abbrev_alias.py`](examples/low_abbrev_alias.py).

Opt-in (0.6.11+, **not** in low/medium/high):

```python
out = ContextManager().compress(
    messages,
    token_budget=None,
    stages=["contractions", "wordy_phrases", "number_normalize"],
)
```

- **Contractions** — `do not` → `don't` (low meaning risk).
- **Wordy phrases** — `due to the fact that` → `because`, `in order to` → `to`, …
- **Number normalize** — multi-word quantities only (`twenty three` → `23`); leaves lone `one` / `two` alone.

3. **Filler** — Removes low-semantic filler words / empty hedges (aggressive discourse strip) and (in chat/agent) drops acknowledgement-only assistant turns. JSON and tool turns are left unmodified.
4. **Abbrev** (0.6.10+) — Replaces ~300 common long forms with shorter equivalents when that actually reduces tokens (`due to the fact that` → `because`, `in order to` → `to`, `application programming interface` → `API`). Chat/agent only (off for `rag_doc`). Skips system / JSON / tool turns. Some popular shortcuts (e.g. `for example` → `e.g.`) are skipped when they do not shrink BPE count.
5. **Alias** (0.6.10+) — Finds multi-word expressions that appear **3+ times** in the same chat, introduces them once as `Phrase (ABBR)`, then uses `ABBR` afterward (e.g. `Context Press (CP)` … `CP`). Chat/agent only. Skips system / JSON / tool turns. Reverts if the whole conversation would grow.
6. **Repetition** — TF-IDF cosine similarity; keeps the more recent of similar turns. Tool-call turns are not dropped (0.6.6+).
7. **Resolution** — Collapses agreed threads into a single `RESOLVED:` synthetic system turn (chat/agent only). Threads that still contain tool/JSON turns are left intact (0.6.6+).
8. **Trim** (0.6.10+) — Drops the middle of a long thread. Keeps the opening turns, the last three non-system turns, and any tool call/result groups that sat in the gap. Short chats are unchanged. Runs after resolution so completed threads can still collapse. **Only in the ``high`` preset** (0.6.13+); or pass ``stages=`` that includes ``trim``.
9. **Recency** — Extractively compresses older turns (or low-relevance chunks in `rag_doc`) while preserving the latest context. JSON blobs, `` ```json `` fences, and tool turns are not summarized (0.6.6+).
10. **Budget** — Enforces a hard token limit with `tiktoken`, removing oldest turns first while protecting system prompts and recent turns. Assistant ``tool_calls`` and matching ``role: tool`` results are dropped together (0.6.4+); Anthropic ``tool_use``/``tool_result`` and Gemini ``functionCall``/``functionResponse`` pairs stay intact the same way (0.6.7+/0.6.8+).

**Cost estimate** (0.6+, approximate list prices for planning):

```python
est = cm.estimate_cost(messages, provider="openai", model="gpt-4o-mini", output_tokens=200)
print(est.total_cost_usd, est.to_dict())
```

## Prompt caching (OpenAI / Anthropic / Gemini)

Contextpress does **not** restore provider prompt caches. Caches are **exact prefix matches**. If you re-run `compress()` on the **full** history every turn, alias / repetition / trim / recency / resolution can rewrite or drop **earlier** turns, the prefix bytes change, and the next request is billed as a cache **miss** (and may pay a cache-**write** surcharge on Anthropic / GPT-5.6+).

That can **cost more** than leaving the raw prompt cached:

| Situation | What happens |
|-----------|----------------|
| No cache, or the bloated part is never in the prefix (pretty tool JSON, RAG chunk stuffed at the **end**) | Compression savings are real. |
| Stable system + tools + long history already getting ~90% cache reads | Recompressing the whole thread is often a **net loss**, especially at `low` (~6% tokens vs ~90% off cached input). |
| `medium`/`high` (~20–50% fewer tokens) vs Anthropic-style 0.1× cache reads | `high` (trim) often busts the prefix. `medium` (recency, no trim) still rewrites older turns — check `compare_cache_tradeoff`. |

Check your numbers:

```python
from contextpress.costs import compare_cache_tradeoff

# 10k-token raw prompt, 6% cut (low), 50% of tokens were cache hits at 0.1×
t = compare_cache_tradeoff(10_000, 9_400, cache_hit_rate=0.5, cache_read_multiplier=0.1)
print(t.compress_is_cheaper, t.break_even_cache_hit_rate, t.to_dict())
```

**Cache-safe patterns**

1. Compress only the **uncached tail** (new tool result, new retrieved files). Leave the already-sent prefix untouched.
2. Compact **once** into a frozen summary/prefix, then **append** new turns without re-pressing the prefix until you explicitly recompact.
3. Put static system / tool schemas first and **do not** run Contextpress on them (system turns are already passed through).
4. Prefer `stages=["structure"]` (or filler on the new tool payload only) when the prefix must stay identical.

Do **not** use `estimate_cost_saved_usd` as the bill delta if the uncompressed traffic was mostly cache reads — that field assumes uncached list prices on both sides.

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

See [`ROADMAP.md`](ROADMAP.md) for positioning vs heavier compression stacks.

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
| **medium** | structure, lexical, filler, abbrev, alias, repetition, recency |
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

## Project status

> **Stable for its original use case — maintained at a low cadence.** Tier 1 (`low` / `medium` / `high`) is deterministic, offline, and covered by tests; fidelity numbers above come from the current corpus.
>
> - **Provided as-is for its original use case.** Bug fixes are reviewed when time permits; **new features are not actively developed** (docs and contract fixes still land in 0.6.x).
> - **PRs are welcome**, but expect a review cycle of **2–4 weeks**. Need something sooner? **Fork** and iterate on your timeline.
> - **License:** [Apache 2.0](LICENSE) — no warranty, no liability. See §7 and §8 of the license for the legal text.
>
> Bugs: [GitHub issues](https://github.com/Taha-azizi/contextpress/issues) with a minimal reproduction. Security: [SECURITY.md](SECURITY.md). Feature requests may be closed with a pointer to fork.

## Dependencies

- **nltk** — Tokenization, tagging, and light parsing for resolution and NLP helpers.
- **scikit-learn** — TF-IDF vectors and cosine similarity for repetition and RAG relevance.
- **sumy** — Extractive summarization for the recency stage.
- **tiktoken** — Token-accurate budgeting aligned with common model encodings.

## Research and citing

For academic use, cite this package in your paper’s software or methods section. A machine-readable citation file is provided as [`CITATION.cff`](CITATION.cff).

## Extension and growth

- **Stabilization** — See [`AUDIT.md`](AUDIT.md) for known contract gaps. See [`ROADMAP.md`](ROADMAP.md) for what already shipped in 0.6.x.
- **Custom stages** — Subclass `contextpress.strategies.base.BaseStrategy` and plug in via a custom `Pipeline` subclass or future registry hooks.
- **Tier 2** — Implement `LLMBackend` (`summarize`, `deduplicate`) for provider-specific semantic compression; failures fall back to Tier 1.
- **Presets API** — `from contextpress.compression import VALID_STAGES, STAGE_ORDER` for tooling and experiments.
- **Profiles** — `configure(stage, ...)` adjusts aggressiveness per stage; `type="rag_doc"` vs `chat` changes dedup and recency behavior.

Invalid inputs are rejected early where practical: for example, `token_budget` must be a positive `int` or `None` (booleans are not accepted).

## Typing

The package includes `py.typed` (PEP 561) for static analysis in downstream projects.
