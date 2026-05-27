"""
Quick demo: long chat + tight token budget so compression is obvious.

Uses default compression **medium** (filler, repetition, recency) plus **budget**
because ``token_budget`` is set.

Run from the repo root after `pip install -e .`:
    python try_compress.py
"""

import tiktoken

from contextpress import ContextManager

enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: list) -> int:
    n = 0
    for m in messages:
        body = m["content"] if isinstance(m["content"], str) else str(m["content"])
        n += len(enc.encode(f"{m['role']}\n{body}"))
    return n


# Long history + filler words + a short recent exchange (kept toward the end)
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Old question: " + "blah " * 300},
    {
        "role": "assistant",
        "content": "Basically, honestly, we should just say: " + "yak " * 300,
    },
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "Four."},
]

# Default compression="medium" (filler, repetition, recency). Use compression="low"
# for less work, or "high" to also allow resolution. token_budget=... turns on budget.
cm = ContextManager(type="chat", compression="medium")
budget = 120  # tight — forces dropping early turns after other stages

before = count_tokens(messages)
out = cm.compress(messages, token_budget=budget)
after = count_tokens(out)

print("turns:", len(messages), "->", len(out))
print("tokens (approx.):", before, "->", after, "(budget", budget, ")")
for i, m in enumerate(out):
    preview = m["content"] if isinstance(m["content"], str) else str(m["content"])
    if len(preview) > 80:
        preview = preview[:77] + "..."
    print(i, m["role"] + ":", preview)
