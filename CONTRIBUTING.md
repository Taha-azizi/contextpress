# Contributing to contextpress

Thank you for your interest in contributing. This project is maintained by [Taha Azizi](https://github.com/Taha-azizi) at a **low cadence**. Bug fixes are welcome; large feature work may be better suited to a fork if you need it quickly.

## Before you start

- Read the [Project Status](README.md#project-status) section in the README.
- Search [existing issues](https://github.com/Taha-azizi/contextpress/issues) before opening a duplicate.
- Expect a **2–4 week** review cycle for pull requests.

## How to contribute

1. **Fork** the repository and create a branch from `main`.
2. **Set up** a local environment:
   ```bash
   pip install -e ".[dev]"
   pytest tests -q
   ```
3. **Make focused changes** — one logical change per PR when possible.
4. **Add or update tests** for behavior you change. Tier 1 tests must stay deterministic (no live LLM calls in `tests/`).
5. **Open a pull request** with:
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

Feature requests may be accepted, deferred, or closed with a suggestion to fork. That is not a rejection of the idea — it reflects limited maintenance bandwidth.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
