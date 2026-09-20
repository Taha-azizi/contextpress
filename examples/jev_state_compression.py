"""Compress agent state before input-metered decision-model calls.

Decision APIs (e.g. TypeSafe Jev) bill per token of serialized conversation state.
Run deterministic Tier 1 compression locally, then send ``result.messages`` to the API.

Run::

    python examples/jev_state_compression.py
"""

from __future__ import annotations

import json

from contextpress import ContextManager

# Noisy agent thread: verbose system prompt, tool JSON, filler-heavy assistant turns.
tool_payload = {
    "tool": "list_incidents",
    "service": "payments-api",
    "environment": "production",
    "incidents": [
        {
            "id": f"inc-{i:04d}",
            "severity": "high" if i % 3 == 0 else "medium",
            "summary": (
                "In order to investigate the elevated error rate, we observed "
                "that the deployment rollout was partially complete."
            ),
            "details": {"region": "us-east-1", "replicas": 6, "error_pct": 2.1 + i * 0.1},
        }
        for i in range(10)
    ],
    "meta": {"query_ms": 142, "truncated": False, "cache_hit": False},
}

messages = [
    {
        "role": "system",
        "content": (
            "You are an on-call agent. In order to respond effectively, you must "
            "utilize the available tools and preserve important facts and decisions."
        ),
    },
    {"role": "user", "content": "What is the current incident status for payments-api in prod?"},
    {
        "role": "assistant",
        "content": (
            "Basically, I will fetch recent incidents. "
            "<tool_call> list_incidents(payments-api, production)"
        ),
    },
    {"role": "user", "content": "Tool result:\n" + json.dumps(tool_payload, indent=2)},
    {
        "role": "assistant",
        "content": (
            "Honestly, there are several open incidents; the most recent high-severity "
            "one looks related to the partial rollout. I recommend paging the owner."
        ),
    },
    {"role": "user", "content": "Should we roll back the latest deploy?"},
]

TOKEN_BUDGET = 1200

cm = ContextManager(type="agent", compression="low", model="gpt-4o-mini")
tokens_before = cm.estimate_tokens(messages)

result = cm.compress(messages, token_budget=TOKEN_BUDGET, return_stats=True)
tokens_after = result.stats.tokens_after

print("Serialized state for the decision API should be result.messages (not the raw thread).")
print()
print("token estimate (tiktoken):", tokens_before, "->", tokens_after)
print(
    "saved:",
    result.stats.tokens_saved,
    f"({result.stats.token_savings_pct:.1f}%)" if result.stats.token_savings_pct else "",
)
print("stages:", result.stats.stages_run)
print("turns:", result.stats.turns_before, "->", result.stats.turns_after)
print()
print("Pass this payload to Jev / other input-metered decision models:")
print(json.dumps(result.messages, indent=2)[:500], "...")
