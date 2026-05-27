from __future__ import annotations

from abc import ABC, abstractmethod

from contextpress.models import Conversation


class BaseStrategy(ABC):
    """
    All pipeline stages inherit from this class.
    Stages must be stateless. Never mutate the input Conversation.
    Always return a new Conversation with modified turns.
    """

    def __init__(self, aggressiveness: float = 0.5, **kwargs: object):
        self.aggressiveness = float(aggressiveness)

    @abstractmethod
    def process(self, conversation: Conversation) -> Conversation:
        """
        Takes a Conversation, returns a new Conversation.
        System turns (role="system") must be passed through untouched.
        """
        ...

    def _is_protected(self, turn) -> bool:
        """System turns are always protected from modification."""
        return turn.role == "system"
