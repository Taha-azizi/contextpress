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


@dataclass(frozen=True)
class CacheTradeoff:
    """Compare raw+prefix-cache vs compressed-as-uncached input cost.

    ``effective_*_tokens`` are uncached-equivalent tokens (cache hits count as
    ``cache_read_multiplier`` each). ``compress_is_cheaper`` is True only when
    rewriting the prompt still beats keeping the raw prefix in cache.
    """

    tokens_raw: int
    tokens_compressed: int
    cache_hit_rate: float
    cache_read_multiplier: float
    effective_cached_raw_tokens: float
    effective_compressed_uncached_tokens: float
    compress_is_cheaper: bool
    break_even_cache_hit_rate: float | None

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return {
            "tokens_raw": self.tokens_raw,
            "tokens_compressed": self.tokens_compressed,
            "cache_hit_rate": self.cache_hit_rate,
            "cache_read_multiplier": self.cache_read_multiplier,
            "effective_cached_raw_tokens": self.effective_cached_raw_tokens,
            "effective_compressed_uncached_tokens": self.effective_compressed_uncached_tokens,
            "compress_is_cheaper": self.compress_is_cheaper,
            "break_even_cache_hit_rate": self.break_even_cache_hit_rate,
        }


def compare_cache_tradeoff(
    tokens_raw: int,
    tokens_compressed: int,
    *,
    cache_hit_rate: float,
    cache_read_multiplier: float = 0.1,
) -> CacheTradeoff:
    """Would compressing (and missing the prefix cache) beat caching the raw prompt?

    Providers match **exact prefixes**. Re-running Contextpress on the full
    history usually changes tokens in the prefix, so the compressed prompt is
    billed as uncached. Typical ``cache_read_multiplier``: Anthropic / recent
    OpenAI cached input ≈ ``0.1``; older OpenAI automatic cache ≈ ``0.5``.

    ``cache_hit_rate`` is the share of *raw* input tokens that would have been
    cache reads (0–1).
    """
    if tokens_raw < 0 or tokens_compressed < 0:
        raise ValueError("token counts must be >= 0")
    if not 0.0 <= cache_hit_rate <= 1.0:
        raise ValueError("cache_hit_rate must be between 0 and 1")
    if not 0.0 <= cache_read_multiplier <= 1.0:
        raise ValueError("cache_read_multiplier must be between 0 and 1")

    h = cache_hit_rate
    r = cache_read_multiplier
    effective_raw = tokens_raw * ((1.0 - h) + h * r)
    effective_comp = float(tokens_compressed)
    denom = 1.0 - r
    if tokens_raw <= 0 or denom <= 0:
        break_even: float | None = None
    else:
        # h where tokens_compressed == tokens_raw * (1 - h*(1-r))
        ratio = tokens_compressed / tokens_raw
        break_even = (1.0 - ratio) / denom
        if break_even < 0.0:
            break_even = 0.0
        elif break_even > 1.0:
            break_even = 1.0
        break_even = round(break_even, 4)

    return CacheTradeoff(
        tokens_raw=int(tokens_raw),
        tokens_compressed=int(tokens_compressed),
        cache_hit_rate=h,
        cache_read_multiplier=r,
        effective_cached_raw_tokens=round(effective_raw, 2),
        effective_compressed_uncached_tokens=round(effective_comp, 2),
        compress_is_cheaper=effective_comp < effective_raw,
        break_even_cache_hit_rate=break_even,
    )
