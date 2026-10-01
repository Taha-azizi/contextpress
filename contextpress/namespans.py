"""Two-word capitalized names. A newline does not join the words."""

from __future__ import annotations

import re

_NAME = re.compile(r"(?<![A-Za-z])[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+(?![A-Za-z])")
_WS = re.compile(r"\s+")


def extract_names(text: str) -> list[str]:
    """Unique names, first-seen order. Words must sit on the same line."""
    return list(dict.fromkeys(_WS.sub(" ", hit) for hit in _NAME.findall(text)))


def name_present(name: str, text: str) -> bool:
    return name in _WS.sub(" ", text)
