"""
CONTEXTPRESS BEHAVIOR CONTRACT
===============================
1. system turns are ALWAYS passed through all stages untouched.
2. Input is NEVER mutated. Always return new objects.
3. Output format ALWAYS mirrors input format.
4. Most recent 3 non-system turns are NEVER compressed by Stage 4.
5. Last 2 non-system turns are NEVER removed by Stage 5.
6. Resolution requires BOTH sides in chat mode. One side is not enough.
7. In repetition detection, the MORE RECENT turn ALWAYS wins.
8. Tier 1 (no LLM) behavior is ALWAYS deterministic. Tests must pass consistently.
9. LLM backend failures fall back to Tier 1 and emit a warning.
10. token_budget=None means run all stages but skip budget enforcement.
11. Compression presets (low/medium/high) select non-budget stages; budget runs when
    token_budget is set unless opted out.
12. Tier 2 (when enabled) may dedupe non-system turns, then replace them with one assistant
    summary; system turns stay unchanged.
"""

from __future__ import annotations

import copy
import warnings
from typing import TYPE_CHECKING, Any

from contextpress.compression import STAGE_ORDER
from contextpress.models import Conversation, Turn
from contextpress.normalizer import extract_text_for_processing
from contextpress.profiles import Profile, StageConfig
from contextpress.registry import (
    build_custom_strategy,
    effective_stage_order,
    registered_stage_names,
)
from contextpress.stats import CompressionStats, count_conversation_tokens
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.budget import BudgetStrategy
from contextpress.strategies.filler import FillerStrategy
from contextpress.strategies.recency import RecencyStrategy
from contextpress.strategies.repetition import RepetitionStrategy
from contextpress.strategies.resolution import ResolutionStrategy

if TYPE_CHECKING:
    from contextpress.llm.base import LLMBackend

VALID_LLM_MODES = frozenset({"replace_all", "dedupe_only", "summarize_only"})


def clone_turn(t: Turn) -> Turn:
    if isinstance(t.content, str):
        c = t.content
    else:
        c = copy.deepcopy(t.content)
    return Turn(
        role=t.role,
        content=c,
        timestamp=t.timestamp,
        metadata=copy.deepcopy(t.metadata),
        importance=t.importance,
        resolved=t.resolved,
        compressed=t.compressed,
        original_content=(
            copy.deepcopy(t.original_content) if t.original_content is not None else None
        ),
    )


def clone_conversation(conversation: Conversation) -> Conversation:
    return Conversation(
        turns=[clone_turn(t) for t in conversation.turns],
        type=conversation.type,
        metadata=copy.deepcopy(conversation.metadata),
    )


