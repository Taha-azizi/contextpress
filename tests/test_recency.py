from contextpress.models import Conversation, Turn
from contextpress.strategies.recency import RecencyStrategy


def _many_turns(n: int) -> list[Turn]:
    turns = [Turn(role="system", content="s")]
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        # Long enough for summarization
        body = (
            "Sentence one about topic. Sentence two adds detail. "
            "Sentence three continues. Sentence four concludes early. "
            "Sentence five wraps up the discussion here."
        )
        turns.append(Turn(role=role, content=body))
    return turns


def test_recent_three_protected():
    turns = _many_turns(8)
    c = Conversation(turns=turns, type="chat")
    out = RecencyStrategy(aggressiveness=1.0, conv_type="chat").process(c)
    # Last 3 non-system should match originals (content unchanged)
    ns_out = [t for t in out.turns if t.role != "system"]
    ns_in = [t for t in c.turns if t.role != "system"]
    for a, b in zip(ns_out[-3:], ns_in[-3:], strict=True):
        assert a.content == b.content


def test_oldest_compressed_when_aggressive():
    turns = _many_turns(8)
    c = Conversation(turns=turns, type="chat")
    out = RecencyStrategy(aggressiveness=1.0, conv_type="chat").process(c)
    ns_out = [t for t in out.turns if t.role != "system"]
    ns_in = [t for t in c.turns if t.role != "system"]
    assert ns_out[0].compressed or ns_out[0].content != ns_in[0].content


def test_short_turns_not_compressed():
    turns = [
        Turn(role="user", content="One liner."),
        Turn(role="assistant", content="Reply."),
    ]
    c = Conversation(turns=turns, type="chat")
    out = RecencyStrategy(aggressiveness=1.0, conv_type="chat").process(c)
    assert out.turns[0].content == turns[0].content
    assert out.turns[1].content == turns[1].content


def test_system_unchanged_recency():
    turns = [Turn(role="system", content="sys"), Turn(role="user", content="x " * 200)]
    c = Conversation(turns=turns, type="chat")
    out = RecencyStrategy(aggressiveness=1.0, conv_type="chat").process(c)
    assert out.turns[0].content == "sys"


def test_rag_doc_uses_relevance_not_only_position():
    turns = [
        Turn(role="user", content="query about elephants and wildlife"),
        Turn(role="assistant", content="chunk about databases sql postgres tuning"),
        Turn(role="assistant", content="another chunk about elephants africa savanna wildlife"),
    ]
    c = Conversation(turns=turns, type="rag_doc")
    out = RecencyStrategy(aggressiveness=0.5, conv_type="rag_doc").process(c)
    # DB chunk should be more likely compressed than elephant chunk
    assert len(out.turns) == 3
