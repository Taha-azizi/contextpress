"""Dictionary-based wording swaps (lexical synonyms, contractions, wordy phrases).

Lookups are frozen JSON dictionaries built offline under ``contextpress/data/``.
Runtime does not call WordNet. A cheap tiktoken gate drops swaps that fail to
shrink the turn. Multi-word keys are matched longest-first with word boundaries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
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
_UNIGRAM = re.compile(r"\b\w+\b")
_NON_WORD = re.compile(r"\W", re.UNICODE)


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


@dataclass(frozen=True)
class RewritePlan:
    """Split a rewrite dict so unigrams are O(1) lookups, not a giant regex.

    The bundled lexical dictionaries are ~20k single words. Compiling them into
    one alternation is the dominant Tier-1 cost (~200 ms / few-KB turn).
    Multi-word keys (contractions, wordy phrases) still use a small regex.
    """

    unigrams: dict[str, str]
    ngrams: dict[str, str]
    ngram_pattern: re.Pattern[str] | None


def build_rewrite_plan(mapping: dict[str, str]) -> RewritePlan:
    unigrams: dict[str, str] = {}
    ngrams: dict[str, str] = {}
    for key, value in mapping.items():
        if _NON_WORD.search(key):
            ngrams[key] = value
        else:
            unigrams[key] = value
    return RewritePlan(
        unigrams=unigrams,
        ngrams=ngrams,
        ngram_pattern=compile_mapping_pattern(ngrams),
    )


@lru_cache(maxsize=16)
def load_rewrite_plan(dict_name: str, encoding_name: str) -> RewritePlan:
    """Build once for each immutable bundled dictionary."""
    return build_rewrite_plan(load_rewrite_dict(dict_name, encoding_name))


def _sub_mapping(match: re.Match[str], mapping: dict[str, str]) -> str:
    surface = match.group(0)
    repl = mapping.get(surface.lower())
    if repl is None:
        return surface
    return preserve_case(surface, repl)


def apply_rewrite_plan(text: str, plan: RewritePlan) -> str:
    new_text = text
    if plan.ngram_pattern is not None:
        new_text = plan.ngram_pattern.sub(lambda m: _sub_mapping(m, plan.ngrams), new_text)
    if plan.unigrams:

        def _uni(match: re.Match[str]) -> str:
            return _sub_mapping(match, plan.unigrams)

        new_text = _UNIGRAM.sub(_uni, new_text)
    return new_text


def apply_lexical_text(
    text: str,
    mapping: dict[str, str],
    *,
    encoding=None,
    pattern: re.Pattern[str] | None = None,
    plan: RewritePlan | None = None,
    allow_equal_tokens: bool = False,
) -> str:
    if not text or not mapping:
        return text
    if pattern is not None:
        new_text = pattern.sub(lambda m: _sub_mapping(m, mapping), text)
    else:
        compiled = plan if plan is not None else build_rewrite_plan(mapping)
        new_text = apply_rewrite_plan(text, compiled)
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
            self._plan = build_rewrite_plan(self._mapping)
        else:
            self._mapping = load_rewrite_dict(dict_name, encoding_name)
            self._plan = load_rewrite_plan(dict_name, encoding_name)
        self._encoding = get_encoding(encoding_name)

    def process(self, conversation: Conversation) -> Conversation:
        return map_editable_turns(
            conversation,
            lambda text: apply_lexical_text(
                text,
                self._mapping,
                encoding=self._encoding,
                plan=self._plan,
                allow_equal_tokens=self._allow_equal_tokens,
            ),
        )
