"""Abbreviation and in-chat alias stages."""

from __future__ import annotations

from contextpress import ContextManager
from contextpress.compression import STAGE_ORDER
from contextpress.models import Conversation, Turn
from contextpress.strategies.abbrev import AbbreviationStrategy, apply_abbreviations
from contextpress.strategies.abbrev_dict import abbreviation_count
from contextpress.strategies.alias import AliasStrategy, find_alias_map
from contextpress.strategies.text_rewrite import get_encoding


def test_abbreviation_dict_size():
    assert 280 <= abbreviation_count() <= 320


def test_abbrev_for_example():
    enc = get_encoding("cl100k_base")
    # Prefer pairs that actually reduce cl100k tokens in-context.
    assert (
        apply_abbreviations("due to the fact that we failed", encoding=enc) == "because we failed"
    )
    assert apply_abbreviations("in order to deploy", encoding=enc) == "to deploy"
    assert apply_abbreviations("Application Programming Interface", encoding=enc) == "API"
    # Equal or higher BPE count → keep original (char-shorter is not enough).
    assert (
        apply_abbreviations("For example, use Postgres.", encoding=enc)
        == "For example, use Postgres."
    )


def test_abbrev_skips_system_and_json():
    conv = Conversation(
        turns=[
            Turn(role="system", content="Due to the fact that keep this."),
            Turn(role="user", content='{"note": "due to the fact that"}'),
            Turn(role="user", content="Due to the fact that change this."),
        ],
        type="chat",
    )
    out = AbbreviationStrategy().process(conv)
    assert out.turns[0].content == "Due to the fact that keep this."
    assert out.turns[1].content == '{"note": "due to the fact that"}'
    assert out.turns[2].content == "Because change this."


def test_alias_defines_then_shortens():
    messages = [
        {"role": "user", "content": "Please install Context Press today."},
        {"role": "assistant", "content": "Context Press is ready."},
        {"role": "user", "content": "Does Context Press support tools?"},
        {"role": "assistant", "content": "Yes, Context Press supports tools."},
        {"role": "user", "content": "Ship Context Press next."},
    ]
    out = ContextManager(type="chat").compress(
        messages, token_budget=None, stages=["alias"], return_stats=True
    )
    texts = [m["content"] for m in out.messages]
    assert "alias" in out.stats.stages_run
    assert any("(CP)" in t for t in texts)
    joined = " ".join(texts)
    assert joined.lower().count("context press") <= 1


def test_alias_requires_three_occurrences():
    messages = [
        {"role": "user", "content": "Context Press once."},
        {"role": "assistant", "content": "Context Press twice."},
    ]
    mapping = find_alias_map([m["content"] for m in messages], min_count=3)
    assert mapping == []
    out = AliasStrategy().process(
        Conversation(
            turns=[Turn(role=m["role"], content=m["content"]) for m in messages],
            type="chat",
        )
    )
    assert out.turns[0].content == "Context Press once."


def test_alias_case_variants_count_together():
    texts = [
        "Use Context Press now.",
        "context press helps.",
        "CONTEXT PRESS works.",
    ]
    mapping = find_alias_map(texts, min_count=3)
    assert mapping
    assert mapping[0][0].lower() == "context press"


def test_abbrev_and_alias_on_low_chat():
    assert "abbrev" in STAGE_ORDER and "alias" in STAGE_ORDER
    messages = [
        {"role": "user", "content": "Due to the fact that Context Press failed."},
        {"role": "assistant", "content": "Context Press works."},
        {"role": "user", "content": "Is Context Press fast?"},
        {"role": "assistant", "content": "Context Press is fast."},
    ]
    result = ContextManager(type="chat", compression="low").compress(
        messages, token_budget=None, return_stats=True
    )
    assert "abbrev" in result.stats.stages_run
    assert "alias" in result.stats.stages_run
    assert "filler" in result.stats.stages_run


def test_rag_skips_abbrev_alias():
    messages = [
        {
            "role": "user",
            "content": "For example, Context Press Context Press Context Press",
        }
    ]
    result = ContextManager(type="rag_doc", compression="low").compress(
        messages, token_budget=None, return_stats=True
    )
    assert "abbrev" not in result.stats.stages_run
    assert "alias" not in result.stats.stages_run
