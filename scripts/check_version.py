"""Fail if package version sources disagree.

Usage (from repo root)::

    python scripts/check_version.py
    python scripts/check_version.py --require-tag
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("pyproject.toml: missing version")
    return m.group(1)


def _init_version() -> str:
    text = (ROOT / "contextpress" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("contextpress/__init__.py: missing __version__")
    return m.group(1)


def _changelog_version() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"(?m)^## \[(\d+\.\d+\.\d+)\]", text)
    if not m:
        raise SystemExit("CHANGELOG.md: missing ## [x.y.z] heading")
    return m.group(1)


def _citation_version() -> str:
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    m = re.search(r"(?m)^version:\s*[\"']?([^\"'\s]+)", text)
    if not m:
        raise SystemExit("CITATION.cff: missing version")
    return m.group(1)


def _git_tags() -> set[str]:
    try:
        out = subprocess.check_output(
            ["git", "tag", "-l", "v*"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--require-tag",
        action="store_true",
        help="Fail if git tag v{version} is missing (use at release time).",
    )
    args = p.parse_args(argv)

    versions = {
        "pyproject.toml": _pyproject_version(),
        "contextpress/__init__.py": _init_version(),
        "CHANGELOG.md": _changelog_version(),
        "CITATION.cff": _citation_version(),
    }
    unique = set(versions.values())
    print("version sources:")
    for name, ver in versions.items():
        print(f"  {name}: {ver}")
    if len(unique) != 1:
        print("ERROR: version mismatch", file=sys.stderr)
        return 1
    ver = unique.pop()
    tags = _git_tags()
    expected = f"v{ver}"
    if expected in tags:
        print(f"  git tag: {expected} (present)")
    elif args.require_tag:
        print(f"ERROR: missing git tag {expected}", file=sys.stderr)
        return 1
    else:
        print(f"  git tag: {expected} (not required this run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
