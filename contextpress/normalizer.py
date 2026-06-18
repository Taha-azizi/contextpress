"""
Input/output gateway: normalize heterogeneous message formats to Conversation
and reconstruct the original format after processing.
"""

from __future__ import annotations

import copy
import warnings
from datetime import datetime
from typing import Any

from contextpress.models import ContentBlock, Conversation, Turn

_VALID_ROLES = frozenset({"user", "assistant", "system"})
_LC_TYPE_MAP = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
}


def _parse_timestamp(meta: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "created_at", "ts"):
        v = meta.get(key)
        if v is None:
            continue
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(v)
            except (OSError, ValueError, OverflowError):
                continue
        if isinstance(v, str):
            try:
                # ISO format
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _blocks_from_openai_style(items: list[dict[str, Any]]) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    for item in items:
        t = item.get("type", "text")
        if t == "text":
            text = item.get("text", "")
            blocks.append(ContentBlock(type="text", content=text, metadata=copy.deepcopy(item)))
        elif t in ("image_url", "image"):
            url = ""
            if "image_url" in item:
                iu = item["image_url"]
                url = (
                    iu
                    if isinstance(iu, str)
                    else (iu.get("url", "") if isinstance(iu, dict) else "")
                )
            blocks.append(
                ContentBlock(type="image", content=url or str(item), metadata=copy.deepcopy(item))
            )
        else:
            blocks.append(
                ContentBlock(
                    type=str(t),
                    content=str(item.get("content", item)),
                    metadata=copy.deepcopy(item),
                )
            )
    return blocks


def _text_from_blocks(blocks: list[ContentBlock]) -> str:
    parts = [b.content for b in blocks if b.type == "text"]
    return " ".join(p for p in parts if p).strip()


