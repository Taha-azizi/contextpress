# Offline chat fixtures (Phase 3)

Synthetic conversations inspired by public chat / RAG / agent patterns.
No network required — used by `tests/test_fixture_chats.py`.

| File | Profile | Focus |
|------|---------|--------|
| `01_filler_heavy.json` | chat | Filler phrases |
| `02_resolution_thread.json` | chat | Agreement / RESOLVED |
| `03_repetition.json` | chat | Near-duplicate turns |
| `04_long_history.json` | chat | Long multi-topic history |
| `05_agent_tools.json` | agent | Tool markers |
| `06_rag_chunks.json` | rag_doc | Chunk + query |
| `07_short_stable.json` | chat | Minimal change |
| `08_mixed_ack_resolution.json` | chat | Ack vs resolution (AUDIT C3) |
