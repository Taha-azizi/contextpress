"""0.6.10 — trim stage keeps opening + last turns, drops the middle."""

from __future__ import annotations

from contextpress import ContextManager
from contextpress.compression import STAGE_ORDER
from contextpress.models import Conversation, Turn
from contextpress.strategies.trim import TrimStrategy


def _long_chat(n: int = 12) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": "You are a support bot."}]
    for i in range(n):
        messages.append({"role": "user", "content": f"User turn {i} with unique token U{i}."})
        messages.append(
            {"role": "assistant", "content": f"Assistant turn {i} with unique token A{i}."}
        )
    return messages


def test_trim_not_in_low_preset():
    assert "trim" in STAGE_ORDER
    low = ContextManager(type="chat", compression="low").compress(
        _long_chat(8), token_budget=None, return_stats=True
    )
    assert "trim" not in low.stats.stages_run
    med = ContextManager(type="chat", compression="medium").compress(
        _long_chat(8), token_budget=None, return_stats=True
    )
    assert "trim" in med.stats.stages_run
    assert med.stats.turns_after < med.stats.turns_before


def test_trim_keeps_opening_and_last_three():
    messages = _long_chat(6)  # system + 12 non-system
    out = ContextManager(type="chat").compress(messages, token_budget=None, stages=["trim"])
    texts = [m.get("content", "") for m in out]
    assert out[0]["content"] == "You are a support bot."
    assert any("U0" in t for t in texts)
    assert any("A0" in t for t in texts)
    assert any("U5" in t for t in texts)
    assert any("A5" in t for t in texts)
    # middle of the thread is gone
    assert not any("U2" in t for t in texts)
    assert any("earlier messages omitted" in t for t in texts)


def test_trim_noop_on_short_chat():
    messages = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
    ]
    cm = ContextManager(type="chat", compression="low")
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert result.stats.turns_after == result.stats.turns_before
    assert "trim" not in result.stats.stages_run


def test_trim_keeps_tool_pair_in_middle():
    messages = _long_chat(5)
    # Insert a tool pair in the middle (after first exchange).
    tool_block = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_mid",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_mid", "name": "lookup", "content": "{}"},
    ]
    # system + u0 a0 + tools + rest
    messages = [messages[0], messages[1], messages[2], *tool_block, *messages[3:]]
    out = ContextManager(type="agent").compress(messages, token_budget=None, stages=["trim"])
    ids = []
    for m in out:
        if m.get("tool_calls"):
            ids.append(m["tool_calls"][0]["id"])
        if m.get("role") == "tool":
            ids.append(m.get("tool_call_id"))
    assert "call_mid" in ids
    assert out[-1]["content"].endswith("A4.") or "A4" in str(out[-1].get("content"))


def test_trim_strategy_direct():
    conv = Conversation(
        turns=[Turn(role="system", content="s")]
        + [Turn(role="user" if i % 2 == 0 else "assistant", content=f"t{i}") for i in range(10)],
        type="chat",
    )
    out = TrimStrategy(aggressiveness=0.55).process(conv)
    ns = [t for t in out.turns if t.role != "system"]
    assert any(t.metadata.get("_trim_stub") for t in out.turns)
    assert ns[-1].content == "t9"
    assert ns[-2].content == "t8"
    assert ns[-3].content == "t7"