def _blocks_to_openai_style(blocks: list[ContentBlock]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in blocks:
        if b.type == "text":
            d = {"type": "text", "text": b.content}
            out.append(d)
        elif b.type == "image":
            meta = b.metadata or {}
            if meta:
                out.append(copy.deepcopy(meta))
            else:
                out.append({"type": "image_url", "image_url": {"url": b.content}})
        else:
            out.append(
                copy.deepcopy(b.metadata) if b.metadata else {"type": b.type, "content": b.content}
            )
    return out


def _get_lc_role_and_content(obj: Any) -> tuple[str, str | list[ContentBlock], dict[str, Any]]:
    role = None
    if hasattr(obj, "type") and obj.type is not None:
        role = _LC_TYPE_MAP.get(str(obj.type).lower(), str(obj.type).lower())
    if role is None and hasattr(obj, "role"):
        role = str(obj.role).lower()
    if role is None:
        role = "user"
    content = getattr(obj, "content", "")
    if isinstance(content, list):
        blocks = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                blocks.append(
                    ContentBlock(
                        type="text", content=part.get("text", ""), metadata=copy.deepcopy(part)
                    )
                )
            elif isinstance(part, str):
                blocks.append(ContentBlock(type="text", content=part))
            else:
                blocks.append(ContentBlock(type="text", content=str(part)))
        return role, blocks, {"_lc_obj": obj}
    if not isinstance(content, str):
        content = str(content)
    return role, content, {"_lc_obj": obj}


def normalize_messages(
    messages: Any,
    context_type: str = "chat",
) -> tuple[Conversation, dict[str, Any]]:
    """
    Returns (Conversation, ctx) where ctx holds format info for denormalize.
    """
    ctx: dict[str, Any] = {"format": "unknown", "extras": []}

    if messages is None:
        return Conversation(turns=[], type=context_type, metadata={}), ctx

    # LangChain-style objects (list of objects with .content)
    if (
        isinstance(messages, list)
        and messages
        and not isinstance(messages[0], (str, bytes, dict, tuple))
    ):
        ctx["format"] = "langchain"
        ctx["lc_objects"] = list(messages)
        turns: list[Turn] = []
        for obj in messages:
            role, content, tmeta = _get_lc_role_and_content(obj)
            ts = _parse_timestamp(getattr(obj, "__dict__", {}) or {})
            if ts is None and hasattr(obj, "additional_kwargs"):
                ak = getattr(obj, "additional_kwargs", {}) or {}
                ts = _parse_timestamp(ak if isinstance(ak, dict) else {})
            meta = {**tmeta, "_lc_original": obj}
            turns.append(Turn(role=role, content=content, timestamp=ts, metadata=meta))
        conv = Conversation(turns=turns, type=context_type, metadata={"_norm_ctx": ctx})
        return conv, ctx

    # Plain string list — alternating user/assistant
    if isinstance(messages, list) and (not messages or isinstance(messages[0], str)):
        ctx["format"] = "str_list"
        turns = []
        for i, s in enumerate(messages):
            role = "user" if i % 2 == 0 else "assistant"
            turns.append(Turn(role=role, content=s, metadata={"_str_index": i}))
        return Conversation(turns=turns, type=context_type, metadata={"_norm_ctx": ctx}), ctx

    # Tuple list
    if isinstance(messages, list) and messages and isinstance(messages[0], tuple):
        ctx["format"] = "tuple_list"
        turns = []
        for i, tup in enumerate(messages):
            if len(tup) < 2:
                continue
            role, content = tup[0], tup[1]
            turns.append(
                Turn(
                    role=str(role).lower(),
                    content=str(content),
                    metadata={"_tuple_index": i},
                )
            )
        return Conversation(turns=turns, type=context_type, metadata={"_norm_ctx": ctx}), ctx

    # Dict list (most common)
    if isinstance(messages, list):
        ctx["format"] = "dict_list"
        turns = []
        for i, raw in enumerate(messages):
            if not isinstance(raw, dict):
                warnings.warn(
                    f"contextpress: unknown message shape at index {i}, skipping", stacklevel=2
                )
                continue
            d = copy.deepcopy(raw)
            role = str(d.get("role", "user")).lower()
            if role not in _VALID_ROLES:
                warnings.warn(
                    f"contextpress: unknown role {role!r} — passing through as-is",
                    stacklevel=2,
                )
            ts = _parse_timestamp(d)
            content = d.get("content", "")
            meta: dict[str, Any] = {"_dict_index": i, "_original_dict": d}

            if isinstance(content, list):
                blocks = _blocks_from_openai_style(content)
                turns.append(
                    Turn(
                        role=role,
                        content=blocks,
                        timestamp=ts,
                        metadata=meta,
                    )
                )
            else:
                turns.append(
                    Turn(
                        role=role,
                        content=str(content) if content is not None else "",
                        timestamp=ts,
                        metadata=meta,
                    )
                )
        return Conversation(turns=turns, type=context_type, metadata={"_norm_ctx": ctx}), ctx

    raise TypeError(f"contextpress: unsupported messages type {type(messages)!r}")


def _turn_to_plain_text(turn: Turn) -> str:
    if isinstance(turn.content, str):
        return turn.content
    return _text_from_blocks(turn.content)


def denormalize_output(conversation: Conversation, ctx: dict[str, Any]) -> Any:
    """Convert Conversation back to the original input container type."""
    fmt = ctx.get("format", "dict_list")
    turns = conversation.turns

    if fmt == "str_list":
        return [_turn_to_plain_text(t) for t in turns]

    if fmt == "tuple_list":
        out: list[tuple[str, str]] = []
        for t in turns:
            out.append((t.role, _turn_to_plain_text(t)))
        return out

    if fmt == "langchain":
        # Reconstruct LangChain objects by copying original and setting content
        lc_objs = ctx.get("lc_objects", [])
        if not lc_objs:
            return []
        result = []
        for i, t in enumerate(turns):
            if i < len(lc_objs):
                obj = copy.copy(lc_objs[i])
                text = _turn_to_plain_text(t)
                if hasattr(obj, "content"):
                    try:
                        obj.content = text
                    except Exception:
                        pass
                result.append(obj)
            else:
                # New synthetic turns — wrap as plain object with role/content
                class _Msg:
                    def __init__(self, role: str, content: str):
                        self.role = role
                        self.type = role
                        self.content = content

                result.append(_Msg(t.role, _turn_to_plain_text(t)))
        return result

    # dict_list
    out_dicts: list[dict[str, Any]] = []
    for t in turns:
        base = copy.deepcopy(t.metadata.get("_original_dict", {}))
        if not base:
            base = {"role": t.role}
        else:
            base["role"] = t.role
        if isinstance(t.content, list):
            base["content"] = _blocks_to_openai_style(t.content)
        else:
            base["content"] = t.content
        out_dicts.append(base)
    return out_dicts


def extract_text_for_processing(turn: Turn) -> str:
    """Plain text for Tier-1 NLP stages."""
    return _turn_to_plain_text(turn)


def apply_text_to_turn(turn: Turn, new_text: str) -> Turn:
    """Replace text in a turn, preserving multimodal non-text blocks."""
    if isinstance(turn.content, str):
        return Turn(
            role=turn.role,
            content=new_text,
            timestamp=turn.timestamp,
            metadata=copy.deepcopy(turn.metadata),
            importance=turn.importance,
            resolved=turn.resolved,
            compressed=True,
            original_content=(
                turn.original_content if turn.original_content is not None else turn.content
            ),
        )
    new_blocks: list[ContentBlock] = []
    text_assigned = False
    for b in turn.content:
        if b.type == "text" and not text_assigned:
            new_blocks.append(ContentBlock(type="text", content=new_text, metadata=b.metadata))
            text_assigned = True
        else:
            new_blocks.append(copy.deepcopy(b))
    if not text_assigned:
        new_blocks.insert(0, ContentBlock(type="text", content=new_text))
    orig = (
        turn.original_content if turn.original_content is not None else copy.deepcopy(turn.content)
    )
    return Turn(
        role=turn.role,
        content=new_blocks,
        timestamp=turn.timestamp,
        metadata=copy.deepcopy(turn.metadata),
        importance=turn.importance,
        resolved=turn.resolved,
        compressed=True,
        original_content=orig,
    )
