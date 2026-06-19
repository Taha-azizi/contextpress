from datetime import datetime, timezone

from contextpress.models import ContentBlock, Conversation, Turn


def test_turn_text_detection():
    t1 = Turn(role="user", content="hello")
    t2 = Turn(role="user", content="")
    t3 = Turn(role="user", content=[ContentBlock(type="text", content="hi")])
    c = Conversation(turns=[t1, t2, t3])
    assert len(c.text_turns()) == 2


def test_non_system_turns():
    c = Conversation(
        turns=[
            Turn(role="system", content="sys"),
            Turn(role="user", content="u"),
        ]
    )
    assert len(c.non_system_turns()) == 1


def test_timestamp_optional():
    t = Turn(role="user", content="x", timestamp=datetime.now(timezone.utc))
    assert t.timestamp is not None
