# Savings study (local)

**Current headline (222 items, 0.6.14 fidelity):** `low` **6.0%** mean token save and **98.4%** weighted fact retention; `medium` **22.7% / 84.8%**; `high` **47.7% / 72.7%**. Details: [`INFO_FIDELITY.md`](INFO_FIDELITY.md). From 0.7.0, `CompressionStats.elapsed_ms` / `elapsed_ms_by_stage` time the same runs.

Tier-1 only (no LLM). Builds a gitignored corpus of **long chats** (many free
HF sources — not only GitHub), **files in the prompt**, and **pretty tool JSON**,
compresses at `low` / `medium` / `high`, records **per-stage token savings**,
then writes:

| Artifact | What |
| --- | --- |
| `benchmarks/RESULTS.md` | Full report: every item × preset + stage breakdown |
| `benchmarks/INFO_FIDELITY.md` | Token savings vs **critical information loss** |
| `benchmarks/results/runs.jsonl` | One row per compression (gitignored) |
| `benchmarks/results/summary.json` | Aggregates (gitignored) |
| `benchmarks/SAVINGS.md` | Shorter marketing brief (in-scope filter) |

## Chat sources (free / public)

- HuggingFaceH4/ultrachat_200k
- OpenAssistant/oasst1 + oasst2
- Aeala/ShareGPT_Vicuna_unfiltered
- philschmid/guanaco-sharegpt-style
- allenai/WildChat-1M (English, long threads)
- LDJnr/Capybara
- Anthropic/hh-rlhf (chosen side)
- glaiveai/glaive-function-calling-v2 (agent tools)
- A few public GitHub issues / Stack Overflow / docs (secondary)

```bash
python -m benchmarks.run_savings --rebuild-corpus
# optional: re-download HF caches
python -m benchmarks.run_savings --rebuild-corpus --refresh

# token savings vs critical / soft information loss
python -m benchmarks.info_fidelity
```

Jev (OpenRouter System One) vs raw, on BoolQ-RAG + QuALITY: [`JEV_STUDY.md`](JEV_STUDY.md).

```bash
python -m benchmarks.run_jev_study
```

`benchmarks/data/` is gitignored (licenses allow local measurement; do not republish user text).