class Pipeline:
    """Runs STAGE_ORDER on a copy of the conversation; optional LLM pass at the end."""

    STAGE_ORDER = list(STAGE_ORDER)

    def __init__(
        self,
        profile: Profile,
        token_budget: int | None = None,
        model: str | None = None,
        llm_backend: LLMBackend | None = None,
        *,
        llm_min_input_chars: int = 1500,
        llm_max_summary_tokens: int = 2048,
        llm_mode: str = "replace_all",
        custom_stages: dict[str, StageConfig] | None = None,
    ):
        self.profile = profile
        self.token_budget = token_budget
        self.model = model
        self.llm_backend = llm_backend  # None = Tier 1 only
        self.llm_min_input_chars = max(0, int(llm_min_input_chars))
        self.llm_max_summary_tokens = max(64, int(llm_max_summary_tokens))
        if llm_mode not in VALID_LLM_MODES:
            raise ValueError(
                f"unknown llm_mode {llm_mode!r}; use one of: {sorted(VALID_LLM_MODES)}"
            )
        self.llm_mode = llm_mode
        self.custom_stages = custom_stages or {}

    def run(
        self,
        conversation: Conversation,
        stats: CompressionStats | None = None,
    ) -> Conversation:
        if stats is not None:
            stats.turns_before = len(conversation.turns)
            stats.tokens_before = count_conversation_tokens(conversation, self.model)
            stats.context_type = conversation.type
            stats.token_budget = self.token_budget

        result = clone_conversation(conversation)
        stage_order = effective_stage_order()
        for stage_name in stage_order:
            if stage_name == "budget" and self.token_budget is None:
                continue
            stage_config = self._stage_config(stage_name)
            if stage_config is None or not stage_config.enabled:
                continue
            before_turns = len(result.turns)
            strategy = self._build_strategy(stage_name, stage_config)
            result = strategy.process(result)
            if stats is not None:
                stats.stages_run.append(stage_name)
                delta = len(result.turns) - before_turns
                if delta != 0:
                    stats.turn_delta_by_stage[stage_name] = delta

        if self.llm_backend is not None:
            result = self._run_llm_tier(result, stats=stats)

        if stats is not None:
            stats.turns_after = len(result.turns)
            stats.tokens_after = count_conversation_tokens(result, self.model)

        return result

    def _stage_config(self, name: str) -> StageConfig | None:
        if name in self.custom_stages:
            return self.custom_stages[name]
        if hasattr(self.profile, name):
            return getattr(self.profile, name)
        return None

    def _build_strategy(self, name: str, config: StageConfig) -> BaseStrategy:
        kwargs: dict[str, Any] = {
            "aggressiveness": config.aggressiveness,
            "conv_type": self.profile.name,
            "role_aware": self.profile.role_aware,
        }
        if name in registered_stage_names():
            return build_custom_strategy(
                name,
                config,
                conv_type=self.profile.name,
                role_aware=self.profile.role_aware,
            )
        if name == "filler":
            return FillerStrategy(**kwargs)
        if name == "repetition":
            return RepetitionStrategy(**kwargs)
        if name == "resolution":
            return ResolutionStrategy(**kwargs)
        if name == "recency":
            return RecencyStrategy(**kwargs)
        if name == "budget":
            if self.token_budget is None:
                raise RuntimeError("budget stage requires token_budget")
            return BudgetStrategy(
                aggressiveness=config.aggressiveness,
                token_budget=self.token_budget,
                model=self.model,
            )
        raise ValueError(f"unknown stage {name!r}")

    def _run_llm_tier(
        self,
        conversation: Conversation,
        stats: CompressionStats | None = None,
    ) -> Conversation:
        if self.llm_backend is None:
            return conversation

        turns = conversation.turns
        system_turns = [clone_turn(t) for t in turns if t.role == "system"]
        ns_turns = [t for t in turns if t.role != "system"]
        if not ns_turns:
            return conversation

        if stats is not None:
            stats.llm_dedup_turns_before = len(ns_turns)

        texts = [extract_text_for_processing(t) for t in ns_turns]
        if self.llm_mode in ("replace_all", "dedupe_only"):
            try:
                keep_idx = self.llm_backend.deduplicate(texts)
            except Exception:
                keep_idx = list(range(len(ns_turns)))
            valid = sorted(
                {
                    i
                    for i in keep_idx
                    if type(i) is int and not isinstance(i, bool) and 0 <= i < len(ns_turns)
                }
            )
            if not valid:
                valid = list(range(len(ns_turns)))
            if len(valid) < len(ns_turns):
                ns_turns = [ns_turns[i] for i in valid]
                texts = [texts[i] for i in valid]

            if stats is not None:
                stats.llm_dedup_turns_after = len(ns_turns)

            if self.llm_mode == "dedupe_only":
                new_turns = list(system_turns) + [clone_turn(t) for t in ns_turns]
                if stats is not None:
                    stats.llm_tier_applied = True
                return Conversation(
                    turns=new_turns,
                    type=conversation.type,
                    metadata=copy.deepcopy(conversation.metadata),
                )

        lines = [f"{t.role}: {txt}" for t, txt in zip(ns_turns, texts, strict=True)]
        combined = "\n\n".join(lines)
        if self.llm_min_input_chars > 0 and len(combined) < self.llm_min_input_chars:
            return conversation

        try:
            summary = self.llm_backend.summarize(combined, max_tokens=self.llm_max_summary_tokens)
        except Exception:
            warnings.warn(
                "contextpress: LLM tier failed; using Tier 1 result only",
                stacklevel=2,
            )
            return conversation

        summary = (summary or "").strip()
        if not summary:
            return conversation

        if stats is not None:
            stats.llm_tier_applied = True

        if self.llm_mode == "summarize_only":
            new_turns = list(system_turns) + [clone_turn(t) for t in ns_turns]
            new_turns.append(
                Turn(
                    role="assistant",
                    content=summary,
                    metadata={"source": "contextpress_llm_tier", "mode": "summarize_only"},
                    compressed=True,
                )
            )
            return Conversation(
                turns=new_turns,
                type=conversation.type,
                metadata=copy.deepcopy(conversation.metadata),
            )

        new_turns: list[Turn] = list(system_turns)
        new_turns.append(
            Turn(
                role="assistant",
                content=summary,
                metadata={"source": "contextpress_llm_tier"},
                compressed=True,
            )
        )
        return Conversation(
            turns=new_turns,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
