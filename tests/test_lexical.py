"""Lexical stage: encoding-specific whole-word synonym swaps."""

from __future__ import annotations

import pytest
import tiktoken

from contextpress import ContextManager
from contextpress.compression import STAGE_ORDER
from contextpress.models import ContentBlock, Conversation, Turn
from contextpress.strategies.lexical import LexicalCompression, load_lexical_dict


def test_utilize_swap_reduces_tokens():
    mapping = load_lexical_dict("cl100k_base")
    assert mapping["utilize"] == "use"
    assert mapping["utilisation"] == "use"
    # Isolated "utilize" is 2 tokens; with a leading space it often merges to 1,
    # so use British "utilisation" which still saves inside a sentence.
    text = "This is the utilisation of the API."
    enc = tiktoken.get_encoding("cl100k_base")
    conv = Conversation(turns=[Turn(role="user", content=text)], type="chat")
    out = LexicalCompression(encoding_name="cl100k_base").process(conv)
    assert out.turns[0].content == "This is the use of the API."
    assert len(enc.encode(out.turns[0].content)) < len(enc.encode(text))


def test_casing_is_preserved():
    conv = Conversation(
        turns=[Turn(role="user", content="Please Utilize the API.")],
        type="chat",
    )
    out = LexicalCompression().process(conv)
    assert out.turns[0].content == "Please Use the API."


def test_system_turns_never_modified():
    text = "Please utilize the API."
    conv = Conversation(turns=[Turn(role="system", content=text)], type="chat")
    out = LexicalCompression().process(conv)
    assert out.turns[0].content == text


def test_json_blob_unmodified():
    payload = '{"task": "please utilize the API"}'
    conv = Conversation(turns=[Turn(role="user", content=payload)], type="chat")
    out = LexicalCompression().process(conv)
    assert out.turns[0].content == payload


def test_fenced_json_unmodified():
    payload = '```json\n{"task": "please utilize the API"}\n```'
    conv = Conversation(turns=[Turn(role="user", content=payload)], type="chat")
    out = LexicalCompression().process(conv)
    assert out.turns[0].content == payload


def test_tool_use_unmodified():
    turn = Turn(
        role="assistant",
        content=[ContentBlock(type="tool_use", content='{"query": "utilize"}')],
        metadata={"tool_use": {"name": "search"}},
    )
    conv = Conversation(turns=[turn], type="agent")
    out = LexicalCompression().process(conv)
    assert out.turns[0].content[0].content == '{"query": "utilize"}'


def test_tool_result_role_unmodified():
    turn = Turn(role="tool", content='{"ok": true, "note": "utilize"}')
    conv = Conversation(turns=[turn], type="agent")
    out = LexicalCompression().process(conv)
    assert out.turns[0].content == '{"ok": true, "note": "utilize"}'


def test_missing_dictionary_raises():
    with pytest.raises(FileNotFoundError, match="no 'lexical' dictionary"):
        LexicalCompression(encoding_name="p50k_base")


def test_invalid_encoding_name_raises():
    with pytest.raises(ValueError, match="invalid encoding name"):
        load_lexical_dict("../secret")


def test_does_not_mutate_input():
    t = Turn(role="user", content="Please utilize the API.")
    conv = Conversation(turns=[t], type="chat")
    LexicalCompression().process(conv)
    assert t.content == "Please utilize the API."


def test_lexical_on_low_chat_not_rag():
    assert "lexical" in STAGE_ORDER
    messages = [{"role": "user", "content": "This is the utilisation of the API."}]
    chat = ContextManager(type="chat", compression="low").compress(
        messages, token_budget=None, return_stats=True
    )
    assert "lexical" in chat.stats.stages_run
    assert "use" in chat.messages[0]["content"]
    rag = ContextManager(type="rag_doc", compression="low").compress(
        messages, token_budget=None, return_stats=True
    )
    assert "lexical" not in rag.stats.stages_run
    assert "utilisation" in rag.messages[0]["content"]


def test_lexical_via_explicit_stages():
    messages = [{"role": "user", "content": "This is the utilisation of the API."}]
    out = ContextManager(type="chat").compress(
        messages,
        token_budget=500,
        stages=["lexical", "filler", "repetition", "budget"],
        return_stats=True,
    )
    assert out.stats.stages_run == ["lexical", "filler", "repetition", "budget"]
    assert "use" in out.messages[0]["content"]
