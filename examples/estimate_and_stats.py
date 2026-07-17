"""Estimate tokens before compressing, then inspect stats after."""

from contextpress import ContextManager

messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Old topic: " + "blah " * 50},
    {"role": "assistant", "content": "Basically, honestly, " + "yak " * 50},
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "Four."},
]

cm = ContextManager(type="chat", compression="medium")
before = cm.estimate_tokens(messages)
print("tokens before:", before)

result = cm.compress(messages, token_budget=200, return_stats=True)
print("tokens after:", result.stats.tokens_after)
print("saved:", result.stats.tokens_saved)
print("stages:", result.stats.stages_run)
print("turns:", result.stats.turns_before, "->", result.stats.turns_after)
