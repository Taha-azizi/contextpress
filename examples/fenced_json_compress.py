"""Minify JSON inside markdown fences (0.6.5+)."""

from __future__ import annotations

import json

from contextpress import ContextManager

payload = {
    "service": "api-v2",
    "environment": "staging",
    "events": [{"id": f"evt-{i:03d}", "version": f"2.4.{i % 3}"} for i in range(8)],
}

messages = [
    {"role": "system", "content": "Answer using the provided document chunks."},
    {
        "role": "user",
        "content": "Chunk:\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n",
    },
    {"role": "user", "content": "Which versions appear in the deploy index?"},
]

cm = ContextManager(type="rag_doc", compression="medium")
result = cm.compress(messages, token_budget=None, return_stats=True)
print(result.summary())
print()
print(result.messages[1]["content"])
