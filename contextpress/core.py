from __future__ import annotations

import copy
import warnings
from typing import TYPE_CHECKING, Any

from contextpress.compression import apply_stage_selection, normalize_compression_level
from contextpress.normalizer import denormalize_output, normalize_messages
from contextpress.pipeline import Pipeline
from contextpress.profiles import PROFILES, Profile, StageConfig

if TYPE_CHECKING:
    from contextpress.llm.base import LLMBackend


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
    ):
        if type not in PROFILES:
            raise ValueError(f"unknown context type {type!r}")
        self._type = type
        self._profile: Profile = copy.deepcopy(PROFILES[type])
        self._compression: str = normalize_compression_level(compression)
        self.model = model
        self.llm_backend = llm_backend
        self.llm_min_input_chars = int(llm_min_input_chars)
        self.llm_max_summary_tokens = int(llm_max_summary_tokens)

    def compress(
        self,
        messages: Any,
        token_budget: int | None = None,
        *,
        compression: str | None = None,
        stages: list[str] | None = None,
        disable: list[str] | None = None,
    ) -> Any:
        """Run the pipeline; return value matches input shape (dict list, tuples, strings, etc.).

        ``token_budget`` must be a positive int or None. Unknown keys in ``disable`` are ignored.
        """
        _validate_token_budget(token_budget)
        profile = copy.deepcopy(self._profile)
        apply_stage_selection(
            profile,
            base_profile=self._profile,
            compression=compression if compression is not None else self._compression,
            stages=stages,
            disable=disable,
            token_budget=token_budget,
        )

        conv, ctx = normalize_messages(messages, context_type=self._type)
        pipeline = Pipeline(
            profile,
            token_budget=token_budget,
            model=self.model,
            llm_backend=self.llm_backend,
            llm_min_input_chars=self.llm_min_input_chars,
            llm_max_summary_tokens=self.llm_max_summary_tokens,
        )
        out = pipeline.run(conv)
        return denormalize_output(out, ctx)

    def set_compression(self, compression: str) -> None:
        """Change the default preset for subsequent ``compress()`` calls (low / medium / high)."""
        self._compression = normalize_compression_level(compression)

    def configure(self, stage: str, **kwargs: Any) -> None:
        """Patch ``StageConfig`` fields on the live profile (e.g. ``aggressiveness``, ``enabled``)."""
        if not hasattr(self._profile, stage):
            raise ValueError(f"unknown stage {stage!r}")
        sc: StageConfig = getattr(self._profile, stage)
        for k, v in kwargs.items():
            if hasattr(sc, k):
                setattr(sc, k, v)
        unknown = [k for k in kwargs if not hasattr(sc, k)]
        if unknown:
            warnings.warn(
                f"contextpress: configure({stage!r}) ignored unknown key(s): {unknown}",
                stacklevel=2,
            )
