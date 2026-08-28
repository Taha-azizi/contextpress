"""Alias repeated multi-word expressions inside one conversation.

Expressions that appear 3+ times are introduced once as ``Phrase (ABBR)`` and
replaced with ``ABBR`` on later occurrences. Case variants count as the same
phrase. Deterministic; no LLM.
"""

from __future__ import annotations

import copy
import re
from collections import Counter

from contextpress.models import Conversation, Turn, clone_turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.text_rewrite import get_encoding
from contextpress.tools import preserve_structured_turn

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:'[A-Za-z]+)?")
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "as",
        "by",
        "with",
        "from",
        "into",
        "over",
        "under",
        "about",
        "after",
        "before",
        "between",
        "through",
        "during",
        "without",
        "within",
        "along",
        "across",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "having",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "i",
        "my",
        "me",
        "not",
        "no",
        "yes",
        "so",
        "than",
        "then",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "what",
        "why",
        "how",
        "can",
        "could",
        "should",
        "would",
        "may",
        "might",
        "must",
        "will",
        "shall",
        "also",
        "just",
        "only",
        "even",
        "still",
        "already",
        "very",
        "really",
        "quite",
        "rather",
        "more",
        "most",
        "some",
        "any",
        "all",
        "each",
        "every",
        "other",
        "another",
        "such",
        "same",
        "own",
        "too",
        "here",
        "there",
        "now",
        "out",
        "up",
        "down",
        "off",
        "again",
        "further",
        "once",
    }
)

_MIN_COUNT = 3
_MIN_WORDS = 2
_MAX_WORDS = 5
_MIN_CHARS = 10
_MAX_ALIASES = 12


def _tokens(text: str) -> list[tuple[str, int, int]]:
    """Return (surface, start, end) for alphabetic tokens."""
    return [(m.group(0), m.start(), m.end()) for m in _WORD.finditer(text or "")]


def _content_word_count(words: list[str]) -> int:
    return sum(1 for w in words if w.lower() not in _STOP)


