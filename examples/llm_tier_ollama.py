"""
Tier 2 compression using **local Ollama** (no OpenAI/Anthropic API key).

Prerequisites:
  - Install Ollama: https://ollama.com
  - Start the daemon (usually automatic after install) or: ``ollama serve``
  - Pull a model: ``ollama pull llama3.2``  (or change ``MODEL`` below)

Then::

  pip install ollama
  python examples/llm_tier_ollama.py

Optional: set ``OLLAMA_HOST`` if Ollama runs elsewhere (default http://127.0.0.1:11434).
"""

from __future__ import annotations

import os

from contextpress import ContextManager
from contextpress.llm.adapters import OllamaBackend

# Match a model you have pulled: `ollama list`
MODEL = os.environ.get("CONTEXTPRESS_OLLAMA_MODEL", "llama3.2")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST")  # e.g. http://192.168.1.5:11434


def main() -> None:
    kwargs = {"model": MODEL}
    if OLLAMA_HOST:
        kwargs["host"] = OLLAMA_HOST

    backend = OllamaBackend(**kwargs)
    cm = ContextManager(
        type="chat",
        llm_backend=backend,
        compression="medium",
        llm_min_input_chars=400,
        llm_max_summary_tokens=512,
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python? " + ("Briefly. " * 120)},
        {"role": "assistant", "content": "Python is a high-level language. " * 80},
        {"role": "user", "content": "And pip? " * 60},
    ]

    out = cm.compress(messages, token_budget=2500)
    print("turns in:", len(messages), "out:", len(out))
    for i, m in enumerate(out):
        c = m["content"]
        preview = (c[:300] + "…") if isinstance(c, str) and len(c) > 300 else c
        print(i, m["role"] + ":", preview)


if __name__ == "__main__":
    main()
