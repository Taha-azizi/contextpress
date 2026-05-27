import warnings

import pytest

from contextpress import ContextManager
from contextpress.models import ContentBlock, Conversation, Turn
from contextpress.strategies.budget import BudgetStrategy


def test_within_budget_unchanged():
    turns = [Turn(role="user", content="hi")]
    c = Conversation(turns=turns, type="chat")
    out = BudgetStrategy(token_budget=500, model=None).process(c)
    assert out.turns[0].content == "hi"


def test_oldest_removed_first():
    turns = [
        Turn(role="user", content="a " * 200),
        Turn(role="assistant", content="b " * 200),
        Turn(role="user", content="c " * 200),
    ]
    c = Conversation(turns=turns, type="chat")
    out = BudgetStrategy(token_budget=30, model=None).process(c)
    assert len(out.turns) >= 2


def test_system_never_removed_before_tail():
    turns = [
        Turn(role="system", content="system prompt " * 50),
        Turn(role="user", content="u1"),
        Turn(role="assistant", content="a1"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = BudgetStrategy(token_budget=20, model=None).process(c)
    assert any(t.role == "system" for t in out.turns)


def test_last_two_non_system_preserved():
    turns = [
        Turn(role="user", content="old " * 100),
        Turn(role="assistant", content="mid " * 100),
        Turn(role="user", content="new1"),
        Turn(role="assistant", content="new2"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = BudgetStrategy(token_budget=15, model=None).process(c)
    assert out.turns[-1].content == "new2"
    assert out.turns[-2].content == "new1"


def test_warning_on_truncation():
    turns = [Turn(role="user", content="x " * 5000)]
    c = Conversation(turns=turns, type="chat")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        BudgetStrategy(token_budget=5, model=None).process(c)
        assert w


def test_model_encoding():
    turns = [Turn(role="user", content="hello world")]
    c = Conversation(turns=turns, type="chat")
    b1 = BudgetStrategy(token_budget=1000, model="gpt-4")
    b2 = BudgetStrategy(token_budget=1000, model=None)
    assert b1.process(c).turns[0].content == b2.process(c).turns[0].content


def test_token_budget_validation():
    cm = ContextManager(type="chat")
    with pytest.raises(ValueError):
        cm.compress([{"role": "user", "content": "x"}], token_budget=0)
    with pytest.raises(TypeError):
        cm.compress([{"role": "user", "content": "x"}], token_budget=True)  # noqa: E712


def test_budget_truncates_multimodal_system_last_resort():
    long_text = "word " * 5000
    turns = [
        Turn(
            role="system",
            content=[ContentBlock(type="text", content=long_text)],
        ),
        Turn(role="user", content="hi"),
    ]
    c = Conversation(turns=turns, type="chat")
    out = BudgetStrategy(token_budget=10, model=None).process(c)
    assert any(t.role == "system" for t in out.turns)
