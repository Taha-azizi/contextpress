"""Build encoding-specific lexical synonym dictionaries for the lexical stage.

Walks WordNet lemmas (4+ letters), finds same-POS synonyms, and keeps a swap
only when tiktoken encodes the synonym in strictly fewer tokens than the
original. Ties: fewer tokens first, then shorter string, then lexicographic.

WordNet synonymy can include register or connotation shifts (formal vs
informal, dated senses, near-miss meanings). Spot-check the generated JSON
by hand before treating it as final. This script does not filter for
semantic quality beyond same-POS WordNet synonymy.

Usage (from repo root):

    python scripts/build_lexical_dict.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import nltk
import tiktoken
from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "contextpress" / "data"
ENCODINGS = ("cl100k_base", "o200k_base")
# Spot-check: 1–2 letter WordNet "synonyms" are almost always abbreviations
# (state codes, element symbols, "ad"). Not a semantic filter — just unusable
# as whole-word chat replacements. "use" (3) is kept so utilize->use works.
MIN_REPLACEMENT_LEN = 3
_SOURCE_RE = re.compile(r"^[a-z]{4,}$")
_CANDIDATE_RE = re.compile(r"^[a-z]{2,}$")


def _surface(name: str, pattern: re.Pattern[str]) -> str | None:
    if "_" in name or "-" in name:
        return None
    word = name.lower()
    if not pattern.fullmatch(word):
        return None
    return word


def _ensure_wordnet() -> None:
    try:
        wn.ensure_loaded()
        return
    except LookupError:
        pass
    for pkg in ("wordnet", "omw-1.4"):
        nltk.download(pkg, quiet=True)
    wn.ensure_loaded()


def _synonym_map() -> dict[str, set[str]]:
    """4+ letter lemmas -> same-POS synonyms (candidates may be 2–3 letters)."""
    synonyms: dict[str, set[str]] = {}
    for synset in wn.all_synsets():
        members: list[str] = []
        for lemma in synset.lemmas():
            key = _surface(lemma.name(), _CANDIDATE_RE)
            if key is not None:
                members.append(key)
        uniq = set(members)
        if len(uniq) < 2:
            continue
        for word in uniq:
            if not _SOURCE_RE.fullmatch(word):
                continue
            others = uniq - {word}
            if others:
                synonyms.setdefault(word, set()).update(others)
    return synonyms


def _token_counts(words: set[str], encode: tiktoken.Encoding) -> dict[str, int]:
    return {w: len(encode.encode(w)) for w in words}


def _pick_replacement(
    word: str,
    candidates: set[str],
    counts: dict[str, int],
) -> str | None:
    n_orig = counts[word]
    best: tuple[int, int, str] | None = None
    for cand in candidates:
        n_cand = counts[cand]
        if n_cand >= n_orig:
            continue
        if len(cand) < MIN_REPLACEMENT_LEN:
            continue
        score = (n_cand, len(cand), cand)
        if best is None or score < best:
            best = score
    if best is None:
        return None
    return best[2]


def _write_dict(encoding_name: str, synonyms: dict[str, set[str]]) -> Path:
    encode = tiktoken.get_encoding(encoding_name)
    vocab: set[str] = set(synonyms)
    for cands in synonyms.values():
        vocab.update(cands)
    counts = _token_counts(vocab, encode)
    mapping: dict[str, str] = {}
    for word, cands in synonyms.items():
        repl = _pick_replacement(word, cands, counts)
        if repl is not None:
            mapping[word] = repl
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"lexical_{encoding_name}.json"
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    _ensure_wordnet()
    synonyms = _synonym_map()
    scanned = len(synonyms)
    print(f"words scanned (4+ letter WordNet lemmas with a same-POS synonym): {scanned}")

    for encoding_name in ENCODINGS:
        try:
            tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            print(f"skip {encoding_name}: {exc}", file=sys.stderr)
            continue
        path = _write_dict(encoding_name, synonyms)
        mapping = json.loads(path.read_text(encoding="utf-8"))
        size = path.stat().st_size
        print(
            f"{encoding_name}: words with a valid swap={len(mapping)} "
            f"output={path} bytes={size}"
        )
        for sample in ("utilize", "commence", "assist", "additional", "implement", "become"):
            if sample in mapping:
                print(f"  e.g. {sample!r} -> {mapping[sample]!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
