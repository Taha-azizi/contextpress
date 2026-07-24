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
    dry_run: bool = False
    warnings_emitted: list[str] = field(default_factory=list)

    @property
    def turns_removed(self) -> int:
        return max(0, self.turns_before - self.turns_after)

    @property
    def tokens_saved(self) -> int:
        return max(0, self.tokens_before - self.tokens_after)

    @property
    def token_savings_pct(self) -> float:
        if self.tokens_before <= 0:
            return 0.0
        return round(100.0 * self.tokens_saved / self.tokens_before, 2)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable snapshot of this run."""
        return {
            "turns_before": self.turns_before,
            "turns_after": self.turns_after,
            "turns_removed": self.turns_removed,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "tokens_saved": self.tokens_saved,
            "token_savings_pct": self.token_savings_pct,
            "stages_run": list(self.stages_run),
            "turn_delta_by_stage": dict(self.turn_delta_by_stage),
            "llm_tier_applied": self.llm_tier_applied,
            "llm_dedup_turns_before": self.llm_dedup_turns_before,
            "llm_dedup_turns_after": self.llm_dedup_turns_after,
            "compression_level": self.compression_level,
            "context_type": self.context_type,
            "token_budget": self.token_budget,
            "dry_run": self.dry_run,
            "warnings_emitted": list(self.warnings_emitted),
        }


@dataclass
class CompressionResult:
    """Messages plus stats when ``return_stats=True``."""

    messages: Any
    stats: CompressionStats

    def to_dict(self, *, include_messages: bool = True) -> dict[str, Any]:
        data = {"stats": self.stats.to_dict()}
        if include_messages:
            data["messages"] = self.messages
        return data
