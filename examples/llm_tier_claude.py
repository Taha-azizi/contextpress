"""
Tier 2 compression with Anthropic Claude.

Requires ``pip install anthropic`` and ``ANTHROPIC_API_KEY``.

Run:
    set ANTHROPIC_API_KEY=sk-ant-...   # Windows
    python examples/llm_tier_claude.py
"""

from __future__ import annotations

import os
import sys

from contextpress import ContextManager
from contextpress.llm.adapters import ClaudeBackend


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run this example.", file=sys.stderr)
        sys.exit(1)

    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is Python? " + ("Explain briefly. " * 200)},
        {"role": "assistant", "content": "Python is a programming language. " * 150},
        {"role": "user", "content": "And numpy? " * 80},
    ]

    backend = ClaudeBackend(model="claude-haiku-4-5")
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
