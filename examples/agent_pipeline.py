"""Agent thread compression — ``type=\"agent\"`` for tool-using pipelines."""

from __future__ import annotations

from contextpress import ContextManager

messages = [
    {"role": "system", "content": "You are a task agent with tools."},
    {"role": "user", "content": "Check whether api-v2 is deployed to staging."},
    {
        "role": "assistant",
        "content": "Checking deploy status <tool_call> get_deploy_status(api-v2)",
    },
    {"role": "user", "content": "We've decided on using the new pipeline for deploy."},
    {"role": "assistant", "content": "Confirmed — staging deploy is scheduled."},
    {"role": "user", "content": "What's the current status?"},
    {"role": "assistant", "content": "Basically, honestly, " + "still rolling out " * 30},
]

cm = ContextManager(type="agent", compression="high")
result = cm.compress(messages, token_budget=300, return_stats=True)

print("context type:", result.stats.context_type)
print("turns:", result.stats.turns_before, "->", result.stats.turns_after)
print("tokens:", result.stats.tokens_before, "->", result.stats.tokens_after)
print("stages:", result.stats.stages_run)
for i, m in enumerate(result.messages):
    preview = str(m.get("content", ""))[:120]
    print(i, m["role"] + ":", preview)
