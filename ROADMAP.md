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
| **0.7.1** | Faster alias candidate scan; cached bundled rewrite plans; per-run token-count reuse for stage stats |
| **0.7.2** | Cached Sumy components in recency; precompiled alias turn patterns; ``tokens_per_second`` on stats |

Stay classical-NLP-first; keep optional LLM extras optional.

## 0.7.3 – 0.7.5 — long prose, planned

The chat fidelity study (222 items) is the wrong headline for documents.
[`benchmarks/LONGFORM.md`](benchmarks/LONGFORM.md) is the baseline these three
releases have to beat. Profile is `rag_doc`. Same machine, same script
(`python -m benchmarks.run_longform`). Do not treat a one-point wobble in a
Sumy cell as a product change; do treat a move in the monolith row, the
question-intact count, or chunked `high` anchor/number retention as the point
of the release.

Measured on 12 public-domain / CC BY-SA works (204 compressions):

| Job | What happened |
|-----|----------------|
| **Monolith** (one pasted passage + question) | `low` = `medium` = `high`. **6.1%** mean save at 8k, **6.9%** at 20k. Anchor words and passage numbers stay (~100%). Gutenberg books **8.8%** at 8k; Wikipedia extracts **0.6%**. Recency and trim never run: two non-system turns are inside the protected tail. |
| **Chunked `medium`** | Median save **5.8% / 10.4% / 12.3%** at 2k / 8k / 20k (means 12.2 / 16.6 / 20.4, sd **23.1** at 20k). Anchor words **96.7%** at 20k. Passage numbers **85.9%** at 20k. The spread is the relevance gate, not noise. |
| **Chunked `high`** | Mean save **55.4% → 67.1% → 85.3%** as length grows. Almost all of the 20k cut is trim (~15.4k tokens removed). Anchor retention **46.3% / 69.5% / 43.9%**. Passage numbers **33.7% / 43.7% / 37.7%**. At 8k `high`, fiction keeps ~1% of numbers and nonfiction ~65%. |
| **Contracts** | System turn **204/204** intact. Question turn **186/204**: filler rewrites discourse words inside the quoted question. |

Chat and agent presets stay on the 0.6.14 behavior. These releases are
`rag_doc` (and the long-turn case) unless a bullet says otherwise.

### 0.7.3 — Compress a pasted chapter inside the turn

**Problem.** People paste a chapter, a PDF extract, or a Wikipedia article as
one user message. Today that job cannot reach recency or trim, so choosing
`medium` or `high` does nothing beyond filler. Filler is worth ~9% on
19th-century prose and ~0% on encyclopedia text.

**Behavior.**

- Only when `type="rag_doc"` and compression is `medium` or `high`.
- Only on a non-question turn longer than **1,500 tokens** (cl100k). Chunked
  sections in the longform study are ~700 tokens, so they must not enter this
  path. The last user turn (the question) is never split.
- Split that turn into sentences. Score each sentence against the question
  with the existing TF-IDF cosine. Keep every sentence at or above the
  current rag_doc relevance cutoff (0.3), plus enough lead sentences that a
  short answer still has context.
- `medium` keeps more (target roughly a third of the sentences, floored by
  the relevant set). `high` keeps the relevant set and a thinner lead.
- No new dependency. No change to `chat` or `agent`. No change to turns that
  are under the 1,500-token bar.

**Tests.**

- Fixture: one ~3k-token prose turn + a question that names a sentence in the
  middle. Question byte-identical. That sentence still present. An off-topic
  paragraph near the end is shorter or gone.
- Fixture: eight short sections + question (the chunked shape). Output matches
  today’s chunked `medium` / `high` for that fixture, so the new branch did
  not fire.
- Input messages still immutable.

**Release gate (re-run LONGFORM.md).**

- Monolith 8k `medium`: mean save **from 6.1% to at least 15%**, anchor-word
  retention **at least 95%** (today 100% because the body is not summarized).
- Monolith 20k `high`: mean save **from 6.9% to at least 25%**, anchor-word
  retention **at least 90%**.
- Chunked 8k `medium` median stays within **2 points of 10.4%**. If it moves
  more, the length gate is wrong and the release stops.

### 0.7.4 — Keep the question, and keep the section it points at

**Problem.** Two measured failures:

