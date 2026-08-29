"""Build encoding-specific English contraction dictionaries.

Closed, hand-maintained list of standard expanded → contracted forms.
No WordNet. Low-risk (no meaning change); candidate for a future default
``low`` preset, but this script only builds data — presets are not wired here.

Keeps a pair for an encoding when ``tokens(contraction) <= tokens(expanded)``
(equal is allowed; a net token increase is not).

Usage (from repo root)::

    python scripts/build_contractions_dict.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "contextpress" / "data"
ENCODINGS = ("cl100k_base", "o200k_base")

# Standard English contractions (expanded -> contracted). Closed set.
CONTRACTIONS: dict[str, str] = {
    "do not": "don't",
    "does not": "doesn't",
    "did not": "didn't",
    "is not": "isn't",
    "are not": "aren't",
    "was not": "wasn't",
    "were not": "weren't",
    "have not": "haven't",
    "has not": "hasn't",
    "had not": "hadn't",
    "will not": "won't",
    "would not": "wouldn't",
    "should not": "shouldn't",
    "could not": "couldn't",
    "cannot": "can't",
    "can not": "can't",
    "must not": "mustn't",
    "might not": "mightn't",
    "need not": "needn't",
    "i am": "i'm",
    "i have": "i've",
    "i will": "i'll",
    "i would": "i'd",
    "i had": "i'd",
    "you are": "you're",
    "you have": "you've",
    "you will": "you'll",
    "you would": "you'd",
    "you had": "you'd",
    "he is": "he's",
    "he has": "he's",
    "he will": "he'll",
    "he would": "he'd",
    "he had": "he'd",
    "she is": "she's",
    "she has": "she's",
    "she will": "she'll",
    "she would": "she'd",
    "she had": "she'd",
    "it is": "it's",
    "it has": "it's",
    "it will": "it'll",
    "it would": "it'd",
    "it had": "it'd",
    "we are": "we're",
    "we have": "we've",
    "we will": "we'll",
    "we would": "we'd",
    "we had": "we'd",
    "they are": "they're",
    "they have": "they've",
    "they will": "they'll",
    "they would": "they'd",
    "they had": "they'd",
    "that is": "that's",
    "that has": "that's",
    "that will": "that'll",
    "that would": "that'd",
    "there is": "there's",
    "there has": "there's",
    "there will": "there'll",
    "what is": "what's",
    "what has": "what's",
    "what will": "what'll",
    "who is": "who's",
    "who has": "who's",
    "who will": "who'll",
    "where is": "where's",
    "where has": "where's",
    "when is": "when's",
    "how is": "how's",
    "how has": "how's",
    "let us": "let's",
}


def _filter_for_encoding(encoding_name: str) -> dict[str, str]:
    enc = tiktoken.get_encoding(encoding_name)
    out: dict[str, str] = {}
    for src, dst in CONTRACTIONS.items():
        if len(enc.encode(dst)) <= len(enc.encode(src)):
            out[src] = dst
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for encoding_name in ENCODINGS:
        try:
            tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            print(f"skip {encoding_name}: {exc}", file=sys.stderr)
            continue
        mapping = _filter_for_encoding(encoding_name)
        path = OUT_DIR / f"contractions_{encoding_name}.json"
        path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{encoding_name}: kept={len(mapping)} / {len(CONTRACTIONS)} -> {path}")
        for sample in ("do not", "cannot", "it is", "they are", "will not", "should not"):
            if sample in mapping:
                print(f"  e.g. {sample!r} -> {mapping[sample]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
