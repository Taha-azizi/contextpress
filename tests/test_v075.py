"""0.7.5: rag_doc pins critical spans dropped by medium/high compression."""

from __future__ import annotations

from contextpress import ContextManager
from contextpress.models import Conversation, Turn
from contextpress.pinned_facts import apply_pinned_facts
from tests.test_v074 import _QUESTION, _sections


def test_high_pins_year_from_dropped_offtopic_section() -> None:
    messages = _sections()
    messages[6] = {
        "role": "user",
        "content": "Warehouse clerks counted 1859 nutmeg crates beside tar barrels.",
    }
    out = ContextManager(type="rag_doc", compression="high").compress(messages, return_stats=True)
    body = "\n".join(str(m.get("content") or "") for m in out.messages)
    assert "1859" in body
    assert "Kept figures:" in body
    assert "nutmeg" not in body
    assert out.stats.pinned_fact_count >= 1
    assert out.messages[-1]["content"] == _QUESTION


def test_pin_not_duplicated_when_span_already_in_question() -> None:
    messages = _sections()
    messages[-1] = {"role": "user", "content": f"{_QUESTION} Reference year 1859."}
    messages[6] = {
        "role": "user",
        "content": "Warehouse clerks counted 1859 nutmeg crates beside tar barrels.",
    }
    out = ContextManager(type="rag_doc", compression="high").compress(messages, return_stats=True)
    body = out.messages[-1]["content"]
    assert body.count("1859") == 1
    assert out.stats.pinned_fact_count == 0


def test_pin_cap_at_forty() -> None:
    dropped = " ".join(str(1000 + i) for i in range(50))
    original = Conversation(
        type="rag_doc",
        turns=[
            Turn(role="user", content=f"Offtopic warehouse prose.\n{dropped}"),
            Turn(role="user", content="What is in the warehouse?"),
        ],
    )
    compressed = Conversation(
        type="rag_doc",
        turns=[
            Turn(
                role="assistant",
                content="[1 earlier messages omitted]",
                compressed=True,
                metadata={"_trim_stub": True},
            ),
            Turn(role="user", content="What is in the warehouse?"),
        ],
    )
    out, count = apply_pinned_facts(original, compressed)
    assert count == 40
    line = next(str(t.content or "") for t in out.turns if "Kept figures:" in str(t.content or ""))
    assert line.count(";") == 39


def test_chat_compression_has_no_kept_figures_line() -> None:
    messages = [
        {"role": "user", "content": "Deploy version 2.4.1 to https://example.com/app now."},
        {"role": "assistant", "content": "Will deploy shortly."},
        {"role": "user", "content": "Thanks."},
    ]
    out = ContextManager(type="chat", compression="high").compress(messages, return_stats=True)
    body = "\n".join(str(m.get("content") or "") for m in out.messages)
    assert "Kept figures:" not in body
    assert out.stats.pinned_fact_count == 0
