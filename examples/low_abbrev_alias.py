"""Low-preset wording compression: filler, abbrev, and alias (0.6.10+).

Run::

    python examples/low_abbrev_alias.py
"""

from __future__ import annotations

from contextpress import ContextManager

messages = [
    {
        "role": "system",
        "content": "You help engineers adopt Context Press in production.",
    },
    {
        "role": "user",
        "content": (
            "Due to the fact that we need fewer tokens, should we use Context Press? "
            "Basically I think that Context Press could help."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Yes. Context Press is deterministic Tier-1 compression. "
            "In order to ship sooner, start with the low preset."
        ),
    },
    {
        "role": "user",
        "content": "Does Context Press keep tool JSON intact?",
    },
    {
        "role": "assistant",
        "content": "Context Press skips JSON blobs and tool turns in lexical/abbrev/alias.",
    },
]

cm = ContextManager(type="chat", model="gpt-4o-mini", compression="low")
before = cm.estimate_tokens(messages)
result = cm.compress(messages, token_budget=None, return_stats=True)

print(result.summary())
print("tokens:", before, "->", result.stats.tokens_after)
print("stages:", result.stats.stages_run)
print("--- compressed user/assistant turns ---")
for m in result.messages:
    if m["role"] == "system":
        continue
    print(f"{m['role']}: {m['content']}")
