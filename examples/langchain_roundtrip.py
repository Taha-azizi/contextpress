"""LangChain-style objects round-trip through compress() (0.6.3+).

Uses duck-typed message objects (``.type`` / ``.content``), so no LangChain
install is required. Real ``HumanMessage`` / ``AIMessage`` lists work the same way.
"""

from __future__ import annotations

from contextpress import ContextManager


class Msg:
    def __init__(self, typ: str, content: str):
        self.type = typ
        self.content = content


messages = [
    Msg("system", "You are a concise assistant."),
    Msg("human", "We've decided on using the new pipeline. Basically just confirm."),
    Msg("ai", "Sounds good"),
    Msg("human", "Schedule the api-v2 staging deploy for Monday."),
    Msg("ai", "Confirmed. Monday staging deploy is scheduled."),
]

cm = ContextManager(
    type="chat",
    model="gpt-4o-mini",
    compression="high",
    cost_provider="openai",
    cost_output_tokens=150,
)
result = cm.compress(messages, token_budget=None, return_stats=True)

print(result.summary())
print()
for m in result.messages:
    preview = str(m.content)[:80]
    print(f"{m.type}: {preview}")
