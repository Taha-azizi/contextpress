"""
Tier 2 (LLM) compression example — requires ``pip install openai`` and ``OPENAI_API_KEY``.

Flow:
1. Tier 1 runs first (filler, repetition, … per your compression preset).
2. Non-system turns are optionally deduplicated via ``LLMBackend.deduplicate``.
3. The remaining transcript is summarized; **system turns stay as-is**, then one
   **assistant** turn holds the summary (output shape changes for non-system messages).

Run:
 set OPENAI_API_KEY=... # Windows: set OPENAI_API_KEY=sk-...
    python examples/llm_tier_openai.py
"""

from __future__ import annotations

import os
import sys

from openai import OpenAI

from contextpress import ContextManager
from contextpress.llm.adapters import OpenAIBackend


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run this example.", file=sys.stderr)
        sys.exit(1)

    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is Python? " + ("Explain briefly. " * 200)},
        {"role": "assistant", "content": "Python is a programming language. " *150},
        {"role": "user", "content": "And numpy? " * 80},
    ]

    backend = OpenAIBackend(client=OpenAI(), model="gpt-4o-mini")
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
