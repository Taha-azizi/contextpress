import copy
import json
from pathlib import Path

import pytest

from contextpress import ContextManager


def test_messages_none_raises():
    cm = ContextManager(type="chat")
    with pytest.raises(TypeError, match="must not be None"):
        cm.compress(None)


def test_extra_dict_keys_preserved():
    cm = ContextManager(type="chat")
    messages = [{"role": "user", "content": "hello basically", "name": "alice", "custom": 123}]
    out = cm.compress(messages, token_budget=None)
    assert out[0]["name"] == "alice"
    assert out[0]["custom"] == 123


def test_rag_doc_skips_resolution_stage():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "chats" / "06_rag_chunks.json").read_text(
            encoding="utf-8"
        )
    )
    cm = ContextManager(type="rag_doc", compression="high")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    assert "resolution" not in result.stats.stages_run
    assert not any("RESOLVED" in str(m.get("content", "")) for m in result.messages)


def test_resolution_fixture_collapses():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "chats" / "02_resolution_thread.json").read_text(
            encoding="utf-8"
        )
    )
    cm = ContextManager(type="chat", compression="high")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    assert any("RESOLVED" in str(m.get("content", "")) for m in result.messages)


def test_compress_many_immutability():
    batches = [
        [{"role": "user", "content": "hello basically"}],
        [{"role": "user", "content": "thanks basically"}],
    ]
    original = copy.deepcopy(batches)
    cm = ContextManager(type="chat")
    cm.compress_many(batches, token_budget=200)
    assert batches == original
