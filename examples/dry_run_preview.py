"""Dry-run preview: see compression stats without changing messages."""

from __future__ import annotations

from contextpress import ContextManager

messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Old topic: " + "blah " * 60},
    {"role": "assistant", "content": "Basically, honestly, " + "yak " * 60},
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "Four."},
]

cm = ContextManager(type="chat", compression="medium")
preview = cm.preview(messages, token_budget=150)

print("dry_run:", preview.stats.dry_run)
print("tokens:", preview.stats.tokens_before, "->", preview.stats.tokens_after)
print("would fit budget 150:", cm.fits_budget(messages, 150))
print("messages unchanged:", preview.messages == messages)
if preview.stats.warnings_emitted:
    print("warnings:", preview.stats.warnings_emitted)
