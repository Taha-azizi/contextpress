"""Compact structured / verbose payloads inside turns (stdlib only)."""

from __future__ import annotations

import copy
import json
import re

from contextpress.models import Conversation, Turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.strategies.base import BaseStrategy
from contextpress.tools import minify_tool_fields

_CODE_FENCE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)
_MULTI_BLANK = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def _try_minify_json(text: str) -> str | None:
    s = text.strip()
    if not s or s[0] not in "{[":
        return None
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _dedupe_consecutive_lines(text: str) -> str:
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    out: list[str] = []
    prev: str | None = None
    for line in lines:
        if prev is not None and line == prev and line.strip() != "":
            continue
        out.append(line)
        prev = line
    return "\n".join(out)


def _compact_plain(text: str, *, aggressiveness: float) -> str:
    s = _MULTI_BLANK.sub("\n\n", text)
    if aggressiveness >= 0.35:
        s = _dedupe_consecutive_lines(s)
    if aggressiveness >= 0.55:
        s = _MULTI_SPACE.sub(" ", s)
    return s.strip() if aggressiveness >= 0.75 else s


def _compact_segment(segment: str, *, aggressiveness: float) -> str:
    if segment.startswith("```"):
        return segment
    mini = _try_minify_json(segment)
    if mini is not None:
        return mini
    return _compact_plain(segment, aggressiveness=aggressiveness)


def compact_structure_text(text: str, *, aggressiveness: float = 0.5) -> str:
    """Minify JSON blobs and tighten whitespace / repeated log lines."""
    if not text or not text.strip():
        return text
    whole = _try_minify_json(text)
    if whole is not None:
        return whole
    parts = _CODE_FENCE.split(text)
    return "".join(_compact_segment(p, aggressiveness=aggressiveness) for p in parts)


class StructureStrategy(BaseStrategy):
    """Early Tier‑1 stage: shrink JSON / whitespace / repeated lines in turns."""

    def __init__(self, aggressiveness: float = 0.5, *, conv_type: str = "chat", **kwargs: object):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type

    def process(self, conversation: Conversation) -> Conversation:
        new_turns: list[Turn] = []
        for turn in conversation.turns:
            if self._is_protected(turn):
                new_turns.append(copy.deepcopy(turn))
                continue
            text = extract_text_for_processing(turn)
            compacted = compact_structure_text(text, aggressiveness=self.aggressiveness)
            if compacted != text:
                nt = apply_text_to_turn(turn, compacted)
            else:
                nt = copy.deepcopy(turn)
            new_turns.append(minify_tool_fields(nt))
        return Conversation(
            turns=new_turns,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )
