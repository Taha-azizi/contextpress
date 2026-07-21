from unittest.mock import MagicMock

from contextpress import ContextManager
from contextpress.llm.adapters import OpenAICompatibleBackend


def test_preview_returns_original_messages():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "user", "content": "hello basically there"},
        {"role": "assistant", "content": "hi"},
    ]
    preview = cm.preview(messages, token_budget=500)
    assert preview.messages == messages
    assert preview.stats.dry_run is True
    assert preview.stats.tokens_before >= preview.stats.tokens_after


def test_dry_run_skips_llm_backend():
    backend = MagicMock()
    cm = ContextManager(type="chat", llm_backend=backend, llm_min_input_chars=0)
    messages = [{"role": "user", "content": "hello " * 500}]
    preview = cm.preview(messages, token_budget=100)
    backend.deduplicate.assert_not_called()
    backend.summarize.assert_not_called()
    assert preview.stats.llm_tier_applied is False


def test_fits_budget():
    cm = ContextManager(type="chat", compression="low")
    messages = [{"role": "user", "content": "short"}]
    assert cm.fits_budget(messages, 500) is True


def test_warnings_captured_on_budget_truncation():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "user", "content": "word " * 200},
        {"role": "assistant", "content": "reply " * 200},
        {"role": "user", "content": "recent"},
        {"role": "assistant", "content": "ok"},
    ]
    preview = cm.preview(messages, token_budget=20, compression="low")
    assert any("token budget" in w.lower() for w in preview.stats.warnings_emitted)


def test_openai_compatible_backend_init():
    client = MagicMock()
    backend = OpenAICompatibleBackend(base_url="http://localhost:8000/v1", model="x", client=client)
    assert backend.model == "x"
    assert backend.client is client
