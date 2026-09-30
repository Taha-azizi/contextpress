"""Extract and match high-signal fact spans (shared with benchmarks)."""

from __future__ import annotations

import re

_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_FILE = re.compile(
    r"\b[\w./\\-]+\.(?:py|json|md|txt|yml|yaml|toml|js|ts|tsx|jsx|go|rs|java|c|cpp|h)\b",
    re.IGNORECASE,
)
_NUM = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|" r"\b\d+\.\d+(?:\.\d+)*\b|" r"\b\d{3,}\b")
_SNAKE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
_CAMEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b")
_TRAIL_PUNCT = re.compile(r"[.,;:)+]+$")
_CAMEL_SKIP = frozenset(
    {
        "chatgpt",
        "openai",
        "youtube",
        "github",
        "javascript",
        "typescript",
        "postgresql",
        "mongodb",
        "graphql",
        "linkedin",
        "facebook",
        "whatsapp",
    }
)


def _clean_span(span: str) -> str:
    return _TRAIL_PUNCT.sub("", (span or "").strip())


def extract_critical_spans(text: str) -> list[str]:
    """URLs, emails, paths, versions/large numbers, ISO dates, identifiers."""
    found: list[str] = []
    for pattern in (_URL, _EMAIL, _FILE, _NUM, _SNAKE, _CAMEL):
        found.extend(pattern.findall(text))
    seen: set[str] = set()
    out: list[str] = []
    for span in found:
        cleaned = _clean_span(span)
        key = cleaned.casefold()
        if len(key) < 2 or key in seen:
            continue
        if key in _CAMEL_SKIP:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def span_present(span: str, haystack_cf: str) -> bool:
    """True if ``span`` still occurs; digits cannot hide inside a longer number."""
    key = span.casefold()
    if not key:
        return False
    if "://" in key or "@" in key or "/" in key or "\\" in key:
        return key in haystack_cf
    return re.search(rf"(?<![0-9a-z]){re.escape(key)}(?![0-9a-z])", haystack_cf) is not None
