import asyncio
from unittest.mock import MagicMock

from contextpress import ContextManager
from contextpress.llm.adapters import GeminiBackend
from contextpress.stats import CompressionStats


def test_stats_to_dict():
    stats = CompressionStats(
        turns_before=5,
        turns_after=3,
        tokens_before=100,
        tokens_after=60,
        stages_run=["filler", "budget"],
        compression_level="medium",
    )
    d = stats.to_dict()
    assert d["turns_removed"] == 2
    assert d["tokens_saved"] == 40
    assert d["stages_run"] == ["filler", "budget"]


def test_result_to_dict():
    cm = ContextManager()
    result = cm.preview([{"role": "user", "content": "hello basically"}], token_budget=100)
    d = result.to_dict()
    assert "stats" in d and "messages" in d
    assert d["stats"]["dry_run"] is True


def test_compare_presets():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "user", "content": "hello basically there"},
        {"role": "assistant", "content": "sounds good"},
    ]
    rows = cm.compare_presets(messages, token_budget=500)
    assert set(rows) == {"low", "medium", "high"}
    assert all(isinstance(v, CompressionStats) for v in rows.values())


def test_compress_async():
    async def _run() -> list:
        cm = ContextManager(type="chat")
        return await cm.compress_async(
            [{"role": "user", "content": "hello basically"}],
            token_budget=200,
        )

    out = asyncio.run(_run())
    assert isinstance(out, list)


def test_gemini_backend_summarize():
    model = MagicMock()
    model.generate_content.return_value = MagicMock(text="summary")
    backend = GeminiBackend(model=model)
    assert backend.summarize("long text", 50) == "summary"


def test_gemini_backend_deduplicate():
    model = MagicMock()
    model.generate_content.return_value = MagicMock(text="0, 2")
    backend = GeminiBackend(model=model)
    assert backend.deduplicate(["a", "b", "c", "d"]) == [0, 2]
