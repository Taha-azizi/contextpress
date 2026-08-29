"""Convert multi-word written numbers into digits (opt-in stage).

Only phrases of **two or more** consecutive number-words are rewritten, so
single words like ``one`` / ``two`` (pronouns, idioms) are left alone. Skips
system / JSON / tool turns via ``map_editable_turns``.
"""

from __future__ import annotations

import re

from contextpress.models import Conversation
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.text_rewrite import (
    get_encoding,
    keep_if_fewer_tokens,
    map_editable_turns,
)

_UNITS: dict[str, int] = {
    "zero": 0,
    "oh": 0,
    "nought": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_SCALES: dict[str, int] = {
    "hundred": 100,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}
_NUMBER_WORDS = frozenset(_UNITS) | frozenset(_TENS) | frozenset(_SCALES)
_NUM_ALT = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_ATOM = rf"(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?"
# Only known number-words (2+), optional "and", optional hyphenated tens-units.
_NUMBER_PHRASE = re.compile(
    rf"\b{_ATOM}(?:\s+(?:and\s+)?{_ATOM})+\b",
    re.IGNORECASE,
)


def _split_tokens(phrase: str) -> list[str]:
    raw = phrase.lower().replace("-", " ").split()
    return [t for t in raw if t != "and"]


def _is_number_phrase(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return False
    return all(t in _UNITS or t in _TENS or t in _SCALES for t in tokens)


def parse_number_words(phrase: str) -> int | None:
    """Parse a multi-word English number phrase into an int, or None."""
    tokens = _split_tokens(phrase)
    if not _is_number_phrase(tokens):
        return None
    total = 0
    current = 0
    for tok in tokens:
        if tok in _UNITS:
            current += _UNITS[tok]
        elif tok in _TENS:
            current += _TENS[tok]
        elif tok in _SCALES:
            scale = _SCALES[tok]
            if current == 0:
                current = 1
            current *= scale
            if scale >= 1000:
                total += current
                current = 0
        else:
            return None
    return total + current


def apply_number_normalize(text: str, *, encoding=None) -> str:
    if not text:
        return text

    def _repl(match: re.Match[str]) -> str:
        surface = match.group(0)
        tokens = _split_tokens(surface)
        if not _is_number_phrase(tokens):
            return surface
        value = parse_number_words(surface)
        if value is None:
            return surface
        return str(value)

    new_text = _NUMBER_PHRASE.sub(_repl, text)
    # Digits are shorter text even when BPE length ties the written form.
    return keep_if_fewer_tokens(text, new_text, encoding, allow_equal=True)


class NumberNormalizeStrategy(BaseStrategy):
    """Rewrite multi-word number phrases to digits when that saves tokens."""

    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        encoding_name: str = "cl100k_base",
        conv_type: str = "chat",
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.encoding_name = encoding_name
        self.conv_type = conv_type
        self._encoding = get_encoding(encoding_name)

    def process(self, conversation: Conversation) -> Conversation:
        return map_editable_turns(
            conversation,
            lambda text: apply_number_normalize(text, encoding=self._encoding),
        )
