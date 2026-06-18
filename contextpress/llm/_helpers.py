"""Shared helpers for Tier 2 LLM adapters."""

from __future__ import annotations

import json
import re


def parse_keep_indices(raw: str, n: int) -> list[int]:
    """Parse an LLM response into sorted unique turn indices to keep."""
    if n <= 0:
        return []
    if n == 1:
        return [0]

    text = (raw or "").strip()
    if not text:
        return list(range(n))

    # JSON array: [0, 2, 4]
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return _validate_indices(data, n)
        except json.JSONDecodeError:
            pass

    # Comma / space separated: 0, 2, 4
    nums = re.findall(r"\d+", text)
    if nums:
        return _validate_indices([int(x) for x in nums], n)

    return list(range(n))


def _validate_indices(values: list[int], n: int) -> list[int]:
    valid = sorted({i for i in values if isinstance(i, int) and 0 <= i < n})
    return valid if valid else list(range(n))


def format_numbered_turns(turns: list[str], *, max_chars: int = 800) -> str:
    lines: list[str] = []
    for i, text in enumerate(turns):
        snippet = text.strip().replace("\n", " ")
        if len(snippet) > max_chars:
            snippet = snippet[: max_chars - 3] + "..."
        lines.append(f"{i}: {snippet}")
    return "\n".join(lines)


DEDUP_SYSTEM_PROMPT = (
    "You deduplicate conversation turns. Given numbered turns, return ONLY the 0-based "
    "indices of turns to KEEP as a comma-separated list (example: 0,2,5). "
    "When turns repeat the same idea, keep the most recent index. "
    "Always keep at least one turn. Output nothing else."
)
