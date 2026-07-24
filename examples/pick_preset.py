"""Pick the mildest compression preset that fits a token budget (dry run)."""

from contextpress import ContextManager

messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Old topic: " + "blah " * 40},
    {"role": "assistant", "content": "Basically, honestly, " + "yak " * 40},
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "Four."},
]

cm = ContextManager(type="chat")
budget = 200
preset = cm.recommend_preset(messages, token_budget=budget)
stats = cm.compare_presets(messages, token_budget=budget)[preset]

print(f"budget={budget}  recommended preset={preset!r}")
print(
    f"  tokens {stats.tokens_before}->{stats.tokens_after} " f"({stats.token_savings_pct}% saved)"
)
