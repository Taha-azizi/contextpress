"""Agent JSON compression + readable savings report (0.6.2+)."""

from __future__ import annotations

import json

from contextpress import ContextManager

payload = {
    "tool": "search_deploys",
    "service": "api-v2",
    "environment": "staging",
    "events": [
        {
            "id": f"evt-{i:03d}",
            "version": f"2.4.{i % 3}",
            "status": "healthy" if i % 2 else "superseded",
            "details": {"replicas": 3, "region": "us-east-1"},
        }
        for i in range(12)
    ],
    "meta": {"query_ms": 38, "truncated": False},
}

messages = [
    {"role": "system", "content": "You are a deploy agent with tools."},
    {"role": "user", "content": "Summarize recent staging deploys for api-v2."},
    {
        "role": "assistant",
        "content": "Fetching deploy history <tool_call> search_deploys(api-v2, staging)",
    },
    {"role": "user", "content": "Tool result:\n" + json.dumps(payload, indent=2)},
    {"role": "assistant", "content": "Staging has multiple recent releases; latest is healthy."},
]

cm = ContextManager(
    type="agent",
    model="gpt-4o-mini",
    compression="medium",
    cost_provider="openai",
)
result = cm.compress(messages, token_budget=None, return_stats=True)

print(result.summary())
print()
print("tool result preview:", result.messages[3]["content"][:120], "...")
