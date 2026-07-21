"""Capture warnings emitted during compression into ``CompressionStats``."""

from __future__ import annotations

import warnings
from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def capture_warnings() -> Generator[list[str], None, None]:
    captured: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield captured
    captured.extend(str(item.message) for item in caught)
