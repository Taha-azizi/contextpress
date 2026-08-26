"""Shared JSON parse/minify helpers (stdlib only)."""

from __future__ import annotations

import json
from typing import Any


def try_parse_json(text: str) -> Any:
    """Return parsed object if ``text`` is a JSON object/array, else ``None``."""
    s = (text or "").strip()
    if not s or s[0] not in "{[":
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def try_minify_json(text: str) -> str | None:
    """Minify a JSON object/array string, or ``None`` if it is not JSON."""
    obj = try_parse_json(text)
    if obj is None:
        return None
    return dumps_compact(obj)


def minify_json_string(text: str) -> str:
    """Minify if ``text`` is JSON; otherwise return ``text`` unchanged."""
    mini = try_minify_json(text)
    return mini if mini is not None else text


def json_body(raw: Any) -> str:
    """Serialize dict/list compactly; stringify other values."""
    if isinstance(raw, (dict, list)):
        return dumps_compact(raw)
    if raw is None:
        return ""
    return str(raw)
