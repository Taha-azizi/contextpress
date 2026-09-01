"""Dictionary-based wording swaps (lexical synonyms, contractions, wordy phrases).

Lookups are frozen JSON dictionaries built offline under ``contextpress/data/``.
Runtime does not call WordNet. A cheap tiktoken gate drops swaps that fail to
shrink the turn. Multi-word keys are matched longest-first with word boundaries.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from contextpress.models import Conversation
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.text_rewrite import (
    get_encoding,
    keep_if_fewer_tokens,
    map_editable_turns,
    preserve_case,
)

_ENCODING_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_DICT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SUPPORTED_ENCODINGS = ("cl100k_base", "o200k_base")
_KNOWN_DICTS = ("lexical", "contractions", "wordy_phrases")


def _dict_filename(dict_name: str, encoding_name: str) -> str:
    return f"{dict_name}_{encoding_name}.json"


def _load_mapping_json(raw: str, *, label: str) -> dict[str, str]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"contextpress: {label} is not a mapping")
    return {str(k).lower(): str(v) for k, v in data.items()}


@lru_cache(maxsize=16)
def load_rewrite_dict(dict_name: str, encoding_name: str) -> dict[str, str]:
    """Load ``{original: replacement}`` for ``dict_name`` + ``encoding_name``."""
    if not _DICT_NAME_RE.fullmatch(dict_name):
        raise ValueError(f"contextpress: invalid rewrite dict name {dict_name!r}")
    if not _ENCODING_NAME_RE.fullmatch(encoding_name):
        raise ValueError(
            f"contextpress: invalid encoding name {encoding_name!r}; "
            f"expected a tiktoken encoding id such as cl100k_base"
        )
    resource = files("contextpress.data") / _dict_filename(dict_name, encoding_name)
    if not resource.is_file():
        raise FileNotFoundError(
            f"contextpress: no {dict_name!r} dictionary for encoding {encoding_name!r}. "
            f"Bundled encodings: {', '.join(_SUPPORTED_ENCODINGS)}. "
            f"Known dicts: {', '.join(_KNOWN_DICTS)}."
        )
    return _load_mapping_json(
        resource.read_text(encoding="utf-8"),
        label=f"{dict_name}/{encoding_name} dictionary",
    )


def load_lexical_dict(encoding_name: str) -> dict[str, str]:
    """Load the default lexical synonym dictionary (backward-compatible name)."""
    return load_rewrite_dict("lexical", encoding_name)


def load_dict_path(path: str | Path) -> dict[str, str]:
    """Load a rewrite dictionary from an explicit filesystem path."""
    p = Path(path)
    return _load_mapping_json(p.read_text(encoding="utf-8"), label=str(p))


def compile_mapping_pattern(mapping: dict[str, str]) -> re.Pattern[str] | None:
    """Build an IGNORECASE alternation; longer / more-word keys first."""
    if not mapping:
        return None
    keys = sorted(mapping.keys(), key=lambda k: (-len(k.split()), -len(k), k))
    body = "|".join(re.escape(k) for k in keys)
    return re.compile(rf"\b(?:{body})\b", re.IGNORECASE)


def apply_lexical_text(
    text: str,
    mapping: dict[str, str],
    *,
    encoding=None,
    pattern: re.Pattern[str] | None = None,
    allow_equal_tokens: bool = False,
) -> str:
    if not text or not mapping:
        return text
    compiled = pattern if pattern is not None else compile_mapping_pattern(mapping)
    if compiled is None:
        return text

    def _repl(match: re.Match[str]) -> str:
        surface = match.group(0)
        repl = mapping.get(surface.lower())
        if repl is None:
            return surface
        return preserve_case(surface, repl)

    new_text = compiled.sub(_repl, text)
    return keep_if_fewer_tokens(text, new_text, encoding, allow_equal=allow_equal_tokens)


class LexicalCompression(BaseStrategy):
    """Whole-phrase / whole-word swaps from an encoding-specific dictionary.

    ``dict_name`` selects a bundled file (``lexical``, ``contractions``,
    ``wordy_phrases``). ``dict_path`` overrides the bundled file entirely.
    Pass ``allow_equal_tokens=True`` for low-risk dicts (e.g. contractions)
    where equal BPE length is still acceptable.
    """

    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        encoding_name: str = "cl100k_base",
        dict_name: str = "lexical",
        dict_path: str | Path | None = None,
        allow_equal_tokens: bool = False,
        conv_type: str = "chat",
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.encoding_name = encoding_name
        self.dict_name = dict_name
        self.dict_path = Path(dict_path) if dict_path is not None else None
        self.conv_type = conv_type
        self._allow_equal_tokens = bool(allow_equal_tokens)
        if self.dict_path is not None:
            self._mapping = load_dict_path(self.dict_path)
        else:
            self._mapping = load_rewrite_dict(dict_name, encoding_name)
        self._pattern = compile_mapping_pattern(self._mapping)
        self._encoding = get_encoding(encoding_name)

    def process(self, conversation: Conversation) -> Conversation:
        return map_editable_turns(
            conversation,
            lambda text: apply_lexical_text(
                text,
                self._mapping,
                encoding=self._encoding,
                pattern=self._pattern,
                allow_equal_tokens=self._allow_equal_tokens,
            ),
        )
