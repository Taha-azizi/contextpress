from contextpress import ContextManager
from contextpress.stats import CompressionStats


def test_attach_cost_on_stats():
    stats = CompressionStats(tokens_before=1_000_000, tokens_after=500_000)
    stats.attach_cost(provider="openai", model="gpt-4o-mini")
    assert stats.cost_provider == "openai"
    assert stats.cost_model == "gpt-4o-mini"
    assert stats.estimated_input_cost_before_usd == 0.15
    assert stats.estimated_input_cost_after_usd == 0.075
    assert stats.estimated_cost_saved_usd == 0.075
    d = stats.to_dict()
    assert d["estimated_cost_saved_usd"] == 0.075


def test_cost_fields_none_by_default():
    cm = ContextManager(type="chat")
    result = cm.compress(
        [{"role": "user", "content": "hello basically"}],
        token_budget=None,
        return_stats=True,
    )
    assert result.stats.cost_provider is None
    assert result.stats.estimated_cost_saved_usd is None


def test_compress_attaches_cost_when_provider_set():
    cm = ContextManager(type="chat", model="gpt-4o-mini", cost_provider="openai")
    messages = [{"role": "user", "content": "basically " + ("word " * 80)}]
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert result.stats.cost_provider == "openai"
    assert result.stats.estimated_input_cost_before_usd is not None
    assert result.stats.estimated_input_cost_after_usd is not None
    assert result.stats.estimated_cost_saved_usd is not None
    assert result.stats.estimated_cost_saved_usd >= 0


def test_compress_cost_provider_kwarg_overrides_default():
    cm = ContextManager(type="chat", model="gpt-4o-mini", cost_provider="openai")
    result = cm.compress(
        [{"role": "user", "content": "hello " * 40}],
        token_budget=None,
        return_stats=True,
        cost_provider="local",
    )
    assert result.stats.cost_provider == "local"
    assert result.stats.estimated_input_cost_before_usd == 0.0


def test_preview_inherits_cost_provider():
    cm = ContextManager(type="chat", model="gpt-4o-mini", cost_provider="anthropic")
    preview = cm.preview([{"role": "user", "content": "hello " * 20}], token_budget=500)
    assert preview.stats.cost_provider == "anthropic"
    assert preview.stats.estimated_input_cost_before_usd is not None
