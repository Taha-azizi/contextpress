"""Helpers for OpenAI, Anthropic, and Gemini tool messages (0.6.4+)."""

from __future__ import annotations

from typing import Any

from contextpress.jsonutil import dumps_compact, minify_json_string, try_parse_json
from contextpress.models import ContentBlock, Turn
from contextpress.normalizer import extract_text_for_processing

_TOOL_META_KEYS = (
    "tool_calls",
    "tool_call",
    "tool_use",
    "tool_result",
    "tool_call_id",
    "functionCall",
    "function_call",
    "functionResponse",
    "function_response",
)
_TEXT_MARKERS = (
    "tool_calls",
    "tool_call",
    "tool_use",
    "tool_result",
    "<tool",
    "[tool",
    "functioncall",
    "function_call",
    "functionresponse",
    "function_response",
)
_RESULT_ROLES = frozenset({"tool", "function"})
_RESULT_BLOCK_TYPES = frozenset({"tool_result", "function_response"})


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
    if isinstance(turn.content, list) and any(
        b.type in ("tool_use", "tool_result", "function_call", "function_response")
        for b in turn.content
    ):
        return True
    for layer in _layers(turn):
        if any(k in layer for k in _TOOL_META_KEYS):
            return True
    text = extract_text_for_processing(turn).lower()
    return any(m in text for m in _TEXT_MARKERS)


def is_structured_text(text: str) -> bool:
    """True for a JSON blob or a markdown fence tagged json."""
    s = (text or "").strip()
    if not s:
        return False
    if "```json" in s.lower():
        return True
    return try_parse_json(s) is not None


def preserve_structured_turn(turn: Turn) -> bool:
    """Tool payloads and JSON/fenced JSON should not be NLP-summarized or dropped."""
    if has_tool_marker(turn):
        return True
    return is_structured_text(extract_text_for_processing(turn))


def _remember_id(ids: list[str], seen: set[str], cid: str | None) -> None:
    if cid is None:
        return
    sid = str(cid)
    if sid not in seen:
        seen.add(sid)
        ids.append(sid)


def _nested_tool_id(block: ContentBlock, *keys: str) -> str | None:
    meta = block.metadata or {}
    for key in keys:
        payload = meta.get(key)
        if isinstance(payload, dict) and payload.get("id") is not None:
            return str(payload["id"])
    return None


def is_tool_result_turn(turn: Turn) -> bool:
    """OpenAI role=tool, Anthropic tool_result-only user, or Gemini functionResponse-only."""
    if turn.role in _RESULT_ROLES:
        return True
    if isinstance(turn.content, list) and turn.content:
        return all(b.type in _RESULT_BLOCK_TYPES for b in turn.content)
    return False


def assistant_tool_call_ids(turn: Turn) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for layer in _layers(turn):
        calls = layer.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if isinstance(call, dict):
                _remember_id(ids, seen, call.get("id"))
        break
    if not isinstance(turn.content, list):
        return ids
    for block in turn.content:
        if block.type == "tool_use":
            _remember_id(ids, seen, (block.metadata or {}).get("id"))
        elif block.type == "function_call":
            _remember_id(ids, seen, _nested_tool_id(block, "functionCall", "function_call"))
    return ids


def result_tool_call_id(turn: Turn) -> str | None:
    for layer in _layers(turn):
        tid = layer.get("tool_call_id")
        if tid is not None:
            return str(tid)
    if not isinstance(turn.content, list):
        return None
    for block in turn.content:
        if block.type == "tool_result":
            cid = (block.metadata or {}).get("tool_use_id")
            if cid is not None:
                return str(cid)
        elif block.type == "function_response":
            cid = _nested_tool_id(block, "functionResponse", "function_response")
            if cid:
                return cid
    return None


def tool_payload_text(turn: Turn) -> str:
    """Extra text for token counting (tool_calls JSON and native tool blocks)."""
    parts: list[str] = []
    for layer in _layers(turn):
        calls = layer.get("tool_calls")
        if isinstance(calls, list) and calls:
            parts.append(dumps_compact(calls))
            break
    if isinstance(turn.content, list):
        for block in turn.content:
            if block.type in ("tool_use", "tool_result", "function_call", "function_response") and (
                block.content
            ):
                parts.append(block.content)
    return "\n".join(parts)


def _minify_str_field(d: dict[str, Any], key: str) -> bool:
    val = d.get(key)
    if not isinstance(val, str):
        return False
    mini = minify_json_string(val)
    if mini == val:
        return False
    d[key] = mini
    return True


