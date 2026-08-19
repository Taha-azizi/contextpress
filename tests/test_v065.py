"""0.6.5 — minify JSON inside markdown code fences."""

from __future__ import annotations

import json
from pathlib import Path

from contextpress import ContextManager
from contextpress.strategies.structure import compact_structure_text

FIXTURE = Path(__file__).parent / "fixtures" / "chats" / "13_rag_fenced_json.json"


def test_fenced_json_minified():
    text = 'payload:\n```json\n{\n  "a": 1,\n  "b": [2, 3]\n}\n```\n'
    out = compact_structure_text(text, aggressiveness=0.5)
    assert '```json\n{"a":1,"b":[2,3]}\n```' in out
    assert '"a": 1' not in out


def test_fenced_json_uppercase_tag():
    text = '```JSON\n{\n  "ok": true\n}\n```'
    out = compact_structure_text(text, aggressiveness=0.5)
    assert out == '```JSON\n{"ok":true}\n```'


def test_bare_fence_json_minified():
    text = '```\n{\n  "x": 1\n}\n```'
    out = compact_structure_text(text, aggressiveness=0.5)
    assert out == '```\n{"x":1}\n```'


def test_python_fence_unchanged():
    text = '```python\nx = {"a": 1}\nprint(x)\n```'
    assert compact_structure_text(text, aggressiveness=0.5) == text


def test_invalid_json_fence_unchanged():
    text = "```json\n{not json, trailing,}\n```"
    assert compact_structure_text(text, aggressiveness=0.5) == text


def test_jsonc_comments_left_alone():
    text = '```jsonc\n{ /* note */ "a": 1 }\n```'
    assert compact_structure_text(text, aggressiveness=0.5) == text


def test_compress_mixed_prose_and_fence_saves_tokens():
    blob = json.dumps({"service": "api-v2", "events": list(range(15))}, indent=2)
    messages = [
        {
            "role": "user",
            "content": f"Use this document:\n\n```json\n{blob}\n```\n\nWhat version is healthy?",
        }
    ]
    cm = ContextManager(type="rag_doc", compression="low")
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert "structure" in result.stats.stages_run
    assert result.stats.tokens_after < result.stats.tokens_before
    assert "```json" in result.messages[0]["content"]
    assert '"service": "api-v2"' not in result.messages[0]["content"]


def test_rag_fenced_json_fixture():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cm = ContextManager(type="rag_doc", compression="medium")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    texts = " ".join(str(m.get("content", "")) for m in result.messages)
    assert "api-v2" in texts
    assert result.stats.tokens_after < result.stats.tokens_before
    fenced = next(m for m in result.messages if "```json" in str(m.get("content", "")))
    assert '"version": "2.4.1"' not in fenced["content"]
