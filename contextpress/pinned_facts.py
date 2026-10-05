"""Pin critical spans dropped by rag_doc medium/high compression."""

from __future__ import annotations

import copy
import re

from contextpress.critical_spans import extract_critical_spans, span_present
from contextpress.models import Conversation, Turn, clone_turn
from contextpress.namespans import extract_names, name_present
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing

KEPT_FIGURES_LINE = "Kept figures:"
KEPT_NAMES_LINE = "Kept names:"
# Numbers are short. One shared cap of 40 filled up on a pasted chapter and
# left later figures unpinned (0.7.7). URLs and identifiers stay tighter.
MAX_PINNED_NUMBERS = 120
MAX_PINNED_OTHER = 40
MAX_PINNED_NAMES = 40
_IS_NUMBER = re.compile(r"^(?:\d{4}-\d{2}-\d{2}|\d+\.\d+(?:\.\d+)*|\d{3,})$")


def _non_system_text(conversation: Conversation) -> str:
    parts: list[str] = []
    for turn in conversation.turns:
        if turn.role == "system":
            continue
        parts.append(extract_text_for_processing(turn))
    return "\n".join(parts)


def _pin_target_index(turns: list[Turn]) -> int | None:
    for i, turn in enumerate(turns):
        if turn.metadata.get("_trim_stub"):
            return i
    last_user: int | None = None
    for i in range(len(turns) - 1, -1, -1):
        if turns[i].role == "user":
            last_user = i
            break
    compressed: list[int] = []
    for i, turn in enumerate(turns):
        if turn.role == "system":
            continue
        if last_user is not None and i == last_user:
            continue
        if turn.compressed:
            compressed.append(i)
    if compressed:
        return compressed[-1]
    if last_user is not None and last_user > 0:
        return last_user - 1
    return None


def _spans_to_pin(original_text: str, compressed_text: str) -> list[str]:
    blob = compressed_text.casefold()
    numbers: list[str] = []
    others: list[str] = []
    for span in extract_critical_spans(original_text):
        if span_present(span, blob):
            continue
        bucket = numbers if _IS_NUMBER.fullmatch(span) else others
        cap = MAX_PINNED_NUMBERS if bucket is numbers else MAX_PINNED_OTHER
        if len(bucket) >= cap:
            continue
        bucket.append(span)
    return numbers + others


def _names_to_pin(original_text: str, compressed_text: str) -> list[str]:
    pins: list[str] = []
    for name in extract_names(original_text):
        if name_present(name, compressed_text):
            continue
        pins.append(name)
        if len(pins) >= MAX_PINNED_NAMES:
            break
    return pins


def apply_pinned_facts(
    original: Conversation, compressed: Conversation
) -> tuple[Conversation, int]:
    """Append dropped figures and names. Returns (conv, pin count)."""
    if original.type != "rag_doc" or compressed.type != "rag_doc":
        return compressed, 0

    orig_text = _non_system_text(original)
    comp_text = _non_system_text(compressed)
    lines: list[tuple[str, str]] = []
    figures = _spans_to_pin(orig_text, comp_text)
    if figures:
        lines.append((KEPT_FIGURES_LINE, f"{KEPT_FIGURES_LINE} " + "; ".join(figures)))
    kept_names = _names_to_pin(orig_text, comp_text)
    if kept_names:
        lines.append((KEPT_NAMES_LINE, f"{KEPT_NAMES_LINE} " + "; ".join(kept_names)))
    if not lines:
        return compressed, 0

    turns = [clone_turn(t) for t in compressed.turns]
    target = _pin_target_index(turns)
    if target is None:
        return compressed, 0

    for marker, line in lines:
        turns[target] = apply_text_to_turn(turns[target], _append_line(turns[target], line, marker))
    return (
        Conversation(
            turns=turns,
            type=compressed.type,
            metadata=copy.deepcopy(compressed.metadata),
        ),
        len(figures) + len(kept_names),
    )


def _append_line(turn: Turn, line: str, marker: str) -> str:
    text = extract_text_for_processing(turn)
    if marker in text:
        return text
    return f"{text.rstrip()}\n{line}" if text.strip() else line
