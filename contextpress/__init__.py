from __future__ import annotations

from typing import Any

from contextpress._bootstrap import bootstrap_nltk
from contextpress.models import ContentBlock, Conversation, Turn

bootstrap_nltk()

__all__ = ["ContextManager", "Turn", "Conversation", "ContentBlock"]
__version__ = "0.1.0"


def __getattr__(name: str) -> Any:
    # Lazy import: ContextManager -> core -> pipeline -> strategies (sumy, etc.)
    if name == "ContextManager":
        from contextpress.core import ContextManager

        return ContextManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
