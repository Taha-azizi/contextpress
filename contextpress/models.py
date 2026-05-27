from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ContentBlock:
    """
    A single block of content within a turn.
    Used when content is multimodal (text + image, tool call, etc.)
    """

    type: str  # "text" | "image" | "tool_use" | "tool_result"
    content: str  # text content or reference string
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Turn:
    """
    A single message in a conversation.
    This is the canonical unit the entire pipeline operates on.
    """

    role: str  # "user" | "assistant" | "system"
    content: str | list[ContentBlock]  # string for simple, list for multimodal
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 1.0  # set by pipeline stages, 0.0–1.0
    resolved: bool = False  # True when flagged by resolution detector
    compressed: bool = False  # True if content was modified by pipeline
    original_content: str | list[ContentBlock] | None = None  # preserves original before compression


@dataclass
class Conversation:
    """
    An ordered list of turns with a declared context type.
    This is the primary object passed into the pipeline.
    """

    turns: list[Turn]
    type: str = "chat"  # "chat" | "rag_doc" | "agent"
    metadata: dict[str, Any] = field(default_factory=dict)

    def text_turns(self) -> list[Turn]:
        """Returns only turns that contain extractable text content."""
        return [t for t in self.turns if self._has_text(t)]

    def non_system_turns(self) -> list[Turn]:
        """Returns all turns except system turns."""
        return [t for t in self.turns if t.role != "system"]

    @staticmethod
    def _has_text(turn: Turn) -> bool:
        if isinstance(turn.content, str):
            return bool(turn.content.strip())
        return any(b.type == "text" for b in turn.content)
