# Release notes

Versions are **[SemVer](https://semver.org/)**. The canonical changelog is [`CHANGELOG.md`](CHANGELOG.md). This file is the GitHub-style narrative for maintainers cutting tags.

**Current package version:** `0.7.1`

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
