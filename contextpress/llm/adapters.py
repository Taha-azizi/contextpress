from __future__ import annotations

import warnings
from typing import Any

from contextpress.llm._helpers import DEDUP_SYSTEM_PROMPT, format_numbered_turns, parse_keep_indices
from contextpress.llm.base import LLMBackend


def _ollama_response_text(resp: Any) -> str:
    """Normalize ollama chat response (object or dict) to a string."""
    if resp is None:
        return ""
    if isinstance(resp, dict):
        msg = resp.get("message") or {}
        if isinstance(msg, dict):
            return str(msg.get("content") or "").strip()
        return str(getattr(msg, "content", "") or "").strip()
    msg = getattr(resp, "message", None)
    if msg is not None:
        c = getattr(msg, "content", None)
        if c is not None:
            return str(c).strip()
    return ""


class OpenAIBackend(LLMBackend):
    """
    Adapter for OpenAI-compatible APIs.
    Requires: pip install openai
    User must pass their own client instance.

    Usage:
        from openai import OpenAI
        from contextpress.llm.adapters import OpenAIBackend

        backend = OpenAIBackend(client=OpenAI(), model="gpt-4o-mini")
        cm = ContextManager(type="chat", llm_backend=backend)
    """

    def __init__(self, client: Any, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def summarize(self, text: str, max_tokens: int) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Summarize the following text concisely."},
                    {"role": "user", "content": text},
                ],
                max_tokens=max_tokens,
            )
            choice = resp.choices[0]
            content = choice.message.content
            return content if content is not None else text
        except Exception as exc:
            warnings.warn(f"contextpress OpenAIBackend.summarize failed: {exc}", stacklevel=2)
            raise

    def deduplicate(self, turns: list[str]) -> list[int]:
        if len(turns) <= 1:
            return list(range(len(turns)))
        prompt = format_numbered_turns(turns)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": DEDUP_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=128,
                temperature=0,
            )
            content = resp.choices[0].message.content or ""
            return parse_keep_indices(content, len(turns))
        except Exception as exc:
            warnings.warn(f"contextpress OpenAIBackend.deduplicate failed: {exc}", stacklevel=2)
            return list(range(len(turns)))


class AnthropicBackend(LLMBackend):
    """
    Adapter for Anthropic Claude APIs.
    Requires: pip install anthropic
    User must pass their own client instance.

    Usage:
        import anthropic
        from contextpress.llm.adapters import AnthropicBackend

        backend = AnthropicBackend(client=anthropic.Anthropic(), model="claude-haiku-4-5")
        cm = ContextManager(type="chat", llm_backend=backend)
    """

    def __init__(self, client: Any, model: str = "claude-haiku-4-5"):
        self.client = client
        self.model = model

    def summarize(self, text: str, max_tokens: int) -> str:
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": f"Summarize concisely:\n\n{text}"}],
            )
            parts = []
            for b in msg.content:
                if hasattr(b, "text"):
                    parts.append(b.text)
            return "".join(parts) if parts else text
        except Exception as exc:
            warnings.warn(f"contextpress AnthropicBackend.summarize failed: {exc}", stacklevel=2)
            raise

    def deduplicate(self, turns: list[str]) -> list[int]:
        if len(turns) <= 1:
            return list(range(len(turns)))
        prompt = format_numbered_turns(turns)
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=128,
                system=DEDUP_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = []
            for b in msg.content:
                if hasattr(b, "text"):
                    parts.append(b.text)
            return parse_keep_indices("".join(parts), len(turns))
        except Exception as exc:
            warnings.warn(f"contextpress AnthropicBackend.deduplicate failed: {exc}", stacklevel=2)
            return list(range(len(turns)))


class OllamaBackend(LLMBackend):
    """
    Adapter for **Ollama** (local or remote) using the official ``ollama`` Python library.

    Requires: ``pip install ollama``

    Ollama must be installed and running (see https://ollama.com). Pull a model first, e.g.::

        ollama pull llama3.2

    Usage::

        from contextpress import ContextManager
        from contextpress.llm.adapters import OllamaBackend

        backend = OllamaBackend(model="llama3.2")
        cm = ContextManager(type="chat", llm_backend=backend, llm_min_input_chars=500)

    Remote server::

        backend = OllamaBackend(model="mistral", host="http://192.168.1.10:11434")

    Custom client (advanced)::

        from ollama import Client
        backend = OllamaBackend(client=Client(host="http://localhost:11434"), model="llama3.2")
    """

    def __init__(
        self,
        model: str = "llama3.2",
        *,
        host: str | None = None,
        client: Any | None = None,
    ):
        self.model = model
        if client is not None:
            self._client = client
            return
        try:
            from ollama import Client as OllamaClient
        except ImportError as exc:
            raise ImportError(
                "OllamaBackend requires the 'ollama' package. Install with: pip install ollama"
            ) from exc
        self._client = OllamaClient(host=host) if host else OllamaClient()

    def summarize(self, text: str, max_tokens: int) -> str:
        try:
            resp = self._client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Summarize the following conversation transcript concisely. "
                            "Preserve important facts, names, and decisions."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                options={"num_predict": max(64, int(max_tokens))},
            )
            content = _ollama_response_text(resp)
            return content if content.strip() else text
        except Exception as exc:
            warnings.warn(f"contextpress OllamaBackend.summarize failed: {exc}", stacklevel=2)
            raise

    def deduplicate(self, turns: list[str]) -> list[int]:
        if len(turns) <= 1:
            return list(range(len(turns)))
        prompt = format_numbered_turns(turns)
        try:
            resp = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": DEDUP_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                options={"num_predict": 128, "temperature": 0},
            )
            return parse_keep_indices(_ollama_response_text(resp), len(turns))
        except Exception as exc:
            warnings.warn(f"contextpress OllamaBackend.deduplicate failed: {exc}", stacklevel=2)
            return list(range(len(turns)))
