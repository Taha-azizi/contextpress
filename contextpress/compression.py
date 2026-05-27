"""Presets (low/medium/high), explicit ``stages=``, and budget toggling."""

from __future__ import annotations

from contextpress.profiles import Profile

STAGE_ORDER: tuple[str, ...] = (
    "filler",
    "repetition",
    "resolution",
    "recency",
    "budget",
)

VALID_STAGES = frozenset(STAGE_ORDER)

_NON_BUDGET_ORDER: tuple[str, ...] = tuple(s for s in STAGE_ORDER if s != "budget")

# NLP stages only; budget is toggled from token_budget (see apply_stage_selection)
_COMPRESSION_PRESETS: dict[str, frozenset[str]] = {
    "low": frozenset({"filler", "repetition"}),
    "medium": frozenset({"filler", "repetition", "recency"}),
    "high": frozenset({"filler", "repetition", "resolution", "recency"}),
}

_COMPRESSION_ALIASES: dict[str, str] = {
    "low": "low",
    "light": "low",
    "medium": "medium",
    "med": "medium",
    "mid": "medium",
    "high": "high",
    "max": "high",
}


__all__ = [
    "STAGE_ORDER",
    "VALID_STAGES",
    "apply_stage_selection",
    "normalize_compression_level",
]


def normalize_compression_level(level: str) -> str:
    key = level.strip().lower()
    if key not in _COMPRESSION_ALIASES:
        raise ValueError(
            f"unknown compression level {level!r}; "
            f"use one of: low, medium, high (aliases: light, med, max)"
        )
    return _COMPRESSION_ALIASES[key]


def apply_stage_selection(
    profile: Profile,
    *,
    base_profile: Profile,
    compression: str,
    stages: list[str] | None,
    disable: list[str] | None,
    token_budget: int | None,
) -> None:
    """
    Mutates ``profile`` in place: sets each stage's ``enabled`` from explicit
    ``stages``, or from a compression preset merged with ``base_profile`` for
    non-budget stages, then applies ``disable``. Budget is set last from
    ``token_budget`` / ``stages`` / ``disable``.
    """
    if stages is not None:
        if not stages:
            raise ValueError("stages= must list at least one stage name when provided")
        unknown = [s for s in stages if s not in VALID_STAGES]
        if unknown:
            raise ValueError(f"unknown stage name(s): {unknown}; valid: {sorted(VALID_STAGES)}")
        want = frozenset(stages)
        for name in _NON_BUDGET_ORDER:
            getattr(profile, name).enabled = name in want
    else:
        level = normalize_compression_level(compression)
        preset = _COMPRESSION_PRESETS[level]
        for name in _NON_BUDGET_ORDER:
            base_on = getattr(base_profile, name).enabled
            getattr(profile, name).enabled = (name in preset) and base_on

    if disable:
        for name in disable:
            if not hasattr(profile, name):
                continue
            getattr(profile, name).enabled = False

    # Budget: token cap enforcement (pipeline still skips if token_budget is None)
    if token_budget is None:
        profile.budget.enabled = False
    elif stages is not None:
        profile.budget.enabled = "budget" in want
    else:
        if disable and "budget" in disable:
            profile.budget.enabled = False
        else:
            profile.budget.enabled = getattr(base_profile, "budget").enabled
