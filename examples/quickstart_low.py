"""README-style low-preset wording example.

Run::

    python examples/quickstart_low.py
"""

from __future__ import annotations

from contextpress import ContextManager

SAMPLE = (
    "In order to utilize the API effectively, due to the fact that rate limits "
    "apply, we should implement caching for the application programming "
    "interface calls we make on a daily basis."
)

cm = ContextManager(type="chat", compression="low")
result = cm.compress(
    [{"role": "user", "content": SAMPLE}],
    token_budget=None,
    return_stats=True,
)

print("before:", SAMPLE)
print("after: ", result.messages[0]["content"])
print("stages:", result.stats.stages_run)
print("token_savings_pct:", result.stats.token_savings_pct)
