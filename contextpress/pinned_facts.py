"""Pin critical spans dropped by rag_doc medium/high compression."""

from __future__ import annotations

import copy

from contextpress.critical_spans import extract_critical_spans, span_present
from contextpress.models import Conversation, Turn, clone_turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing

KEPT_FIGURES_LINE = "Kept figures:"
MAX_PINNED_SPANS = 40


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


def _spans_to_pin(
    original_text: str, compressed_text: str, *, limit: int = MAX_PINNED_SPANS
) -> list[str]:
    blob = compressed_text.casefold()
    pins: list[str] = []
    for span in extract_critical_spans(original_text):
        if span_present(span, blob):
            continue
        pins.append(span)
        if len(pins) >= limit:
            break
    return pins


def apply_pinned_facts(
    original: Conversation, compressed: Conversation
) -> tuple[Conversation, int]:
    """Append ``Kept figures: …`` when critical spans were dropped. Returns (conv, count)."""
    if original.type != "rag_doc" or compressed.type != "rag_doc":
        return compressed, 0

    orig_text = _non_system_text(original)
    comp_text = _non_system_text(compressed)
    pins = _spans_to_pin(orig_text, comp_text)
    if not pins:
        return compressed, 0

    line = f"{KEPT_FIGURES_LINE} " + "; ".join(pins)
    turns = [clone_turn(t) for t in compressed.turns]
    target = _pin_target_index(turns)
    if target is None:
        return compressed, 0

    turns[target] = apply_text_to_turn(turns[target], _append_line(turns[target], line))
    return (
        Conversation(
            turns=turns,
            type=compressed.type,
            metadata=copy.deepcopy(compressed.metadata),
        ),
        len(pins),
    )


def _append_line(turn: Turn, line: str) -> str:
    text = extract_text_for_processing(turn)
    if KEPT_FIGURES_LINE in text:
        return text
    return f"{text.rstrip()}\n{line}" if text.strip() else line
