"""Anthropic tool_use / tool_result content-block round-trip (0.6.7+)."""

from __future__ import annotations

import json

from contextpress import ContextManager

tool_result = json.dumps(
    {
        "service": "api-v2",
        "events": [{"id": "evt-001", "version": "2.4.1", "status": "healthy"}],
    },
    indent=2,
)

messages = [
    {"role": "system", "content": "You are a deploy agent."},
    {"role": "user", "content": "Find recent staging deploys for api-v2."},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Checking deploys."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "search_deploys",
                "input": {"service": "api-v2", "environment": "staging"},
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": tool_result,
            }
        ],
    },
    {"role": "assistant", "content": "Staging is healthy on 2.4.1."},
]

cm = ContextManager(type="agent", compression="medium", cost_provider="anthropic")
result = cm.compress(messages, token_budget=None, return_stats=True)
print(result.summary())
print()
for m in result.messages:
    content = m.get("content")
    if isinstance(content, list):
        kinds = [p.get("type") for p in content]
        print(f"{m['role']} blocks: {kinds}")
        for p in content:
            if p.get("type") == "tool_result":
                print("  tool_result:", str(p.get("content", ""))[:80])
            if p.get("type") == "tool_use":
                print("  tool_use input:", p.get("input"))
    else:
        print(f"{m['role']}:", str(content)[:80])
