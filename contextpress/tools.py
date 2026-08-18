"""Helpers for OpenAI-style tool_calls / role=tool messages (0.6.4+)."""

from __future__ import annotations

import json
from typing import Any

from contextpress.models import Turn
from contextpress.normalizer import extract_text_for_processing

_TOOL_META_KEYS = ("tool_calls", "tool_call", "tool_use", "tool_result", "tool_call_id")
_TEXT_MARKERS = ("tool_calls", "tool_call", "tool_use", "tool_result", "<tool", "[tool")
_RESULT_ROLES = frozenset({"tool", "function"})


def _layers(turn: Turn) -> list[dict[str, Any]]:
    meta = turn.metadata or {}
    layers: list[dict[str, Any]] = [meta]
    orig = meta.get("_original_dict")
    if isinstance(orig, dict) and orig is not meta:
        layers.append(orig)
    return layers


def has_tool_marker(turn: Turn) -> bool:
    """True if this turn is a tool call, tool result, or has a textual tool marker."""
    if turn.role in _RESULT_ROLES:
        return True
    for layer in _layers(turn):
        if any(k in layer for k in _TOOL_META_KEYS):
            return True
    text = extract_text_for_processing(turn).lower()
    return any(m in text for m in _TEXT_MARKERS)


def assistant_tool_call_ids(turn: Turn) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for layer in _layers(turn):
        calls = layer.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            cid = call.get("id")
            if cid is None:
                continue
            sid = str(cid)
            if sid not in seen:
                seen.add(sid)
                ids.append(sid)
        break
    return ids


def result_tool_call_id(turn: Turn) -> str | None:
    for layer in _layers(turn):
        tid = layer.get("tool_call_id")
        if tid is not None:
            return str(tid)
    return None


def tool_payload_text(turn: Turn) -> str:
    """Extra text for token counting (tool_calls JSON, not already in content)."""
    for layer in _layers(turn):
        calls = layer.get("tool_calls")
        if isinstance(calls, list) and calls:
            return json.dumps(calls, ensure_ascii=False)
    return ""


def _minify_json_string(text: str) -> str:
    s = text.strip()
    if not s or s[0] not in "{[":
        return text
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return text
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def minify_tool_fields(turn: Turn) -> Turn:
    """Minify JSON in tool_calls[].function.arguments; write back to metadata."""
    meta = turn.metadata
    if not meta:
        return turn
    changed = False
    new_meta = dict(meta)

    def _compact_calls(calls: Any) -> Any:
        nonlocal changed
        if not isinstance(calls, list):
            return calls
        out = []
        for call in calls:
            if not isinstance(call, dict):
                out.append(call)
                continue
            c = dict(call)
            fn = c.get("function")
            if isinstance(fn, dict):
                fn = dict(fn)
                args = fn.get("arguments")
                if isinstance(args, str):
                    mini = _minify_json_string(args)
                    if mini != args:
                        fn["arguments"] = mini
                        changed = True
                c["function"] = fn
            out.append(c)
        return out

    if "tool_calls" in new_meta:
        new_meta["tool_calls"] = _compact_calls(new_meta["tool_calls"])
    orig = new_meta.get("_original_dict")
    if isinstance(orig, dict):
        orig = dict(orig)
        if "tool_calls" in orig:
            orig["tool_calls"] = _compact_calls(orig["tool_calls"])
        if turn.role in _RESULT_ROLES and isinstance(orig.get("content"), str):
            target = turn.content if isinstance(turn.content, str) else orig["content"]
            mini = _minify_json_string(target)
            if mini != orig["content"]:
                orig["content"] = mini
                changed = True
        new_meta["_original_dict"] = orig

    if not changed:
        return turn
    return Turn(
        role=turn.role,
        content=turn.content,
        timestamp=turn.timestamp,
        metadata=new_meta,
        importance=turn.importance,
        resolved=turn.resolved,
        compressed=True,
        original_content=(
            turn.original_content if turn.original_content is not None else turn.content
        ),
    )


def tool_group_indices(turns: list[Turn], index: int) -> list[int]:
    """Indices of an assistant tool_calls turn plus following matching tool results.

    If ``index`` is a tool result, walk back to the parent assistant first.
    """
    if index < 0 or index >= len(turns):
        return [index]
    t = turns[index]
    if t.role in _RESULT_ROLES:
        k = index - 1
        while k >= 0:
            if turns[k].role == "assistant" and assistant_tool_call_ids(turns[k]):
                rid = result_tool_call_id(t)
                ids = set(assistant_tool_call_ids(turns[k]))
                if rid is None or rid in ids:
                    return tool_group_indices(turns, k)
                break
            if turns[k].role not in _RESULT_ROLES:
                break
            k -= 1
        return [index]

    ids = set(assistant_tool_call_ids(t))
    if t.role != "assistant" or not ids:
        return [index]
    group = [index]
    j = index + 1
    while j < len(turns) and turns[j].role in _RESULT_ROLES:
        rid = result_tool_call_id(turns[j])
        if rid is None or rid in ids:
            group.append(j)
        else:
            break
        j += 1
    return group
