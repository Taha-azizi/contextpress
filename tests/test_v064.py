"""0.6.4 — OpenAI tool_calls / role=tool round-trip."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from contextpress import ContextManager
from contextpress.models import Conversation, Turn
from contextpress.normalizer import normalize_messages
from contextpress.strategies.budget import BudgetStrategy
from contextpress.tools import has_tool_marker

FIXTURE = Path(__file__).parent / "fixtures" / "chats" / "12_openai_tools.json"


def _pretty_args() -> str:
    return json.dumps({"service": "api-v2", "environment": "staging", "limit": 20}, indent=2)


def _openai_tool_thread() -> list[dict]:
    return [
        {"role": "system", "content": "You are a deploy agent."},
        {"role": "user", "content": "Find staging deploys."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_search_1",
                    "type": "function",
                    "function": {"name": "search_deploys", "arguments": _pretty_args()},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_search_1",
            "name": "search_deploys",
            "content": json.dumps({"ok": True, "version": "2.4.1"}, indent=2),
        },
        {"role": "assistant", "content": "Staging is healthy on 2.4.1."},
        {"role": "user", "content": "Thanks, that is all."},
    ]


def _call_and_result_ids(messages: list[dict]) -> tuple[set[str], set[str]]:
    calls: set[str] = set()
    results: set[str] = set()
    for m in messages:
        if m.get("role") == "assistant":
            for c in m.get("tool_calls") or []:
                if isinstance(c, dict) and c.get("id"):
                    calls.add(str(c["id"]))
        if m.get("role") == "tool" and m.get("tool_call_id"):
            results.add(str(m["tool_call_id"]))
    return calls, results


def test_tool_role_no_unknown_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        conv, _ = normalize_messages(_openai_tool_thread())
    assert conv.turns[3].role == "tool"
    assert not any("unknown role" in str(w.message).lower() for w in caught)


def test_tool_keys_copied_to_metadata():
    conv, _ = normalize_messages(_openai_tool_thread())
    asst = conv.turns[2]
    tool = conv.turns[3]
    assert "tool_calls" in asst.metadata
    assert asst.metadata["tool_calls"][0]["id"] == "call_search_1"
    assert tool.metadata.get("tool_call_id") == "call_search_1"
    assert tool.metadata.get("name") == "search_deploys"
    assert has_tool_marker(asst)
    assert has_tool_marker(tool)


def test_has_tool_marker_via_original_dict_only():
    t = Turn(
        role="assistant",
        content="",
        metadata={
            "_original_dict": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "x"}],
            }
        },
    )
    assert has_tool_marker(t)


def test_empty_tool_calls_assistant_not_dropped():
    messages = [
        {"role": "user", "content": "search now"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": "{}"},
                }
            ],
        },
    ]
    cm = ContextManager(type="agent", compression="high")
    out = cm.compress(messages, token_budget=None)
    assert any(m.get("tool_calls") for m in out)
    assert out[1]["content"] is None


def test_roundtrip_keeps_tool_keys_and_minifies_json():
    messages = _openai_tool_thread()
    original = json.loads(json.dumps(messages))
    cm = ContextManager(type="agent", compression="medium")
    out = cm.compress(messages, token_budget=None)
    assert messages == original
    asst = next(m for m in out if m.get("tool_calls"))
    tool = next(m for m in out if m.get("role") == "tool")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert "\n" not in args
    assert json.loads(args)["service"] == "api-v2"
    assert "\n" not in tool["content"]
    assert json.loads(tool["content"])["ok"] is True
    assert tool["tool_call_id"] == "call_search_1"
    assert tool["name"] == "search_deploys"


def test_budget_does_not_orphan_tool_result():
    padding = "deploy status note " * 40
    turns = [
        Turn(
            role="assistant",
            content="",
            metadata={
                "tool_calls": [
                    {
                        "id": "call_old",
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"},
                    }
                ]
            },
        ),
        Turn(role="tool", content=padding, metadata={"tool_call_id": "call_old"}),
        Turn(role="user", content="what is the latest status?"),
        Turn(role="assistant", content="Latest is healthy."),
    ]
    c = Conversation(turns=turns, type="agent")
    out = BudgetStrategy(token_budget=40, model=None).process(c)
    remaining = [(t.role, (t.metadata or {}).get("tool_call_id")) for t in out.turns]
    tool_ids = {t.metadata.get("tool_call_id") for t in out.turns if t.role == "tool"}
    call_ids = set()
    for t in out.turns:
        for call in (t.metadata or {}).get("tool_calls") or []:
            if isinstance(call, dict) and call.get("id"):
                call_ids.add(call["id"])
    assert tool_ids <= call_ids
    assert remaining[-1][0] == "assistant"


def test_fixture_openai_tools_compresses():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cm = ContextManager(type="agent", compression="medium")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    calls, results = _call_and_result_ids(result.messages)
    assert results <= calls
    assert result.stats.tokens_after <= result.stats.tokens_before
    asst = next(m for m in result.messages if m.get("tool_calls"))
    assert "\n" not in asst["tool_calls"][0]["function"]["arguments"]
