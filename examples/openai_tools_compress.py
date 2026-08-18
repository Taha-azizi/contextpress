"""OpenAI Chat Completions tool_calls round-trip (0.6.4+)."""

from __future__ import annotations

import json

from contextpress import ContextManager

arguments = json.dumps(
    {"service": "api-v2", "environment": "staging", "limit": 20},
    indent=2,
)
tool_result = json.dumps(
    {
        "service": "api-v2",
        "events": [{"id": "evt-001", "version": "2.4.1", "status": "healthy"}],
    },
    indent=2,
)

messages = [
    {"role": "system", "content": "You are a deploy agent with function tools."},
    {"role": "user", "content": "Find recent staging deploys for api-v2."},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_search_1",
                "type": "function",
                "function": {"name": "search_deploys", "arguments": arguments},
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_search_1",
        "name": "search_deploys",
        "content": tool_result,
    },
    {"role": "assistant", "content": "Staging is healthy on 2.4.1."},
]

cm = ContextManager(type="agent", compression="medium", cost_provider="openai")
result = cm.compress(messages, token_budget=None, return_stats=True)

print(result.summary())
print()
for m in result.messages:
    role = m["role"]
    if m.get("tool_calls"):
        args = m["tool_calls"][0]["function"]["arguments"]
        print(f"{role} tool_calls arguments:", args[:80])
    elif role == "tool":
        print(f"{role} ({m.get('tool_call_id')}):", str(m.get("content", ""))[:80])
    else:
        print(f"{role}:", str(m.get("content", ""))[:80])
