from __future__ import annotations

import copy
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer

from contextpress.models import Conversation, Turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.strategies.base import BaseStrategy

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentence_count(text: str) -> int:
    t = text.strip()
    if not t:
        return 0
    parts = _split_sentences(t)
    return len(parts)


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def _recency_threshold(aggressiveness: float) -> float:
    return 0.1 + float(aggressiveness) * 0.6


def _target_sentence_count(n_sentences: int) -> int | None:
    if n_sentences <= 3:
        return None
    if n_sentences <= 8:
        return 2
    return 3


def _summarize_text(text: str, sentence_count: int) -> str:
    if sentence_count <= 0:
        return text
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LsaSummarizer()
        sents = summarizer(parser.document, sentence_count)
        if not sents:
            return text
        return " ".join(str(s) for s in sents)
    except Exception:
        sents = _split_sentences(text)
        if len(sents) <= sentence_count:
            return text
        return " ".join(sents[-sentence_count:])


class RecencyStrategy(BaseStrategy):
    def __init__(self, aggressiveness: float = 0.5, *, conv_type: str = "chat", **kwargs: object):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type

    def process(self, conversation: Conversation) -> Conversation:
        turns = conversation.turns
        ns_indices = [i for i, t in enumerate(turns) if not self._is_protected(t)]
        n_ns = len(ns_indices)
        if n_ns == 0:
            return copy.deepcopy(conversation)

        threshold = _recency_threshold(self.aggressiveness)
        protected_ns = set(ns_indices[-3:]) if n_ns >= 1 else set()

        query_text = ""
        if self.conv_type == "rag_doc":
            for t in reversed(turns):
                if t.role == "user" and not self._is_protected(t):
                    query_text = extract_text_for_processing(t)
                    break
            if not query_text and ns_indices:
                query_text = " ".join(extract_text_for_processing(turns[i]) for i in ns_indices)

        processed_by_ns: list[Turn] = []
        for pos, i in enumerate(ns_indices):
            t = turns[i]

            if i in protected_ns:
                processed_by_ns.append(copy.deepcopy(t))
                continue

            text = extract_text_for_processing(t)

            if self.conv_type == "rag_doc":
                rel = self._relevance_score(query_text, text)
                should_compress = rel < 0.3
            else:
                recency_score = 1.0 if n_ns == 1 else pos / (n_ns - 1)
                should_compress = recency_score < threshold

            if not should_compress:
                processed_by_ns.append(copy.deepcopy(t))
                continue

            n_sent = _sentence_count(text)
            tgt = _target_sentence_count(n_sent)
            if tgt is None:
                processed_by_ns.append(copy.deepcopy(t))
                continue

            new_text = _summarize_text(text, tgt)
            if new_text.strip() != text.strip():
                processed_by_ns.append(apply_text_to_turn(t, new_text.strip()))
            else:
                processed_by_ns.append(copy.deepcopy(t))

        by_idx = dict(zip(ns_indices, processed_by_ns))
        out: list[Turn] = []
        for i, t in enumerate(conversation.turns):
            if i in by_idx:
                out.append(by_idx[i])
            else:
                out.append(copy.deepcopy(t))
        return Conversation(turns=out, type=conversation.type, metadata=copy.deepcopy(conversation.metadata))

    def _relevance_score(self, query: str, chunk: str) -> float:
        if not query.strip() or not chunk.strip():
            return 0.0
        try:
            vec = TfidfVectorizer(min_df=1, max_df=1.0)
            mat = vec.fit_transform([query, chunk])
            return float(cosine_similarity(mat[0:1], mat[1:2])[0, 0])
        except ValueError:
            return 0.0
