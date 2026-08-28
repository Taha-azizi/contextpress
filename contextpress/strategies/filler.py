from __future__ import annotations

import copy
import re

from contextpress.models import Conversation, Turn, clone_turn
from contextpress.normalizer import apply_text_to_turn, extract_text_for_processing
from contextpress.strategies.base import BaseStrategy
from contextpress.tools import preserve_structured_turn

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
    # Extra low-value discourse / empty hedges (chat padding, not propositional).
    "it is important to note that",
    "it should be noted that",
    "it goes without saying",
    "as a matter of fact",
    "to be perfectly honest",
    "to be honest",
    "to tell you the truth",
    "if you know what i mean",
    "if that makes sense",
    "from my perspective",
    "in my humble opinion",
    "in my opinion",
    "in my view",
    "i just wanted to say",
    "i just wanted to",
    "don't hesitate to",
    "please feel free to",
    "feel free to",
    "as you may know",
    "as you know",
    "as you can see",
    "to be fair",
    "that being said",
    "having said that",
    "with that said",
    "all things considered",
    "by and large",
    "more or less",
    "a little bit",
    "at this point in time",
    "in the process of",
    "for the most part",
    "let me see",
    "let me think",
    "if you will",
    "i suppose",
    "i guess",
    # Aggressive discourse / empty padding (still removal-only, not paraphrase).
    "due to the fact that",
    "in spite of the fact that",
    "regardless of the fact that",
    "the fact of the matter is",
    "the fact is that",
    "the fact is",
    "it is worth noting that",
    "it is worth mentioning that",
    "it is worth pointing out that",
    "it bears mentioning that",
    "for what it's worth",
    "needless to mention",
    "as a general rule",
    "in a sense",
    "in a way",
    "in some sense",
    "in some ways",
    "to some extent",
    "to a certain extent",
    "in certain cases",
    "in most cases",
    "generally speaking",
    "broadly speaking",
    "strictly speaking",
    "technically speaking",
    "all in all",
    "at any rate",
    "be that as it may",
    "come to think of it",
    "funnily enough",
    "interestingly enough",
    "strangely enough",
    "as it turns out",
    "as it happens",
    "truth be told",
    "if i'm being honest",
    "if i'm honest",
    "not gonna lie",
    "not going to lie",
    "just so you know",
    "for your information",
    "by the way",
    "as an aside",
    "on another note",
    "moving on",
    "that said",
    "this being said",
    "with that in mind",
    "keeping in mind that",
    "bearing in mind that",
    "it goes without saying that",
    "i would argue that",
    "i would say that",
    "i would like to say that",
    "i wanted to say that",
    "i think that",
    "i feel like",
    "i feel that",
    "i believe that",
    "it seems to me that",
    "it seems that",
    "it appears that",
    "it looks like",
    "what i'm trying to say is",
    "what i mean is",
    "the point is that",
    "the point is",
    "the thing is that",
    "the thing is",
    "here's the thing",
    "here's the deal",
    "when all is said and done",
    "in the final analysis",
    "last but not least",
    "first and foremost",
    "please note that",
    "please note",
    "please be advised that",
    "kindly note that",
    "rest assured that",
    "make no mistake",
    "without a doubt",
    "there is no doubt that",
    "needless to add",
    "suffice it to say that",
    "suffice it to say",
    "to put it simply",
    "to put it mildly",
    "to put it another way",
    "put another way",
    "in other words",
    "or rather",
    "so to speak",
    "as it were",
    "per se",
    "a bit",
    "a tad",
    "kinda",
    "sorta",
]

# Single filler tokens (word-boundary); avoid standalone "just" globally — use phrases
FILLER_WORDS_STANDALONE = [
    "so",
    "um",
    "uh",
    "er",
    "ah",
    "hmm",
    "anyways",
    "anyhow",
    "frankly",
    "personally",
    "seemingly",
    "apparently",
    "arguably",
    "admittedly",
    "presumably",
    "supposedly",
    "ostensibly",
    "interestingly",
    "surprisingly",
    "fortunately",
    "unfortunately",
    "hopefully",
    "thankfully",
    "honestly",
    "truthfully",
    "sincerely",
    "indeed",
    "perhaps",
    "maybe",
    "somehow",
    "somewhat",
    "anyway",
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
    "no problem",
    "no worries",
    "happy to help",
    "will do",
    "copy that",
]


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


def _cleanup_after_filler(text: str) -> str:
    """Repair punctuation left behind after filler phrase removal."""
    s = re.sub(r"\s+", " ", text)
    s = re.sub(r"\s*,\s*(?:,\s*)+", ", ", s)
    s = re.sub(r"\s*;\s*(?:;\s*)+", "; ", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"^[\s,;:.]+", "", s)
    s = re.sub(r"[,;]\s*$", "", s)
    s = s.strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


def _remove_fillers_text(text: str) -> str:
    if _ACTUALLY_NO.match(text):
        return text
    # do not strip "actually" in "actually, no"
    s = _FILLER_RE.sub("", text)
    if s == text:
        return text
    return _cleanup_after_filler(s)


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
            if self._is_protected(turn) or preserve_structured_turn(turn):
                new_turns.append(clone_turn(turn))
                continue

            if self.conv_type == "rag_doc":
                nt = self._apply_fillers_only(turn)
                if nt is not None:
                    new_turns.append(nt)
                continue

            text = extract_text_for_processing(turn)

            if self.conv_type in ("chat", "agent"):
                if turn.role == "assistant" and _is_acknowledgement_only(text):
                    continue  # drop turn

            new_text = _remove_fillers_text(text)
            if not new_text.strip():
                # Never drop user turns entirely (filler-only user messages stay).
                if turn.role == "user":
                    new_turns.append(clone_turn(turn))
                continue

            if new_text != text:
                nt = apply_text_to_turn(turn, new_text)
                new_turns.append(nt)
            else:
                new_turns.append(clone_turn(turn))

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
        return clone_turn(turn)
