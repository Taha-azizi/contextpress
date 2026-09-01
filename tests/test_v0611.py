"""Opt-in contractions, wordy_phrases, and number_normalize (0.6.11+)."""

from __future__ import annotations

from pathlib import Path

import tiktoken

from contextpress import ContextManager
from contextpress.compression import STAGE_ORDER
from contextpress.models import Conversation, Turn
from contextpress.strategies.lexical import LexicalCompression, load_rewrite_dict
from contextpress.strategies.number_normalize import (
    NumberNormalizeStrategy,
    apply_number_normalize,
    parse_number_words,
)

DATA = Path(__file__).resolve().parent.parent / "contextpress" / "data"


def test_new_stages_in_order_not_in_low_preset():
    for name in ("contractions", "wordy_phrases", "number_normalize"):
        assert name in STAGE_ORDER
    messages = [{"role": "user", "content": "I do not want that."}]
    low = ContextManager(type="chat", compression="low").compress(
        messages, token_budget=None, return_stats=True
    )
    assert "contractions" not in low.stats.stages_run
    assert "wordy_phrases" not in low.stats.stages_run
    assert "number_normalize" not in low.stats.stages_run


def test_contractions_dict_loads_and_saves_tokens():
    mapping = load_rewrite_dict("contractions", "cl100k_base")
    assert mapping["do not"] == "don't"
    assert "will not" in mapping
    enc = tiktoken.get_encoding("cl100k_base")
    for src, dst in mapping.items():
        assert len(enc.encode(dst)) <= len(enc.encode(src))


def test_allow_equal_tokens_is_explicit():
    path = DATA / "contractions_cl100k_base.json"
    text = "Please do not stop."
    conv = Conversation(turns=[Turn(role="user", content=text)], type="chat")
    # Without allow_equal_tokens, equal-BPE contractions may be rejected.
    strict = LexicalCompression(dict_path=path, encoding_name="cl100k_base").process(conv)
    equal_ok = LexicalCompression(
        dict_path=path, encoding_name="cl100k_base", allow_equal_tokens=True
    ).process(conv)
    assert equal_ok.turns[0].content != text or "don't" in equal_ok.turns[0].content.lower()
    # Pipeline stage sets allow_equal_tokens=True for contractions.
    staged = ContextManager(type="chat").compress(
        [{"role": "user", "content": text}],
        token_budget=None,
        stages=["contractions"],
        return_stats=True,
    )
    assert "don't" in staged.messages[0]["content"].lower()
    assert strict.turns[0].content in {text, equal_ok.turns[0].content}


def test_contractions_via_dict_path_and_stage():
    path = DATA / "contractions_cl100k_base.json"
    conv = Conversation(
        turns=[Turn(role="user", content="Please do not stop. They are ready.")],
        type="chat",
    )
    out = LexicalCompression(
        dict_path=path, encoding_name="cl100k_base", allow_equal_tokens=True
    ).process(conv)
    text = out.turns[0].content
    assert "don't" in text.lower() or "do not" not in text.lower()
    staged = ContextManager(type="chat").compress(
        [{"role": "user", "content": "I will not go if it is raining."}],
        token_budget=None,
        stages=["contractions"],
        return_stats=True,
    )
    assert staged.stats.stages_run == ["contractions"]
    assert (
        "won't" in staged.messages[0]["content"].lower()
        or "it's" in staged.messages[0]["content"].lower()
    )


def test_wordy_phrases_multiword_longest_first():
    mapping = load_rewrite_dict("wordy_phrases", "cl100k_base")
    assert mapping["in order to"] == "to"
    assert mapping["due to the fact that"] == "because"
    assert len(mapping) >= 25
    enc = tiktoken.get_encoding("cl100k_base")
    for src, dst in mapping.items():
        assert len(enc.encode(dst)) < len(enc.encode(src))

    text = "Due to the fact that we left in order to help."
    out = LexicalCompression(dict_name="wordy_phrases").process(
        Conversation(turns=[Turn(role="user", content=text)], type="chat")
    )
    assert out.turns[0].content == "Because we left to help."

    staged = ContextManager(type="chat").compress(
        [{"role": "user", "content": "At this point in time, call me."}],
        token_budget=None,
        stages=["wordy_phrases"],
        return_stats=True,
    )
    assert staged.stats.stages_run == ["wordy_phrases"]
    assert "now" in staged.messages[0]["content"].lower()


def test_number_normalize_multiword_only():
    assert parse_number_words("twenty three") == 23
    assert parse_number_words("one thousand two hundred") == 1200
    assert parse_number_words("one") is None
    assert parse_number_words("two") is None

    enc = tiktoken.get_encoding("cl100k_base")
    phrase = "twenty three"
    digits = "23"
    assert len(enc.encode(digits)) < len(enc.encode(phrase))
    long_phrase = "one thousand two hundred"
    assert len(enc.encode("1200")) < len(enc.encode(long_phrase))

    text = "We need twenty three units, not one or two extras."
    out = apply_number_normalize(text, encoding=enc)
    assert "23" in out
    assert " not one or two " in out or out.endswith("one or two extras.")

    conv = Conversation(
        turns=[
            Turn(role="system", content="Keep twenty three."),
            Turn(role="user", content='{"n": "twenty three"}'),
            Turn(role="user", content="Ship twenty three boxes."),
        ],
        type="chat",
    )
    processed = NumberNormalizeStrategy().process(conv)
    assert processed.turns[0].content == "Keep twenty three."
    assert processed.turns[1].content == '{"n": "twenty three"}'
    assert "23" in processed.turns[2].content

    staged = ContextManager(type="chat").compress(
        [{"role": "user", "content": "Budget is one hundred fifty dollars."}],
        token_budget=None,
        stages=["number_normalize"],
        return_stats=True,
    )
    assert staged.stats.stages_run == ["number_normalize"]
    assert "150" in staged.messages[0]["content"]
