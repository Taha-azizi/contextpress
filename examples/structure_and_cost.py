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

cm = ContextManager(
    type="agent",
    model="gpt-4o-mini",
    compression="medium",
    cost_provider="openai",
)
before = cm.estimate_tokens(messages)
result = cm.compress(messages, token_budget=None, return_stats=True)
stats = result.stats

print("tokens:", before, "->", stats.tokens_after)
print(
    "est. input USD:",
    f"{stats.estimated_input_cost_before_usd:.6f}",
    "->",
    f"{stats.estimated_input_cost_after_usd:.6f}",
    f"(saved {stats.estimated_cost_saved_usd:.6f})",
)
print("stages:", stats.stages_run)
print("user content:", result.messages[1]["content"][:80])
