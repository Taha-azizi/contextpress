"""0.6.7 — Anthropic tool_use / tool_result content blocks."""

from __future__ import annotations

import json
from pathlib import Path

from contextpress import ContextManager
from contextpress.normalizer import normalize_messages
from contextpress.strategies.budget import BudgetStrategy
from contextpress.tools import has_tool_marker, tool_group_indices

FIXTURE = Path(__file__).parent / "fixtures" / "chats" / "14_anthropic_tools.json"


def _pretty() -> str:
    return json.dumps({"service": "api-v2", "environment": "staging", "limit": 20}, indent=2)


def _anthropic_thread() -> list[dict]:
    return [
        {"role": "system", "content": "You are a deploy agent."},
        {"role": "user", "content": "Find staging deploys."},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Checking deploys."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "search_deploys",
                    "input": {"service": "api-v2", "environment": "staging"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": _pretty(),
                }
            ],
        },
        {"role": "assistant", "content": "Staging is healthy on 2.4.1."},
    ]


def test_anthropic_blocks_roundtrip_types():
    conv, ctx = normalize_messages(_anthropic_thread())
    asst = conv.turns[2]
    result = conv.turns[3]
    assert isinstance(asst.content, list)
    assert any(b.type == "tool_use" for b in asst.content)
    assert all(b.type == "tool_result" for b in result.content)
    assert has_tool_marker(asst)
    assert has_tool_marker(result)


def test_anthropic_tool_result_json_minified():
    messages = _anthropic_thread()
    original = json.loads(json.dumps(messages))
    cm = ContextManager(type="agent", compression="medium")
    out = cm.compress(messages, token_budget=None)
    assert messages == original
    result = next(
        m
        for m in out
        if isinstance(m.get("content"), list)
        and any(p.get("type") == "tool_result" for p in m["content"])
    )
    body = result["content"][0]["content"]
    assert "\n" not in body
    assert json.loads(body)["service"] == "api-v2"
    asst = next(
        m
        for m in out
        if isinstance(m.get("content"), list)
        and any(p.get("type") == "tool_use" for p in m["content"])
    )
    use = next(p for p in asst["content"] if p["type"] == "tool_use")
    assert use["id"] == "toolu_1"
    assert use["name"] == "search_deploys"
    assert use["input"]["service"] == "api-v2"


def test_anthropic_budget_keeps_tool_use_and_result_together():
    padding = "deploy status note " * 40
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_old",
                    "name": "search",
                    "input": {"q": padding},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_old",
                    "content": padding,
                }
            ],
        },
        {"role": "user", "content": "what is the latest status?"},
        {"role": "assistant", "content": "Latest is healthy."},
    ]
    conv, _ = normalize_messages(messages, context_type="agent")
    group = tool_group_indices(conv.turns, 0)
    assert group == [0, 1]
    out = BudgetStrategy(token_budget=50, model=None).process(conv)
    use_ids = set()
    result_ids = set()
    for t in out.turns:
        if isinstance(t.content, list):
            for b in t.content:
                if b.type == "tool_use" and (b.metadata or {}).get("id"):
                    use_ids.add(str(b.metadata["id"]))
                if b.type == "tool_result" and (b.metadata or {}).get("tool_use_id"):
                    result_ids.add(str(b.metadata["tool_use_id"]))
    assert result_ids <= use_ids


def test_anthropic_fixture_compresses():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cm = ContextManager(type="agent", compression="medium")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    assert result.stats.tokens_after <= result.stats.tokens_before
    tool_result = next(
        block
        for m in result.messages
        if isinstance(m.get("content"), list)
        for block in m["content"]
        if block.get("type") == "tool_result"
    )
    assert "\n" not in tool_result["content"]
    json.loads(tool_result["content"])
