"""Replace multi-token words with fewer-token same-POS near-synonyms.

Lookups are a frozen JSON dictionary built offline
(``scripts/build_lexical_dict.py``). Runtime does not call WordNet. A cheap
tiktoken gate drops swaps that fail to shrink the turn.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files

from contextpress.models import Conversation
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.text_rewrite import (
    get_encoding,
    keep_if_fewer_tokens,
    map_editable_turns,
    preserve_case,
)

_ENCODING_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_WORD_RE = re.compile(r"\b[A-Za-z]{4,}\b")
_SUPPORTED = ("cl100k_base", "o200k_base")


def _dict_filename(encoding_name: str) -> str:
    return f"lexical_{encoding_name}.json"


@lru_cache(maxsize=8)
def load_lexical_dict(encoding_name: str) -> dict[str, str]:
    """Load ``{original: replacement}`` for ``encoding_name`` (lowercase keys)."""
    if not _ENCODING_NAME_RE.fullmatch(encoding_name):
        raise ValueError(
            f"contextpress: invalid lexical encoding name {encoding_name!r}; "
            f"expected a tiktoken encoding id such as cl100k_base"
        )
    resource = files("contextpress.data") / _dict_filename(encoding_name)
    if not resource.is_file():
        raise FileNotFoundError(
            f"contextpress: no lexical dictionary for encoding {encoding_name!r}. "
            f"Bundled encodings: {', '.join(_SUPPORTED)}. "
            "Rebuild with: python scripts/build_lexical_dict.py"
        )
    raw = resource.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"contextpress: lexical dictionary for {encoding_name!r} is not a mapping")
    return {str(k).lower(): str(v) for k, v in data.items()}


def apply_lexical_text(
    text: str,
    mapping: dict[str, str],
    *,
    encoding=None,
) -> str:
    if not text or not mapping:
        return text

    def _repl(match: re.Match[str]) -> str:
        word = match.group(0)
        repl = mapping.get(word.lower())
        if repl is None:
            return word
        return preserve_case(word, repl)

    new_text = _WORD_RE.sub(_repl, text)
    return keep_if_fewer_tokens(text, new_text, encoding)


class LexicalCompression(BaseStrategy):
    """Whole-word synonym swaps from an encoding-specific dictionary."""

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
        self._mapping = load_lexical_dict(encoding_name)
        self._encoding = get_encoding(encoding_name)

    def process(self, conversation: Conversation) -> Conversation:
        return map_editable_turns(
            conversation,
            lambda text: apply_lexical_text(text, self._mapping, encoding=self._encoding),
        )
