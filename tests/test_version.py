from __future__ import annotations

import runpy
from pathlib import Path

import contextpress

ROOT = Path(__file__).resolve().parents[1]


def test_dunder_version_matches_check_script() -> None:
    ns = runpy.run_path(str(ROOT / "scripts" / "check_version.py"))
    assert contextpress.__version__ == ns["_pyproject_version"]()
    assert contextpress.__version__ == ns["_changelog_version"]()
    assert contextpress.__version__ == ns["_citation_version"]()
