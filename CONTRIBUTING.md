# Contributing to contextpress

Thank you for your interest in contributing. This project is **actively stabilizing**; **0.6.x is stable for Tier 1**. Bug fixes and contract/docs work are welcome; large new surfaces may be better suited to a fork if you need them quickly.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security reports: [SECURITY.md](SECURITY.md).

## Before you start

- Read the [Project Status](README.md#project-status) section in the README.
- Search [existing issues](https://github.com/Taha-azizi/contextpress/issues) before opening a duplicate.
- Expect a **2–4 week** review cycle for pull requests.

## Branches

| Branch | Purpose |
|--------|---------|
| **`dev`** | Active development — **branch from here, open PRs here** |
| **`main`** | Stable releases (merged from `dev` at release time) |

After cloning:

```bash
git checkout dev
```

## How to contribute

1. **Fork** the repository and create a feature branch from **`dev`** (not `main`).
2. **Set up** a local environment:
   ```bash
   pip install -e ".[dev]"
   pytest tests -q
   ```
3. **Make focused changes** — one logical change per PR when possible.
4. **Add or update tests** for behavior you change. Tier 1 tests must stay deterministic (no live LLM calls in `tests/`).
5. **Open a pull request** targeting **`dev`** with:
   - A short summary of *why* the change is needed
   - How you tested it (`pytest tests -q`, etc.)
   - A note if you changed public API (update `CHANGELOG.md`)

## Code guidelines

- Match existing style in the file you edit.
- Do not break the [behavior contract](contextpress/pipeline.py) at the top of `pipeline.py`.
- System turns stay protected; input is never mutated in place.
- Keep Tier 1 deterministic — mock LLM backends in tests.

## Reporting bugs

Open a [GitHub issue](https://github.com/Taha-azizi/contextpress/issues) with:

- Python version
- `contextpress` version (`pip show contextpress`)
- Minimal input that reproduces the problem
- Expected vs actual behavior

## Feature requests

Feature requests may be accepted, deferred, or closed with a suggestion to fork. That is not a rejection of the idea — it reflects a focus on stabilizing Tier 1 rather than expanding scope.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
