"""Replace common long forms with standard abbreviations."""

from __future__ import annotations

import re

import tiktoken

from contextpress.models import Conversation
from contextpress.strategies.abbrev_dict import ABBREVIATIONS
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.text_rewrite import (
    get_encoding,
    keep_if_fewer_tokens,
    map_editable_turns,
    preserve_case,
)

# Longest keys first so "that is to say" wins over "that is".
_ABBREV_ITEMS: tuple[tuple[str, str], ...] = tuple(
    sorted(ABBREVIATIONS.items(), key=lambda kv: len(kv[0]), reverse=True)
)
_ABBREV_RE = re.compile(
    "|".join(rf"\b{re.escape(src)}\b" for src, _ in _ABBREV_ITEMS),
    re.IGNORECASE,
)
_LOOKUP = {src: dst for src, dst in _ABBREV_ITEMS}


def _format_abbrev(src: str, dst: str) -> str:
    if not dst.isalpha():
        return dst.upper() if src.isupper() else dst
    if src.isupper():
        return dst.upper()
    if src.islower():
        return dst.lower()
    # Title / mixed multi-word → keep dictionary form (usually ALLCAPS abbr).
    if dst.isupper() or len(dst) <= 5:
        return dst
    return preserve_case(src.split()[0], dst)


def apply_abbreviations(text: str, *, encoding: tiktoken.Encoding | None = None) -> str:
    if not text:
        return text

    def _repl(match: re.Match[str]) -> str:
        src = match.group(0)
        dst = _LOOKUP.get(src.lower())
        if dst is None:
            return src
        return _format_abbrev(src, dst)

    new_text = _ABBREV_RE.sub(_repl, text)
    return keep_if_fewer_tokens(text, new_text, encoding)


class AbbreviationStrategy(BaseStrategy):
    """Whole-phrase abbreviation swaps from a frozen ~300-entry dictionary."""

    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        encoding_name: str = "cl100k_base",
        conv_type: str = "chat",
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type
        self.encoding_name = encoding_name
        self._encoding = get_encoding(encoding_name)

    def process(self, conversation: Conversation) -> Conversation:
        return map_editable_turns(
            conversation,
            lambda text: apply_abbreviations(text, encoding=self._encoding),
        )
