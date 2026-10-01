"""0.7.6: rag_doc pins two-word names dropped by medium/high compression."""

from __future__ import annotations

from contextpress import ContextManager
from contextpress.models import Conversation, Turn
from contextpress.pinned_facts import apply_pinned_facts
from tests.test_v074 import _QUESTION, _sections


def test_high_pins_name_from_dropped_section() -> None:
    messages = _sections()
    messages[6] = {
        "role": "user",
        "content": "Warehouse clerks counted nutmeg beside Ada Lovelace.",
    }
    out = ContextManager(type="rag_doc", compression="high").compress(messages, return_stats=True)
    body = "\n".join(str(m.get("content") or "") for m in out.messages)
    assert "Ada Lovelace" in body
    assert "Kept names:" in body
    assert "nutmeg" not in body
    assert out.stats.pinned_fact_count >= 1
    assert out.messages[-1]["content"] == _QUESTION


def test_name_already_in_the_question_is_not_repeated() -> None:
    messages = _sections()
    messages[-1] = {"role": "user", "content": f"{_QUESTION} Asked of Ada Lovelace."}
    messages[6] = {
        "role": "user",
        "content": "Warehouse clerks counted nutmeg beside Ada Lovelace.",
    }
    out = ContextManager(type="rag_doc", compression="high").compress(messages, return_stats=True)
    body = "\n".join(str(m.get("content") or "") for m in out.messages)
    assert body.count("Ada Lovelace") == 1
    assert "Kept names:" not in body


def test_name_cap_at_forty() -> None:
    dropped = "\n".join(f"Ann {chr(65 + (i // 26))}{chr(97 + (i % 26))}a" for i in range(50))
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
    line = next(str(t.content or "") for t in out.turns if "Kept names:" in str(t.content or ""))
    assert line.count(";") == 39


def test_chat_compression_has_no_kept_names_line() -> None:
    messages = [
        {"role": "user", "content": "Ask Ada Lovelace about the migration plan."},
        {"role": "assistant", "content": "Will ask shortly."},
        {"role": "user", "content": "Thanks."},
    ]
    out = ContextManager(type="chat", compression="high").compress(messages, return_stats=True)
    body = "\n".join(str(m.get("content") or "") for m in out.messages)
    assert "Kept names:" not in body
    assert out.stats.pinned_fact_count == 0
