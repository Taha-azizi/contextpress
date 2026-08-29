# Savings study (local)

Tier-1 only (no LLM). Builds a gitignored corpus of **long chats** (many free
HF sources — not only GitHub), **files in the prompt**, and **pretty tool JSON**,
compresses at `low` / `medium` / `high`, records **per-stage token savings**,
then writes:

| Artifact | What |
| --- | --- |
| `benchmarks/RESULTS.md` | Full report: every item × preset + stage breakdown |
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
```

`benchmarks/data/` is gitignored (licenses allow local measurement; do not republish user text).
