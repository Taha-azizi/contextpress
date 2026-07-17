"""Register custom pipeline stages without subclassing ``Pipeline``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from contextpress.profiles import StageConfig
from contextpress.strategies.base import BaseStrategy

# (name, factory, insert_before)
_CustomEntry = tuple[str, Callable[..., BaseStrategy], str]
_REGISTRY: list[_CustomEntry] = []


def _builtin_stages() -> tuple[str, ...]:
    from contextpress.compression import STAGE_ORDER

    return STAGE_ORDER


def register_stage(
    name: str,
    factory: Callable[..., BaseStrategy],
    *,
    before: str = "budget",
) -> None:
    """Register a custom stage factory.

    ``factory`` receives ``aggressiveness``, ``conv_type``, ``role_aware``, and
    optional ``**kwargs`` — same as built-in strategies. Custom stages run when
    named in ``stages=`` on ``compress()``.

    Parameters
    ----------
    name:
        Unique stage name (must not collide with a built-in stage).
    before:
        Built-in or custom stage name to insert before (default: ``budget``).
    """
    if not name or name in _builtin_stages():
        raise ValueError(f"cannot register stage {name!r}: name invalid or reserved")
    if any(e[0] == name for e in _REGISTRY):
        raise ValueError(f"stage {name!r} is already registered")
    _REGISTRY.append((name, factory, before))


def registered_stage_names() -> frozenset[str]:
    return frozenset(name for name, _, _ in _REGISTRY)


def clear_registry() -> None:
    """Remove all custom stages (for tests)."""
    _REGISTRY.clear()


def effective_stage_order() -> list[str]:
    """Built-in ``STAGE_ORDER`` with registered custom stages inserted."""
    order = list(_builtin_stages())
    for name, _, before in _REGISTRY:
        if before not in order:
            raise RuntimeError(f"custom stage {name!r}: anchor {before!r} not in stage order")
        order.insert(order.index(before), name)
    return order


def build_custom_strategy(
    name: str,
    config: StageConfig,
    *,
    conv_type: str,
    role_aware: bool,
    extra_kwargs: dict[str, Any] | None = None,
) -> BaseStrategy:
    for reg_name, factory, _ in _REGISTRY:
        if reg_name == name:
            kwargs: dict[str, Any] = {
                "aggressiveness": config.aggressiveness,
                "conv_type": conv_type,
                "role_aware": role_aware,
            }
            if extra_kwargs:
                kwargs.update(extra_kwargs)
            return factory(**kwargs)
    raise ValueError(f"no registered factory for custom stage {name!r}")
