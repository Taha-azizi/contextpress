"""Structure compaction + approximate USD cost (0.6+)."""

from __future__ import annotations

import json

from contextpress import ContextManager

payload = {
    "tool": "search",
    "results": [{"id": i, "text": f"hit {i}"} for i in range(5)],
    "meta": {"ok": True, "retries": 0},
}

messages = [
    {"role": "system", "content": "You are a concise agent."},
    {"role": "user", "content": json.dumps(payload, indent=2)},
    {"role": "assistant", "content": "line\nline\nline\nnext"},
]

cm = ContextManager(type="agent", model="gpt-4o-mini", compression="medium")
before = cm.estimate_tokens(messages)
before_cost = cm.estimate_cost(messages, provider="openai")
result = cm.compress(messages, token_budget=None, return_stats=True)
after_cost = cm.estimate_cost(result.messages, provider="openai")

print("tokens:", before, "->", result.stats.tokens_after)
print(
    "est. input USD:",
    f"{before_cost.input_cost_usd:.6f}",
    "->",
    f"{after_cost.input_cost_usd:.6f}",
)
print("stages:", result.stats.stages_run)
print("user content:", result.messages[1]["content"][:80])
