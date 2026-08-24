"""0.6.8 — Gemini functionCall / functionResponse parts."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from contextpress import ContextManager
from contextpress.normalizer import normalize_messages
from contextpress.strategies.budget import BudgetStrategy
from contextpress.tools import has_tool_marker, tool_group_indices

FIXTURE = Path(__file__).parent / "fixtures" / "chats" / "15_gemini_tools.json"


def _pretty() -> str:
    return json.dumps({"service": "api-v2", "environment": "staging", "limit": 20}, indent=2)


def copy_messages(messages: list[dict]) -> list[dict]:
    return json.loads(json.dumps(messages))


def _gemini_thread() -> list[dict]:
    return [
        {"role": "user", "parts": [{"text": "Find staging deploys."}]},
        {
            "role": "model",
            "parts": [
                {
                    "functionCall": {
                        "id": "fc_1",
                        "name": "search_deploys",
                        "args": {"service": "api-v2", "environment": "staging"},
                    },
                    "thought_signature": "sig-abc",
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "id": "fc_1",
                        "name": "search_deploys",
                        "response": _pretty(),
                    }
                }
            ],
        },
        {"role": "model", "parts": [{"text": "Staging is healthy on 2.4.1."}]},
    ]


def test_model_role_no_unknown_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        conv, _ = normalize_messages(_gemini_thread())
    assert conv.turns[1].role == "assistant"
    assert not any("unknown role" in str(w.message).lower() for w in caught)


def test_gemini_roundtrip_keeps_parts_and_signature():
    messages = _gemini_thread()
    original = copy_messages(messages)
    cm = ContextManager(type="agent", compression="medium")
    out = cm.compress(messages, token_budget=None)
    assert messages == original
    model = next(
        m
        for m in out
        if m.get("role") == "model" and any(p.get("functionCall") for p in m.get("parts") or [])
    )
    assert "content" not in model
    call = next(p for p in model["parts"] if p.get("functionCall"))
    assert call["thought_signature"] == "sig-abc"
    assert call["functionCall"]["id"] == "fc_1"
    assert call["functionCall"]["name"] == "search_deploys"
    assert isinstance(call["functionCall"]["args"], dict)
    assert call["functionCall"]["args"]["service"] == "api-v2"
    resp_msg = next(
        m
        for m in out
        if m.get("role") == "user" and any("functionResponse" in p for p in m.get("parts") or [])
    )
    body = resp_msg["parts"][0]["functionResponse"]["response"]
    assert isinstance(body, str)
    assert "\n" not in body
    assert json.loads(body)["service"] == "api-v2"


def test_gemini_pretty_args_string_minified_stays_string():
    messages = [
        {
            "role": "model",
            "parts": [
                {
                    "functionCall": {
                        "id": "fc_1",
                        "name": "search",
                        "args": _pretty(),
                    }
                }
            ],
        }
    ]
    original = copy_messages(messages)
    out = ContextManager(type="agent", compression="medium").compress(messages, token_budget=None)
    assert messages == original
    args = out[0]["parts"][0]["functionCall"]["args"]
    assert isinstance(args, str)
    assert "\n" not in args
    assert json.loads(args)["service"] == "api-v2"


def test_gemini_snake_case_parts():
    messages = [
        {
            "role": "model",
            "parts": [
                {
                    "function_call": {
                        "id": "fc_x",
                        "name": "echo",
                        "arguments": _pretty(),
                    }
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    "function_response": {
                        "id": "fc_x",
                        "name": "echo",
                        "response": {"ok": True},
                    }
                }
            ],
        },
    ]
    conv, _ = normalize_messages(messages, context_type="agent")
    assert has_tool_marker(conv.turns[0])
    assert has_tool_marker(conv.turns[1])
    out = ContextManager(type="agent", compression="low").compress(messages, token_budget=None)
    call = out[0]["parts"][0]["function_call"]
    assert isinstance(call["arguments"], str)
    assert "\n" not in call["arguments"]
    assert json.loads(call["arguments"])["service"] == "api-v2"
    assert isinstance(out[1]["parts"][0]["function_response"]["response"], dict)
    assert out[0]["role"] == "model"


def test_gemini_budget_keeps_call_and_response_together():
    padding = "deploy status note " * 40
    messages = [
        {
            "role": "model",
            "parts": [
                {
                    "functionCall": {
                        "id": "fc_old",
                        "name": "search",
                        "args": {"q": padding},
                    }
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "id": "fc_old",
                        "name": "search",
                        "response": {"note": padding},
                    }
                }
            ],
        },
        {"role": "user", "parts": [{"text": "what is the latest status?"}]},
        {"role": "model", "parts": [{"text": "Latest is healthy."}]},
    ]
    conv, _ = normalize_messages(messages, context_type="agent")
    assert tool_group_indices(conv.turns, 0) == [0, 1]
    out = BudgetStrategy(token_budget=50, model=None).process(conv)
    call_ids = set()
    result_ids = set()
    for t in out.turns:
        if not isinstance(t.content, list):
            continue
        for b in t.content:
            if b.type == "function_call":
                cid = (b.metadata or {}).get("functionCall", {}).get("id")
                if cid:
                    call_ids.add(str(cid))
            if b.type == "function_response":
                cid = (b.metadata or {}).get("functionResponse", {}).get("id")
                if cid:
                    result_ids.add(str(cid))
    assert result_ids <= call_ids


def test_gemini_fixture_compresses():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cm = ContextManager(type="agent", compression="medium")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    assert result.stats.tokens_after <= result.stats.tokens_before
    model = next(
        m
        for m in result.messages
        if m.get("role") == "model"
        and any(p.get("thought_signature") for p in m.get("parts") or [])
    )
    assert model["parts"][0]["thought_signature"] == "sig-keep-me"
    resp = next(
        p["functionResponse"]["response"]
        for m in result.messages
        for p in m.get("parts") or []
        if "functionResponse" in p
    )
    assert "\n" not in resp
    json.loads(resp)
