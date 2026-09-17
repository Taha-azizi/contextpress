# Roadmap — low-cost context compression

## Competitive landscape (ideas only — not copies)

Surveyed for inspiration while keeping **contextpress** on its niche:
deterministic Tier‑1 NLP for chat / RAG / agent **message histories**, with optional Tier‑2 LLM.

| Package | Approach | Cost posture | Takeaway for us |
|---------|----------|--------------|-----------------|
| **headroom-ai** | Content-type routers (JSON, logs, code, tool I/O); proxy/MCP/agent wrap; optional ML | Local-first, heavy surface area | Idea: **structure-aware compaction of payloads inside turns** — without proxy/MCP |
| **selective-context** | Self-information via GPT‑2 / spaCy | Needs small LM at runtime | Skip — conflicts with offline / no-GPU Tier‑1 |
| **context-compressor** | BERT / BART / T5 strategies | Heavy transformers | Skip — not low-cost |
| **llm-token-optimizer** | Prompt strip + **USD cost estimates** + budgets | Lightweight | Idea: **make savings measurable in $**, not only tokens |
| **contpress** (`pip install contpress`) | Full preflight toolkit (cache, CLI, compact JSON, pruning) | Mixed; optional LLMLingua | Different product. We stay a **conversation pipeline**, not a prompt OS. Name collision: we are **`contextpress`** |

### What we already win at

- Multi-stage deterministic pipeline with invariants (system protection, recency/budget rules)
- Profiles: `chat` / `rag_doc` / `agent`
- Observability: preview, compare_presets, recommend_preset, stats, fixtures
- Optional Tier‑2 without forcing LLM for Tier‑1
- Structure compaction (JSON minify, whitespace/log cleanup) and approximate USD cost estimates — shipped in 0.6.x

### Explicit non-goals (near term)

- OpenAI-compatible proxy / MCP server
- Semantic / embedding caches
- Local GPT‑2 / BERT / LLMLingua as required path
- Cloning another project's API surface

## 0.6.x — shipped (stable for Tier 1)

The 0.6 line is **stable for Tier 1**. Remaining work is **stabilization** (contracts, docs, release hygiene, fidelity reporting) — not a new 0.6.2-style feature plan.

| Version | What shipped |
|---------|----------------|
| **0.6.0** | `structure` stage + `estimate_cost()` |
| **0.6.1** | Estimated USD on `CompressionStats` / reports |
| **0.6.2** | Agent-oriented fixtures; `summary()` report |
| **0.6.3** | LangChain compress round-trip; `output_tokens` on cost stats |
| **0.6.4** | OpenAI `tool_calls` / `role=tool` round-trip, JSON minify, budget pair integrity |
| **0.6.5** | Minify JSON inside markdown code fences |
| **0.6.6** | Protect tool/JSON payloads from recency, repetition, and resolution |
| **0.6.7** | Anthropic `tool_use` / `tool_result` content blocks |
| **0.6.8** | Gemini `functionCall` / `functionResponse` parts |
| **0.6.9** | Internal refactor: jsonutil, clone_turn in stages |
| **0.6.10** | `trim`; `lexical` / `abbrev` / `alias` + expanded filler on chat/agent `low` |
| **0.6.11** | Opt-in `contractions` / `wordy_phrases` + `number_normalize` |
| **0.6.12** | Explicit `allow_equal_tokens` for contractions |
| **0.6.13** | `medium` drops `trim` (keep on `high`); `compare_cache_tradeoff()` |
| **0.6.14** | Fidelity tables: save vs fact-loss (medium ≠ high) |

## 0.7.x — performance and measurement

Same Tier-1 behavior as 0.6.14. The series is faster calls and better timing, not new stages.

| Version | Focus |
|---------|--------|
| **0.7.0** | Lexical unigram hash matcher; ``elapsed_ms`` / ``elapsed_ms_by_stage``; lazy NLTK/Sumy import |

Stay classical-NLP-first; keep optional LLM extras optional.
