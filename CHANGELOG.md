# Changelog

All notable changes to `contextpress` are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.8] - 2026-08-24

- **Gemini function calling** — ``parts`` with ``functionCall`` / ``functionResponse``
  (and snake_case aliases) round-trip; ``role: model`` maps internally to assistant
  and is restored on output. ``thought_signature`` on the original part is preserved.
- JSON **strings** in ``args`` / ``arguments`` / ``response`` are minified; objects
  stay objects.
- Budget treats a user turn of only ``functionResponse`` parts as the match for the
  preceding ``model``/assistant ``functionCall`` ids (same pair integrity as OpenAI
  ``role=tool`` and Anthropic ``tool_result``).
- Example: `examples/gemini_tools_compress.py`.

## [0.6.7] - 2026-08-22

- **Anthropic tool blocks** — ``tool_use`` / ``tool_result`` content lists round-trip;
  JSON strings in ``tool_result`` (and string ``tool_use.input``) are minified.
- Budget treats a user turn of only ``tool_result`` blocks as the match for the
  preceding assistant ``tool_use`` ids (same pair integrity as OpenAI ``role=tool``).
- Example: `examples/anthropic_tools_compress.py`.

## [0.6.6] - 2026-08-19

- **Protect structured payloads in later stages** — recency no longer LSA-summarizes
  JSON blobs, `` ```json `` fences, or tool turns; repetition will not drop an
  assistant ``tool_calls`` turn (which would orphan ``role=tool`` results);
  resolution will not collapse a thread that still contains tool/JSON turns.
- Chat resolution without tools is unchanged.

## [0.6.5] - 2026-08-19

- **Fenced JSON** — the ``structure`` stage minifies JSON inside markdown code fences
  (`` ```json ``, `` ```JSON ``, unlabeled `` ``` ``) when the body parses as JSON.
  Other languages and invalid JSON are left unchanged.
- Fixture: `tests/fixtures/chats/13_rag_fenced_json.json`.
- Example: `examples/fenced_json_compress.py`.

## [0.6.4] - 2026-08-18

- **OpenAI tool messages** — ``role: tool`` / ``function`` are valid; ``tool_calls``,
  ``tool_call_id``, and ``name`` round-trip on dict messages.
- Structure minifies JSON in ``tool_calls[].function.arguments`` and tool-result content.
- Filler never drops empty assistant turns that only carry ``tool_calls``.
- Budget removes an assistant ``tool_calls`` turn together with matching ``role=tool``
  results (no orphan tool messages).
- Example: `examples/openai_tools_compress.py`.

## [0.6.3] - 2026-08-12

- **LangChain round-trip** — ``compress()`` maps remaining turns back onto their original
  message objects (not list index), so dropped turns no longer remap roles/content.
- **``output_tokens`` on cost stats** — ``attach_cost(output_tokens=...)``,
  ``compress(..., output_tokens=...)``, and ``ContextManager(cost_output_tokens=...)``
  add assumed completion USD; ``summary()`` prints output + total when set.
- Example: `examples/langchain_roundtrip.py`.

## [0.6.2] - 2026-07-27

- **Agent-oriented fixtures** — three offline agent threads under `tests/fixtures/chats/`
  (large tool JSON, repeated log lines, mixed tool call/result trace).
- **`CompressionStats.summary()`** / **`CompressionResult.summary()`** — one-line human-readable
  savings report (tokens, stages, optional USD when ``cost_provider`` is set).
- Example: `examples/agent_json_compress.py`.

## [0.6.1] - 2026-07-26

- **USD on stats** — ``CompressionStats.attach_cost()`` and optional ``cost_provider`` on
  ``ContextManager`` / ``compress()`` fill ``estimated_input_cost_*_usd`` and
  ``estimated_cost_saved_usd`` (included in ``to_dict()``).
- Opt-in only: without ``cost_provider``, cost fields stay ``None``.

## [0.6.0] - 2026-07-26

- **`structure` stage** — early Tier 1 compaction: JSON minify, whitespace tighten, consecutive log-line dedupe (stdlib only).
- **`estimate_cost()`** — approximate USD cost from token counts + bundled provider pricing.
- Presets (low/medium/high) include ``structure``; agent profile uses higher structure aggressiveness.
- [`ROADMAP.md`](ROADMAP.md) — competitive landscape (ideas only) and 0.6.x plan.
- Example: `examples/structure_and_cost.py`.

## [0.5.8] - 2026-07-26

