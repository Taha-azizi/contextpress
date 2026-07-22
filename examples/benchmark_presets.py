"""Compare compression presets on the same fixture (dry run)."""

from contextpress import ContextManager

messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Old topic: " + "blah " * 40},
    {"role": "assistant", "content": "Basically, honestly, " + "yak " * 40},
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "Four."},
]

cm = ContextManager(type="chat")
rows = cm.compare_presets(messages, token_budget=200)

print(f"{'preset':<8} {'tokens':>12} {'saved':>8} {'turns':>12}")
for preset, stats in rows.items():
    print(
        f"{preset:<8} "
        f"{stats.tokens_before:>5}->{stats.tokens_after:<5} "
        f"{stats.tokens_saved:>8} "
        f"{stats.turns_before:>5}->{stats.turns_after:<5}"
    )
