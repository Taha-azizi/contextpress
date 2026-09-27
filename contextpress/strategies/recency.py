from __future__ import annotations

import copy
import re

from contextpress.models import Conversation, Turn, clone_conversation, clone_turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.stats import get_encoding
from contextpress.strategies.base import BaseStrategy
from contextpress.text_sim import tfidf_cosine, tfidf_query_scores
from contextpress.tools import preserve_structured_turn

# Pasted chapters below this size stay on the normal recency path. Chunked
# sections in the long-prose study are ~700 tokens, so they do not enter it.
_LONG_TURN_TOKENS = 1500
_LONG_TURN_RELEVANCE = 0.3
_TOKEN_ENCODING = None

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SUMY_TOKENIZER = None
_SUMY_SUMMARIZER = None


def _get_sumy_components():
    global _SUMY_TOKENIZER, _SUMY_SUMMARIZER
    if _SUMY_TOKENIZER is None or _SUMY_SUMMARIZER is None:
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lsa import LsaSummarizer

        _SUMY_TOKENIZER = Tokenizer("english")
        _SUMY_SUMMARIZER = LsaSummarizer()
    return _SUMY_TOKENIZER, _SUMY_SUMMARIZER


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


def _encoding():
    global _TOKEN_ENCODING
    if _TOKEN_ENCODING is None:
        _TOKEN_ENCODING = get_encoding(None)
    return _TOKEN_ENCODING


def _token_count(text: str) -> int:
    if len(text) < _LONG_TURN_TOKENS:
        return len(text)
    return len(_encoding().encode(text))


def _select_long_turn_sentences(sentences: list[str], query: str, *, mode: str) -> list[str]:
    """Keep query-matching sentences plus a lead. ``medium`` also fills to ~1/3."""
    n = len(sentences)
    if n <= 3 or not query.strip():
        return sentences
    scores = tfidf_query_scores(query, sentences)
    relevant = {i for i, score in enumerate(scores) if score >= _LONG_TURN_RELEVANCE}
    lead_n = 4 if mode == "medium" else 2
    keep = set(range(min(lead_n, n)))
    keep.update(relevant)
    if mode == "medium":
        target = max(len(relevant), (n + 2) // 3)
        ranked = sorted(range(n), key=lambda i: (-scores[i], i))
        for i in ranked:
            if len(keep) >= target:
                break
            keep.add(i)
    if len(keep) >= n:
        return sentences
    return [sentences[i] for i in range(n) if i in keep]


def _compress_long_turn(text: str, query: str, *, mode: str) -> str:
    sentences = _split_sentences(text)
    chosen = _select_long_turn_sentences(sentences, query, mode=mode)
    if len(chosen) == len(sentences):
        return text
    return " ".join(chosen)


def _summarize_text(text: str, sentence_count: int) -> str:
    if sentence_count <= 0:
        return text
    try:
        from sumy.parsers.plaintext import PlaintextParser

        tok, summarizer = _get_sumy_components()
        parser = PlaintextParser.from_string(text, tok)
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
    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        conv_type: str = "chat",
        long_turn_mode: str | None = None,
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type
        if long_turn_mode not in (None, "medium", "high"):
            raise ValueError("long_turn_mode must be 'medium', 'high', or None")
        self.long_turn_mode = long_turn_mode

    def process(self, conversation: Conversation) -> Conversation:
        turns = conversation.turns
        ns_indices = [i for i, t in enumerate(turns) if not self._is_protected(t)]
        n_ns = len(ns_indices)
        if n_ns == 0:
            return clone_conversation(conversation)

        threshold = _recency_threshold(self.aggressiveness)
        protected_ns = set(ns_indices[-3:]) if n_ns >= 1 else set()

        query_text = ""
        query_idx: int | None = None
        if self.conv_type == "rag_doc":
            for i in range(len(turns) - 1, -1, -1):
                t = turns[i]
                if t.role == "user" and not self._is_protected(t):
                    query_text = extract_text_for_processing(t)
                    query_idx = i
                    break
            if not query_text and ns_indices:
                query_text = " ".join(extract_text_for_processing(turns[i]) for i in ns_indices)

        processed_by_ns: list[Turn] = []
        for pos, i in enumerate(ns_indices):
            t = turns[i]

            if self._should_extract_long_turn(t, i, query_idx):
                text = extract_text_for_processing(t)
                new_text = _compress_long_turn(
                    text, query_text, mode=self.long_turn_mode or "medium"
                )
                if new_text.strip() != text.strip():
                    processed_by_ns.append(apply_text_to_turn(t, new_text.strip()))
                else:
                    processed_by_ns.append(clone_turn(t))
                continue

            if i in protected_ns:
                processed_by_ns.append(clone_turn(t))
                continue

            text = extract_text_for_processing(t)

            if preserve_structured_turn(t):
                processed_by_ns.append(clone_turn(t))
                continue

            if self.conv_type == "rag_doc":
                rel = self._relevance_score(query_text, text)
                should_compress = rel < 0.3
            else:
                recency_score = 1.0 if n_ns == 1 else pos / (n_ns - 1)
                should_compress = recency_score < threshold

            if not should_compress:
                processed_by_ns.append(clone_turn(t))
                continue

            n_sent = _sentence_count(text)
            tgt = _target_sentence_count(n_sent)
            if tgt is None:
                processed_by_ns.append(clone_turn(t))
                continue

            new_text = _summarize_text(text, tgt)
            if new_text.strip() != text.strip():
                processed_by_ns.append(apply_text_to_turn(t, new_text.strip()))
            else:
                processed_by_ns.append(clone_turn(t))

        by_idx = dict(zip(ns_indices, processed_by_ns, strict=True))
        out: list[Turn] = []
        for i, t in enumerate(conversation.turns):
            if i in by_idx:
                out.append(by_idx[i])
            else:
                out.append(clone_turn(t))
        return Conversation(
            turns=out, type=conversation.type, metadata=copy.deepcopy(conversation.metadata)
        )

    def _should_extract_long_turn(self, turn: Turn, index: int, query_idx: int | None) -> bool:
        if self.conv_type != "rag_doc" or self.long_turn_mode not in ("medium", "high"):
            return False
        if query_idx is not None and index == query_idx:
            return False
        if preserve_structured_turn(turn):
            return False
        text = extract_text_for_processing(turn)
        return _token_count(text) > _LONG_TURN_TOKENS

    def _relevance_score(self, query: str, chunk: str) -> float:
        return tfidf_cosine(query, chunk)