- **Stabilization Phase 4** — fixture-driven fixes:
  - Filler stage cleans orphan commas / leading punctuation after removals.
  - User turns are never dropped when filler removal would empty them.
  - ``compress(None)`` / ``normalize_messages(None)`` raise ``TypeError``.
  - Regression tests for rag_doc (no resolution), resolution fixture, extra dict keys, batch immutability.

## [0.5.7] - 2026-07-26

- **Stabilization Phase 3** — offline chat fixtures under `tests/fixtures/chats/` (8 synthetic threads).
- Fixture smoke tests: compress, input immutability, preview, ``recommend_preset``.
- Documents AUDIT C3 (filler ack vs resolution) with a dedicated fixture.

## [0.5.6] - 2026-07-26

- **Stabilization Phase 2** — low-risk refactors (see [`AUDIT.md`](AUDIT.md)):
  - Shared ``tfidf_cosine`` / ``tfidf_similarity_matrix`` in ``contextpress.text_sim``.
  - ``BudgetStrategy`` uses ``stats.get_encoding`` / ``count_turn_tokens``.
  - NLTK bootstrap drops unused ``stopwords``; warning text fixed.
  - Behavior contract clarifies budget may truncate system as last resort.
  - LLM deduplicate failures now emit a warning (invariant 9).

## [0.5.5] - 2026-07-26

- **Stabilization Phase 1** — codebase audit and prioritized backlog in [`AUDIT.md`](AUDIT.md).
- No runtime API changes; prep for low-risk refactors (0.5.6) and fixture-driven fixes (0.5.7–0.5.8).

## [0.5.4] - 2026-07-25

- **`compress_many()`** — batch ``compress()`` over a list of conversations.
- Example: `examples/agent_pipeline.py` for ``type="agent"`` tool/task threads.

## [0.5.3] - 2026-07-24

- **`recommend_preset()`** — pick the mildest preset (low → medium → high) that fits a token budget.
- **`CompressionStats.token_savings_pct`** — percentage tokens saved; included in ``to_dict()``.
- Example: `examples/pick_preset.py`.

## [0.5.2] - 2026-07-22

- **`OpenAIBackend`** — optional `api_key` / env (`OPENAI_API_KEY`); no manual client required.

## [0.5.1] - 2026-07-22

- **`ClaudeBackend`** — shortcut for Anthropic Claude (`ANTHROPIC_API_KEY` or `api_key=`).
- **`GeminiBackend`** — optional `model_name` + `api_key` / env (`GOOGLE_API_KEY`, `GEMINI_API_KEY`).
- Examples: `examples/llm_tier_claude.py`, `examples/llm_tier_gemini.py`.

## [0.5.0] - 2026-07-22

- **`compress_async()`** — async wrapper around ``compress()`` for asyncio apps.
- **`compare_presets()`** — dry-run low/medium/high on the same messages and compare stats.
- **`CompressionStats.to_dict()` / `CompressionResult.to_dict()`** — JSON-friendly export.
- **`GeminiBackend`** — Google Gemini Tier 2 adapter (optional ``google-generativeai``).
- Example: `examples/benchmark_presets.py`.

## [0.4.0] - 2026-07-20

- **`preview()` / `dry_run=True`** — simulate compression and get stats without changing messages (Tier 1 only; no LLM calls).
- **`fits_budget()`** — check whether messages would fit a token budget after compression.
- **`CompressionStats.warnings_emitted`** — pipeline warnings collected during a run.
- **`OpenAICompatibleBackend`** — vLLM, LM Studio, LocalAI, and other OpenAI-compatible servers.
- Example: `examples/dry_run_preview.py`.

## [0.3.0] - 2026-07-14

- **`estimate_tokens(messages)`** — count tokens before compressing (same tiktoken encoding as budget).
- **Stage registry** — `ContextManager.register_stage()` for custom `BaseStrategy` stages in `stages=[...]`.
- **Tier 2 `llm_mode`** — `replace_all` (default), `dedupe_only`, or `summarize_only`.
- Example: `examples/estimate_and_stats.py`.

## [0.2.0] - 2026-05-24

- **`return_stats=True`** on `ContextManager.compress()` returns a `CompressionResult` with token/turn counts, stages run, and per-stage turn deltas.
- **Tier 2 deduplication** implemented in OpenAI, Anthropic, and Ollama adapters (LLM selects indices to keep).
- **GitHub Actions CI** runs `pytest` on Python 3.10–3.13.
- Added **`CONTRIBUTING.md`** with contribution and review expectations.

## [0.1.0] - 2026-04-19

- Initial release by Taha Azizi.
- Tier 1 pipeline (filler, repetition, resolution, recency, budget) and optional Tier 2 `LLMBackend` (OpenAI, Anthropic, Ollama adapters).
