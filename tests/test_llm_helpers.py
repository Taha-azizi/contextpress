from unittest.mock import MagicMock

import pytest

from contextpress.llm._helpers import parse_keep_indices
from contextpress.llm.adapters import AnthropicBackend, OllamaBackend, OpenAIBackend


def test_parse_keep_indices_comma_separated():
    assert parse_keep_indices("0, 2, 4", 6) == [0, 2, 4]


def test_parse_keep_indices_json_array():
    assert parse_keep_indices("[1, 3]", 4) == [1, 3]


def test_parse_keep_indices_empty_falls_back_to_all():
    assert parse_keep_indices("", 3) == [0, 1, 2]


def test_parse_keep_indices_invalid_falls_back_to_all():
    assert parse_keep_indices("keep everything please", 2) == [0, 1]


def test_openai_deduplicate_parses_response():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="0, 2"))]
    )
    b = OpenAIBackend(client=client)
    assert b.deduplicate(["a", "b", "c", "d"]) == [0, 2]
    client.chat.completions.create.assert_called_once()


def test_openai_deduplicate_single_turn_skips_llm():
    client = MagicMock()
    b = OpenAIBackend(client=client)
    assert b.deduplicate(["only one"]) == [0]
    client.chat.completions.create.assert_not_called()


def test_openai_deduplicate_error_keeps_all():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network")
    b = OpenAIBackend(client=client)
    with pytest.warns(UserWarning):
        assert b.deduplicate(["a", "b", "c"]) == [0, 1, 2]


def test_anthropic_deduplicate_parses_response():
    client = MagicMock()
    block = MagicMock()
    block.text = "0,1"
    msg = MagicMock()
    msg.content = [block]
    client.messages.create.return_value = msg
    b = AnthropicBackend(client=client)
    assert b.deduplicate(["x", "y", "z"]) == [0, 1]


def test_ollama_deduplicate_parses_response():
    client = MagicMock()
    client.chat.return_value = {"message": {"content": "0, 2"}}
    b = OllamaBackend(client=client, model="llama3.2")
    assert b.deduplicate(["a", "b", "c"]) == [0, 2]