def _compact_calls(calls: Any) -> tuple[Any, bool]:
    if not isinstance(calls, list):
        return calls, False
    changed = False
    out = []
    for call in calls:
        if not isinstance(call, dict):
            out.append(call)
            continue
        c = dict(call)
        fn = c.get("function")
        if isinstance(fn, dict):
            fn = dict(fn)
            if _minify_str_field(fn, "arguments"):
                changed = True
            c["function"] = fn
        out.append(c)
    return out, changed


def _compact_block_dict(item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    out = dict(item)
    kind = out.get("type")
    if kind == "tool_use" and _minify_str_field(out, "input"):
        changed = True
    if kind == "tool_result" and _minify_str_field(out, "content"):
        changed = True
    for call_key, arg_keys in (
        ("functionCall", ("args", "arguments")),
        ("function_call", ("args", "arguments")),
    ):
        payload = out.get(call_key)
        if not isinstance(payload, dict):
            continue
        payload = dict(payload)
        for ak in arg_keys:
            if _minify_str_field(payload, ak):
                changed = True
        out[call_key] = payload
    for resp_key in ("functionResponse", "function_response"):
        payload = out.get(resp_key)
        if not isinstance(payload, dict):
            continue
        payload = dict(payload)
        if _minify_str_field(payload, "response"):
            changed = True
        out[resp_key] = payload
    return out, changed


def minify_tool_fields(turn: Turn) -> Turn:
    """Minify JSON strings in tool_calls, Anthropic blocks, and Gemini parts."""
    meta = turn.metadata or {}
    if not meta and not isinstance(turn.content, list):
        return turn
    changed = False
    new_meta = dict(meta)
    new_content: str | list[ContentBlock] = turn.content

    if "tool_calls" in new_meta:
        compacted, ch = _compact_calls(new_meta["tool_calls"])
        new_meta["tool_calls"] = compacted
        changed = changed or ch
    orig = new_meta.get("_original_dict")
    if isinstance(orig, dict):
        orig = dict(orig)
        if "tool_calls" in orig:
            compacted, ch = _compact_calls(orig["tool_calls"])
            orig["tool_calls"] = compacted
            changed = changed or ch
        if turn.role in _RESULT_ROLES and isinstance(orig.get("content"), str):
            target = turn.content if isinstance(turn.content, str) else orig["content"]
            mini = minify_json_string(target)
            if mini != orig["content"]:
                orig["content"] = mini
                changed = True
        if isinstance(orig.get("content"), list):
            items = []
            for x in orig["content"]:
                if isinstance(x, dict):
                    d, ch = _compact_block_dict(x)
                    items.append(d)
                    changed = changed or ch
                else:
                    items.append(x)
            orig["content"] = items
        if isinstance(orig.get("parts"), list):
            items = []
            for x in orig["parts"]:
                if isinstance(x, dict):
                    d, ch = _compact_block_dict(x)
                    items.append(d)
                    changed = changed or ch
                else:
                    items.append(x)
            orig["parts"] = items
        new_meta["_original_dict"] = orig

    if isinstance(turn.content, list):
        new_blocks: list[ContentBlock] = []
        for block in turn.content:
            if block.type not in (
                "tool_use",
                "tool_result",
                "function_call",
                "function_response",
            ):
                new_blocks.append(block)
                continue
            mini = (
                minify_json_string(block.content)
                if isinstance(block.content, str)
                else block.content
            )
            bmeta, ch = _compact_block_dict(dict(block.metadata or {}))
            if mini != block.content or ch:
                changed = True
            new_blocks.append(
                ContentBlock(
                    type=block.type,
                    content=mini,
                    mime_type=block.mime_type,
                    metadata=bmeta,
                )
            )
        new_content = new_blocks

    if not changed:
        return turn
    return Turn(
        role=turn.role,
        content=new_content,
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
    """Indices of an assistant tool call turn plus following matching tool results.

    If ``index`` is a tool result, walk back to the parent assistant first.
    """
    if index < 0 or index >= len(turns):
        return [index]
    t = turns[index]
    if is_tool_result_turn(t):
        k = index - 1
        while k >= 0:
            if turns[k].role == "assistant" and assistant_tool_call_ids(turns[k]):
                rid = result_tool_call_id(t)
                ids = set(assistant_tool_call_ids(turns[k]))
                if rid is None or rid in ids:
                    return tool_group_indices(turns, k)
                break
            if not is_tool_result_turn(turns[k]):
                break
            k -= 1
        return [index]

    ids = set(assistant_tool_call_ids(t))
    if t.role != "assistant" or not ids:
        return [index]
    group = [index]
    j = index + 1
    while j < len(turns) and is_tool_result_turn(turns[j]):
        rid = result_tool_call_id(turns[j])
        if rid is None or rid in ids:
            group.append(j)
        else:
            break
        j += 1
    return group
