"""
CONTEXTPRESS BEHAVIOR CONTRACT
===============================
1. system turns are ALWAYS passed through NLP stages untouched. Budget may
   truncate system content as a last resort when the token cap cannot otherwise
   be met (emits a warning).
2. Input is NEVER mutated. Always return new objects.
3. Output format ALWAYS mirrors input format.
4. Most recent 3 non-system turns are NEVER compressed by recency.
5. Last 2 non-system turns are NEVER removed by budget.
6. Trim never removes system turns, the opening non-system turns, or the last 3
   non-system turns. Tool call/result groups that fall in the dropped span are kept.
7. Resolution requires BOTH sides in chat mode. One side is not enough.
8. In repetition detection, the MORE RECENT turn ALWAYS wins.
9. Tier 1 (no LLM) behavior is ALWAYS deterministic. Tests must pass consistently.
10. LLM backend failures fall back to Tier 1 and emit a warning.
11. token_budget=None means run all stages but skip budget enforcement.
12. Compression presets (low/medium/high) select non-budget stages; budget runs when
    token_budget is set unless opted out.
13. Tier 2 (when enabled) may dedupe non-system turns, then replace them with one assistant
    summary; system turns stay unchanged.
14. Lexical never mutates system turns, JSON blobs, fenced JSON, or tool
    call/result turns. It only substitutes whole words/phrases from a frozen
    dictionary. rag_doc leaves lexical off unless stages= names it.
    Opt-in ``contractions`` / ``wordy_phrases`` reuse the same mechanism with
    different dictionaries; ``number_normalize`` rewrites multi-word number
    phrases to digits. None of those three are in low/medium/high presets.
15. Abbrev and alias never mutate system / JSON / tool turns. Alias only fires
    for phrases that repeat 3+ times in the conversation (chat/agent).
"""

from __future__ import annotations

import copy
import warnings
from typing import TYPE_CHECKING, Any

from contextpress.compression import STAGE_ORDER
from contextpress.models import Conversation, Turn, clone_conversation, clone_turn
from contextpress.normalizer import extract_text_for_processing
from contextpress.profiles import Profile, StageConfig
from contextpress.registry import (
    build_custom_strategy,
    effective_stage_order,
    registered_stage_names,
)
from contextpress.stats import CompressionStats, count_conversation_tokens, get_encoding
from contextpress.strategies.abbrev import AbbreviationStrategy
from contextpress.strategies.alias import AliasStrategy
from contextpress.strategies.base import BaseStrategy
from contextpress.strategies.budget import BudgetStrategy
from contextpress.strategies.filler import FillerStrategy
from contextpress.strategies.lexical import LexicalCompression
from contextpress.strategies.number_normalize import NumberNormalizeStrategy
from contextpress.strategies.recency import RecencyStrategy
from contextpress.strategies.repetition import RepetitionStrategy
from contextpress.strategies.resolution import ResolutionStrategy
from contextpress.strategies.structure import StructureStrategy
from contextpress.strategies.trim import TrimStrategy

if TYPE_CHECKING:
    from contextpress.llm.base import LLMBackend

VALID_LLM_MODES = frozenset({"replace_all", "dedupe_only", "summarize_only"})


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
        *,
        dry_run: bool = False,
    ) -> Conversation:
        if stats is not None:
            stats.turns_before = len(conversation.turns)
            stats.tokens_before = count_conversation_tokens(conversation, self.model)
            stats.context_type = conversation.type
            stats.token_budget = self.token_budget
            stats.dry_run = dry_run

        result = clone_conversation(conversation)
        stage_order = effective_stage_order()
        for stage_name in stage_order:
            if stage_name == "budget" and self.token_budget is None:
                continue
            stage_config = self._stage_config(stage_name)
            if stage_config is None or not stage_config.enabled:
                continue
            before_turns = len(result.turns)
            before_tokens = (
                count_conversation_tokens(result, self.model) if stats is not None else 0
            )
            strategy = self._build_strategy(stage_name, stage_config)
            result = strategy.process(result)
            if stats is not None:
                stats.stages_run.append(stage_name)
                turn_delta = len(result.turns) - before_turns
                if turn_delta != 0:
                    stats.turn_delta_by_stage[stage_name] = turn_delta
                token_delta = count_conversation_tokens(result, self.model) - before_tokens
                if token_delta != 0:
                    stats.token_delta_by_stage[stage_name] = token_delta

        if self.llm_backend is not None and not dry_run:
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
        if name == "structure":
            return StructureStrategy(**kwargs)
        if name == "lexical":
            return LexicalCompression(
                encoding_name=get_encoding(self.model).name,
                dict_name="lexical",
                **kwargs,
            )
        if name == "contractions":
            return LexicalCompression(
                encoding_name=get_encoding(self.model).name,
                dict_name="contractions",
                **kwargs,
            )
        if name == "wordy_phrases":
            return LexicalCompression(
                encoding_name=get_encoding(self.model).name,
                dict_name="wordy_phrases",
                **kwargs,
            )
        if name == "number_normalize":
            return NumberNormalizeStrategy(
                encoding_name=get_encoding(self.model).name,
                **kwargs,
            )
        if name == "filler":
            return FillerStrategy(**kwargs)
        if name == "abbrev":
            return AbbreviationStrategy(
                encoding_name=get_encoding(self.model).name,
                **kwargs,
            )
        if name == "alias":
            return AliasStrategy(
                encoding_name=get_encoding(self.model).name,
                **kwargs,
            )
        if name == "repetition":
            return RepetitionStrategy(**kwargs)
        if name == "trim":
            return TrimStrategy(**kwargs)
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
                warnings.warn(
                    "contextpress: LLM deduplicate failed; keeping all non-system turns",
                    stacklevel=2,
                )
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
