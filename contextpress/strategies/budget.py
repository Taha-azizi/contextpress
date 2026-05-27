from __future__ import annotations

import copy
import warnings

import tiktoken

from contextpress.models import Conversation, Turn
from contextpress.normalizer import extract_text_for_processing
from contextpress.strategies.base import BaseStrategy


def _turn_tokens(turn: Turn, encoding: tiktoken.Encoding) -> int:
    role = turn.role
    if isinstance(turn.content, str):
        body = turn.content
    else:
        body = extract_text_for_processing(turn)
    text = f"{role}\n{body}"
    return len(encoding.encode(text))


def _truncate_system_turn(turn: Turn, encoding: tiktoken.Encoding, max_tokens: int) -> Turn:
    if isinstance(turn.content, str):
        tokens = encoding.encode(turn.content)
        if len(tokens) <= max_tokens:
            return copy.deepcopy(turn)
        new_text = encoding.decode(tokens[:max_tokens])
        nt = copy.deepcopy(turn)
        nt.content = new_text
        nt.compressed = True
        if nt.original_content is None:
            nt.original_content = turn.content
        return nt
    blocks = copy.deepcopy(turn.content)
    for i, b in enumerate(blocks):
        if b.type == "text":
            tokens = encoding.encode(b.content)
            if len(tokens) > max_tokens:
                nb = copy.deepcopy(b)
                nb.content = encoding.decode(tokens[:max_tokens])
                blocks[i] = nb
            break
    nt = copy.deepcopy(turn)
    nt.content = blocks
    nt.compressed = True
    if nt.original_content is None:
        nt.original_content = copy.deepcopy(turn.content)
    return nt


class BudgetStrategy(BaseStrategy):
    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        token_budget: int,
        model: str | None = None,
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.token_budget = int(token_budget)
        self.model = model

    def _encoding(self) -> tiktoken.Encoding:
        if self.model:
            try:
                return tiktoken.encoding_for_model(self.model)
            except KeyError:
                pass
        return tiktoken.get_encoding("cl100k_base")

    def process(self, conversation: Conversation) -> Conversation:
        enc = self._encoding()
        turns: list[Turn] = [copy.deepcopy(t) for t in conversation.turns]

        def total_toks(ts: list[Turn]) -> int:
            return sum(_turn_tokens(t, enc) for t in ts)

        if total_toks(turns) <= self.token_budget:
            return Conversation(
                turns=turns,
                type=conversation.type,
                metadata=copy.deepcopy(conversation.metadata),
            )

        n_removed = 0

        while total_toks(turns) > self.token_budget:
            ns_positions = [i for i, t in enumerate(turns) if t.role != "system"]
            keep = min(2, len(ns_positions))
            protected = set(ns_positions[-keep:]) if keep else set()
            removable = [i for i in ns_positions if i not in protected]
            if removable:
                turns.pop(removable[0])
                n_removed += 1
                continue

            # No non-system left to remove (or only protected pair) — truncate system from end
            warnings.warn(
                "contextpress: truncating system prompt to satisfy token budget",
                stacklevel=2,
            )
            for si, t in enumerate(turns):
                if t.role != "system":
                    continue
                others = total_toks(turns) - _turn_tokens(t, enc)
                room = max(1, self.token_budget - others)
                turns[si] = _truncate_system_turn(t, enc, room)
            break

        if n_removed > 0:
            warnings.warn(
                f"contextpress: token budget enforced - {n_removed} turns removed to fit "
                f"{self.token_budget} tokens",
                stacklevel=2,
            )

        return Conversation(
            turns=turns,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
