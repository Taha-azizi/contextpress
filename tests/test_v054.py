import pytest

from contextpress import CompressionResult, ContextManager


def test_compress_many_returns_list():
    cm = ContextManager(type="chat")
    batches = [
        [{"role": "user", "content": "hello basically"}],
        [{"role": "user", "content": "thanks basically"}],
    ]
    out = cm.compress_many(batches, token_budget=200)
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(item, list) for item in out)


def test_compress_many_with_stats():
    cm = ContextManager(type="chat")
    batches = [
        [{"role": "user", "content": "hello basically there"}],
        [{"role": "assistant", "content": "sounds good"}],
    ]
    results = cm.compress_many(batches, token_budget=500, return_stats=True)
    assert len(results) == 2
    assert all(isinstance(r, CompressionResult) for r in results)
    assert results[0].stats.turns_before == 1
    assert results[1].stats.turns_before == 1


def test_compress_many_empty():
    cm = ContextManager(type="chat")
    assert cm.compress_many([], token_budget=100) == []


def test_compress_many_requires_list():
    cm = ContextManager(type="chat")
    with pytest.raises(TypeError, match="conversations must be a list"):
        cm.compress_many("not a list")  # type: ignore[arg-type]


def test_agent_pipeline_compresses():
    cm = ContextManager(type="agent", compression="high")
    messages = [
        {"role": "system", "content": "Agent."},
        {"role": "user", "content": "Deploy api-v2?"},
        {"role": "assistant", "content": "Using pipeline <tool_call> deploy"},
        {"role": "user", "content": "We've decided on using the new pipeline for deploy."},
        {"role": "assistant", "content": "Confirmed."},
    ]
    result = cm.compress(messages, token_budget=200, return_stats=True)
    assert result.stats.context_type == "agent"
    assert result.stats.tokens_after <= result.stats.tokens_before
