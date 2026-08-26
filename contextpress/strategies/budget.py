from __future__ import annotations

import copy
import warnings

import tiktoken

from contextpress.models import Conversation, Turn, clone_turn
from contextpress.stats import count_turn_tokens, get_encoding
from contextpress.strategies.base import BaseStrategy
from contextpress.tools import tool_group_indices


def _truncate_system_turn(turn: Turn, encoding: tiktoken.Encoding, max_tokens: int) -> Turn:
    if isinstance(turn.content, str):
        tokens = encoding.encode(turn.content)
        if len(tokens) <= max_tokens:
            return clone_turn(turn)
        new_text = encoding.decode(tokens[:max_tokens])
        nt = clone_turn(turn)
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
    nt = clone_turn(turn)
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

    def process(self, conversation: Conversation) -> Conversation:
        enc = get_encoding(self.model)
        turns: list[Turn] = [clone_turn(t) for t in conversation.turns]

        def total_toks(ts: list[Turn]) -> int:
            return sum(count_turn_tokens(t, enc) for t in ts)

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
            group: list[int] | None = None
            for idx in removable:
                candidate = tool_group_indices(turns, idx)
                if any(g in protected for g in candidate):
                    continue
                group = candidate
                break
            if group is not None:
                for g in sorted(group, reverse=True):
                    turns.pop(g)
                    n_removed += 1
                continue

            # Last resort: truncate system (see behavior contract note on invariant 1)
            warnings.warn(
                "contextpress: truncating system prompt to satisfy token budget",
                stacklevel=2,
            )
            for si, t in enumerate(turns):
                if t.role != "system":
                    continue
                others = total_toks(turns) - count_turn_tokens(t, enc)
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
