"""Keep the opening and the live tail; drop the middle of the thread."""

from __future__ import annotations

import copy

from contextpress.models import Conversation, Turn, clone_turn
from contextpress.strategies.base import BaseStrategy
from contextpress.tools import has_tool_marker, tool_group_indices

_STUB = "[{n} earlier messages omitted]"


def _head_tail(aggressiveness: float) -> tuple[int, int]:
    """Non-system turns to keep at each end. Tail is always at least 3."""
    if aggressiveness < 0.35:
        return 3, 4
    if aggressiveness < 0.7:
        return 2, 3
    return 1, 3


class TrimStrategy(BaseStrategy):
    """Drop middle history. Opening intent and the last few turns stay verbatim."""

    def __init__(self, aggressiveness: float = 0.5, **kwargs: object):
        super().__init__(aggressiveness, **kwargs)

    def process(self, conversation: Conversation) -> Conversation:
        turns = conversation.turns
        ns = [i for i, t in enumerate(turns) if not self._is_protected(t)]
        head, tail = _head_tail(self.aggressiveness)
        if len(ns) <= head + tail:
            return Conversation(
                turns=[clone_turn(t) for t in turns],
                type=conversation.type,
                metadata=copy.deepcopy(conversation.metadata),
            )

        keep: set[int] = {i for i, t in enumerate(turns) if self._is_protected(t)}
        keep.update(ns[:head])
        keep.update(ns[-tail:])
        for i in ns:
            if has_tool_marker(turns[i]):
                keep.update(tool_group_indices(turns, i))

        dropped = [i for i in ns if i not in keep]
        if not dropped:
            return Conversation(
                turns=[clone_turn(t) for t in turns],
                type=conversation.type,
                metadata=copy.deepcopy(conversation.metadata),
            )

        stub_at = dropped[0]
        out: list[Turn] = []
        stub_added = False
        for i, t in enumerate(turns):
            if i == stub_at and not stub_added:
                out.append(
                    Turn(
                        role="assistant",
                        content=_STUB.format(n=len(dropped)),
                        compressed=True,
                        metadata={"_trim_stub": True, "omitted": len(dropped)},
                    )
                )
                stub_added = True
            if i in keep:
                out.append(clone_turn(t))

        if not stub_added:
            out.append(
                Turn(
                    role="assistant",
                    content=_STUB.format(n=len(dropped)),
                    compressed=True,
                    metadata={"_trim_stub": True, "omitted": len(dropped)},
                )
            )

        return Conversation(
            turns=out,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
