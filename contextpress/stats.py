"""Compression statistics returned when ``return_stats=True``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tiktoken

from contextpress.costs import estimate_token_cost
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
    # Optional USD estimates (0.6.1+); filled when cost_provider is set or via attach_cost()
    cost_provider: str | None = None
    cost_model: str | None = None
    estimated_input_cost_before_usd: float | None = None
    estimated_input_cost_after_usd: float | None = None
    # Optional completion-side estimate (0.6.3+); same before/after (compression is input-only)
    estimated_output_tokens: int | None = None
    estimated_output_cost_usd: float | None = None
    estimated_total_cost_before_usd: float | None = None
    estimated_total_cost_after_usd: float | None = None

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

    @property
    def estimated_cost_saved_usd(self) -> float | None:
        """Approximate input-USD saved (None if cost was not attached)."""
        before = self.estimated_input_cost_before_usd
        after = self.estimated_input_cost_after_usd
        if before is None or after is None:
            return None
        return round(max(0.0, before - after), 8)

    def attach_cost(
        self,
        *,
        provider: str = "openai",
        model: str | None = "gpt-4o-mini",
        output_tokens: int = 0,
    ) -> CompressionStats:
        """Fill USD fields from ``tokens_before`` / ``tokens_after``. Returns self.

        ``output_tokens`` is an assumed completion size (unchanged by compression).
        """
        before = estimate_token_cost(
            self.tokens_before, provider=provider, model=model, output_tokens=output_tokens
        )
        after = estimate_token_cost(
            self.tokens_after, provider=provider, model=model, output_tokens=output_tokens
        )
        self.cost_provider = before.provider
        self.cost_model = before.model
        self.estimated_input_cost_before_usd = before.input_cost_usd
        self.estimated_input_cost_after_usd = after.input_cost_usd
        if output_tokens > 0:
            self.estimated_output_tokens = after.output_tokens
            self.estimated_output_cost_usd = after.output_cost_usd
            self.estimated_total_cost_before_usd = before.total_cost_usd
            self.estimated_total_cost_after_usd = after.total_cost_usd
        else:
            self.estimated_output_tokens = None
            self.estimated_output_cost_usd = None
            self.estimated_total_cost_before_usd = None
            self.estimated_total_cost_after_usd = None
        return self

    def summary(self) -> str:
        """One-line human-readable report for logs, notebooks, and demos."""
        level = self.compression_level or "default"
        dry = " [dry-run]" if self.dry_run else ""
        lines = [
            (
                f"contextpress ({self.context_type}, {level}){dry}: "
                f"{self.turns_before} -> {self.turns_after} turns, "
                f"{self.tokens_before} -> {self.tokens_after} tokens "
                f"({self.token_savings_pct}% saved)"
            )
        ]
        if self.stages_run:
            lines.append(f"stages: {', '.join(self.stages_run)}")
        saved = self.estimated_cost_saved_usd
        before_usd = self.estimated_input_cost_before_usd
        after_usd = self.estimated_input_cost_after_usd
        if saved is not None and before_usd is not None and after_usd is not None:
            lines.append(
                "est. input cost: "
                f"${before_usd:.6f} -> ${after_usd:.6f} (saved ${saved:.6f})"
            )
        out_usd = self.estimated_output_cost_usd
        out_tok = self.estimated_output_tokens
        if out_usd is not None and out_tok is not None:
            lines.append(f"est. output cost: ${out_usd:.6f} ({out_tok} tokens)")
        total_before = self.estimated_total_cost_before_usd
        total_after = self.estimated_total_cost_after_usd
        if total_before is not None and total_after is not None:
            lines.append(f"est. total: ${total_before:.6f} -> ${total_after:.6f}")
        return "\n".join(lines)

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
            "cost_provider": self.cost_provider,
            "cost_model": self.cost_model,
            "estimated_input_cost_before_usd": self.estimated_input_cost_before_usd,
            "estimated_input_cost_after_usd": self.estimated_input_cost_after_usd,
            "estimated_cost_saved_usd": self.estimated_cost_saved_usd,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_output_cost_usd": self.estimated_output_cost_usd,
            "estimated_total_cost_before_usd": self.estimated_total_cost_before_usd,
            "estimated_total_cost_after_usd": self.estimated_total_cost_after_usd,
        }


@dataclass
class CompressionResult:
    """Messages plus stats when ``return_stats=True``."""

    messages: Any
    stats: CompressionStats

    def summary(self) -> str:
        """Human-readable report for this compression run."""
        return self.stats.summary()

    def to_dict(self, *, include_messages: bool = True) -> dict[str, Any]:
        data = {"stats": self.stats.to_dict()}
        if include_messages:
            data["messages"] = self.messages
        return data
