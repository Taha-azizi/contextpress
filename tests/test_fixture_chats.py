"""Smoke + invariant tests over offline chat fixtures (Phase 3)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from contextpress import ContextManager

FIXTURES = sorted(Path(__file__).parent.joinpath("fixtures", "chats").glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_fixture_compress_smoke(path: Path):
    data = _load(path)
    messages = data["messages"]
    cm = ContextManager(type=data.get("type", "chat"), compression="medium")
    result = cm.compress(messages, token_budget=800, return_stats=True)
    assert isinstance(result.messages, list)
    assert result.stats.tokens_after <= result.stats.tokens_before
    assert result.stats.turns_after >= 1 or len(messages) == 0
    assert result.stats.context_type == data.get("type", "chat")


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_fixture_input_immutable(path: Path):
    data = _load(path)
    original = copy.deepcopy(data["messages"])
    messages = copy.deepcopy(data["messages"])
    cm = ContextManager(type=data.get("type", "chat"))
    cm.compress(messages, token_budget=400)
    assert messages == original


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_fixture_preview_unchanged(path: Path):
    data = _load(path)
    messages = data["messages"]
    cm = ContextManager(type=data.get("type", "chat"))
    preview = cm.preview(messages, token_budget=400)
    assert preview.messages == messages
    assert preview.stats.dry_run is True


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_fixture_recommend_preset(path: Path):
    data = _load(path)
    cm = ContextManager(type=data.get("type", "chat"))
    preset = cm.recommend_preset(data["messages"], token_budget=500)
    assert preset in ("low", "medium", "high")


def test_fixture_catalog_not_empty():
    assert len(FIXTURES) >= 15


def test_c3_ack_may_weaken_resolution_signal():
    """Document AUDIT C3: filler can drop ack-only turns before resolution."""
    data = _load(Path(__file__).parent / "fixtures" / "chats" / "08_mixed_ack_resolution.json")
    cm = ContextManager(type="chat", compression="high")
    result = cm.compress(data["messages"], token_budget=None, return_stats=True)
    # Still a valid pipeline outcome; may or may not emit RESOLVED depending on remaining signals.
    texts = " ".join(str(m.get("content", "")) for m in result.messages)
    assert result.stats.turns_after <= result.stats.turns_before
    assert "Monday" in texts or "RESOLVED" in texts
