# Notes for agents and contributors

## Where things live

| Area | Path |
|------|------|
| Public API | `contextpress/core.py` → `ContextManager` |
| I/O formats | `contextpress/normalizer.py` |
| Stage presets | `contextpress/compression.py` (`STAGE_ORDER`, `VALID_STAGES`) |
| Tier 1 stages | `contextpress/strategies/*.py` |
| Tier 2 | `contextpress/llm/` (`LLMBackend`, `adapters.py`) |
| Orchestration | `contextpress/pipeline.py` (behavior contract at top of file) |
| Profiles | `contextpress/profiles.py` |

`contextpress/__init__.py` lazy-loads `ContextManager` so `from contextpress.models import Turn` avoids pulling optional Tier-2 / sumy import chains when possible.

## Commands

```bash
pip install -e ".[dev]"
pytest tests -q
```

## Invariants (non-negotiable)

See the numbered block at the top of `contextpress/pipeline.py`. Tests assume Tier 1 is deterministic (no live LLM calls in `tests/`).

## Adding a stage

1. Subclass `BaseStrategy`, implement `process`.
2. Register it in `Pipeline._build_strategy`.
3. Add the name to `compression.STAGE_ORDER` and presets if it should be user-selectable.
4. Extend `profiles.Profile` / `PROFILES` if it needs per-type defaults.