1. Filler edits the live question when the quoted sentence contains `very`,
   `quite`, `rather`, and the rest of the filler list. **18 questions in 204**
   runs were not byte-identical.
2. Trim ignores relevance. The anchor sentence is planted in the first fifth
   of the passage, which is usually the middle trim deletes. Chunked `high`
   therefore saves 67–85% and often drops the only sentence the question
   asked about (anchor retention 44–70%).

**Behavior.**

- On `rag_doc`, do not run filler (or any wording rewrite) on the **last user
  turn**. `chat` and `agent` filler stay as they are, so the 222-item chat
  table does not move.
- On `rag_doc` trim, also keep any non-system turn whose TF-IDF similarity to
  the question is **≥ 0.3**, using the same helper recency already uses. Then
  drop the other middle turns and leave the existing stub. Head and tail
  rules stay. `chat` trim is unchanged.
- Recency’s “last three turns” rule stays. This change is trim-only.

**Tests.**

- Question text containing `very` and `quite` is byte-identical after
  `rag_doc` `low` and `high`.
- Chunked thread where the relevant section is turn 4 of 10: that turn
  survives `high`. A clearly off-topic middle turn does not.
- Chat fixture that previously lost a filler word in an older user turn still
  does so (no accidental chat change).

**Release gate.**

- Question byte-identical: **204/204** on the longform run (today 186/204).
- Chunked 8k `high` anchor retention: **from 69.5% to at least 90%**.
- Chunked 8k `high` mean save: **stays at least 40%** (today 67.1%). Giving
  back some of the trim cut is the point; falling back to the monolith’s 6%
  is a failed design.
- Chunked 20k `high` anchor retention: **at least 85%** (today 43.9%), mean
  save **at least 50%** (today 85.3%).

### 0.7.5 — Pin figures that a lossy document preset would drop

**Problem.** After 0.7.4 the asked section should survive, and the rest of a
`high` cut should still be large. Whole-passage number retention on chunked
`high` is still the weak number: **43.7%** at 8k and **37.7%** at 20k, and
fiction at 8k `high` keeps about **1%**. A reviewer who says “high deletes
the document” is describing this row. Stuffing the dropped prose back would
erase the savings. Pinning the spans that the fidelity study already treats
as facts does not.

**Behavior.**

- `rag_doc` only, `medium` and `high` only.
- When recency replaces a turn’s text, or trim drops a turn, scan the
  discarded text for the same span classes as `benchmarks/info_fidelity.py`:
  URLs, emails, paths, versions / decimals / 3+ digit numbers, ISO dates.
- Spans that are no longer present anywhere in the output are appended once,
  in a single trailing line on the trim stub or on the summarized turn:
  `Kept figures: 1859; 3.14; https://…`. Cap at **40** spans per compression
  so a number-dense page cannot undo the cut. Order is first-seen.
- Wording around the number is not kept. The span is.
- New counter on `CompressionStats`: `pinned_fact_count` (0 when nothing was
  pinned), included in `to_dict()`. Chat runs stay at 0.

**Tests.**

- Chunked `high` fixture with `1859` only in a middle off-topic section:
  that section’s prose is gone, `1859` appears in the kept-figures line,
  `pinned_fact_count >= 1`.
- The same number already in the question or a kept head turn is not repeated.
- Cap: 50 distinct numbers in dropped turns produce at most 40 pins.
- `chat` compression of an existing fixture does not gain a kept-figures line.

**Release gate.**

- Chunked 8k `high` number retention: **from 43.7% to at least 80%**, mean
  save **at least 50%** (today 67.1%, and 0.7.4 may already have lowered it).
- Chunked 20k `high` number retention: **from 37.7% to at least 80%**, mean
  save **at least 45%**.
- Anchor retention must not fall relative to the 0.7.4 longform table.
- Re-publish `benchmarks/LONGFORM.md` in the same commit as the tag. The
  222-item chat headline in the README stays, with a pointer at this study,
  until a later docs pass. Do not replace the chat numbers with these.

### Explicitly not in 0.7.3–0.7.5

- No LLM-as-judge, no new model dependency, no required network in `pytest`.
- No change to chat/agent preset membership.
- No within-turn compression of tool JSON or code (the agent low path).
- No claim that `high` preserves answer quality. The gate is tokens, the
  anchor sentence, and pinned numeric spans.
