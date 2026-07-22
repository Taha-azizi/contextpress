from __future__ import annotations

import os
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
    Adapter for **OpenAI** chat APIs.

    Requires: ``pip install openai``

    Usage (API key from env ``OPENAI_API_KEY`` or ``api_key=``)::

        from contextpress.llm.adapters import OpenAIBackend

        backend = OpenAIBackend(model=\"gpt-4o-mini\")
        cm = ContextManager(type=\"chat\", llm_backend=backend)

    Or pass your own client::

        from openai import OpenAI

        backend = OpenAIBackend(client=OpenAI(), model=\"gpt-4o-mini\")
    """

    def __init__(
        self,
        client: Any | None = None,
        model: str = "gpt-4o-mini",
        *,
        api_key: str | None = None,
    ):
        if client is not None:
            self.client = client
            self.model = model
            return
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "OpenAIBackend requires the 'openai' package. " "Install with: pip install openai"
            ) from exc
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("Set OPENAI_API_KEY or pass api_key= for OpenAIBackend")
        self.client = OpenAI(api_key=key)
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


class ClaudeBackend(AnthropicBackend):
    """
    Convenience adapter for **Anthropic Claude** (wraps ``AnthropicBackend``).

    Requires: ``pip install anthropic``

    Usage::

        from contextpress.llm.adapters import ClaudeBackend

        backend = ClaudeBackend(model=\"claude-haiku-4-5\")  # uses ANTHROPIC_API_KEY
        cm = ContextManager(type=\"chat\", llm_backend=backend)
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5",
        *,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        if client is not None:
            super().__init__(client=client, model=model)
            return
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "ClaudeBackend requires the 'anthropic' package. "
                "Install with: pip install anthropic"
            ) from exc
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Set ANTHROPIC_API_KEY or pass api_key= for ClaudeBackend")
        super().__init__(client=anthropic.Anthropic(api_key=key), model=model)


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


class OpenAICompatibleBackend(OpenAIBackend):
    """
    Adapter for **OpenAI-compatible HTTP APIs** (vLLM, LM Studio, LocalAI, etc.).

    Requires: ``pip install openai``

    Usage::

        from contextpress.llm.adapters import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(
            base_url="http://localhost:8000/v1",
            model="mistral",
        )
        cm = ContextManager(type="chat", llm_backend=backend)
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str = "not-needed",
        client: Any | None = None,
    ):
        if client is not None:
            super().__init__(client=client, model=model)
            return
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "OpenAICompatibleBackend requires the 'openai' package. "
                "Install with: pip install openai"
            ) from exc
        super().__init__(
            client=OpenAI(base_url=base_url, api_key=api_key),
            model=model,
        )


class GeminiBackend(LLMBackend):
    """
    Adapter for Google Gemini via ``google-generativeai``.

    Requires: ``pip install google-generativeai``

    Usage (API key from env ``GOOGLE_API_KEY`` or ``GEMINI_API_KEY``)::

        from contextpress.llm.adapters import GeminiBackend

        backend = GeminiBackend(model_name=\"gemini-2.0-flash\")
        cm = ContextManager(type=\"chat\", llm_backend=backend)

    Or pass a preconfigured model instance::

        import google.generativeai as genai
        genai.configure(api_key=\"...\")
        backend = GeminiBackend(model=genai.GenerativeModel(\"gemini-2.0-flash\"))
    """

    def __init__(
        self,
        model: Any | None = None,
        *,
        model_name: str = "gemini-2.0-flash",
        api_key: str | None = None,
    ):
        if model is not None:
            self.model = model
            return
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "GeminiBackend requires 'google-generativeai'. "
                "Install with: pip install google-generativeai"
            ) from exc
        key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if key:
            genai.configure(api_key=key)
        self.model = genai.GenerativeModel(model_name)

    def _generate(self, prompt: str, *, max_tokens: int) -> str:
        resp = self.model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max(64, int(max_tokens))},
        )
        text = getattr(resp, "text", None)
        return str(text).strip() if text else ""

    def summarize(self, text: str, max_tokens: int) -> str:
        try:
            out = self._generate(f"Summarize concisely:\n\n{text}", max_tokens=max_tokens)
            return out if out else text
        except Exception as exc:
            warnings.warn(f"contextpress GeminiBackend.summarize failed: {exc}", stacklevel=2)
            raise

    def deduplicate(self, turns: list[str]) -> list[int]:
        if len(turns) <= 1:
            return list(range(len(turns)))
        prompt = f"{DEDUP_SYSTEM_PROMPT}\n\n{format_numbered_turns(turns)}"
        try:
            out = self._generate(prompt, max_tokens=128)
            return parse_keep_indices(out, len(turns))
        except Exception as exc:
            warnings.warn(f"contextpress GeminiBackend.deduplicate failed: {exc}", stacklevel=2)
            return list(range(len(turns)))
