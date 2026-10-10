"""0.7.8: two-word names pin up to 160."""

from __future__ import annotations

from contextpress.models import Conversation, Turn
from contextpress.pinned_facts import apply_pinned_facts


def test_name_pins_cap_at_one_hundred_sixty() -> None:
    dropped = "\n".join(f"Ann {chr(65 + (i // 26))}{chr(97 + (i % 26))}n" for i in range(170))
    original = Conversation(
        type="rag_doc",
        turns=[
            Turn(role="user", content=dropped),
            Turn(role="user", content="What is the roster?"),
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
            Turn(role="user", content="What is the roster?"),
        ],
    )
    _out, count = apply_pinned_facts(original, compressed)
    assert count == 160
