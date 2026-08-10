"""0.6.2 — agent fixtures, stats.summary(), example script."""

from __future__ import annotations

import json
from pathlib import Path

from contextpress import ContextManager
from contextpress.stats import CompressionResult, CompressionStats

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "chats"
AGENT_FIXTURES = [
    FIXTURES_DIR / "09_agent_tool_json.json",
    FIXTURES_DIR / "10_agent_repeated_logs.json",
    FIXTURES_DIR / "11_agent_mixed.json",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_summary_basic():
    stats = CompressionStats(
        context_type="agent",
        compression_level="medium",
        turns_before=8,
        turns_after=6,
        tokens_before=1000,
        tokens_after=500,
        stages_run=["structure", "filler", "repetition"],
    )
    text = stats.summary()
    assert "agent" in text
    assert "medium" in text
    assert "1000 -> 500 tokens" in text
    assert "50.0% saved" in text
    assert "structure" in text
    assert "est. input cost" not in text


def test_summary_includes_cost_when_present():
    stats = CompressionStats(
        context_type="chat",
        compression_level="low",
        turns_before=4,
        turns_after=4,
        tokens_before=200,
        tokens_after=150,
        stages_run=["structure"],
        estimated_input_cost_before_usd=0.000030,
        estimated_input_cost_after_usd=0.0000225,
    )
    text = stats.summary()
    assert "est. input cost:" in text
    assert "saved $0.000008" in text


def test_summary_dry_run_flag():
    stats = CompressionStats(
        context_type="chat",
        dry_run=True,
        turns_before=2,
        turns_after=2,
        tokens_before=50,
        tokens_after=50,
    )
    assert "[dry-run]" in stats.summary()


def test_compression_result_summary_delegates():
    stats = CompressionStats(
        context_type="agent",
        turns_before=3,
        turns_after=3,
        tokens_before=100,
        tokens_after=80,
    )
    result = CompressionResult(messages=[], stats=stats)
    assert result.summary() == stats.summary()


def test_agent_tool_json_fixture_structure_saves_tokens():
    data = _load(AGENT_FIXTURES[0])
    cm = ContextManager(type="agent", compression="medium")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    assert "structure" in result.stats.stages_run
    assert result.stats.tokens_after < result.stats.tokens_before
    texts = " ".join(str(m.get("content", "")) for m in result.messages)
    assert "tool_call" in texts or "api-v2" in texts


def test_agent_repeated_logs_dedupes_lines():
    data = _load(AGENT_FIXTURES[1])
    cm = ContextManager(type="agent", compression="medium")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    assert "structure" in result.stats.stages_run
    tool_turn = next(m for m in result.messages if m.get("role") == "user" and "Tool result" in str(m.get("content", "")))
    content = str(tool_turn["content"])
    assert content.count("payment gateway timeout") == 1


def test_agent_mixed_preserves_tool_markers():
    data = _load(AGENT_FIXTURES[2])
    cm = ContextManager(type="agent", compression="high")
    result = cm.compress(data["messages"], token_budget=600, return_stats=True)
    texts = " ".join(str(m.get("content", "")) for m in result.messages)
    assert "tool_call" in texts or "DEP-4821" in texts or "pipeline" in texts
    assert result.stats.tokens_after <= result.stats.tokens_before


def test_compress_summary_with_cost_provider():
    cm = ContextManager(type="agent", model="gpt-4o-mini", cost_provider="openai")
    messages = [
        {"role": "user", "content": json.dumps({"hits": list(range(50))}, indent=2)},
    ]
    result = cm.compress(messages, token_budget=None, return_stats=True)
    summary = result.summary()
    assert "est. input cost:" in summary
    assert result.stats.estimated_cost_saved_usd is not None
