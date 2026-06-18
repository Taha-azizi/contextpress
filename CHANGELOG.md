# Changelog

All notable changes to `contextpress` are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-24

- **`return_stats=True`** on `ContextManager.compress()` returns a `CompressionResult` with token/turn counts, stages run, and per-stage turn deltas.
- **Tier 2 deduplication** implemented in OpenAI, Anthropic, and Ollama adapters (LLM selects indices to keep).
- **GitHub Actions CI** runs `pytest` on Python 3.10–3.13.
- Added **`CONTRIBUTING.md`** with contribution and review expectations.

## [0.1.0] - 2026-04-19

- Initial release by Taha Azizi.
- Tier 1 pipeline (filler, repetition, resolution, recency, budget) and optional Tier 2 `LLMBackend` (OpenAI, Anthropic, Ollama adapters).
