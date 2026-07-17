import copy

import pytest

from contextpress import ContextManager
from contextpress.compression import known_stages
from contextpress.models import Conversation, Turn
from contextpress.pipeline import Pipeline
from contextpress.profiles import PROFILES
from contextpress.registry import clear_registry, register_stage
from contextpress.strategies.base import BaseStrategy


class _DropMarkedStrategy(BaseStrategy):
    def process(self, conversation: Conversation) -> Conversation:
        kept = [
            copy.deepcopy(t)
            for t in conversation.turns
            if t.role == "system"
            or "DROP" not in (t.content if isinstance(t.content, str) else str(t.content))
        ]
        return Conversation(
            turns=kept,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    yield
    clear_registry()


def test_estimate_tokens_dict_list():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "user", "content": "Hello world"},
        {"role": "assistant", "content": "Hi there"},
    ]
    n = cm.estimate_tokens(messages)
    assert isinstance(n, int) and n > 0


def test_register_stage_and_run():
    cm = ContextManager(type="chat")
    cm.register_stage("drop_marked", _DropMarkedStrategy)
    assert "drop_marked" in known_stages()
    messages = [
        {"role": "user", "content": "keep me"},
        {"role": "assistant", "content": "DROP this turn"},
    ]
    out = cm.compress(messages, stages=["drop_marked"])
    assert len(out) == 1
    assert out[0]["content"] == "keep me"


def test_register_stage_reserved_name_raises():
    with pytest.raises(ValueError):
        register_stage("filler", _DropMarkedStrategy)


def test_configure_custom_stage():
    cm = ContextManager(type="chat")
    cm.register_stage("drop_marked", _DropMarkedStrategy, aggressiveness=0.2)
    cm.configure("drop_marked", aggressiveness=0.9)
    assert cm._custom_stages["drop_marked"].aggressiveness == 0.9


class _DedupOnlyBackend:
    def summarize(self, text: str, max_tokens: int) -> str:
        raise AssertionError("summarize should not run in dedupe_only mode")

    def deduplicate(self, turns: list[str]) -> list[int]:
        return [0]


class _SummarizeOnlyBackend:
    def summarize(self, text: str, max_tokens: int) -> str:
        return "summary appended"

    def deduplicate(self, turns: list[str]) -> list[int]:
        raise AssertionError("deduplicate should not run in summarize_only mode")


def test_llm_mode_dedupe_only():
    conv = Conversation(
        turns=[
            Turn(role="user", content="hello"),
            Turn(role="user", content="hello again"),
        ],
        type="chat",
    )
    p = Pipeline(
        PROFILES["chat"],
        token_budget=None,
        llm_backend=_DedupOnlyBackend(),
        llm_mode="dedupe_only",
        llm_min_input_chars=0,
    )
    out = p.run(conv)
    assert len(out.turns) == 1
    assert out.turns[0].content == "hello"


def test_llm_mode_summarize_only():
    conv = Conversation(
        turns=[Turn(role="user", content="hello " * 200)],
        type="chat",
    )
    p = Pipeline(
        PROFILES["chat"],
        token_budget=None,
        llm_backend=_SummarizeOnlyBackend(),
        llm_mode="summarize_only",
        llm_min_input_chars=0,
    )
    out = p.run(conv)
    assert len(out.turns) == 2
    assert out.turns[0].role == "user"
    assert out.turns[1].content == "summary appended"
    assert out.turns[1].metadata.get("mode") == "summarize_only"


def test_invalid_llm_mode_raises():
    with pytest.raises(ValueError):
        ContextManager(llm_mode="invalid")
