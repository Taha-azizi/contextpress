from contextpress.models import Conversation, Turn
from contextpress.strategies.repetition import RepetitionStrategy, _threshold_for_aggr


def test_near_identical_users_keep_recent():
    older = " " + "word " * 12 + "about postgres database choice for our application stack"
    newer = " " + "word " * 12 + "about postgres database choice for our application stacks"
    turns = [
        Turn(role="user", content=older),
        Turn(role="user", content=newer),
    ]
    c = Conversation(turns=turns, type="chat")
    out = RepetitionStrategy(aggressiveness=0.5, role_aware=True, conv_type="chat").process(c)
    assert len(out.turns) == 1
    assert "stacks" in out.turns[0].content or "stack" in out.turns[0].content


def test_near_identical_assistant_keep_recent():
    base = "The answer is " + "x " * 12 + "for the database question we discussed earlier today"
    turns = [
        Turn(role="assistant", content=base + " old"),
        Turn(role="assistant", content=base + " new"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = RepetitionStrategy(aggressiveness=0.5, role_aware=True, conv_type="chat").process(c)
    assert len(out.turns) == 1


def test_user_vs_assistant_not_deduped():
    text = "word " * 15 + "about the same topic repeated here"
    turns = [
        Turn(role="user", content=text),
        Turn(role="assistant", content=text + " suffix"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = RepetitionStrategy(aggressiveness=0.5, role_aware=True, conv_type="chat").process(c)
    assert len(out.turns) == 2


def test_system_unchanged():
    turns = [
        Turn(role="system", content="sys"),
        Turn(role="user", content="word " * 15 + "a"),
        Turn(role="user", content="word " * 15 + "a"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = RepetitionStrategy(aggressiveness=0.5, role_aware=True, conv_type="chat").process(c)
    assert out.turns[0].role == "system"
    assert out.turns[0].content == "sys"


def test_short_turns_skipped():
    turns = [
        Turn(role="user", content="yes ok short"),
        Turn(role="user", content="yes ok short"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = RepetitionStrategy(aggressiveness=0.5, role_aware=True, conv_type="chat").process(c)
    assert len(out.turns) == 2


def test_aggressiveness_scales_threshold():
    assert _threshold_for_aggr(0.0) > _threshold_for_aggr(1.0)
