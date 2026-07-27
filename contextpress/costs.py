"""Approximate USD cost estimates from token counts (bundled list prices)."""

from __future__ import annotations

from dataclasses import dataclass

# Approximate list prices USD per 1M tokens (input / output). For planning only.
_PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (2.50, 10.00),
        "gpt-4.1-mini": (0.40, 1.60),
        "gpt-4.1": (2.00, 8.00),
        "o4-mini": (1.10, 4.40),
        "default": (0.15, 0.60),
    },
    "anthropic": {
        "claude-haiku-4-5": (1.00, 5.00),
        "claude-sonnet-4-5": (3.00, 15.00),
        "claude-3-5-haiku": (0.80, 4.00),
        "claude-3-5-sonnet": (3.00, 15.00),
        "default": (1.00, 5.00),
    },
    "google": {
        "gemini-2.0-flash": (0.10, 0.40),
        "gemini-1.5-flash": (0.075, 0.30),
        "gemini-1.5-pro": (1.25, 5.00),
        "default": (0.10, 0.40),
    },
    "local": {
        "default": (0.0, 0.0),
    },
}

_PROVIDER_ALIASES = {
    "openai": "openai",
    "oai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "google": "google",
    "gemini": "google",
    "local": "local",
    "ollama": "local",
}


@dataclass(frozen=True)
class CostEstimate:
    """Rough USD estimate for a prompt (and optional completion)."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    input_usd_per_1m: float
    output_usd_per_1m: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "input_cost_usd": self.input_cost_usd,
            "output_cost_usd": self.output_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "input_usd_per_1m": self.input_usd_per_1m,
            "output_usd_per_1m": self.output_usd_per_1m,
        }


def normalize_provider(provider: str) -> str:
    key = provider.strip().lower()
    if key not in _PROVIDER_ALIASES:
        raise ValueError(
            f"unknown provider {provider!r}; use one of: {sorted(set(_PROVIDER_ALIASES.values()))}"
        )
    return _PROVIDER_ALIASES[key]


def resolve_rates(provider: str, model: str | None) -> tuple[str, str, float, float]:
    prov = normalize_provider(provider)
    table = _PRICING[prov]
    model_key = (model or "default").strip()
    if model_key in table:
        inp, out = table[model_key]
        return prov, model_key, inp, out
    # fuzzy: substring match
    lower = model_key.lower()
    for name, rates in table.items():
        if name != "default" and name.lower() in lower:
            return prov, name, rates[0], rates[1]
    inp, out = table["default"]
    return prov, model_key or "default", inp, out


def estimate_token_cost(
    input_tokens: int,
    *,
    provider: str = "openai",
    model: str | None = "gpt-4o-mini",
    output_tokens: int = 0,
) -> CostEstimate:
    """Estimate USD cost from token counts using bundled approximate prices."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be >= 0")
    prov, model_name, inp_rate, out_rate = resolve_rates(provider, model)
    in_cost = (input_tokens / 1_000_000.0) * inp_rate
    out_cost = (output_tokens / 1_000_000.0) * out_rate
    return CostEstimate(
        provider=prov,
        model=model_name,
        input_tokens=int(input_tokens),
        output_tokens=int(output_tokens),
        input_cost_usd=round(in_cost, 8),
        output_cost_usd=round(out_cost, 8),
        total_cost_usd=round(in_cost + out_cost, 8),
        input_usd_per_1m=inp_rate,
        output_usd_per_1m=out_rate,
    )
