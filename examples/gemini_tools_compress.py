"""Gemini functionCall / functionResponse parts round-trip (0.6.8+)."""

from __future__ import annotations

import json

from contextpress import ContextManager

response = json.dumps(
    {
        "service": "api-v2",
        "events": [{"id": "evt-001", "version": "2.4.1", "status": "healthy"}],
    },
    indent=2,
)

messages = [
    {"role": "user", "parts": [{"text": "Find recent staging deploys for api-v2."}]},
    {
        "role": "model",
        "parts": [
            {
                "functionCall": {
                    "id": "fc_1",
                    "name": "search_deploys",
                    "args": {"service": "api-v2", "environment": "staging"},
                },
                "thought_signature": "sig-demo",
            }
        ],
    },
    {
        "role": "user",
        "parts": [
            {
                "functionResponse": {
                    "id": "fc_1",
                    "name": "search_deploys",
                    "response": response,
                }
            }
        ],
    },
    {"role": "model", "parts": [{"text": "Staging is healthy on 2.4.1."}]},
]

cm = ContextManager(type="agent", compression="medium", cost_provider="google")
result = cm.compress(messages, token_budget=None, return_stats=True)
print(result.summary())
print()
for m in result.messages:
    parts = m.get("parts") or []
    print(m["role"], [list(p.keys()) for p in parts])
    for p in parts:
        if "functionCall" in p:
            print("  thought_signature:", p.get("thought_signature"))
            print("  functionCall:", p["functionCall"])
        if "functionResponse" in p:
            print("  functionResponse:", str(p["functionResponse"].get("response", ""))[:80])
        if "text" in p:
            print("  text:", p["text"][:80])
