from __future__ import annotations

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """
    Interface for optional Tier 2 LLM processing.
    Users implement this to connect their preferred LLM provider.
    contextpress never imports any LLM SDK directly.
    """

    @abstractmethod
    def summarize(self, text: str, max_tokens: int) -> str:
        """
        Abstractively summarize text to fit within max_tokens.
        Must return a plain string.
        """
        ...

    @abstractmethod
    def deduplicate(self, turns: list[str]) -> list[int]:
        """
        Given a list of turn texts, return indices of turns to KEEP.
        The backend decides which are semantically redundant.
        """
        ...
