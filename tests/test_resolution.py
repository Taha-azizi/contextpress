from contextpress.models import Conversation, Turn
from contextpress.strategies.resolution import ResolutionStrategy


def test_chat_single_sided_no_collapse():
    turns = [
        Turn(role="user", content="What db?"),
        Turn(role="assistant", content="Let's go with Postgres."),
    ]
    c = Conversation(turns=turns, type="chat")
    out = ResolutionStrategy(conv_type="chat").process(c)
    assert len(out.turns) == 2


def test_chat_both_sides_collapse():
    turns = [
        Turn(role="user", content="Should we use Postgres or Mongo?"),
        Turn(role="assistant", content="Postgres is relational."),
        Turn(role="user", content="Ok let's go with Postgres then."),
        Turn(role="assistant", content="Agreed. Postgres it is."),
    ]
    c = Conversation(turns=turns, type="chat")
    out = ResolutionStrategy(conv_type="chat").process(c)
    assert any(t.role == "system" and "RESOLVED" in str(t.content) for t in out.turns)


def test_resolved_is_system():
    turns = [
        Turn(role="user", content="Pick A or B?"),
        Turn(role="assistant", content="A is fine."),
        Turn(role="user", content="We'll use option A."),
        Turn(role="assistant", content="Confirmed on that decision."),
    ]
    c = Conversation(turns=turns, type="chat")
    out = ResolutionStrategy(conv_type="chat").process(c)
    sys_turns = [t for t in out.turns if "RESOLVED" in str(t.content)]
    assert sys_turns and sys_turns[0].role == "system"


def test_short_thread_no_collapse():
    turns = [Turn(role="assistant", content="Let's go with X.")]
    c = Conversation(turns=turns, type="chat")
    out = ResolutionStrategy(conv_type="chat").process(c)
    assert len(out.turns) == 1


def test_system_unchanged():
    turns = [
        Turn(role="system", content="sys"),
        Turn(role="user", content="Ok let's go with Y."),
        Turn(role="assistant", content="Agreed."),
    ]
    c = Conversation(turns=turns, type="chat")
    out = ResolutionStrategy(conv_type="chat").process(c)
    assert out.turns[0].content == "sys"


def test_agent_single_layer_a():
    turns = [
        Turn(role="user", content="task status?"),
        Turn(role="assistant", content="We've decided on using the new pipeline for deploy."),
    ]
    c = Conversation(turns=turns, type="agent")
    out = ResolutionStrategy(conv_type="agent").process(c)
    assert any("RESOLVED" in str(t.content) for t in out.turns)
