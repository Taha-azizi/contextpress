# Release notes

Versions are **[SemVer](https://semver.org/)**. The canonical changelog is [`CHANGELOG.md`](CHANGELOG.md). This file is the GitHub-style narrative for maintainers cutting tags.

**Current package version:** `0.7.7`

Sources that must match before a PyPI upload (CI runs `python scripts/check_version.py`):

| Source | Field |
|--------|--------|
| `pyproject.toml` | `[project] version` |
| `contextpress/__init__.py` | `__version__` |
| `CHANGELOG.md` | latest `## [x.y.z]` heading |
| `CITATION.cff` | `version` |
| git tag | `v{version}` on the release commit |
| PyPI | `pip index versions contextpress` |

Do not retag `main`/`dev` from a machine that has not verified the table above.

---

## 0.7.7 — 2026-10-04

### Why this release

0.7.6 pins names on their own line, but every other critical span still shares one cap of 40. A pasted chapter drops more than 40 numbers, so the rest never appear. Numbers are short. URLs are not.

### Changes

- `rag_doc` `medium` / `high`: numbers, decimals, and ISO dates pin up to **120**. URLs, emails, paths, and identifiers stay at **40**.
- One `Kept figures:` line. Numbers come first.
- `Kept names:` stays capped at **40**.
- Chat and agent still do not pin.

On the 12-work long-prose corpus, monolith 20k `high` passage numbers went from **84.0% to 100%** and mean save stayed **98.0%**. Chunked 8k `high` numbers are **100%** at **61.4%** save (names **89.6%**, anchor **95.2%**). Chunked 20k `high` numbers are **100%** at **79.3%** save (names **73.2%**).

Tag: `v0.7.7` (local until published)

---

## 0.7.6 — 2026-09-30

### Why this release

0.7.5 pins numbers, URLs, paths, dates, and ids. It does not pin the two-word names the long-prose study counts. On chunked `high` those names were kept at **44.7%** (8k) and **33.3%** (20k). Putting them on the figure line would take slots away from numbers.

### Changes

- `rag_doc` `medium` / `high`: dropped two-word names are appended once, on the same turn as `Kept figures:`.
- The line is `Kept names: Ada Lovelace; John Smith`. Cap **40**, separate from the figure cap.
- A name already present in the output is not repeated. A newline does not form a name.
- Chat and agent still do not pin.

On the 12-work long-prose corpus, chunked 8k `high` name retention went from **44.7% to 89.6%** at **61.5%** mean save (numbers **95.6%**, anchor **95.2%**). Chunked 20k `high` names went from **33.3% to 73.2%** at **79.3%** save. Monolith 20k `high` names went from **2.1% to 45.8%**. Passage-number retention is the same as 0.7.5.

Tag: `v0.7.6` (local until published)

---

## 0.7.5 — 2026-09-29

### Why this release

Chunked `high` finally kept the asked section (0.7.4) but still dropped most passage numbers sitting in trimmed or sentence-cut prose. Reviewers read that as “high deletes the document.” Re-stuffing the dropped text would erase the savings; pinning the numeric spans does not.

### Changes

- `rag_doc` `medium` / `high` only: after trim, recency, or long-turn cuts, missing critical spans are listed once on the trim stub or a compressed turn (`Kept figures: …`, cap **40**).
- ``CompressionStats.pinned_fact_count`` for observability. Chat/agent stay at 0.
- Shared span extraction lives in ``contextpress.critical_spans`` (benchmarks import the same helpers).

### Measured (12-work long-prose corpus)

- Chunked 8k `high`: mean save **62.4%**, anchor **95.2%**, passage numbers **95.6%** (numbers were **49.2%** on 0.7.4).
- Chunked 20k `high`: mean save **80.0%**, anchor **96.3%**, passage numbers **94.1%** (was **42.0%**).
- Question turn byte-identical **204/204**.

Tag: `v0.7.5` (local until published)

---

## 0.7.4 — 2026-09-27

### Why this release

On chunked documents, `high` deleted the middle of the passage, which is often the section the question asked about. Filler also rewrote filler words inside that question.

### Changes

- `rag_doc` filler leaves the last user turn unchanged.
- `rag_doc` trim keeps a middle turn when its best sentence has TF-IDF cosine ≥ 0.3 against that question, then still drops the other middle turns.
- Chat and agent behavior is unchanged.

On the 12-work long-prose corpus, the question is byte-identical in **204/204** runs. Chunked 8k `high` anchor retention went from **69.5% to 95.5%** while mean save stayed at **62.8%** (floor was 40%). Chunked 20k `high` anchor retention went from **43.9% to 96.7%** with mean save **80.2%** (floor was 50%).

Tag: `v0.7.4` (local until published)

---

## 0.7.3 — 2026-09-27

### Why this release

A chapter pasted as one user message never reached recency or trim, so `medium` and `high` saved the same ~6% as `low`. The long-prose study set the gate: move that pasted-chapter row without moving chunked sections.

### Changes

- `rag_doc` `medium` / `high`: turns over 1,500 cl100k tokens, except the last user turn, keep query-matching sentences (cosine ≥ 0.3) plus a lead. `medium` fills to about one third of the sentences (four-sentence lead). `high` keeps a two-sentence lead and the matches.
- `low`, chat, and agent presets are unchanged. Shorter turns still use turn-level recency.

On the 12-work long-prose corpus, monolith 8k `medium` mean save went from **6.1% to 57.2%** with **100%** anchor-word retention. Monolith 20k `high` is **99.1%** save and **94.3%** anchor retention. Chunked 8k `medium` median stayed **10.4%**. `high` drops figures that sit outside the kept sentences (20k monolith number retention **0.4%**). Pinning those spans is 0.7.5.

Tag: `v0.7.3` (local until published)

---

## 0.7.2 — 2026-09-23

### Why this release

While 0.7.0 and 0.7.1 optimized lexical and alias stages, recency summarization was repeatedly instantiating `Tokenizer("english")` and loading NLTK punkt tables on every summarized turn (~40 ms each). Caching these components drops per-turn summarization to ~0.8 ms.

### Changes

- Cache Sumy tokenizer and LSA summarizer components on first import in `recency`.
- Precompile alias replacement regex patterns across turns and optimize word extraction.
- Precompile filler cleanup regex patterns.
- Add `CompressionStats.tokens_per_second` for compression throughput tracking.
- Add regression test for input messages immutability (AUDIT T1).

Tag: `v0.7.2` (local until published)

---

## 0.7.1 — 2026-09-22

### Why this release

The 0.7.0 lexical fix exposed the next costs on repeated production calls:
alias candidate validation repeated the same string work, bundled rewrite plans
were rebuilt for every compression, and stage statistics re-tokenized unchanged
cloned turns after every stage.

### Changes

- Fuse alias candidate validation without changing which phrases qualify.
- Cache immutable bundled lexical plans by dictionary + tokenizer encoding.
- Reuse exact per-turn token counts within one pipeline run.

On the cached 222-item corpus, 888 compressions fell from **216s to 39s** on the
same machine. Median `low` latency fell from ~280ms to ~34ms; `medium` from
~312ms to ~68ms; `high` from ~299ms to ~56ms. Token savings are unchanged apart
from small pre-existing extractive-summary variation.

Tag: `v0.7.1` (local until published)

---

## 0.7.0 — 2026-09-17

### Why this release

Profiling (not the earlier “recount tokens / reuse TF-IDF” guess) showed the **lexical** stage compiling ~20k unigrams into one regex (~200 ms per few-KB turn). `return_stats` vs not was a wash. Sumy LSA is real (~15–30 ms per summarized turn) but is not the `low` preset.

### Changes

- Lexical unigrams: word-boundary **hash lookup**. Multi-word dicts unchanged.
- `CompressionStats.elapsed_ms` and `elapsed_ms_by_stage`.
- NLTK bootstrap only when resolution runs; Sumy imported only when recency summarizes.
- TF-IDF cosine via `linear_kernel` (L2-normalized, same scores).

No new stages. Token-save / fact-retention tables from 0.6.14 still apply.

Tag: `v0.7.0` (local until published)

---

## 0.6.14 — 2026-09-16

**Docs / measurement.** README and [`benchmarks/INFO_FIDELITY.md`](benchmarks/INFO_FIDELITY.md) publish the post-0.6.13 numbers: `medium` is recency (not trim). Overall: **low 6.0% save / 1.6% fact loss**; **medium 22.7% / 15.2%**; **high 47.7% / 27.3%**, plus chat / rag_doc / agent splits.

Tag: `v0.6.14` · PyPI: `contextpress==0.6.14`

---

## 0.6.13 — 2026-09-14

### Why this release

`trim` on **medium** was collapsing the middle of long chats, so “medium” looked like “high” on token save **and** fact loss (~48% tokens / ~27% facts). That was the wrong default for people who wanted recency without deleting mid-thread turns.

### Changes

- **`medium` no longer runs `trim`.** Preset is wording stages + **recency**. Opening turns and the last three non-system turns stay; older leftover turns may still be shortened.
- **`trim` stays on `high`**, or via `stages=["trim", ...]`.
- **Prompt caching:** re-compressing a full history can bust exact-prefix caches and raise cost. Added `compare_cache_tradeoff()` to compare cached-raw vs compressed-uncached effective input tokens.
- README documents cache-safe patterns (compress the tail, compact once then append).

### Upgrade notes

- If you depended on medium dropping the middle of the thread, pass `compression="high"` or include `"trim"` in `stages=`.
- `low` is unchanged (wording only).
- After this release, do not quote the old “medium ≈ 47% tokens” figure; use the 0.6.14 fidelity tables.

Tag: `v0.6.13` · PyPI: `contextpress==0.6.13`
