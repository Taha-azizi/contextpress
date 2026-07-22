import os
from unittest.mock import MagicMock, patch

import pytest

from contextpress.llm.adapters import ClaudeBackend, GeminiBackend


def test_claude_backend_with_client():
    client = MagicMock()
    backend = ClaudeBackend(model="claude-haiku-4-5", client=client)
    assert backend.client is client
    assert backend.model == "claude-haiku-4-5"


def test_claude_backend_requires_api_key():
    mock_anthropic = MagicMock()
    with patch.dict(os.environ, {}, clear=True):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                ClaudeBackend()


def test_claude_backend_from_api_key():
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_module.Anthropic.return_value = mock_client
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        with patch.dict("sys.modules", {"anthropic": mock_module}):
            backend = ClaudeBackend(model="claude-haiku-4-5")
    assert backend.client is mock_client


def test_gemini_backend_with_model_instance():
    model = MagicMock()
    backend = GeminiBackend(model=model)
    assert backend.model is model


def test_gemini_backend_from_model_name():
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    fake_google = MagicMock()
    fake_google.generativeai = mock_genai
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "key-test"}):
        with patch.dict("sys.modules", {"google": fake_google, "google.generativeai": mock_genai}):
            backend = GeminiBackend(model_name="gemini-2.0-flash")
    assert backend.model is mock_model
    mock_genai.configure.assert_called_once_with(api_key="key-test")
