"""0.6.9 — shared jsonutil and clone helpers (no behavior change)."""

from __future__ import annotations

from contextpress.jsonutil import minify_json_string, try_minify_json, try_parse_json
from contextpress.models import Conversation, Turn, clone_conversation, clone_turn
from contextpress.pipeline import clone_turn as pipeline_clone_turn


def test_try_minify_json_object():
    raw = '{\n  "a": 1,\n  "b": [2, 3]\n}'
    assert try_minify_json(raw) == '{"a":1,"b":[2,3]}'
    assert try_parse_json(raw) == {"a": 1, "b": [2, 3]}


def test_minify_json_string_leaves_non_json():
    text = "not json at all"
    assert minify_json_string(text) == text
    assert try_minify_json(text) is None


def test_clone_turn_is_independent():
    t = Turn(role="user", content="hello", metadata={"k": [1]})
    c = clone_turn(t)
    assert c.content == "hello"
    c.content = "mutated"
    c.metadata["k"].append(2)
    assert t.content == "hello"
    assert t.metadata["k"] == [1]


def test_clone_conversation_is_independent():
    conv = Conversation(turns=[Turn(role="user", content="a")], type="chat", metadata={"x": 1})
    out = clone_conversation(conv)
    out.turns[0].content = "b"
    out.metadata["x"] = 2
    assert conv.turns[0].content == "a"
    assert conv.metadata["x"] == 1


def test_pipeline_reexports_clone_turn():
    t = Turn(role="assistant", content="x")
    assert pipeline_clone_turn(t).content == "x"
