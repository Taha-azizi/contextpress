"""0.7.3: sentence selection inside a long rag_doc turn."""

from __future__ import annotations

import copy

from contextpress import ContextManager
from contextpress.normalizer import normalize_messages
from contextpress.strategies.recency import RecencyStrategy, _token_count

_ANCHOR = "The brass sextant showed a bearing of 214 degrees toward the island of Zephyra."
_END = "County 200 recorded a dry summer and stored grain in barn number 200 nutmeg."
_QUESTION = (
    "Using only the passage, what does it say in the part that begins "
    "“The brass sextant showed a bearing”? Answer in one or two sentences and keep any numbers."
)


def _long_passage() -> str:
    sentences = []
    for i in range(220):
        if i == 80:
            sentences.append(_ANCHOR)
        elif i == 200:
            sentences.append(_END)
        else:
            sentences.append(
                f"County {i} recorded a dry summer and stored grain in barn number {i}."
            )
    return " ".join(sentences)


def _messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Answer from the passage only."},
        {"role": "user", "content": _long_passage()},
        {"role": "user", "content": _QUESTION},
    ]


def test_long_passage_exceeds_token_gate() -> None:
    assert _token_count(_long_passage()) > 1500


def test_medium_keeps_anchor_and_drops_offtopic_tail() -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    out = ContextManager(type="rag_doc", compression="medium").compress(messages, return_stats=True)
    assert messages == original
    assert out.messages[0]["content"] == "Answer from the passage only."
    assert out.messages[-1]["content"] == _QUESTION
    body = out.messages[1]["content"]
    assert "Zephyra" in body
    assert "214" in body
    assert "nutmeg" not in body
    assert out.stats.token_savings_pct >= 15


def test_high_keeps_anchor_and_is_thinner_than_medium() -> None:
    messages = _messages()
    medium = ContextManager(type="rag_doc", compression="medium").compress(
        messages, return_stats=True
    )
    high = ContextManager(type="rag_doc", compression="high").compress(messages, return_stats=True)
    assert "Zephyra" in high.messages[1]["content"]
    assert "nutmeg" not in high.messages[1]["content"]
    assert high.messages[-1]["content"] == _QUESTION
    assert high.stats.tokens_after < medium.stats.tokens_after


def test_low_does_not_drop_the_long_turn() -> None:
    out = ContextManager(type="rag_doc", compression="low").compress(_messages())
    assert "nutmeg" in out[1]["content"]
    assert "Zephyra" in out[1]["content"]


def test_short_chunks_match_recency_without_long_turn_mode() -> None:
    chunks = [
        f"Section {i} describes river silt and canal locks in district {i}. " * 4 for i in range(8)
    ]
    messages = [{"role": "user", "content": c} for c in chunks]
    messages.append({"role": "user", "content": "What does the passage say about river silt?"})
    for chunk in chunks:
        assert _token_count(chunk) < 1500
    conv, _ = normalize_messages(messages, context_type="rag_doc")
    with_mode = RecencyStrategy(conv_type="rag_doc", long_turn_mode="medium").process(conv)
    without = RecencyStrategy(conv_type="rag_doc", long_turn_mode=None).process(conv)
    assert [t.content for t in with_mode.turns] == [t.content for t in without.turns]


def test_chat_does_not_extract_a_long_turn() -> None:
    passage = _long_passage()
    messages = [
        {"role": "user", "content": passage},
        {"role": "assistant", "content": "Noted."},
        {"role": "user", "content": "Thanks."},
    ]
    out = ContextManager(type="chat", compression="high").compress(messages)
    assert "nutmeg" in out[0]["content"]


def test_last_user_turn_is_not_split() -> None:
    passage = _long_passage()
    out = ContextManager(type="rag_doc", compression="medium").compress(
        [{"role": "user", "content": passage}]
    )
    assert out[0]["content"].count("nutmeg") == 1
