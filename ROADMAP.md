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

### Gaps we will close (on-strategy)

1. **Structure compaction** — JSON minify, whitespace/log-line cleanup inside non-system turns (stdlib only).
2. **Cost estimation** — approximate USD from token counts + bundled pricing estimates.
3. Later: richer agent-trace helpers, optional cost fields on stats — still no transformers/proxy.

### Explicit non-goals (near term)

- OpenAI-compatible proxy / MCP server
- Semantic / embedding caches
- Local GPT‑2 / BERT / LLMLingua as required path
- Cloning another project's API surface

## 0.6.x plan

| Version | Focus |
|---------|--------|
| **0.6.0** | `structure` stage + `estimate_cost()` + this roadmap — shipped |
| **0.6.1** | Wire estimated USD into `CompressionStats` / reports — shipped |
| **0.6.2** | Agent-oriented fixtures for JSON/tool payloads; `summary()` report — shipped |
| **0.6.3** | LangChain compress round-trip; `output_tokens` on cost stats / `summary()` — shipped |
| **0.6.4** | OpenAI `tool_calls` / `role=tool` round-trip, JSON minify, budget pair integrity — shipped |
| **0.6.5** | Minify JSON inside markdown code fences (`structure` stage) — shipped |
| **0.6.6** | Protect tool/JSON payloads from recency, repetition, and resolution — shipped |
| **0.6.7** | Anthropic `tool_use` / `tool_result` content blocks — shipped |
| **0.6.8** | Gemini `functionCall` / `functionResponse` parts — shipped |
| **0.6.9** | Internal refactor: jsonutil, clone_turn in stages — shipped. |
| **0.6.10** | `trim` (medium/high); `lexical` / `abbrev` / `alias` + expanded filler on chat/agent `low` — shipped. |

Stay classical-NLP-first; keep optional LLM extras optional.
