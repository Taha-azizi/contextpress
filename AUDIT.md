# Pre-0.6.0 stabilization audit (0.5.5)

Recorded after the 0.5.x ergonomics arc. This is the Phase 1 deliverable:
findings + backlog for Phases 2–4. Behavior changes are deferred unless marked
**fix now**.

## Architecture (summary)

```
ContextManager (core.py)
  → normalize_messages (normalizer.py)
  → apply_stage_selection (compression.py)
  → Pipeline.run (pipeline.py)
      → structure → filler → repetition → resolution → recency → budget
      → optional Tier 2 LLM
  → denormalize_output
```

Profiles: `chat`, `rag_doc`, `agent`. Tier 1 deps: nltk, scikit-learn, sumy, tiktoken.

## Findings

### Contract / correctness

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| C1 | Medium | Invariant 1 says system turns are untouched; `BudgetStrategy` truncates system as last resort (`budget.py`) | Document in contract (Phase 2) or change behavior later |
| C2 | Medium | LLM dedup failures in `Pipeline._run_llm_tier` fall back silently (no warning); summarize path warns | Add warning (Phase 2) |
| C3 | Low | Filler drops assistant-only ack phrases like `"sounds good"` before resolution (`filler.py` / `resolution.py`) | **By design** — fixture `08_*` + Layer-A still collapses; documented |
| C4 | Low | `Turn.importance` / `Turn.resolved` set by resolution but unused by pipeline | Leave; optional cleanup later |

### Duplication / maintainability (Phase 2)

| ID | Finding | Action |
|----|---------|--------|
| R1 | TF-IDF + cosine similarity copied in `repetition.py`, `recency.py`, `resolution.py` | Extract shared helper |
| R2 | Token counting duplicated in `stats.py` and `budget.py` | Budget uses `stats` helpers |
| R3 | `_bootstrap.py` downloads unused `stopwords`; warning mentions recency (doesn't use NLTK) | Trim packages; fix message |
| R4 | Strategies use ad hoc `deepcopy` vs `clone_turn` | Prefer `clone_turn` where safe — **0.6.9** |

### Test / fixture gaps (Phases 3–4)

| ID | Gap |
|----|-----|
| T1 | No assert that input `messages` are immutable after `compress()` |
| T2 | No end-to-end `rag_doc` / richer `agent` pipeline tests |
| T3 | Normalizer edge cases: `None`, bad types, tuple skip, LangChain turn-count mismatch |
| T4 | No offline real-chat fixtures under `tests/fixtures/` |
| T5 | Cross-stage filler → resolution interaction untested |

### Normalizer fragility (document; fix only if fixtures break)

| ID | Area |
|----|------|
| N1 | LangChain detection heuristic on first list element |
| N2 | Dict/tuple skips change turn count vs input |
| N3 | New turns (RESOLVED / LLM summary) lose `_original_dict` keys |
| N4 | `apply_text_to_turn` only replaces the first text block |

### Deferred (not in 0.5.x stabilization)

- Resolution / normalizer rewrites
- New pipeline stages
- New LLM backends
- New hard dependencies
- Changing stage order without a proven bug

## Phase plan

| Phase | Version | Scope |
|-------|---------|--------|
| 1 Analysis | **0.5.5** | This document + backlog — shipped |
| 2 Refactor | **0.5.6** | R1–R3, C1 doc, C2 warning (no semantic stage changes) — shipped |
| 3 Fixtures | **0.5.7** | Offline chat samples + smoke/invariant tests — shipped |
| 4 Fixes | **0.5.8** | Bugs proven by fixtures + T1–T5 regression tests — shipped |

### Phase 4 outcomes (0.5.8)

| Fix | Detail |
|-----|--------|
| Filler punctuation | Cleanup orphan commas / leading punctuation after phrase removal |
| User filler-only | User turns are not dropped when filler removal empties them |
| `messages=None` | Raises ``TypeError`` (was silently empty) |
| Regression tests | Extra keys, rag_doc skips resolution, resolution fixture, ``compress_many`` immutability |

## Invariants checklist (from `pipeline.py`)

1. System turns pass through stages untouched — **except** budget last-resort truncation (C1).
2. Input never mutated — enforced by clones; **needs T1**.
3. Output format mirrors input — denormalize; weaker after turn collapse.
4. Last 3 non-system not compressed by recency — unit tested.
5. Last 2 non-system not removed by budget — unit tested.
6. Resolution (chat) needs both sides — unit tested; C3 may weaken signals.
7. Repetition: more recent wins — unit tested.
8. Tier 1 deterministic — assumed; sumy/NLTK have fallbacks.
9. LLM failure → Tier 1 + warning — summarize yes; dedup **C2**.
10. `token_budget=None` skips budget enforcement — OK.
11–12. Presets + Tier 2 modes — covered by existing tests.
