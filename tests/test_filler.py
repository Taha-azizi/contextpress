from contextpress.models import Conversation, Turn
from contextpress.strategies.filler import FillerStrategy


def _run(conv_type: str = "chat"):
    def inner(turns: list[Turn]):
        c = Conversation(turns=turns, type=conv_type)
        return FillerStrategy(aggressiveness=0.7, conv_type=conv_type, role_aware=True).process(c)

    return inner


def test_filler_middle_of_sentence():
    t = Turn(role="assistant", content="We should basically use Postgres here.")
    out = _run()([t]).turns[0]
    assert "basically" not in out.content.lower()
    assert "postgres" in out.content.lower()


def test_filler_sentence_start():
    t = Turn(role="assistant", content="Basically, we use Postgres.")
    out = _run()([t]).turns[0]
    assert "basically" not in out.content.lower()
    assert not out.content.startswith(",")
    assert out.content.startswith("We")


def test_filler_cleans_orphan_commas():
    t = Turn(role="assistant", content="Yeah, you know, you can add indexes.")
    out = _run()([t]).turns[0]
    assert "you know" not in out.content.lower()
    assert ", ," not in out.content
    assert "Yeah, you can" in out.content


def test_filler_only_user_not_dropped():
    t = Turn(role="user", content="Basically.")
    out = _run()([t]).turns
    assert len(out) == 1
    assert out[0].role == "user"


def test_acknowledgement_assistant_dropped():
    t = Turn(role="assistant", content="Sounds good")
    out = _run()([t]).turns
    assert len(out) == 0


def test_user_never_fully_dropped():
    t = Turn(role="user", content="Sounds good")
    out = _run()([t]).turns
    assert len(out) == 1


def test_system_unchanged():
    t = Turn(role="system", content="You are helpful. Basically.")
    out = _run()([t]).turns[0]
    assert out.content == "You are helpful. Basically."


def test_just_in_time_preserved():
    t = Turn(role="assistant", content="We use just in time compilation.")
    out = _run()([t]).turns[0]
    assert "just in time" in out.content.lower()


def test_empty_conversation():
    out = _run()([]).turns
    assert out == []


def test_extra_low_value_phrase_removed():
    t = Turn(role="assistant", content="To be honest, we should use Postgres.")
    out = _run()([t]).turns[0]
    assert "to be honest" not in out.content.lower()
    assert "postgres" in out.content.lower()


def test_um_disfluency_removed():
    t = Turn(role="user", content="Um we should use Postgres.")
    out = _run()([t]).turns[0]
    assert "um" not in out.content.lower().split()
    assert "postgres" in out.content.lower()


def test_filler_skips_json_blob():
    payload = '{"note": "basically utilize this"}'
    t = Turn(role="user", content=payload)
    out = _run()([t]).turns[0]
    assert out.content == payload


def test_ack_no_problem_dropped():
    t = Turn(role="assistant", content="No problem")
    out = _run()([t]).turns
    assert len(out) == 0


def test_extra_discourse_removed():
    t = Turn(role="assistant", content="Due to the fact that we need indexes, add them.")
    out = _run()([t]).turns[0]
    assert "due to the fact that" not in out.content.lower()
    assert "indexes" in out.content.lower()


def test_aggressive_maybe_removed():
    t = Turn(role="assistant", content="Maybe we should use Postgres.")
    out = _run()([t]).turns[0]
    assert "maybe" not in out.content.lower().split()
    assert "postgres" in out.content.lower()


def test_agent_preserves_tool_marker_turn():
    t = Turn(
        role="assistant",
        content="Basically this is fine <tool_call>",
        metadata={"tool_calls": [{"id": "1"}]},
    )
    c = Conversation(turns=[t], type="agent")
    out = FillerStrategy(aggressiveness=0.5, conv_type="agent", role_aware=True).process(c)
    assert len(out.turns) == 1
    assert "Basically" in out.turns[0].content or "<tool" in out.turns[0].content
