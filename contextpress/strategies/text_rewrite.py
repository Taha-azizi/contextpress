"""Shared helpers for text-rewriting stages (lexical, abbrev, alias, number_normalize)."""

from __future__ import annotations

import copy
from collections.abc import Callable

import tiktoken

from contextpress.models import Conversation, Turn, clone_turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.tools import preserve_structured_turn


def preserve_case(original: str, replacement: str) -> str:
    """Map replacement onto all-caps / capitalized / lowercase of ``original``."""
    if not original or not replacement:
        return replacement
    if original.isupper():
        return replacement.upper()
    if original.islower():
        return replacement.lower()
    if original[0].isupper() and original[1:].islower():
        return replacement[:1].upper() + replacement[1:].lower()
    return replacement.lower()


def get_encoding(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def keep_if_fewer_tokens(
    original: str,
    rewritten: str,
    encoding: tiktoken.Encoding | None,
    *,
    allow_equal: bool = False,
) -> str:
    """Return ``rewritten`` only when it encodes to fewer tokens (or equal if allowed)."""
    if rewritten == original or encoding is None:
        return rewritten if rewritten != original else original
    after = len(encoding.encode(rewritten))
    before = len(encoding.encode(original))
    if after < before or (allow_equal and after == before):
        return rewritten
    return original


def map_editable_turns(
    conversation: Conversation,
    rewrite: Callable[[str], str],
) -> Conversation:
    """Apply ``rewrite`` to non-system, non-JSON/tool turns; clone everything else."""
    new_turns: list[Turn] = []
    for turn in conversation.turns:
        if turn.role == "system" or preserve_structured_turn(turn):
            new_turns.append(clone_turn(turn))
            continue
        text = extract_text_for_processing(turn)
        new_text = rewrite(text)
        if new_text != text:
            new_turns.append(apply_text_to_turn(turn, new_text))
        else:
            new_turns.append(clone_turn(turn))
    return Conversation(
        turns=new_turns,
        type=conversation.type,
        metadata=copy.deepcopy(conversation.metadata),
    )
