"""One-time NLTK data download.

Runs on first import; writes a flag file so later imports stay silent.
Offline installs will hit the network here — set the flag manually
(``touch ~/.contextpress/nltk_ready``) or pre-populate NLTK_DATA to skip.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import nltk


def bootstrap_nltk() -> None:
    flag = Path.home() / ".contextpress" / "nltk_ready"
    if flag.exists():
        return
    packages = ["punkt", "stopwords", "averaged_perceptron_tagger"]
    failed: list[str] = []
    for pkg in packages:
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            failed.append(pkg)
    if failed:
        warnings.warn(
            f"contextpress: could not download NLTK data {failed}; "
            "resolution/recency may degrade. Check network or set NLTK_DATA.",
            stacklevel=2,
        )
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
