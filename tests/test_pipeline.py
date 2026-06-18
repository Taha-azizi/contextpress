import copy
import warnings
from unittest.mock import MagicMock

import pytest

from contextpress import ContextManager
from contextpress.compression import apply_stage_selection
from contextpress.llm.adapters import AnthropicBackend, OllamaBackend, OpenAIBackend
from contextpress.llm.base import LLMBackend
from contextpress.models import Conversation, Turn
from contextpress.pipeline import Pipeline
from contextpress.profiles import PROFILES


def test_full_chat_pipeline_order():
    turns = [
        Turn(role="system", content="sys"),
        Turn(role="user", content="Hello basically there"),
    ]
    c = Conversation(turns=turns, type="chat")
    p = Pipeline(PROFILES["chat"], token_budget=None, model=None)
    out = p.run(c)
    assert len(out.turns) == 2


def test_rag_skips_resolution():
    profile = PROFILES["rag_doc"]
    assert profile.resolution.enabled is False


def test_disable_resolution():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "user", "content": "hello basically"},
    ]
    r = cm.compress(messages, token_budget=None, disable=["resolution"])
    assert r


def test_system_survives():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hi"},
    ]
    r = cm.compress(messages, token_budget=500)
    assert r[0]["role"] == "system"
    assert r[0]["content"] == "You are helpful."


def test_dict_in_dict_out():
    cm = ContextManager(type="chat")
    messages = [{"role": "user", "content": "hello"}]
    r = cm.compress(messages, token_budget=None)
    assert isinstance(r, list) and isinstance(r[0], dict)


def test_empty_input():
    cm = ContextManager(type="chat")
    r = cm.compress([], token_budget=None)
    assert r == []


def test_invalid_context_type():
    with pytest.raises(ValueError):
        ContextManager(type="nope")


def test_configure_stage():
    cm = ContextManager(type="chat")
    cm.configure("repetition", aggressiveness=0.2, enabled=True)
    assert cm._profile.repetition.aggressiveness == 0.2


def test_configure_warns_on_unknown_keys():
    cm = ContextManager(type="chat")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cm.configure("repetition", aggressiveness=0.5, not_a_field=1)
        assert any("unknown key" in str(x.message).lower() for x in w)


def test_configure_unknown_stage():
    cm = ContextManager(type="chat")
    with pytest.raises(ValueError):
        cm.configure("not_a_stage", enabled=False)


def test_compress_disable_unknown_stage_ignored():
    cm = ContextManager(type="chat")
    out = cm.compress([{"role": "user", "content": "hi"}], disable=["not_a_stage"])
    assert out == [{"role": "user", "content": "hi"}]


class _OkBackend(LLMBackend):
    def summarize(self, text: str, max_tokens: int) -> str:
        return "[llm] " + text[: min(200, len(text))]

    def deduplicate(self, turns: list[str]) -> list[int]:
        return list(range(len(turns)))


class _DedupKeepFirst(LLMBackend):
    def summarize(self, text: str, max_tokens: int) -> str:
        return "[sum]"

    def deduplicate(self, turns: list[str]) -> list[int]:
        return [0]


class _FailBackend(LLMBackend):
    def summarize(self, text: str, max_tokens: int) -> str:
        raise RuntimeError("boom")

    def deduplicate(self, turns: list[str]) -> list[int]:
        return []


def test_llm_tier_runs_with_backend():
    conv = Conversation(turns=[Turn(role="user", content="hello " * 2000)], type="chat")
    p = Pipeline(PROFILES["chat"], token_budget=None, llm_backend=_OkBackend())
    out = p.run(conv)
    assert len(out.turns) == 1
    assert out.turns[0].role == "assistant"
    assert "[llm]" in out.turns[0].content


def test_llm_tier_skips_when_transcript_short():
    conv = Conversation(turns=[Turn(role="user", content="short")], type="chat")
    p = Pipeline(
        PROFILES["chat"],
        token_budget=None,
        llm_backend=_OkBackend(),
        llm_min_input_chars=500,
    )
    out = p.run(conv)
    assert len(out.turns) == 1
    assert out.turns[0].role == "user"


def test_llm_tier_preserves_system_then_summary():
    conv = Conversation(
        turns=[
            Turn(role="system", content="sys"),
            Turn(role="user", content="hello " * 2000),
        ],
        type="chat",
    )
    p = Pipeline(PROFILES["chat"], token_budget=None, llm_backend=_OkBackend())
    out = p.run(conv)
    assert len(out.turns) == 2
    assert out.turns[0].role == "system" and out.turns[0].content == "sys"
    assert out.turns[1].role == "assistant"


def test_llm_tier_deduplicate_before_summarize():
    body = "word " * 400
    conv = Conversation(
        turns=[
            Turn(role="user", content=body),
            Turn(role="user", content=body + " tail"),
        ],
        type="chat",
    )
    p = Pipeline(PROFILES["chat"], token_budget=None, llm_backend=_DedupKeepFirst())
    out = p.run(conv)
    assert len(out.turns) == 1
    assert out.turns[0].content == "[sum]"


