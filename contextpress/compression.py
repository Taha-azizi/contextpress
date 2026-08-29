"""Presets (low/medium/high), explicit ``stages=``, and budget toggling."""

from __future__ import annotations

from contextpress.profiles import Profile, StageConfig

STAGE_ORDER: tuple[str, ...] = (
    "structure",
    "lexical",
    "contractions",
    "wordy_phrases",
    "number_normalize",
    "filler",
    "abbrev",
    "alias",
    "repetition",
    "resolution",
    "trim",
    "recency",
    "budget",
)

VALID_STAGES = frozenset(STAGE_ORDER)


def known_stages() -> frozenset[str]:
    """Built-in plus registered custom stage names."""
    from contextpress.registry import registered_stage_names

    return VALID_STAGES | registered_stage_names()


_NON_BUDGET_ORDER: tuple[str, ...] = tuple(s for s in STAGE_ORDER if s != "budget")

# NLP stages only; budget is toggled from token_budget (see apply_stage_selection)
_COMPRESSION_PRESETS: dict[str, frozenset[str]] = {
    "low": frozenset({"structure", "lexical", "filler", "abbrev", "alias", "repetition"}),
    "medium": frozenset(
        {"structure", "lexical", "filler", "abbrev", "alias", "repetition", "trim", "recency"}
    ),
    "high": frozenset(
        {
            "structure",
            "lexical",
            "filler",
            "abbrev",
            "alias",
            "repetition",
            "trim",
            "resolution",
            "recency",
        }
    ),
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
    "known_stages",
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
    custom_stages: dict[str, StageConfig] | None = None,
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
        unknown = [s for s in stages if s not in known_stages()]
        if unknown:
            raise ValueError(f"unknown stage name(s): {unknown}; valid: {sorted(known_stages())}")
        want = frozenset(stages)
        for name in _NON_BUDGET_ORDER:
            getattr(profile, name).enabled = name in want
        if custom_stages:
            for name, cfg in custom_stages.items():
                cfg.enabled = name in want
    else:
        level = normalize_compression_level(compression)
        preset = _COMPRESSION_PRESETS[level]
        for name in _NON_BUDGET_ORDER:
            base_on = getattr(base_profile, name).enabled
            getattr(profile, name).enabled = (name in preset) and base_on

    if disable:
        for name in disable:
            if custom_stages and name in custom_stages:
                custom_stages[name].enabled = False
                continue
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
            profile.budget.enabled = base_profile.budget.enabled
