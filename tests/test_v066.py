"""0.6.6 — later stages must not mangle tool or JSON payloads."""

from __future__ import annotations

import json

from contextpress import ContextManager
from contextpress.models import Conversation, Turn
from contextpress.strategies.recency import RecencyStrategy
from contextpress.strategies.repetition import RepetitionStrategy
from contextpress.strategies.resolution import ResolutionStrategy
from contextpress.tools import is_structured_text, preserve_structured_turn

_JSON_PROSE = (
    "Sentence one about topic. Sentence two adds detail. "
    "Sentence three continues. Sentence four concludes early. "
    "Sentence five wraps up the discussion here."
)


def _chat_padding(n: int) -> list[Turn]:
    body = (
        "Sentence one about topic. Sentence two adds detail. "
        "Sentence three continues. Sentence four concludes early. "
        "Sentence five wraps up the discussion here."
    )
    turns: list[Turn] = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        turns.append(Turn(role=role, content=body))
    return turns


def test_is_structured_text_json_and_fence():
    assert is_structured_text('{\n  "a": 1\n}')
    assert is_structured_text('```json\n{"a": 1}\n```')
    assert not is_structured_text("Hello. This is prose about Postgres.")


def test_preserve_tool_marker_turn():
    t = Turn(
        role="assistant",
        content="",
        metadata={"tool_calls": [{"id": "c1"}]},
    )
    assert preserve_structured_turn(t)


def test_recency_does_not_summarize_json_blob():
    payload = json.dumps({"notes": _JSON_PROSE, "extra": _JSON_PROSE}, indent=2)
    turns = [Turn(role="user", content=payload)] + _chat_padding(6)
    c = Conversation(turns=turns, type="chat")
    out = RecencyStrategy(aggressiveness=1.0, conv_type="chat").process(c)
    json.loads(out.turns[0].content)
    assert out.turns[0].content == payload


def test_recency_does_not_summarize_fenced_json():
    blob = json.dumps({"notes": _JSON_PROSE, "service": "api-v2"}, indent=2)
    fenced = f"```json\n{blob}\n```"
    turns = [
        Turn(role="user", content=fenced),
        Turn(role="user", content="Chunk: rain is expected tomorrow in Seattle with strong winds."),
        Turn(role="user", content="What is the weather tomorrow?"),
    ]
    c = Conversation(turns=turns, type="rag_doc")
    out = RecencyStrategy(aggressiveness=1.0, conv_type="rag_doc").process(c)
    content = out.turns[0].content
    assert "```json" in content
    assert '"service": "api-v2"' in content or '"service":"api-v2"' in content


def test_repetition_does_not_drop_tool_calls_assistant():
    base = "The search found " + "x " * 12 + "matching deploy records in staging today"
    turns = [
        Turn(
            role="assistant",
            content=base + " old",
            metadata={
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"},
                    }
                ]
            },
        ),
        Turn(role="tool", content=base, metadata={"tool_call_id": "call_1"}),
        Turn(role="assistant", content=base + " new"),
    ]
    c = Conversation(turns=turns, type="agent")
    out = RepetitionStrategy(aggressiveness=1.0, role_aware=True, conv_type="agent").process(c)
    assert any((t.metadata or {}).get("tool_calls") for t in out.turns)
    tool_ids = {t.metadata.get("tool_call_id") for t in out.turns if t.role == "tool"}
    call_ids = set()
    for t in out.turns:
        for call in (t.metadata or {}).get("tool_calls") or []:
            if isinstance(call, dict) and call.get("id"):
                call_ids.add(call["id"])
    assert tool_ids <= call_ids
    assert len(out.turns) == 3


def test_resolution_does_not_collapse_thread_with_tools():
    shared = "We've decided on using the new pipeline for api-v2 staging."
    turns = [
        Turn(role="user", content=shared + " Check deploy status."),
        Turn(
            role="assistant",
            content=shared + " Checking now.",
            metadata={"tool_calls": [{"id": "call_1", "type": "function"}]},
        ),
        Turn(
            role="tool",
            content=shared + ' {"ok": true}',
            metadata={"tool_call_id": "call_1"},
        ),
        Turn(role="user", content=shared + " Ok let's go with that."),
        Turn(role="assistant", content="Confirmed. " + shared),
    ]
    c = Conversation(turns=turns, type="agent")
    out = ResolutionStrategy(aggressiveness=0.8, conv_type="agent").process(c)
    assert not any("RESOLVED" in str(t.content) for t in out.turns)
    assert any(t.role == "tool" for t in out.turns)
    assert any((t.metadata or {}).get("tool_calls") for t in out.turns)


def test_resolution_still_collapses_chat_without_tools():
    turns = [
        Turn(role="user", content="Should we use Postgres or Mongo?"),
        Turn(role="assistant", content="Postgres is relational."),
        Turn(role="user", content="Ok let's go with Postgres then."),
        Turn(role="assistant", content="Agreed. Postgres it is."),
    ]
    c = Conversation(turns=turns, type="chat")
    out = ResolutionStrategy(conv_type="chat").process(c)
    assert any(t.role == "system" and "RESOLVED" in str(t.content) for t in out.turns)


def test_compress_agent_tools_keep_json_parseable():
    payload = json.dumps({"notes": _JSON_PROSE, "service": "api-v2"}, indent=2)
    messages = [
        {"role": "system", "content": "You are a deploy agent."},
        {"role": "user", "content": payload},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "echo", "arguments": payload},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": payload},
        {"role": "user", "content": "What is the service name?"},
        {"role": "assistant", "content": "api-v2 is healthy."},
    ]
    cm = ContextManager(type="agent", compression="high")
    out = cm.compress(messages, token_budget=None)
    tool = next(m for m in out if m.get("role") == "tool")
    json.loads(tool["content"])
    asst = next(m for m in out if m.get("tool_calls"))
    json.loads(asst["tool_calls"][0]["function"]["arguments"])
