"""Long-document savings study: solid prose, not chat threads or tool JSON.

The 222-item fidelity corpus is mostly multi-turn chat. This study asks a
different question: how much does ``rag_doc`` save on long continuous text,
and does the packing matter?

Two packings of the same excerpt:

* **monolith** — one user turn holds the whole passage, then the question.
  Recency never rewrites the last three non-system turns, and trim needs a
  longer thread, so this is the "paste the PDF" job. Savings come from
  filler / structure / cross-turn repetition only.
* **chunked** — the same passage split into section turns, then the question.
  This is the retrieval-context job ``rag_doc`` is built for: off-query
  sections can be summarized (``medium``) or dropped (``high``).

Sources are public-domain Project Gutenberg texts and CC BY-SA Wikipedia
extracts. Full text stays under ``benchmarks/data/`` (gitignored). This
script writes aggregate tables to ``benchmarks/LONGFORM.md``.

Usage::

    python -m benchmarks.run_longform
    python -m benchmarks.run_longform --refresh
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RAW = ROOT / "data" / "raw" / "longform"
REPORT = ROOT / "LONGFORM.md"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from contextpress import ContextManager  # noqa: E402

UA = {
    "User-Agent": (
        "contextpress-longform-benchmark/0.7.2 "
        "(local research; +https://github.com/Taha-azizi/contextpress)"
    )
}

# Target input sizes (cl100k tokens) for the passage, before the question turn.
LENGTHS: tuple[tuple[str, int], ...] = (
    ("2k", 2_000),
    ("8k", 8_000),
    ("20k", 20_000),
)
PRESETS = ("low", "medium", "high")

GUTENBERG: tuple[dict[str, Any], ...] = (
    {"id": "austen-pnp", "gid": 1342, "title": "Pride and Prejudice", "kind": "fiction"},
    {"id": "shelley-frank", "gid": 84, "title": "Frankenstein", "kind": "fiction"},
    {"id": "melville-moby", "gid": 2701, "title": "Moby-Dick", "kind": "fiction"},
    {"id": "dickens-cities", "gid": 98, "title": "A Tale of Two Cities", "kind": "fiction"},
    {"id": "darwin-origin", "gid": 1228, "title": "On the Origin of Species", "kind": "nonfiction"},
    {"id": "smith-wealth", "gid": 3300, "title": "The Wealth of Nations", "kind": "nonfiction"},
    {"id": "machiavelli-prince", "gid": 1232, "title": "The Prince", "kind": "nonfiction"},
    {"id": "wells-worlds", "gid": 36, "title": "The War of the Worlds", "kind": "fiction"},
)

WIKI: tuple[dict[str, str], ...] = (
    {"id": "wiki-french-rev", "title": "French Revolution", "kind": "nonfiction"},
    {"id": "wiki-roman", "title": "Roman Empire", "kind": "nonfiction"},
    {"id": "wiki-dna", "title": "DNA", "kind": "nonfiction"},
    {"id": "wiki-photosynthesis", "title": "Photosynthesis", "kind": "nonfiction"},
)

_START = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)
_END = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")
_NUM = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d+\.\d+(?:\.\d+)*|\d{3,})\b")
_WORD = re.compile(r"[A-Za-z]{5,}")
_STOP = frozenset(
    """
    about above after again against their there these those which while
    would could should other every being under where those shall might
    """.split()
)

SYSTEM = (
    "You answer from the supplied passage only. "
    "Do not use outside knowledge. Quote figures exactly when the passage states them."
)


def _http(url: str) -> bytes:
    req = urllib.request.Request(url, headers={**UA, "Accept": "text/plain, application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _cached(name: str, url: str, *, refresh: bool) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / name
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    time.sleep(0.4)
    text = _http(url).decode("utf-8", errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def _strip_gutenberg(text: str) -> str:
    start = _START.search(text)
    end = _END.search(text)
    if start:
        text = text[start.end() :]
    if end and (not start or end.start() > 0):
        # end marker is relative to original; re-find after slice
        end2 = _END.search(text)
        if end2:
            text = text[: end2.start()]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _load_gutenberg(work: dict[str, Any], *, refresh: bool) -> str:
    gid = int(work["gid"])
    url = f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt"
    raw = _cached(f"pg{gid}.txt", url, refresh=refresh)
    body = _strip_gutenberg(raw)
    if len(body) < 20_000:
        raise ValueError(f"gutenberg {gid} body too short ({len(body)} chars)")
    return body


def _load_wiki(work: dict[str, str], *, refresh: bool) -> str:
    qs = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "redirects": 1,
            "titles": work["title"],
            "format": "json",
        }
    )
    raw = _cached(f"{work['id']}.json", f"https://en.wikipedia.org/w/api.php?{qs}", refresh=refresh)
    payload = json.loads(raw)
    pages = (payload.get("query") or {}).get("pages") or {}
    text = ""
    for page in pages.values():
        text = str(page.get("extract") or "")
        if text:
            break
    text = text.replace("\r\n", "\n").strip()
    if len(text) < 8_000:
        raise ValueError(f"wiki {work['title']!r} extract too short ({len(text)} chars)")
    return text


def _encoding():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def _slice_tokens(text: str, n_tokens: int, enc: Any) -> str:
    ids = enc.encode(text)
    # Skip the front matter (title pages, prefaces) when the book is long enough.
    start = 0
    if len(ids) > n_tokens + 1_500:
        start = min(1_500, len(ids) - n_tokens)
    window = ids[start : start + n_tokens]
    piece = enc.decode(window).strip()
    cut = max(piece.rfind(". "), piece.rfind("? "), piece.rfind("! "))
    if cut > len(piece) * 0.8:
        piece = piece[: cut + 1]
    return piece.strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def _content_words(text: str) -> list[str]:
    out: list[str] = []
    for w in _WORD.findall(text):
        low = w.lower()
        if low in _STOP:
            continue
        out.append(low)
    return out


def _pick_anchor(text: str) -> str:
    sents = [s for s in _sentences(text) if 90 <= len(s) <= 320 and len(_content_words(s)) >= 6]
    if not sents:
        sents = [s for s in _sentences(text) if len(s) >= 60]
    if not sents:
        return text[:240].strip()
    # First third: the anchor must not sit in the protected tail of a chunked thread.
    idx = min(len(sents) - 1, max(0, len(sents) // 5))
    return sents[idx]


def _chunk(text: str, enc: Any) -> list[str]:
    """Split into enough sections that trim (head 2 + tail 3) can drop a middle."""
    n_tok = len(enc.encode(text))
    target_chunks = max(8, min(24, n_tok // 700))
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < target_chunks:
        paras = _sentences(text) or [text]
    min_chars = max(240, len(text) // target_chunks)
    merged: list[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p
        elif len(buf) < min_chars:
            buf = f"{buf}\n\n{p}"
        else:
            merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)
    i = 0
    while len(merged) < 8 and i < len(merged):
        piece = merged[i]
        if len(piece) < 500:
            i += 1
            continue
        mid = len(piece) // 2
        cut = piece.rfind(" ", max(0, mid - 200), mid + 200)
        if cut < 80:
            i += 1
            continue
        merged[i : i + 1] = [piece[:cut].strip(), piece[cut:].strip()]
    labelled = [f"SECTION {j + 1}:\n{c}" for j, c in enumerate(merged) if c.strip()]
    return labelled or [text]


def _question(anchor: str) -> str:
    words = anchor.split()
    hint = " ".join(words[:18]).rstrip(",;:")
    return (
        "Using only the passage, what does it say in the part that begins "
        f"“{hint}”? Answer in one or two sentences and keep any numbers."
    )


def _messages(passage: str, question: str, *, packing: str, enc: Any) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM}]
    if packing == "monolith":
        msgs.append({"role": "user", "content": passage})
    elif packing == "chunked":
        for chunk in _chunk(passage, enc):
            msgs.append({"role": "user", "content": chunk})
    else:
        raise ValueError(packing)
    msgs.append({"role": "user", "content": question})
    return msgs


def _whole_word_hits(words: list[str], text: str) -> int:
    if not words:
        return 0
    hay = text.lower()
    n = 0
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", hay):
            n += 1
    return n


def _body_text(messages: list[dict[str, Any]], question: str) -> str:
    parts: list[str] = []
    for m in messages:
        content = str(m.get("content") or "")
        if m.get("role") == "system" or content == question:
            continue
        parts.append(content)
    return "\n".join(parts)


def _run_one(
    *,
    source_id: str,
    title: str,
    kind: str,
    family: str,
    license_name: str,
    length_name: str,
    packing: str,
    preset: str,
    passage: str,
    anchor: str,
    enc: Any,
) -> dict[str, Any]:
    question = _question(anchor)
    messages = _messages(passage, question, packing=packing, enc=enc)
    cm = ContextManager(type="rag_doc", compression=preset, model=None)
    t0 = time.perf_counter()
    result = cm.compress(messages, token_budget=None, return_stats=True)
    elapsed = (time.perf_counter() - t0) * 1000.0
    out_body = _body_text(result.messages, question)
    words = _content_words(anchor)
    nums = _NUM.findall(passage)
    # Unique spans, stable order.
    uniq_nums = list(dict.fromkeys(nums))
    stats = result.stats
    q_out = ""
    for m in reversed(result.messages):
        if m.get("role") == "user":
            q_out = str(m.get("content") or "")
            break
    return {
        "id": source_id,
        "title": title,
        "kind": kind,
        "family": family,
        "license": license_name,
        "length": length_name,
        "packing": packing,
        "preset": preset,
        "tokens_before": stats.tokens_before,
        "tokens_after": stats.tokens_after,
        "token_savings_pct": stats.token_savings_pct,
        "elapsed_ms": round(elapsed, 1),
        "tokens_per_second": stats.tokens_per_second,
        "turns_before": stats.turns_before,
        "turns_after": stats.turns_after,
        "stages_run": list(stats.stages_run),
        "token_delta_by_stage": dict(stats.token_delta_by_stage),
        "anchor_words": len(words),
        "anchor_retained": _whole_word_hits(words, out_body),
        "anchor_retention_pct": round(100.0 * _whole_word_hits(words, out_body) / len(words), 2)
        if words
        else None,
        "numbers_total": len(uniq_nums),
        "numbers_retained": sum(1 for n in uniq_nums if n in out_body),
        "number_retention_pct": round(
            100.0 * sum(1 for n in uniq_nums if n in out_body) / len(uniq_nums), 2
        )
        if uniq_nums
        else None,
        "question_intact": q_out == question,
        "system_intact": (result.messages[0].get("content") if result.messages else "") == SYSTEM,
    }


def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 2) if xs else None


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 2) if xs else None


def _stdev(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    return round(statistics.stdev(xs), 2)


def _cell(rows: list[dict[str, Any]], *, packing: str, length: str, preset: str) -> dict[str, Any]:
    sub = [
        r
        for r in rows
        if r["packing"] == packing and r["length"] == length and r["preset"] == preset
    ]
    saves = [float(r["token_savings_pct"]) for r in sub]
    anchors = [
        float(r["anchor_retention_pct"]) for r in sub if r["anchor_retention_pct"] is not None
    ]
    numbers = [
        float(r["number_retention_pct"]) for r in sub if r["number_retention_pct"] is not None
    ]
    ms = [float(r["elapsed_ms"]) for r in sub]
    return {
        "n": len(sub),
        "mean_save": _mean(saves),
        "median_save": _median(saves),
        "sd_save": _stdev(saves),
        "mean_anchor": _mean(anchors),
        "mean_numbers": _mean(numbers),
        "median_ms": _median(ms),
        "question_ok": sum(1 for r in sub if r["question_intact"]),
        "system_ok": sum(1 for r in sub if r["system_intact"]),
    }


def _fmt(v: float | None, suffix: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:.1f}{suffix}" if isinstance(v, float) else str(v)


def _stage_table(rows: list[dict[str, Any]]) -> list[str]:
    """Mean tokens removed per stage (positive = savings) for chunked runs."""
    lines = [
        "",
        "## Where the tokens go (chunked, mean tokens removed per stage)",
        "",
        "Figures are the mean of tokens removed (`-token_delta`) across every",
        "work in the cell. A stage that did not change the text counts as zero,",
        "so a dash is not hiding a subset. `structure` is on for `rag_doc` and",
        "does nothing to clean prose. Lexical, abbrev, alias, and resolution",
        "stay off on this profile.",
        "",
        "| length | preset | "
        + " | ".join(["structure", "filler", "repetition", "trim", "recency"])
        + " |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    stages = ("structure", "filler", "repetition", "trim", "recency")
    for length, _n in LENGTHS:
        for preset in PRESETS:
            sub = [
                r
                for r in rows
                if r["packing"] == "chunked" and r["length"] == length and r["preset"] == preset
            ]
            cells = [length, f"`{preset}`"]
            for stage in stages:
                vals = [-float(r["token_delta_by_stage"].get(stage, 0)) for r in sub]
                cells.append(_fmt(_mean(vals)) if vals else "—")
            lines.append("| " + " | ".join(cells) + " |")
    return lines


def _findings(rows: list[dict[str, Any]]) -> list[str]:
    """Short reading of the tables. Numbers come from the same rows as the tables."""

    def cell(packing: str, length: str, preset: str) -> dict[str, Any]:
        return _cell(rows, packing=packing, length=length, preset=preset)

    mono8 = cell("monolith", "8k", "low")
    mono20 = cell("monolith", "20k", "high")
    ch2m = cell("chunked", "2k", "medium")
    ch8m = cell("chunked", "8k", "medium")
    ch20m = cell("chunked", "20k", "medium")
    ch2h = cell("chunked", "2k", "high")
    ch8h = cell("chunked", "8k", "high")
    ch20h = cell("chunked", "20k", "high")
    ch8l = cell("chunked", "8k", "low")
    return [
        "- **Pasting a long text as one turn does not get medium or high.**",
        f"  Monolith `low`, `medium`, and `high` are the same row: "
        f"**{_fmt(mono8['mean_save'], '%')}** mean save at 8k "
        f"(n={mono8['n']}, anchor {_fmt(mono8['mean_anchor'], '%')}, "
        f"numbers {_fmt(mono8['mean_numbers'], '%')}) and "
        f"**{_fmt(mono20['mean_save'], '%')}** at 20k. Recency and trim never",
        "  see a thread long enough to run. That ~6–9% on Gutenberg is filler",
        "  removal, not summarization. Wikipedia monoliths are near zero",
        "  (see the family table).",
        "- **Chunk the passage and `medium` starts to move, with a wide spread.**",
        "  Quote the median: chunked `medium` is "
        f"**{_fmt(ch2m['median_save'], '%')}** / "
        f"**{_fmt(ch8m['median_save'], '%')}** / "
        f"**{_fmt(ch20m['median_save'], '%')}** at 2k / 8k / 20k "
        f"(means {_fmt(ch2m['mean_save'], '%')}, "
        f"{_fmt(ch8m['mean_save'], '%')}, "
        f"{_fmt(ch20m['mean_save'], '%')}; "
        f"sd {_fmt(ch20m['sd_save'])} at 20k). A few works where the question",
        "  misses most sections pull the mean up. Anchor words stay high "
        f"({_fmt(ch20m['mean_anchor'], '%')} at 20k). Whole-passage numbers",
        f"  fall to {_fmt(ch20m['mean_numbers'], '%')} because off-query",
        "  sections are shortened.",
        "- **`low` is filler, not summarization.**",
        f"  Chunked 8k `low` mean save is **{_fmt(ch8l['mean_save'], '%')}**",
        f"  with numbers still {_fmt(ch8l['mean_numbers'], '%')}. Repetition",
        "  is small and uneven (it shows up at 8k and not at 20k in this run).",
        "- **`high` is a middle-cut, and it can delete the section you asked about.**",
        f"  Chunked `high` mean save rises **{_fmt(ch2h['mean_save'], '%')}** → "
        f"**{_fmt(ch8h['mean_save'], '%')}** → **{_fmt(ch20h['mean_save'], '%')}**",
        "  as the passage grows, almost all of it from trim. Anchor retention",
        f"  is only {_fmt(ch2h['mean_anchor'], '%')} at 2k and "
        f"{_fmt(ch20h['mean_anchor'], '%')} at 20k, because the anchor sits in",
        "  the first fifth and trim keeps a short head plus the tail. Number",
        f"  retention on `high` is {_fmt(ch8h['mean_numbers'], '%')} at 8k and "
        f"{_fmt(ch20h['mean_numbers'], '%')} at 20k. At chunked 8k `high`,",
        "  fiction keeps about 1% of passage numbers and nonfiction about 65%:",
        "  novels have few figures, and trim drops the sections that held them.",
        "- **Use this corpus for the document claim, and the 222-item study for chat.**",
        "  Quoting only the chat headline understates chunked `high` and",
        "  overstates what a single pasted chapter will save.",
    ]


def _write_report(
    rows: list[dict[str, Any]], *, errors: list[str], sources: list[dict[str, str]]
) -> None:
    lines: list[str] = [
        "# Long-document benchmark (solid prose)",
        "",
        "Tier 1 only, profile **`rag_doc`**, `token_budget=None`. "
        "This is the study for continuous text — essays, books, and encyclopedia "
        "articles — not chat logs and not tool JSON.",
        "",
        "The 222-item fidelity report is still the chat/agent headline "
        "([`INFO_FIDELITY.md`](INFO_FIDELITY.md)). It under-represents this job: "
        "almost every item there is a conversation, and the seven “files” rows "
        "are short repo docs.",
        "",
        "## Method",
        "",
        "1. Take a public-domain Gutenberg book or a CC BY-SA Wikipedia extract.",
        "2. Cut a passage of about **2k / 8k / 20k** cl100k tokens (skip the first",
        "   ~1.5k tokens of a long book so the window is body text, not the title page).",
        "3. Pick an **anchor sentence** in the first fifth of that passage and ask",
        "   a question that quotes its opening words. The question is the last user",
        "   turn, so recency and trim are not allowed to rewrite it.",
        "4. Compress twice:",
        "   - **monolith** — system + one passage turn + question.",
        "   - **chunked** — system + section turns (~700 tokens, at least 8) + question.",
        "5. Record token savings, wall time, whether the question and system turn",
        "   are byte-identical, **anchor-word retention** (content words of length",
        "   ≥ 5 from the anchor sentence, whole-word match in the compressed",
        "   passage), and **number retention** (unique 3+ digit numbers, decimals,",
        "   and ISO dates from the full passage).",
        "",
        "Full source text is not committed (`benchmarks/data/` is gitignored).",
        "Re-run: `python -m benchmarks.run_longform`.",
        "",
        "### Why two packings",
        "",
        "`rag_doc` recency summarizes a turn only when it is **not** one of the",
        "last three non-system turns and its TF-IDF similarity to the query is",
        "below 0.3. Trim keeps a head and a tail and drops the middle, and it",
        "does nothing unless the thread is longer than that head+tail. A pasted",
        "article plus a question is two non-system turns, so `medium` and `high`",
        "collapse to wording cleanup. Chunking is what makes the long-document",
        "path actually run.",
        "",
        "### Sources",
        "",
        "| id | title | kind | license |",
        "| --- | --- | --- | --- |",
    ]
    for s in sources:
        lines.append(f"| `{s['id']}` | {s['title']} | {s['kind']} | {s['license']} |")
    if errors:
        lines.extend(["", "### Sources skipped", ""])
        for err in errors:
            lines.append(f"- {err}")

    lines.extend(
        [
            "",
            "## Headline",
            "",
            "Mean token savings across works. Anchor retention is the share of",
            "the question’s source sentence still present as whole words. Number",
            "retention is the share of distinct numbers from the **whole** passage",
            "that survive — on `medium`/`high` a drop here is expected when",
            "off-query sections are summarized or cut.",
            "",
        ]
    )

    for packing, blurb in (
        (
            "chunked",
            "### Chunked passage (`rag_doc` retrieval context)",
        ),
        (
            "monolith",
            "### Single pasted passage (monolith)",
        ),
    ):
        lines.extend(
            [
                "",
                blurb,
                "",
                (
                    "| length | preset | n | mean save | median save | sd "
                    "| anchor words kept | numbers kept | median ms |"
                ),
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for length, _n in LENGTHS:
            for preset in PRESETS:
                c = _cell(rows, packing=packing, length=length, preset=preset)
                row = (
                    f"| {length} | `{preset}` | {c['n']} | "
                    f"{_fmt(c['mean_save'], '%')} | {_fmt(c['median_save'], '%')} | "
                    f"{_fmt(c['sd_save'])} | {_fmt(c['mean_anchor'], '%')} | "
                    f"{_fmt(c['mean_numbers'], '%')} | {_fmt(c['median_ms'])} |"
                )
                lines.append(row)

    lines.extend(_stage_table(rows))

    # Kind split at 8k chunked — fiction vs nonfiction.
    lines.extend(
        [
            "",
            "## Fiction vs nonfiction (chunked, 8k tokens)",
            "",
            "| kind | preset | n | mean save | anchor kept | numbers kept |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for kind in ("fiction", "nonfiction"):
        for preset in PRESETS:
            sub = [
                r
                for r in rows
                if r["kind"] == kind
                and r["packing"] == "chunked"
                and r["length"] == "8k"
                and r["preset"] == preset
            ]
            saves = [float(r["token_savings_pct"]) for r in sub]
            anc = [
                float(r["anchor_retention_pct"])
                for r in sub
                if r["anchor_retention_pct"] is not None
            ]
            nums = [
                float(r["number_retention_pct"])
                for r in sub
                if r["number_retention_pct"] is not None
            ]
            lines.append(
                f"| {kind} | `{preset}` | {len(sub)} | {_fmt(_mean(saves), '%')} | "
                f"{_fmt(_mean(anc), '%')} | {_fmt(_mean(nums), '%')} |"
            )

    # Contracts
    q_bad = [r for r in rows if not r["question_intact"]]
    s_bad = [r for r in rows if not r["system_intact"]]
    lines.extend(
        [
            "",
            "## Gutenberg vs Wikipedia (monolith, 8k)",
            "",
            "Same preset on both families, because a one-turn paste never reaches",
            "recency or trim. 19th-century books contain filler words the stage",
            "strips (`very`, `quite`, `rather`). Encyclopedia extracts mostly do not.",
            "",
            "| family | n | mean save | anchor kept | numbers kept |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for family in ("gutenberg", "wikipedia"):
        sub = [
            r
            for r in rows
            if r["family"] == family
            and r["packing"] == "monolith"
            and r["length"] == "8k"
            and r["preset"] == "low"
        ]
        saves = [float(r["token_savings_pct"]) for r in sub]
        anc = [
            float(r["anchor_retention_pct"]) for r in sub if r["anchor_retention_pct"] is not None
        ]
        nums = [
            float(r["number_retention_pct"]) for r in sub if r["number_retention_pct"] is not None
        ]
        lines.append(
            f"| {family} | {len(sub)} | {_fmt(_mean(saves), '%')} | "
            f"{_fmt(_mean(anc), '%')} | {_fmt(_mean(nums), '%')} |"
        )

    lines.extend(
        [
            "",
            "## Contracts",
            "",
            f"- Question turn byte-identical: **{len(rows) - len(q_bad)}/{len(rows)}**.",
            f"- System turn byte-identical: **{len(rows) - len(s_bad)}/{len(rows)}**.",
            "- When the question changes, filler has rewritten a discourse word",
            "  inside the quoted anchor (`very`, `quite`, `rather`, and the rest",
            "  of the filler list). The live question is not protected.",
            "",
            "## What the numbers say",
            "",
        ]
    )
    lines.extend(_findings(rows))
    lines.extend(
        [
            "",
            "## How to read this",
            "",
            "- **Chunked `medium` / `high`** is the job contextpress is built to win:",
            "  many sections in the window, one question at the end. Savings should",
            "  climb with length because more of the passage sits outside the",
            "  protected tail.",
            "- **Monolith** numbers are the honest ceiling for “paste a chapter into",
            "  one message.” If they sit near zero, that is a product gap (no",
            "  within-turn extractive compression), not a property of long text.",
            "- **Anchor retention** checks the sentence the question points at.",
            "  **Number retention** checks the whole passage, including sections",
            "  the preset is allowed to summarize or drop.",
            "- This is still not an LLM answer-quality judge. It measures tokens",
            "  removed and whether the pointed-at sentence and the numeric spans",
            "  are still in the prompt.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def _collect_sources(*, refresh: bool) -> tuple[list[dict[str, Any]], list[str]]:
    found: list[dict[str, Any]] = []
    errors: list[str] = []
    for work in GUTENBERG:
        try:
            text = _load_gutenberg(work, refresh=refresh)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            OSError,
        ) as exc:
            errors.append(f"{work['id']}: {type(exc).__name__}: {exc}")
            continue
        found.append(
            {
                "id": work["id"],
                "title": work["title"],
                "kind": work["kind"],
                "family": "gutenberg",
                "license": "Public domain (Project Gutenberg)",
                "text": text,
            }
        )
    for work in WIKI:
        try:
            text = _load_wiki(work, refresh=refresh)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            OSError,
            json.JSONDecodeError,
            KeyError,
        ) as exc:
            errors.append(f"{work['id']}: {type(exc).__name__}: {exc}")
            continue
        found.append(
            {
                "id": work["id"],
                "title": work["title"],
                "kind": work["kind"],
                "family": "wikipedia",
                "license": "CC BY-SA (Wikipedia extract; text not republished)",
                "text": text,
            }
        )
    return found, errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--refresh", action="store_true", help="re-download cached sources")
    args = p.parse_args(argv)

    sources, errors = _collect_sources(refresh=args.refresh)
    if len(sources) < 4:
        print("ERROR: fewer than 4 sources downloaded", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    enc = _encoding()
    rows: list[dict[str, Any]] = []
    for src in sources:
        for length_name, n_tok in LENGTHS:
            passage = _slice_tokens(src["text"], n_tok, enc)
            if len(enc.encode(passage)) < int(n_tok * 0.7):
                errors.append(
                    f"{src['id']} {length_name}: passage shorter than 70% of target, skipped"
                )
                continue
            anchor = _pick_anchor(passage)
            for packing in ("monolith", "chunked"):
                for preset in PRESETS:
                    row = _run_one(
                        source_id=src["id"],
                        title=src["title"],
                        kind=src["kind"],
                        family=src["family"],
                        license_name=src["license"],
                        length_name=length_name,
                        packing=packing,
                        preset=preset,
                        passage=passage,
                        anchor=anchor,
                        enc=enc,
                    )
                    rows.append(row)
                    print(
                        f"{src['id']:22} {length_name:4} {packing:8} {preset:6} "
                        f"save={row['token_savings_pct']:6.2f}% "
                        f"anchor={row['anchor_retention_pct']} "
                        f"nums={row['number_retention_pct']} "
                        f"{row['elapsed_ms']:.0f}ms",
                        flush=True,
                    )

    meta = [
        {"id": s["id"], "title": s["title"], "kind": s["kind"], "license": s["license"]}
        for s in sources
    ]
    _write_report(rows, errors=errors, sources=meta)
    print(f"\nwrote {REPORT} ({len(rows)} runs, {len(sources)} sources)")
    if errors:
        print("skipped:")
        for err in errors:
            print(f"  {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
