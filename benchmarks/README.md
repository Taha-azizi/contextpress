# Savings brief (local)

Tier-1 only (no LLM). Builds a gitignored corpus of **long chats**, **files
in the prompt**, and **pretty tool JSON**, compresses at `low` / `medium` /
`high`, then writes a marketing brief to `SAVINGS.md`.

Jobs that barely move (2-turn FAQ, already-minified JSON) are measured then
dropped from the story.

```bash
python -m benchmarks.run_savings --rebuild-corpus
```

`benchmarks/data/` is gitignored.
