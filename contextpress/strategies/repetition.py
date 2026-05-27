from __future__ import annotations

import copy

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from contextpress.models import Conversation, Turn
from contextpress.normalizer import extract_text_for_processing
from contextpress.strategies.base import BaseStrategy


def _threshold_for_aggr(aggressiveness: float) -> float:
    # 0.0 -> 0.95, 0.5 -> 0.82, 1.0 -> 0.70
    return 0.95 - float(aggressiveness) * 0.25


def _token_count(text: str) -> int:
    return len(text.split())


class RepetitionStrategy(BaseStrategy):
    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        role_aware: bool = True,
        conv_type: str = "chat",
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.role_aware = role_aware
        self.conv_type = conv_type

    def process(self, conversation: Conversation) -> Conversation:
        threshold = _threshold_for_aggr(self.aggressiveness)
        turns = conversation.turns
        indices_to_drop: set[int] = set()

        # Positions of non-system turns with their global index
        nst: list[tuple[int, Turn]] = [(i, t) for i, t in enumerate(turns) if not self._is_protected(t)]

        def run_group(group: list[tuple[int, Turn]]) -> None:
            if len(group) < 2:
                return
            texts = []
            g_idx = []
            for gi, t in group:
                tx = extract_text_for_processing(t)
                if _token_count(tx) < 10:
                    continue
                texts.append(tx)
                g_idx.append(gi)
            if len(texts) < 2:
                return
            vec = TfidfVectorizer(min_df=1, max_df=1.0)
            try:
                mat = vec.fit_transform(texts)
            except ValueError:
                return
            sim = cosine_similarity(mat)
            n = len(g_idx)
            for a in range(n):
                for b in range(a + 1, n):
                    if sim[a, b] > threshold:
                        ia, ib = g_idx[a], g_idx[b]
                        # drop earlier (smaller global index)
                        indices_to_drop.add(min(ia, ib))

        if self.role_aware and self.conv_type != "rag_doc":
            user_group = [(i, t) for i, t in nst if t.role == "user"]
            asst_group = [(i, t) for i, t in nst if t.role == "assistant"]
            run_group(user_group)
            run_group(asst_group)
        else:
            run_group(nst)

        new_turns: list[Turn] = []
        for i, t in enumerate(turns):
            if i in indices_to_drop:
                continue
            new_turns.append(copy.deepcopy(t))

        return Conversation(
            turns=new_turns,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
