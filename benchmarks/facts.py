"""Critical facts and the adjusted save used by every benchmark report.

Information loss is the share of critical facts that disappear. A critical
fact is a content word from the asked sentence (filler words excluded), a
distinct number, or a two-word name whose words sit on the same line.
The chat fidelity study uses its own critical-fact set (numbers, URLs,
paths, identifiers) and the same subtraction.

Adjusted save = token save − critical information loss.
"""

from __future__ import annotations

import re
from typing import Any

from contextpress.strategies.filler import FILLER_PHRASES

_NAME = re.compile(r"(?<![A-Za-z])[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+(?![A-Za-z])")
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[A-Za-z']+")
FILLER_TOKENS = frozenset(
    token.lower() for phrase in FILLER_PHRASES for token in _WORD.findall(phrase)
)


def names(text: str) -> list[str]:
    """Two-word capitalized phrases. Newlines do not join the words."""
    return list(dict.fromkeys(_WS.sub(" ", hit) for hit in _NAME.findall(text)))


def names_kept(name_list: list[str], body: str) -> int:
    flat = _WS.sub(" ", body)
    return sum(1 for name in name_list if name in flat)


def fact_adjusted(token_save_pct: float, info_loss_pct: float) -> float:
    """Token save minus critical-information loss. Can be negative."""
    return float(token_save_pct) - float(info_loss_pct)


def pooled_loss(rows: list[dict[str, Any]], pairs: tuple[tuple[str, str], ...]) -> float | None:
    kept = 0
    total = 0
    for row in rows:
        for kept_key, total_key in pairs:
            kept += int(row[kept_key])
            total += int(row[total_key])
    if total <= 0:
        return None
    return 100.0 * (1.0 - kept / total)
