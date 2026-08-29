"""Build encoding-specific wordy-phrase → shorter-form dictionaries.

Hand-maintained exact paraphrases from plain-language writing guides.
Not auto-mined. Keeps a pair only when the shorter form uses strictly fewer
tiktoken tokens for that encoding.

Usage (from repo root)::

    python scripts/build_wordy_phrases_dict.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "contextpress" / "data"
ENCODINGS = ("cl100k_base", "o200k_base")

# Exact meaning substitutions (wordy / formal → plain shorter form).
WORDY_PHRASES: dict[str, str] = {
    "in order to": "to",
    "due to the fact that": "because",
    "owing to the fact that": "because",
    "at this point in time": "now",
    "at the present time": "now",
    "at the present moment": "now",
    "in the event that": "if",
    "in the event of": "if",
    "for the purpose of": "for",
    "for the purposes of": "for",
    "in spite of the fact that": "although",
    "despite the fact that": "although",
    "notwithstanding the fact that": "although",
    "with regard to": "about",
    "with respect to": "about",
    "in regard to": "about",
    "in reference to": "about",
    "concerning the matter of": "about",
    "in the near future": "soon",
    "in the not too distant future": "soon",
    "a large number of": "many",
    "a small number of": "few",
    "a great number of": "many",
    "a majority of": "most",
    "the majority of": "most",
    "on a daily basis": "daily",
    "on a regular basis": "regularly",
    "on a weekly basis": "weekly",
    "on a monthly basis": "monthly",
    "on an annual basis": "annually",
    "prior to": "before",
    "subsequent to": "after",
    "in advance of": "before",
    "in excess of": "over",
    "in addition to": "besides",
    "as a result of": "because of",
    "as a consequence of": "because of",
    "by means of": "by",
    "by virtue of": "by",
    "in the absence of": "without",
    "in the course of": "during",
    "during the course of": "during",
    "in the process of": "while",
    "it is important to note that": "note that",
    "it should be noted that": "note that",
    "it is worth noting that": "note that",
    "for the reason that": "because",
    "the reason why is that": "because",
    "in light of the fact that": "because",
    "under the circumstances that": "if",
    "until such time as": "until",
    "in a timely manner": "promptly",
    "at a later date": "later",
    "at an early date": "soon",
    "has the ability to": "can",
    "has the capacity to": "can",
    "is able to": "can",
    "is required to": "must",
    "is necessary to": "must",
    "make a decision": "decide",
    "make a determination": "decide",
    "come to a conclusion": "conclude",
    "give consideration to": "consider",
    "take into consideration": "consider",
    "take into account": "consider",
    "provide assistance to": "help",
    "provide assistance": "help",
    "in close proximity to": "near",
    "in the vicinity of": "near",
    "a sufficient number of": "enough",
    "in accordance with": "under",
    "pursuant to": "under",
}


def _filter_for_encoding(encoding_name: str) -> dict[str, str]:
    enc = tiktoken.get_encoding(encoding_name)
    out: dict[str, str] = {}
    for src, dst in WORDY_PHRASES.items():
        if len(enc.encode(dst)) < len(enc.encode(src)):
            out[src] = dst
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"candidates: {len(WORDY_PHRASES)}")
    for encoding_name in ENCODINGS:
        try:
            tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            print(f"skip {encoding_name}: {exc}", file=sys.stderr)
            continue
        mapping = _filter_for_encoding(encoding_name)
        path = OUT_DIR / f"wordy_phrases_{encoding_name}.json"
        path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{encoding_name}: kept={len(mapping)} / {len(WORDY_PHRASES)} -> {path}")
        for sample in (
            "in order to",
            "due to the fact that",
            "at this point in time",
            "in the event that",
            "a large number of",
            "on a daily basis",
        ):
            if sample in mapping:
                print(f"  e.g. {sample!r} -> {mapping[sample]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
