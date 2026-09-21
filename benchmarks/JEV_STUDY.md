# Jev × Contextpress study

**Registered before any Jev calls.** Results are appended below after the run.

## Access check (2026-09-20)

| Item | Value |
|------|--------|
| Available | Yes |
| Model id | `typesafe/jev-1.13` (alias `jev-1.13`; latest `~typesafe/jev-latest`) |
| Endpoint | `POST https://openrouter.ai/api/v1/systemone` (not chat completions) |
| Price | **$0.042 / 1M input**, **$0 / 1M output** ([OpenRouter](https://openrouter.ai/typesafe/jev-1.13)) |
| Context | 32k tokens |
| What it is | Structured **decisions** (`noul` / `choice` / `score`), not free-form answers |

The hypothesis that “output is free, so every removed input token is a bill saving” matches posted list prices. Whether Contextpress is a **huge win** still depends on how much input it cuts **and** whether Jev’s labelled accuracy falls.

## Hypothesis (split)

1. **Cost** — Jev bills input only. Compressing the file/RAG payload reduces billed tokens and `usage.cost`.
2. **Effectiveness on files/RAG** — Contextpress cuts a *useful* share of those tokens while Jev still matches the gold labels.

## Design choices

| Choice | What | Why |
|--------|------|-----|
| Datasets | **BoolQ + distractors** (RAG) and **QuALITY** (long file). Fallback: **SciFact** abstracts if QuALITY is unavailable. | Open, labelled, file/RAG-shaped. Jev is a decision model, so tasks must be yes/no or multiple-choice — not extractive spans. |
| BoolQ RAG (run 1) | Gold + 4 distractors **concatenated into one body turn**. | Invalid: recency/trim never fire on 2 turns. |
| BoolQ RAG (run 2) | Gold + **8 distractors as separate turns**, gold last, question last. | Real RAG packing; last-3 recency guard keeps the gold. |
| QuALITY (run 1) | Whole article as **one** turn (12k cap). | Same 2-turn no-op. |
| QuALITY (run 2) | Article split into **≥8 section turns**. | Trim can drop the middle; recency can shorten early sections. |
| `type` | `rag_doc` | File/chunk profile: no lexical/abbrev/alias/resolution; recency is query-relevance. |
| Presets | `raw` (no Contextpress), `low`, `medium`, `high` | Same product surface as the 0.6.14 fidelity tables. `token_budget=None` so budget truncation is not counted as savings. |
| n (run 1) | 40 + 40 | Invalid packing; do not use for preset comparison. |
| n (run 2) | **60** BoolQ-RAG + **60** QuALITY = **120 items** × 4 = **480** Jev calls. | Larger sample after the packing fix. |
| Compression target | Document body only | Matches “files stuffed into the prompt”; keeps the decision question identical. |
| Token / $ | OpenRouter `usage.input_tokens` and `usage.cost` | Ground truth for Jev’s bill, not only tiktoken. |
| Fact loss | Same factoid method as [`INFO_FIDELITY.md`](INFO_FIDELITY.md) on the document body | Comparable to the 0.6.14 file numbers. |
| Decision quality | Accuracy vs labels. noul: `noul ≥ 0.5` → yes. choice: argmax. **Loss = acc(raw) − acc(preset)** in percentage points. | What the user asked. |
| Stats | Mean/median token save; weighted fact loss; accuracy + **McNemar** (paired raw vs preset); Wilson 95% CI on accuracies. | Paired items; report null/negative as clearly as positive. |

## Pass criteria (locked before the run)

| Claim | Pass if | Fail if |
|-------|---------|---------|
| **H-cost** | Mean billed-input save **≥ 5%** on the file/RAG mix at `low` **or** `medium`, and mean `usage.cost` falls. | Save &lt; 5% or cost does not fall. |
| **H-facts (`low`)** | Weighted critical-fact loss **≤ 5%** on `low` (0.6.14 files were 0%). | Loss &gt; 5% on `low`. |
| **H-decision (`low`)** | Accuracy drop **&lt; 3 pp** vs raw (and 95% CI for the drop includes 0 **or** McNemar p ≥ 0.05). | Drop ≥ 3 pp. |
| **H-decision (`medium`)** | Accuracy drop **&lt; 8 pp**. | Drop ≥ 8 pp. |
| **Huge win** | H-cost **and** H-decision pass at a preset with **≥ 20%** mean billed-input save. | Cost save without a 20% cut, or a 20%+ cut that fails H-decision. |

`high` is reported but **not** required for “huge win” (trim/recency on long files is expected to drop mid-document facts).

## Design correction (before run 2)

Run 1 stuffed each item as **question + one concatenated body**. Contextpress recency never rewrites the last 3 non-system turns, and trim keeps the head and last 3. With only two user turns, `medium` and `high` could not do extra work, so savings matched `low`. That is a packing bug, not a product fact.

Run 2 (this correction is registered before those Jev calls) uses **multi-chunk threads** so the three presets can diverge. Pass criteria above are unchanged.

## How to re-run

```bash
# OPEN_ROUTER_API_KEY in the environment or .env
python -m benchmarks.run_jev_study
# re-aggregate without calling Jev
python -m benchmarks.run_jev_study --from-jsonl
```

Raw rows: `benchmarks/results/jev_study.jsonl` (gitignored).

---

## Run 1 results (invalid packing — do not use for preset comparison)

Run date: 2026-09-20. Served model: `typesafe/jev-1.13-20260917`. 80 items × 4 conditions in 205s. Two user turns per item, so recency/trim were no-ops and `low`=`medium`=`high`.

Corpus: BoolQ RAG n=40; QuALITY n=40; replay pairing by run order

### Verdict vs pre-registered criteria

| Claim | Result |
|-------|--------|
| **H-cost** | **FAIL** |
| **H-facts (low)** | **PASS** |
| **H-decision (low)** | **PASS** |
| **H-decision (medium)** | **PASS** |
| **Huge win** | **FAIL** |

### Overall

| Preset | Billed save | Fact loss | Acc | Acc drop | McNemar p | Mean $ |
|--------|------------:|----------:|----:|---------:|----------:|-------:|
| `raw` | — | — | 83.8% [74.2, 90.2] | — | — | $0.000089 |
| `low` | 4.9% | 0.0% | 83.8% [74.2, 90.2] | 0.00 pp | 1.000 | $0.000085 |
| `medium` | 4.9% | 0.0% | 83.8% [74.2, 90.2] | 0.00 pp | 1.000 | $0.000085 |
| `high` | 4.9% | 0.0% | 83.8% [74.2, 90.2] | 0.00 pp | 1.000 | $0.000085 |

### By bucket

| Bucket | `low` save → fact → acc drop | `medium` | `high` |
|--------|------------------------------|----------|--------|
| file | 6.1% → 0.0% → 0.0 pp | 6.1% → 0.0% → 0.0 pp | 6.1% → 0.0% → 0.0 pp |
| rag | 0.73% → 0.0% → 0.0 pp | 0.73% → 0.0% → 0.0 pp | 0.73% → 0.0% → 0.0 pp |

### Plain reading

- **Billing:** Jev list price is input-only. `usage.cost` moved with input tokens; output tokens were unused for the bill.
- **Overall save:** billed input fell **4.87%** at `low`/`medium`/`high` (same bodies on `rag_doc`). That is **below** the ≥20% huge-win bar and **misses** the ≥5% H-cost bar.
- **Decisions:** accuracy drop **0.0 pp** vs raw; McNemar p=1.0. Contextpress did not change labelled accuracy on this sample.
- **Facts:** weighted critical-fact loss **0.0%** at `low`.
- **RAG (BoolQ):** billed save **0.73%**, fact loss 0.0%, acc drop 0.0 pp.
- **Files (QuALITY):** billed save **6.1%**, fact loss 0.0%, acc drop 0.0 pp.
- **Why presets tied:** packing bug (2 turns). Not a product finding.

### How to read this

- **Billed save** uses OpenRouter `usage.input_tokens` vs the raw call.
- **Acc drop** is `acc(raw) − acc(preset)` in points. Negative means compression helped.
- **McNemar p** ≥ 0.05: we cannot reject “no accuracy change.”
- Null and negative results use the same verdict table as passes.

List price used for planning: $0.042/1M input, $0 output. Actual billed $ is `usage.cost`.

## Results

Run date: 2026-09-20. Served model: `typesafe/jev-1.13-20260917`. 120 items × 4 conditions in 395s.

Corpus: BoolQ RAG n=60; QuALITY n=60

### Verdict vs pre-registered criteria

| Claim | Result |
|-------|--------|
| **H-cost** | **PASS** |
| **H-facts (low)** | **PASS** |
| **H-decision (low)** | **PASS** |
| **H-decision (medium)** | **PASS** |
| **Huge win** | **FAIL** |

### Overall

| Preset | Billed save | Fact loss | Acc | Acc drop | McNemar p | Mean $ |
|--------|------------:|----------:|----:|---------:|----------:|-------:|
| `raw` | — | — | 80.8% [72.9, 86.9] | — | — | $0.000103 |
| `low` | 3.6% | 0.0% | 80.8% [72.9, 86.9] | 0.00 pp | 1.000 | $0.000099 |
| `medium` | 44.1% | 30.4% | 77.5% [69.2, 84.0] | 3.33 pp | 0.344 | $0.000058 |
| `high` | 66.2% | 67.2% | 72.5% [63.9, 79.7] | 8.33 pp | 0.021 | $0.000035 |

### By bucket

| Bucket | `low` save → fact → acc drop | `medium` | `high` |
|--------|------------------------------|----------|--------|
| file | 4.72% → 0.0% → 0.0 pp | 51.69% → 52.23% → 6.67 pp | 72.65% → 81.53% → 15.0 pp |
| rag | 1.37% → 0.0% → 0.0 pp | 28.33% → 26.34% → 0.0 pp | 52.59% → 64.48% → 1.67 pp |

### Plain reading

- **Billing:** Jev list price is input-only. `usage.cost` moved with input tokens.
- **`low`:** billed save **3.63%**, fact loss **0.0%**, acc drop **0.0 pp**.
- **`medium`:** billed save **44.12%**, fact loss **30.42%**, acc drop **3.33 pp** (McNemar p=0.3438).
- **`high`:** billed save **66.15%**, fact loss **67.17%**, acc drop **8.33 pp** (McNemar p=0.0213).
- **RAG:** `low` 1.37% / 0.0 pp; `medium` 28.33% / 0.0 pp.
- **Files:** `low` 4.72% / 0.0 pp; `medium` 51.69% / 6.67 pp.
- **Presets are not tied** when the prompt is packed as many document turns. They only matched in run 1 because that run used two turns.

### How to read this

- **Billed save** uses OpenRouter `usage.input_tokens` vs the raw call.
- **Acc drop** is `acc(raw) − acc(preset)` in points. Negative means compression helped.
- **McNemar p** ≥ 0.05: we cannot reject “no accuracy change.”
- Null and negative results use the same verdict table as passes.

List price used for planning: $0.042/1M input, $0 output. Actual billed $ is `usage.cost`.

Re-run: `python -m benchmarks.run_jev_study`
