# contextpress

Deterministic context compression for LLM chat, RAG, and agent pipelines.
Created and maintained by **[Taha Azizi](https://github.com/Taha-azizi)**.

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

# Default compression is "medium" (filler + repetition + recency); see below.
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

### Minimal examples

```python
from contextpress import ContextManager

# Shortest useful call (default compression=medium, budget on because token_budget set)
out = ContextManager().compress(
    [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}],
    token_budget=500,
)

# Lighter pass: only filler + repetition (+ budget if token_budget set)
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
- **agent** — Tool-using or task-oriented threads. Resolution can trigger on a single high-confidence completion signal; filler rules preserve tool-related turns when markers are present.

```python
ContextManager(type="chat")
ContextManager(type="rag_doc")
ContextManager(type="agent")
```

## Pipeline stages

1. **Filler** — Removes low-semantic filler words and (in chat/agent) drops acknowledgement-only assistant turns.
2. **Repetition** — TF-IDF cosine similarity; keeps the more recent of similar turns.
3. **Resolution** — Collapses agreed threads into a single `RESOLVED:` synthetic system turn (chat/agent only).
4. **Recency** — Extractively compresses older turns (or low-relevance chunks in `rag_doc`) while preserving the latest context.
5. **Budget** — Enforces a hard token limit with `tiktoken`, removing oldest turns first while protecting system prompts and recent turns.

## Tier 1 vs Tier 2 (classical NLP vs LLM)

| | **Tier 1** (always available) | **Tier 2** (optional) |
|---|-------------------------------|------------------------|
| **What** | Pipeline stages: filler, repetition, resolution, recency, budget | `LLMBackend`: semantic `deduplicate` + `summarize` after Tier 1 |
| **Where in code** | `contextpress/strategies/`, orchestrated by `pipeline.py` | `contextpress/llm/` (`base.py`, `adapters.py`) |
| **Techniques** | Rules, TF–IDF, cosine similarity, NLTK, Sumy extractive summarization, tiktoken | Your provider’s chat/completions API (you supply the client) |
| **API key** | None | Required for your chosen provider (OpenAI, Anthropic, …) |
| **Determinism** | Deterministic for a fixed input and settings | Non-deterministic (model sampling) |
| **How to enable** | Default: `ContextManager()` runs Tier 1 only | Pass `llm_backend=` (`OpenAIBackend`, `AnthropicBackend`, **`OllamaBackend`**, or custom `LLMBackend`) |

**Note:** `ContextManager(model="gpt-4")` is only for **tiktoken** encoding when counting tokens in the **budget** stage. It does **not** call that model unless you also pass **`llm_backend`**.

## Compression presets and custom stages

**Presets** (`low` / `medium` / `high`, default **`medium`**) control how many NLP stages run. Aliases: `light`→low, `med`/`mid`→medium, `max`→high.

| Preset | Non-budget stages enabled |
|--------|-----------------------------|
| **low** | filler, repetition |
| **medium** | filler, repetition, recency |
| **high** | filler, repetition, resolution, recency |

The **budget** stage is separate: if you pass **`token_budget=<int>`**, the budget stage runs as well (unless you opt out with `disable=["budget"]` or omit `"budget"` from an explicit `stages=` list). If `token_budget` is `None`, the budget stage does not run.

Presets are **merged with the context profile** (for example, **resolution stays off** for `rag_doc` even on `high`, unless you pass an explicit `stages=` list that includes `resolution`).

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

Optional constructor knobs: **`llm_min_input_chars`**, **`llm_max_summary_tokens`**.

**Install SDKs** (not bundled): `pip install openai`, `anthropic`, and/or **`ollama`** (for local Ollama), or `pip install "contextpress[llm]"` from this repo’s `pyproject.toml` to pull all optional LLM clients.

```python
from openai import OpenAI
from contextpress import ContextManager
from contextpress.llm.adapters import OpenAIBackend

backend = OpenAIBackend(client=OpenAI(), model="gpt-4o-mini")
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

For academic use, cite this package in your paper’s software or methods section. A machine-readable citation file is provided as [`CITATION.cff`](CITATION.cff) (GitHub and Zenodo can ingest it). Replace the placeholder repository URL in that file with your fork’s URL when you publish.

## Extension and growth

- **Custom stages** — Subclass `contextpress.strategies.base.BaseStrategy` and plug in via a custom `Pipeline` subclass or future registry hooks.
- **Tier 2** — Implement `LLMBackend` (`summarize`, `deduplicate`) for provider-specific semantic compression; failures fall back to Tier 1.
- **Presets API** — `from contextpress.compression import VALID_STAGES, STAGE_ORDER` for tooling and experiments.
- **Profiles** — `configure(stage, ...)` adjusts aggressiveness per stage; `type="rag_doc"` vs `chat` changes dedup and recency behavior.

Invalid inputs are rejected early where practical: for example, `token_budget` must be a positive `int` or `None` (booleans are not accepted).

## Typing

The package includes `py.typed` (PEP 561) for static analysis in downstream projects.
