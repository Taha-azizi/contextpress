import os
from unittest.mock import MagicMock, patch

import pytest

from contextpress.llm.adapters import OpenAIBackend


def test_openai_backend_with_client():
    client = MagicMock()
    backend = OpenAIBackend(client=client, model="gpt-4o-mini")
    assert backend.client is client
    assert backend.model == "gpt-4o-mini"


def test_openai_backend_requires_api_key():
    mock_openai = MagicMock()
    with patch.dict(os.environ, {}, clear=True):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIBackend()


def test_openai_backend_from_api_key():
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_module.OpenAI.return_value = mock_client
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        with patch.dict("sys.modules", {"openai": mock_module}):
            backend = OpenAIBackend(model="gpt-4o-mini")
    assert backend.client is mock_client
    mock_module.OpenAI.assert_called_once_with(api_key="sk-test")
