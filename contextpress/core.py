from __future__ import annotations

import copy
import warnings
from typing import TYPE_CHECKING, Any

from contextpress.compression import apply_stage_selection, normalize_compression_level
from contextpress.normalizer import denormalize_output, normalize_messages
from contextpress.pipeline import VALID_LLM_MODES, Pipeline
from contextpress.profiles import PROFILES, Profile, StageConfig
from contextpress.registry import register_stage as _register_stage
from contextpress.stats import CompressionResult, CompressionStats, count_conversation_tokens

if TYPE_CHECKING:
    from collections.abc import Callable

    from contextpress.llm.base import LLMBackend
    from contextpress.strategies.base import BaseStrategy


def _validate_token_budget(token_budget: int | None) -> None:
    if token_budget is None:
        return
    if isinstance(token_budget, bool) or not isinstance(token_budget, int):
        raise TypeError("token_budget must be a positive int or None (bools are not allowed)")
    if token_budget < 1:
        raise ValueError("token_budget must be >= 1 when set")


class ContextManager:
    """Main API: ``compress()`` runs Tier 1 (and Tier 2 if ``llm_backend`` is set).

    ``model`` is only for tiktoken when enforcing ``token_budget``. It does not call that model
    unless you pass an ``llm_backend`` that uses it.
    """

    def __init__(
        self,
        type: str = "chat",
        model: str | None = None,
        llm_backend: LLMBackend | None = None,
        *,
        compression: str = "medium",
        llm_min_input_chars: int = 1500,
        llm_max_summary_tokens: int = 2048,
        llm_mode: str = "replace_all",
    ):
        if type not in PROFILES:
            raise ValueError(f"unknown context type {type!r}")
        if llm_mode not in VALID_LLM_MODES:
            raise ValueError(
                f"unknown llm_mode {llm_mode!r}; use one of: {sorted(VALID_LLM_MODES)}"
            )
        self._type = type
        self._profile: Profile = copy.deepcopy(PROFILES[type])
        self._compression: str = normalize_compression_level(compression)
        self.model = model
        self.llm_backend = llm_backend
        self.llm_min_input_chars = int(llm_min_input_chars)
        self.llm_max_summary_tokens = int(llm_max_summary_tokens)
        self.llm_mode = llm_mode
        self._custom_stages: dict[str, StageConfig] = {}

    def estimate_tokens(self, messages: Any, *, model: str | None = None) -> int:
        """Count tokens for ``messages`` using the same encoding as the budget stage."""
        conv, _ = normalize_messages(messages, context_type=self._type)
        return count_conversation_tokens(conv, model if model is not None else self.model)

    def register_stage(
        self,
        name: str,
        factory: Callable[..., BaseStrategy],
        *,
        before: str = "budget",
        aggressiveness: float = 0.5,
    ) -> None:
        """Register a custom pipeline stage (see ``contextpress.registry``)."""
        _register_stage(name, factory, before=before)
        self._custom_stages[name] = StageConfig(enabled=False, aggressiveness=aggressiveness)

    def compress(
        self,
        messages: Any,
        token_budget: int | None = None,
        *,
        compression: str | None = None,
        stages: list[str] | None = None,
        disable: list[str] | None = None,
        return_stats: bool = False,
    ) -> Any | CompressionResult:
        """Run the pipeline; return value matches input shape (dict list, tuples, strings, etc.).

        ``token_budget`` must be a positive int or None. Unknown keys in ``disable`` are ignored.
        With ``return_stats=True``, returns a ``CompressionResult`` with ``messages`` and ``stats``.
        """
        _validate_token_budget(token_budget)
        level = compression if compression is not None else self._compression
        profile = copy.deepcopy(self._profile)
        custom_stages = copy.deepcopy(self._custom_stages)
        apply_stage_selection(
            profile,
            base_profile=self._profile,
            compression=level,
            stages=stages,
            disable=disable,
            token_budget=token_budget,
            custom_stages=custom_stages,
        )

        conv, ctx = normalize_messages(messages, context_type=self._type)
        stats = CompressionStats(compression_level=level) if return_stats else None
        pipeline = Pipeline(
            profile,
            token_budget=token_budget,
            model=self.model,
            llm_backend=self.llm_backend,
            llm_min_input_chars=self.llm_min_input_chars,
            llm_max_summary_tokens=self.llm_max_summary_tokens,
            llm_mode=self.llm_mode,
            custom_stages=custom_stages,
        )
        out = pipeline.run(conv, stats=stats)
        messages_out = denormalize_output(out, ctx)
        if return_stats:
            assert stats is not None
            return CompressionResult(messages=messages_out, stats=stats)
        return messages_out

    def set_compression(self, compression: str) -> None:
        """Change the default preset for subsequent ``compress()`` calls (low / medium / high)."""
        self._compression = normalize_compression_level(compression)

    def configure(self, stage: str, **kwargs: Any) -> None:
        """Patch ``StageConfig`` fields on the live profile (e.g. aggressiveness, enabled)."""
        if stage in self._custom_stages:
            sc = self._custom_stages[stage]
        elif hasattr(self._profile, stage):
            sc = getattr(self._profile, stage)
        else:
            raise ValueError(f"unknown stage {stage!r}")
        for k, v in kwargs.items():
            if hasattr(sc, k):
                setattr(sc, k, v)
        unknown = [k for k in kwargs if not hasattr(sc, k)]
        if unknown:
            warnings.warn(
                f"contextpress: configure({stage!r}) ignored unknown key(s): {unknown}",
                stacklevel=2,
            )
