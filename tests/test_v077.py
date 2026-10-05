"""0.7.7: numbers pin up to 120; other critical spans stay at 40."""

from __future__ import annotations

from contextpress.models import Conversation, Turn
from contextpress.pinned_facts import apply_pinned_facts


def _dropped(body: str) -> tuple[Conversation, Conversation]:
    original = Conversation(
        type="rag_doc",
        turns=[
            Turn(role="user", content=f"Offtopic warehouse prose.\n{body}"),
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
    return original, compressed


def test_number_pins_cap_at_one_hundred_twenty() -> None:
    original, compressed = _dropped(" ".join(str(1000 + i) for i in range(130)))
    _out, count = apply_pinned_facts(original, compressed)
    assert count == 120


def test_non_number_pins_still_cap_at_forty() -> None:
    urls = " ".join(f"https://example.com/item/{i}" for i in range(50))
    original, compressed = _dropped(urls)
    out, count = apply_pinned_facts(original, compressed)
    assert count == 40
    assert any("Kept figures:" in str(t.content or "") for t in out.turns)