def _candidate_ok(words: list[str]) -> bool:
    if not (_MIN_WORDS <= len(words) <= _MAX_WORDS):
        return False
    joined = " ".join(words)
    if len(joined) < _MIN_CHARS:
        return False
    if _content_word_count(words) < 1:
        return False
    # Avoid nearly-all-stopword phrases like "in the of the"
    if _content_word_count(words) < max(1, len(words) // 2):
        return False
    # Skip pure repetition ("word word word") — not a real named phrase.
    content = [w.lower() for w in words if w.lower() not in _STOP]
    if len(set(content)) < 2 and len(words) >= 2:
        # Allow two-word proper-style phrases only when surfaces differ in form
        # or at least one token is capitalized in the source span (checked later).
        if len(set(w.lower() for w in words)) < 2:
            return False
    return True


def _looks_like_name(words: list[str]) -> bool:
    """Prefer multi-word names / titles (Context Press) over random n-grams."""
    caps = sum(1 for w in words if w[:1].isupper())
    if caps >= 2:
        return True
    if caps >= 1 and _content_word_count(words) >= 2:
        return True
    # Technical lowercase multi-word with distinct content words (e.g. "pull request"
    # already handled by abbrev; still allow distinctive lowercase phrases).
    content = [w.lower() for w in words if w.lower() not in _STOP]
    return len(set(content)) >= 2 and all(len(w) >= 3 for w in content)


def _make_abbr(words: list[str], used: set[str]) -> str | None:
    content = [w for w in words if w.lower() not in _STOP] or list(words)
    base = "".join(w[0].upper() for w in content if w)
    if len(base) < 2:
        base = "".join(w[0].upper() for w in words if w)
    if len(base) < 2:
        return None
    cand = base
    n = 2
    while cand in used or len(cand) < 2:
        # Prefer longer initials, then numeric suffixes.
        if n <= len(content):
            cand = "".join((w[:n] if len(w) >= n else w).title() for w in content)[:8]
            n += 1
        else:
            suffix = 2
            while f"{base}{suffix}" in used:
                suffix += 1
            cand = f"{base}{suffix}"
            break
    return cand


def find_alias_map(texts: list[str], *, min_count: int = _MIN_COUNT) -> list[tuple[str, str]]:
    """Return ``[(canonical_phrase, abbr), ...]`` ordered by estimated savings."""
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for text in texts:
        toks = _tokens(text)
        lowers = [t[0].lower() for t in toks]
        for n in range(_MIN_WORDS, _MAX_WORDS + 1):
            for i in range(0, len(lowers) - n + 1):
                words = [toks[i + j][0] for j in range(n)]
                if not _candidate_ok(words) or not _looks_like_name(words):
                    continue
                key = " ".join(lowers[i : i + n])
                counts[key] += 1
                display.setdefault(key, " ".join(words))

    scored: list[tuple[int, int, str]] = []
    for key, count in counts.items():
        if count < min_count:
            continue
        phrase = display[key]
        # Net token-ish char savings after paying for " (ABBR)" on first use.
        overhead = len(f" ({'X' * 3})")  # approx; refined after abbr chosen
        raw = (len(phrase) - 3) * (count - 1) - overhead
        if raw <= 0:
            continue
        scored.append((raw, len(phrase), key))
    scored.sort(reverse=True)

    used: set[str] = set()
    out: list[tuple[str, str]] = []
    for _, _, key in scored:
        if len(out) >= _MAX_ALIASES:
            break
        words = display[key].split()
        abbr = _make_abbr(words, used)
        if abbr is None:
            continue
        # Skip if abbreviation already appears as a standalone token in corpus.
        if any(re.search(rf"\b{re.escape(abbr)}\b", t) for t in texts):
            used.add(abbr)
            abbr = _make_abbr(words, used)
            if abbr is None or any(re.search(rf"\b{re.escape(abbr)}\b", t) for t in texts):
                continue
        # Re-check net savings with the real abbreviation length.
        count = counts[key]
        phrase = display[key]
        overhead = len(f" ({abbr})")
        net = (len(phrase) - len(abbr)) * (count - 1) - overhead
        if net <= 0:
            continue
        used.add(abbr)
        out.append((phrase, abbr))
    # Longer phrases first when applying, to avoid nested overlap issues.
    out.sort(key=lambda kv: len(kv[0]), reverse=True)
    return out


def apply_aliases_to_text(
    text: str,
    aliases: list[tuple[str, str]],
    seen: dict[str, bool],
) -> str:
    """Apply aliases; ``seen`` tracks whether the definition form was emitted."""
    if not text or not aliases:
        return text
    out = text
    for phrase, abbr in aliases:
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)

        def _repl(match: re.Match[str], *, _phrase: str = phrase, _abbr: str = abbr) -> str:
            key = _phrase.lower()
            if not seen.get(key):
                seen[key] = True
                return f"{match.group(0)} ({_abbr})"
            return _abbr

        out = pattern.sub(_repl, out)
    return out


class AliasStrategy(BaseStrategy):
    """Introduce short aliases for phrases that repeat 3+ times in the chat."""

    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        conv_type: str = "chat",
        encoding_name: str = "cl100k_base",
        min_count: int = _MIN_COUNT,
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type
        self.encoding_name = encoding_name
        self.min_count = max(2, int(min_count))
        self._encoding = get_encoding(encoding_name)

    def process(self, conversation: Conversation) -> Conversation:
        editable: list[tuple[int, Turn, str]] = []
        for i, turn in enumerate(conversation.turns):
            if self._is_protected(turn) or preserve_structured_turn(turn):
                continue
            text = extract_text_for_processing(turn)
            if text.strip():
                editable.append((i, turn, text))

        aliases = find_alias_map([t for _, _, t in editable], min_count=self.min_count)
        if not aliases:
            return Conversation(
                turns=[clone_turn(t) for t in conversation.turns],
                type=conversation.type,
                metadata=copy.deepcopy(conversation.metadata),
            )

        seen: dict[str, bool] = {}
        candidates: list[Turn] = []
        before_tokens = 0
        after_tokens = 0
        enc = self._encoding

        editable_map = {i: text for i, _, text in editable}
        for i, turn in enumerate(conversation.turns):
            if i not in editable_map:
                candidates.append(clone_turn(turn))
                continue
            original = editable_map[i]
            new_text = apply_aliases_to_text(original, aliases, seen)
            before_tokens += len(enc.encode(original))
            after_tokens += len(enc.encode(new_text))
            if new_text != original:
                candidates.append(apply_text_to_turn(turn, new_text))
            else:
                candidates.append(clone_turn(turn))

        if after_tokens > before_tokens:
            return Conversation(
                turns=[clone_turn(t) for t in conversation.turns],
                type=conversation.type,
                metadata=copy.deepcopy(conversation.metadata),
            )
        return Conversation(
            turns=candidates,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