def test_llm_tier_failure_warns():
    conv = Conversation(turns=[Turn(role="user", content="hello " * 2000)], type="chat")
    p = Pipeline(PROFILES["chat"], token_budget=None, llm_backend=_FailBackend())
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out = p.run(conv)
        assert len(out.turns) == 1
        assert out.turns[0].role == "user"
        assert w


def test_openai_backend_summarize_ok():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="short summary"))]
    )
    b = OpenAIBackend(client=client, model="gpt-4o-mini")
    assert b.summarize("long text", 50) == "short summary"
    client.chat.completions.create.assert_called_once()


def test_openai_backend_summarize_warns_on_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network")
    b = OpenAIBackend(client=client)
    with pytest.warns(UserWarning):
        with pytest.raises(RuntimeError):
            b.summarize("x", 10)


def test_anthropic_backend_summarize_ok():
    client = MagicMock()
    block = MagicMock()
    block.text = "summary text"
    msg = MagicMock()
    msg.content = [block]
    client.messages.create.return_value = msg
    b = AnthropicBackend(client=client, model="claude-haiku-4-5")
    assert b.summarize("hello", 50) == "summary text"


def test_anthropic_backend_summarize_warns_on_error():
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("network")
    b = AnthropicBackend(client=client)
    with pytest.warns(UserWarning):
        with pytest.raises(RuntimeError):
            b.summarize("x", 10)


def test_adapter_deduplicate_single_turn():
    client = MagicMock()
    assert OpenAIBackend(client=client).deduplicate(["a"]) == [0]
    assert AnthropicBackend(client=client).deduplicate(["a"]) == [0]
    assert OllamaBackend(client=client, model="x").deduplicate(["a"]) == [0]
    client.chat.completions.create.assert_not_called()


def test_ollama_backend_summarize_dict_response():
    client = MagicMock()
    client.chat.return_value = {"message": {"content": "  ollama summary  "}}
    b = OllamaBackend(client=client, model="llama3.2")
    assert b.summarize("word " * 500, 128) == "ollama summary"
    client.chat.assert_called_once()
    call_kw = client.chat.call_args.kwargs
    assert call_kw["model"] == "llama3.2"
    assert "num_predict" in call_kw["options"]


def test_ollama_backend_summarize_object_response():
    client = MagicMock()
    msg = MagicMock(content="object summary")
    client.chat.return_value = MagicMock(message=msg)
    b = OllamaBackend(client=client, model="mistral")
    assert b.summarize("x" * 2000, 256) == "object summary"


def test_ollama_backend_summarize_warns_on_error():
    client = MagicMock()
    client.chat.side_effect = RuntimeError("connection refused")
    b = OllamaBackend(client=client, model="llama3.2")
    with pytest.warns(UserWarning):
        with pytest.raises(RuntimeError):
            b.summarize("x" * 2000, 100)


def test_preset_low_enables_filler_and_repetition_only():
    base = copy.deepcopy(PROFILES["chat"])
    p = copy.deepcopy(base)
    apply_stage_selection(
        p,
        base_profile=base,
        compression="low",
        stages=None,
        disable=None,
        token_budget=None,
    )
    assert p.filler.enabled and p.repetition.enabled
    assert not p.resolution.enabled and not p.recency.enabled and not p.budget.enabled


def test_preset_medium_adds_recency():
    base = copy.deepcopy(PROFILES["chat"])
    p = copy.deepcopy(base)
    apply_stage_selection(
        p,
        base_profile=base,
        compression="medium",
        stages=None,
        disable=None,
        token_budget=None,
    )
    assert p.filler.enabled and p.repetition.enabled and p.recency.enabled
    assert not p.resolution.enabled


def test_preset_high_respects_rag_doc_resolution_off():
    base = copy.deepcopy(PROFILES["rag_doc"])
    p = copy.deepcopy(base)
    apply_stage_selection(
        p,
        base_profile=base,
        compression="high",
        stages=None,
        disable=None,
        token_budget=None,
    )
    assert not p.resolution.enabled
    assert p.filler.enabled and p.recency.enabled


def test_explicit_stages_list():
    base = copy.deepcopy(PROFILES["chat"])
    p = copy.deepcopy(base)
    apply_stage_selection(
        p,
        base_profile=base,
        compression="high",
        stages=["filler", "budget"],
        disable=None,
        token_budget=100,
    )
    assert p.filler.enabled and p.budget.enabled
    assert not p.repetition.enabled


def test_disable_after_preset():
    base = copy.deepcopy(PROFILES["chat"])
    p = copy.deepcopy(base)
    apply_stage_selection(
        p,
        base_profile=base,
        compression="medium",
        stages=None,
        disable=["recency"],
        token_budget=None,
    )
    assert p.recency.enabled is False
    assert p.filler.enabled


def test_invalid_compression_level():
    with pytest.raises(ValueError):
        ContextManager(compression="ultra")


def test_set_compression():
    cm = ContextManager(compression="low")
    cm.set_compression("high")
    assert cm._compression == "high"


def test_stages_empty_raises():
    cm = ContextManager(type="chat")
    with pytest.raises(ValueError):
        cm.compress([{"role": "user", "content": "x"}], stages=[])
