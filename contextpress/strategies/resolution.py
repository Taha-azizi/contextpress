from __future__ import annotations

import copy
import re

import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from contextpress.models import Conversation, Turn
from contextpress.normalizer import extract_text_for_processing
from contextpress.strategies.base import BaseStrategy

LAYER_A_PHRASES = [
    "let's go with",
    "we'll use",
    "we'll go with",
    "decided on",
    "agreed on",
    "confirmed",
    "settled on",
    "locked in",
    "final decision",
    "final answer",
    "we've decided",
    "conclusion is",
    "approved",
    "let's proceed with",
    "we're going with",
    "that's our answer",
    "we'll do that",
]

LAYER_B_A = [
    "agreed",
    "sounds good",
    "works for me",
    "perfect",
    "+1",
    "that works",
    "yes let's do that",
    "great",
    "correct",
    "exactly",
    "that's right",
    "fair enough",
]

_QUESTION_ONLY = re.compile(r"^\s*[^.!?]*\?\s*$")


def _lower(text: str) -> str:
    return text.lower()


def _has_layer_a(text: str) -> bool:
    t = _lower(text)
    return any(p in t for p in LAYER_A_PHRASES)


def _has_signal_any(text: str) -> bool:
    t = _lower(text)
    if _has_layer_a(text):
        return True
    for p in LAYER_B_A:
        if re.search(rf"\b{re.escape(p)}\b", t):
            return True
    return False


def _find_thread_start(conv: Conversation, res_idx: int, max_lookback: int = 20) -> int:
    """Walk backward from resolution: include turns while similarity to resolution >= 0.3."""
    turns = conv.turns
    res_text = extract_text_for_processing(turns[res_idx])
    start = res_idx
    low = max(0, res_idx - max_lookback)
    for i in range(res_idx - 1, low - 1, -1):
        if turns[i].role == "system":
            break
        ttext = extract_text_for_processing(turns[i])
        try:
            vec = TfidfVectorizer(min_df=1, max_df=1.0)
            mat = vec.fit_transform([ttext, res_text])
            sim = cosine_similarity(mat[0:1], mat[1:2])[0, 0]
        except ValueError:
            sim = 0.0
        if sim >= 0.3:
            start = i
        else:
            break
    # Short-turn TF-IDF can fail to link an entire debate; ensure at least two turns when possible
    if start == res_idx and res_idx >= 1 and turns[res_idx - 1].role != "system":
        start = res_idx - 1
    return start


def _extract_subject_description(res_text: str) -> tuple[str, str]:
    t = res_text.strip()
    subj = "Topic"
    desc = t[:120]
    for phrase in LAYER_A_PHRASES:
        if phrase in _lower(t):
            after = t[_lower(t).find(phrase) + len(phrase) :].strip(" :—-\t")
            if after:
                # strip trailing punctuation
                desc = after.split(".")[0].strip()[:200]
                words = desc.split()[:6]
                subj = words[0].title() if words else subj
            break
    return subj, desc


def _noun_subject(text: str) -> str:
    try:
        tokens = nltk.word_tokenize(text)
        tagged = nltk.pos_tag(tokens)
        for w, tag in tagged:
            if tag.startswith("NN"):
                return w.title()
    except Exception:
        pass
    return "Topic"


class ResolutionStrategy(BaseStrategy):
    def __init__(self, aggressiveness: float = 0.5, *, conv_type: str = "chat", **kwargs: object):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type

    def process(self, conversation: Conversation) -> Conversation:
        if conversation.type == "rag_doc":
            return copy.deepcopy(conversation)

        turns = conversation.turns
        # Find last Layer A resolution index (prefer later collapses)
        res_idx = -1
        for i in range(len(turns) - 1, -1, -1):
            t = turns[i]
            if self._is_protected(t):
                continue
            tx = extract_text_for_processing(t)
            if _QUESTION_ONLY.match(tx):
                continue
            if _has_layer_a(tx):
                res_idx = i
                break

        if res_idx < 0:
            return copy.deepcopy(conversation)

        if res_idx == 0:
            return copy.deepcopy(conversation)

        thread_start = _find_thread_start(conversation, res_idx)
        while thread_start < len(turns) and turns[thread_start].role == "system":
            thread_start += 1
        if thread_start > res_idx:
            return copy.deepcopy(conversation)
        if res_idx - thread_start < 1:
            return copy.deepcopy(conversation)

        slice_turns = turns[thread_start : res_idx + 1]
        if len(slice_turns) < 2:
            return copy.deepcopy(conversation)

        res_text = extract_text_for_processing(turns[res_idx])

        if self.conv_type == "chat":
            # Include one trailing turn so an assistant acknowledgement after a user's resolution still counts
            scan_end = min(len(turns) - 1, res_idx + 1)
            has_user = any(
                turns[i].role == "user" and _has_signal_any(extract_text_for_processing(turns[i]))
                for i in range(thread_start, scan_end + 1)
            )
            has_asst = any(
                turns[i].role == "assistant" and _has_signal_any(extract_text_for_processing(turns[i]))
                for i in range(thread_start, scan_end + 1)
            )
            if not (has_user and has_asst):
                return copy.deepcopy(conversation)

        elif self.conv_type == "agent":
            if not any(
                _has_layer_a(extract_text_for_processing(turns[i]))
                for i in range(thread_start, res_idx + 1)
                if not self._is_protected(turns[i])
            ):
                return copy.deepcopy(conversation)

        subj = _noun_subject(res_text)
        _, desc = _extract_subject_description(res_text)
        if not desc:
            desc = "decision recorded"
        fact = f"RESOLVED: {subj} — {desc}"

        collapse_end = res_idx
        if (
            res_idx + 1 < len(turns)
            and turns[res_idx + 1].role == "assistant"
            and _has_signal_any(extract_text_for_processing(turns[res_idx + 1]))
        ):
            collapse_end = res_idx + 1

        collapsed = collapse_end - thread_start + 1
        new_turns = [copy.deepcopy(t) for t in turns[:thread_start]]
        new_turns.append(
            Turn(
                role="system",
                content=fact,
                metadata={"source": "resolution_detector", "collapsed_turns": collapsed},
                importance=1.0,
                resolved=False,
                compressed=False,
            )
        )
        new_turns.extend(copy.deepcopy(t) for t in turns[collapse_end + 1 :])

        return Conversation(
            turns=new_turns,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
