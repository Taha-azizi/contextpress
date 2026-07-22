"""
Tier 2 compression with Google Gemini.

Requires ``pip install google-generativeai`` and ``GOOGLE_API_KEY``.

Run:
    set GOOGLE_API_KEY=...   # or GEMINI_API_KEY
    python examples/llm_tier_gemini.py
"""

from __future__ import annotations

import os
import sys

from contextpress import ContextManager
from contextpress.llm.adapters import GeminiBackend


def main() -> None:
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        print("Set GOOGLE_API_KEY or GEMINI_API_KEY to run this example.", file=sys.stderr)
        sys.exit(1)

    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is Python? " + ("Explain briefly. " * 200)},
        {"role": "assistant", "content": "Python is a programming language. " * 150},
        {"role": "user", "content": "And numpy? " * 80},
    ]

    backend = GeminiBackend(model_name="gemini-2.0-flash")
    cm = ContextManager(
        type="chat",
        llm_backend=backend,
        compression="medium",
        llm_min_input_chars=500,
        llm_max_summary_tokens=512,
    )

    out = cm.compress(messages, token_budget=2000)
    print("turns in:", len(messages), "out:", len(out))
    for i, m in enumerate(out):
        c = m["content"]
        preview = (c[:200] + "…") if isinstance(c, str) and len(c) > 200 else c
        print(i, m["role"] + ":", preview)


if __name__ == "__main__":
    main()
