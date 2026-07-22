# Changelog

All notable changes to `contextpress` are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
