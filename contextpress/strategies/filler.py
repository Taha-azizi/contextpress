from __future__ import annotations

import copy
import re

from contextpress.models import Conversation, Turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.strategies.base import BaseStrategy

# Curated lists — longer phrases first for safe replacement order
FILLER_PHRASES = [
    "as i mentioned",
    "as we discussed",
    "as i said",
    "at the end of the day",
    "for all intents and purposes",
    "needless to say",
    "in terms of",
    "you know",
    "i mean",
    "kind of",
    "sort of",
    "basically",
    "actually",
    "literally",
    "honestly",
    "seriously",
    "clearly",
    "obviously",
    "essentially",
    "certainly",
    "definitely",
    "absolutely",
    "totally",
    "completely",
    "simply",
    "really",
    "very",
    "quite",
    "rather",
    "fairly",
    "pretty",
    "right",
    "okay",
    "anyway",
    "well",
]

# Single filler tokens (word-boundary); avoid standalone "just" globally — use phrases
FILLER_WORDS_STANDALONE = [
    "so",
]

ACKNOWLEDGEMENT_PHRASES = [
    "great question",
    "good question",
    "excellent question",
    "you're absolutely right",
    "that's a great point",
    "of course",
    "sure thing",
    "sounds good",
    "makes sense",
    "i understand",
    "i see",
    "got it",
    "noted",
    "understood",
    "thanks for clarifying",
    "thank you for that",
]

_TOOL_MARKERS = ("tool_calls", "tool_call", "tool_use", "tool_result", "<tool", "[tool")


def _has_tool_marker(turn: Turn) -> bool:
    meta = turn.metadata or {}
    if any(k in meta for k in ("tool_calls", "tool_call", "tool_use", "tool_result")):
        return True
    text = extract_text_for_processing(turn).lower()
    return any(m in text for m in _TOOL_MARKERS)


def _build_filler_pattern() -> re.Pattern[str]:
    pattern_parts: list[str] = []
    for phrase in sorted(FILLER_PHRASES, key=len, reverse=True):
        pattern_parts.append(rf"\b{re.escape(phrase)}\b")
    for w in FILLER_WORDS_STANDALONE:
        pattern_parts.append(rf"\b{re.escape(w)}\b")
    # "just" but not when introducing "just in time"
    pattern_parts.append(r"\bjust\b(?!\s+in\s+time)")
    return re.compile("|".join(pattern_parts), re.IGNORECASE)


_FILLER_RE = _build_filler_pattern()

# Keep "actually" when it starts a phrase like "actually, no" (per spec).
_ACTUALLY_NO = re.compile(r"^\s*actually\s*,\s*no\b", re.IGNORECASE)


def _remove_fillers_text(text: str) -> str:
    if _ACTUALLY_NO.match(text):
        return text
    # do not strip "actually" in "actually, no"
    s = _FILLER_RE.sub("", text)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _is_acknowledgement_only(text: str) -> bool:
    t = text.strip().lower().rstrip(".!?")
    if not t:
        return False
    return any(t == p.rstrip(".") or t == p for p in ACKNOWLEDGEMENT_PHRASES)


class FillerStrategy(BaseStrategy):
    def __init__(
        self,
        aggressiveness: float = 0.5,
        *,
        conv_type: str = "chat",
        role_aware: bool = True,
        **kwargs: object,
    ):
        super().__init__(aggressiveness, **kwargs)
        self.conv_type = conv_type
        self.role_aware = role_aware

    def process(self, conversation: Conversation) -> Conversation:
        new_turns: list[Turn] = []
        for turn in conversation.turns:
            if self._is_protected(turn):
                new_turns.append(copy.deepcopy(turn))
                continue

            if self.conv_type == "rag_doc":
                nt = self._apply_fillers_only(turn)
                if nt is not None:
                    new_turns.append(nt)
                continue

            if self.conv_type == "agent" and _has_tool_marker(turn):
                new_turns.append(copy.deepcopy(turn))
                continue

            text = extract_text_for_processing(turn)

            if self.conv_type in ("chat", "agent"):
                if turn.role == "assistant" and _is_acknowledgement_only(text):
                    continue  # drop turn

            new_text = _remove_fillers_text(text)
            if not new_text.strip():
                continue

            if new_text != text:
                nt = apply_text_to_turn(turn, new_text)
                new_turns.append(nt)
            else:
                new_turns.append(copy.deepcopy(turn))

        return Conversation(
            turns=new_turns,
            type=conversation.type,
            metadata=copy.deepcopy(conversation.metadata),
        )

    def _apply_fillers_only(self, turn: Turn) -> Turn | None:
        text = extract_text_for_processing(turn)
        new_text = _remove_fillers_text(text)
        if not new_text.strip():
            return None
        if new_text != text:
            return apply_text_to_turn(turn, new_text)
        return copy.deepcopy(turn)
