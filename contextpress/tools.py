"""Helpers for OpenAI, Anthropic, and Gemini tool messages (0.6.4+)."""

from __future__ import annotations

import json
from typing import Any

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
    if s[0] in "{[":
        try:
            json.loads(s)
            return True
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
    return False


def preserve_structured_turn(turn: Turn) -> bool:
    """Tool payloads and JSON/fenced JSON should not be NLP-summarized or dropped."""
    if has_tool_marker(turn):
        return True
    return is_structured_text(extract_text_for_processing(turn))


def _ids_from_blocks(turn: Turn, *, block_type: str, id_key: str) -> list[str]:
    ids: list[str] = []
    if not isinstance(turn.content, list):
        return ids
    for block in turn.content:
        if block.type != block_type:
            continue
        cid = (block.metadata or {}).get(id_key)
        if cid is not None:
            ids.append(str(cid))
    return ids


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
    for cid in _ids_from_blocks(turn, block_type="tool_use", id_key="id"):
        if cid not in seen:
            seen.add(cid)
            ids.append(cid)
    if isinstance(turn.content, list):
        for block in turn.content:
            if block.type != "function_call":
                continue
            cid = _nested_tool_id(block, "functionCall", "function_call")
            if cid and cid not in seen:
                seen.add(cid)
                ids.append(cid)
    return ids


def result_tool_call_id(turn: Turn) -> str | None:
    for layer in _layers(turn):
        tid = layer.get("tool_call_id")
        if tid is not None:
            return str(tid)
    block_ids = _ids_from_blocks(turn, block_type="tool_result", id_key="tool_use_id")
    if block_ids:
        return block_ids[0]
    if isinstance(turn.content, list):
        for block in turn.content:
            if block.type != "function_response":
                continue
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
            parts.append(json.dumps(calls, ensure_ascii=False))
            break
    if isinstance(turn.content, list):
        for block in turn.content:
            if block.type in ("tool_use", "tool_result", "function_call", "function_response") and (
                block.content
            ):
                parts.append(block.content)
    return "\n".join(parts)


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
    """Minify JSON strings in tool_calls, Anthropic blocks, and Gemini parts."""
    meta = turn.metadata or {}
    if not meta and not isinstance(turn.content, list):
        return turn
    changed = False
    new_meta = dict(meta)
    new_content: str | list[ContentBlock] = turn.content

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

    def _compact_block_dict(item: dict[str, Any]) -> dict[str, Any]:
        nonlocal changed
        kind = item.get("type")
        out = dict(item)
        if kind == "tool_use" and isinstance(out.get("input"), str):
            mini = _minify_json_string(out["input"])
            if mini != out["input"]:
                out["input"] = mini
                changed = True
        if kind == "tool_result" and isinstance(out.get("content"), str):
            mini = _minify_json_string(out["content"])
            if mini != out["content"]:
                out["content"] = mini
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
                if isinstance(payload.get(ak), str):
                    mini = _minify_json_string(payload[ak])
                    if mini != payload[ak]:
                        payload[ak] = mini
                        changed = True
            out[call_key] = payload
        for resp_key in ("functionResponse", "function_response"):
            payload = out.get(resp_key)
            if not isinstance(payload, dict):
                continue
            payload = dict(payload)
            if isinstance(payload.get("response"), str):
                mini = _minify_json_string(payload["response"])
                if mini != payload["response"]:
                    payload["response"] = mini
                    changed = True
            out[resp_key] = payload
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
        if isinstance(orig.get("content"), list):
            orig["content"] = [
                _compact_block_dict(x) if isinstance(x, dict) else x for x in orig["content"]
            ]
        if isinstance(orig.get("parts"), list):
            orig["parts"] = [
                _compact_block_dict(x) if isinstance(x, dict) else x for x in orig["parts"]
            ]
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
                _minify_json_string(block.content)
                if isinstance(block.content, str)
                else block.content
            )
            bmeta = _compact_block_dict(dict(block.metadata or {}))
            if mini != block.content:
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
