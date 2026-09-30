"""One-time NLTK data download.

Downloads only the NLTK resources that are missing, at most once per process.
Offline installs will hit the network here — pre-populate NLTK_DATA to skip.
Newer NLTK (3.9+) needs ``punkt_tab`` and ``averaged_perceptron_tagger_eng``;
older releases use ``punkt`` and ``averaged_perceptron_tagger``.
"""

from __future__ import annotations

import warnings

import nltk

# package name -> resource path checked with nltk.data.find
_RESOURCES = {
    "punkt": "tokenizers/punkt",
    "punkt_tab": "tokenizers/punkt_tab",
    "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
    "averaged_perceptron_tagger_eng": "taggers/averaged_perceptron_tagger_eng",
}
_ATTEMPTED = False


def _missing_packages() -> list[str]:
    missing: list[str] = []
    for pkg, path in _RESOURCES.items():
        try:
            nltk.data.find(path)
        except LookupError:
            missing.append(pkg)
    return missing


def bootstrap_nltk() -> None:
    global _ATTEMPTED
    if _ATTEMPTED:
        return
    _ATTEMPTED = True
    for pkg in _missing_packages():
        try:
            # Old/new NLTK each lack one of the package names; failures are expected.
            nltk.download(pkg, quiet=True)
        except Exception:
            pass
    missing = set(_missing_packages())
    # Either punkt generation is enough; warn only if neither is usable.
    if {"punkt", "punkt_tab"} <= missing:
        warnings.warn(
            "contextpress: could not download NLTK sentence data (punkt / punkt_tab); "
            "sentence splitting may degrade. Check network or set NLTK_DATA.",
            stacklevel=2,
        )
