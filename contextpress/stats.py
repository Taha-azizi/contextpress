"""Compression statistics returned when ``return_stats=True``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tiktoken

from contextpress.models import Conversation, Turn
from contextpress.normalizer import extract_text_for_processing


def get_encoding(model: str | None) -> tiktoken.Encoding:
    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass
    return tiktoken.get_encoding("cl100k_base")


def count_turn_tokens(turn: Turn, encoding: tiktoken.Encoding) -> int:
    if isinstance(turn.content, str):
        body = turn.content
    else:
        body = extract_text_for_processing(turn)
    return len(encoding.encode(f"{turn.role}\n{body}"))


def count_conversation_tokens(conversation: Conversation, model: str | None) -> int:
    enc = get_encoding(model)
    return sum(count_turn_tokens(t, enc) for t in conversation.turns)


@dataclass
class CompressionStats:
    """Observed effects of a single ``compress()`` call."""

    turns_before: int = 0
    turns_after: int = 0
    tokens_before: int = 0
    tokens_after: int = 0
    stages_run: list[str] = field(default_factory=list)
    turn_delta_by_stage: dict[str, int] = field(default_factory=dict)
    llm_tier_applied: bool = False
    llm_dedup_turns_before: int = 0
    llm_dedup_turns_after: int = 0
    compression_level: str | None = None
    context_type: str = "chat"
    token_budget: int | None = None

    @property
    def turns_removed(self) -> int:
        return max(0, self.turns_before - self.turns_after)

    @property
    def tokens_saved(self) -> int:
        return max(0, self.tokens_before - self.tokens_after)


@dataclass
class CompressionResult:
    """Messages plus stats when ``return_stats=True``."""

    messages: Any
    stats: CompressionStats
