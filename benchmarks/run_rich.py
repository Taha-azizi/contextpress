"""Richer long-document study. Does not change the package version.

``LONGFORM.md`` is 12 works, one question in the first fifth, and two loss
checks. This run adds domains, question position, weighted fact loss, and
whether the sentences that match the question survive.

Full text stays in ``benchmarks/data/`` (gitignored). Aggregates go to
``benchmarks/RICH.md``.

Usage::

    python -m benchmarks.run_rich
"""

from __future__ import annotations

import argparse
import random
import re
import statistics
import sys
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
REPORT = ROOT / "RICH.md"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.facts import (  # noqa: E402
    FILLER_TOKENS,
    fact_adjusted,
    names,
    names_kept,
    pooled_loss,
)
from benchmarks.run_longform import (  # noqa: E402
    _NUM,
    _body_text,
    _content_words,
    _encoding,
    _load_gutenberg,
    _load_wiki,
    _messages,
    _question,
    _sentences,
    _slice_tokens,
    _whole_word_hits,
)
from contextpress import ContextManager, __version__  # noqa: E402
from contextpress.text_sim import tfidf_query_scores  # noqa: E402

LENGTHS: tuple[tuple[str, int], ...] = (
    ("4k", 4_000),
    ("8k", 8_000),
    ("16k", 16_000),
    ("32k", 32_000),
)
PRESETS = ("low", "medium", "high")
POSITIONS: tuple[tuple[str, float], ...] = (
    ("early", 0.15),
    ("middle", 0.50),
    ("late", 0.85),
)
_WS = re.compile(r"\s+")

# gid / wiki title. Domain is the reporting bucket, not the profile.
SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "austen-pnp", "gid": 1342, "title": "Pride and Prejudice", "domain": "fiction"},
    {"id": "shelley-frank", "gid": 84, "title": "Frankenstein", "domain": "fiction"},
    {"id": "melville-moby", "gid": 2701, "title": "Moby-Dick", "domain": "fiction"},
    {"id": "dickens-cities", "gid": 98, "title": "A Tale of Two Cities", "domain": "fiction"},
    {"id": "wells-worlds", "gid": 36, "title": "The War of the Worlds", "domain": "fiction"},
    {"id": "darwin-origin", "gid": 1228, "title": "On the Origin of Species", "domain": "science"},
    {"id": "darwin-descent", "gid": 2300, "title": "The Descent of Man", "domain": "science"},
    {
        "id": "russell-problems",
        "gid": 5827,
        "title": "The Problems of Philosophy",
        "domain": "philosophy",
    },
    {"id": "aurelius-meditations", "gid": 2680, "title": "Meditations", "domain": "philosophy"},
    {"id": "thoreau-walden", "gid": 205, "title": "Walden", "domain": "essay"},
    {
        "id": "douglass-narrative",
        "gid": 23,
        "title": "Narrative of Frederick Douglass",
        "domain": "history",
    },
    {"id": "dubois-souls", "gid": 408, "title": "The Souls of Black Folk", "domain": "history"},
    {"id": "smith-wealth", "gid": 3300, "title": "The Wealth of Nations", "domain": "politics"},
    {"id": "machiavelli-prince", "gid": 1232, "title": "The Prince", "domain": "politics"},
    {"id": "mill-liberty", "gid": 34901, "title": "On Liberty", "domain": "politics"},
    {"id": "hobbes-leviathan", "gid": 3207, "title": "Leviathan", "domain": "politics"},
    {"id": "federalist", "gid": 1404, "title": "The Federalist Papers", "domain": "politics"},
    {"id": "wiki-french-rev", "title": "French Revolution", "domain": "history"},
    {"id": "wiki-roman", "title": "Roman Empire", "domain": "history"},
    {"id": "wiki-civil-war", "title": "American Civil War", "domain": "history"},
    {"id": "wiki-ww2", "title": "World War II", "domain": "history"},
    {"id": "wiki-industrial", "title": "Industrial Revolution", "domain": "history"},
    {"id": "wiki-byzantine", "title": "Byzantine Empire", "domain": "history"},
    {"id": "wiki-constitution", "title": "United States Constitution", "domain": "politics"},
    {"id": "wiki-dna", "title": "DNA", "domain": "science"},
    {"id": "wiki-photosynthesis", "title": "Photosynthesis", "domain": "science"},
    {"id": "wiki-evolution", "title": "Evolution", "domain": "science"},
    {"id": "wiki-quantum", "title": "Quantum mechanics", "domain": "science"},
    {"id": "wiki-tectonics", "title": "Plate tectonics", "domain": "science"},
    {"id": "wiki-black-hole", "title": "Black hole", "domain": "science"},
    {"id": "wiki-periodic", "title": "Periodic table", "domain": "science"},
)


def _pick_at(text: str, frac: float) -> str:
    sents = [s for s in _sentences(text) if 90 <= len(s) <= 320 and len(_content_words(s)) >= 6]
    if not sents:
        sents = [s for s in _sentences(text) if len(s) >= 60] or [text[:240].strip()]
    idx = min(len(sents) - 1, max(0, int(round(frac * (len(sents) - 1)))))
    return sents[idx]


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _weighted(rows: list[dict[str, Any]], num: str, den: str) -> float | None:
    top = sum(int(r[num]) for r in rows)
    bottom = sum(int(r[den]) for r in rows)
    if bottom <= 0:
        return None
    return round(100.0 * top / bottom, 1)


def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 1) if xs else None


def _ci(xs: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 2:
        return None, None
    rng = random.Random(0)
    n = len(xs)
    means = []
    for _ in range(2000):
        draw = [xs[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(draw))
    means.sort()
    lo = means[int(0.025 * (len(means) - 1))]
    hi = means[int(0.975 * (len(means) - 1))]
    return round(lo, 1), round(hi, 1)


def _fmt(v: float | None, suffix: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:.1f}{suffix}"


def _ci_fmt(xs: list[float]) -> str:
    lo, hi = _ci(xs)
    if lo is None:
        return "—"
    return f"{lo:.1f}–{hi:.1f}"


def _run(
    *,
    src: dict[str, Any],
    passage: str,
    length: str,
    position: str,
    packing: str,
    preset: str,
    enc: Any,
) -> dict[str, Any]:
    anchor = _pick_at(passage, dict(POSITIONS)[position])
    question = _question(anchor)
    messages = _messages(passage, question, packing=packing, enc=enc)
    cm = ContextManager(type="rag_doc", compression=preset)
    result = cm.compress(messages, token_budget=None, return_stats=True)
    result.stats.attach_cost(provider="openai", model="gpt-4o-mini")
    body = _body_text(result.messages, question)
    words = [w for w in _content_words(anchor) if w not in FILLER_TOKENS]
    nums = list(dict.fromkeys(_NUM.findall(passage)))
    found_names = names(passage)
    sents = [s for s in _sentences(passage) if len(s) >= 40]
    scores = tfidf_query_scores(question, sents) if sents else []
    norm_body = _norm(body)
    rel_idx = [i for i, s in enumerate(scores) if s >= 0.3]
    irrel_idx = [i for i, s in enumerate(scores) if s < 0.3]

    def _alive(idxs: list[int]) -> int:
        return sum(1 for i in idxs if _norm(sents[i]) in norm_body)

    q_out = ""
    for message in reversed(result.messages):
        if message.get("role") == "user":
            q_out = str(message.get("content") or "")
            break
    return {
        "id": src["id"],
        "title": src["title"],
        "domain": src["domain"],
        "length": length,
        "position": position,
        "packing": packing,
        "preset": preset,
        "token_savings_pct": float(result.stats.token_savings_pct),
        "usd_saved": float(result.stats.estimated_cost_saved_usd or 0.0),
        "anchor_words": len(words),
        "anchor_retained": _whole_word_hits(words, body),
        "numbers_total": len(nums),
        "numbers_retained": sum(1 for n in nums if n in body),
        "names_total": len(found_names),
        "names_retained": names_kept(found_names, body),
        "sents_total": len(sents),
        "sents_kept": _alive(list(range(len(sents)))),
        "rel_total": len(rel_idx),
        "rel_kept": _alive(rel_idx),
        "irrel_total": len(irrel_idx),
        "irrel_kept": _alive(irrel_idx),
        "question_intact": q_out == question,
    }


def _subset(rows: list[dict[str, Any]], **kw: str) -> list[dict[str, Any]]:
    out = rows
    for key, val in kw.items():
        out = [r for r in out if r[key] == val]
    return out


def _public(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r["domain"] != "synthetic"]


_FACT_PAIRS = (
    ("anchor_retained", "anchor_words"),
    ("numbers_retained", "numbers_total"),
    ("names_retained", "names_total"),
)


def _info_loss_raw(rows: list[dict[str, Any]]) -> float | None:
    return pooled_loss(rows, _FACT_PAIRS)


def _info_loss(rows: list[dict[str, Any]]) -> float | None:
    raw = _info_loss_raw(rows)
    if raw is None:
        return None
    return round(raw, 1)


def _combo_of(rows: list[dict[str, Any]]) -> float | None:
    """``mean token save − pooled information loss``."""
    if not rows:
        return None
    loss = _info_loss_raw(rows)
    if loss is None:
        return None
    save = statistics.fmean(float(r["token_savings_pct"]) for r in rows)
    return fact_adjusted(save, loss)


def _combo_ci(rows: list[dict[str, Any]]) -> str:
    if len(rows) < 2:
        return "—"
    rng = random.Random(0)
    n = len(rows)
    vals: list[float] = []
    for _ in range(2000):
        draw = [rows[rng.randrange(n)] for _ in range(n)]
        val = _combo_of(draw)
        if val is not None:
            vals.append(val)
    if len(vals) < 2:
        return "—"
    vals.sort()
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(0.975 * (len(vals) - 1))]
    return f"{lo:.1f}–{hi:.1f}"


def _trio(row: dict[str, Any]) -> str:
    """One work: token save / information loss / adjusted save."""
    return (
        f"{float(row['token_savings_pct']):.1f}% / {_fmt(_info_loss([row]), '%')} / "
        f"{_fmt(_combo_of([row]), '%')}"
    )


def _kpi(rows: list[dict[str, Any]], *, ci: bool = False) -> str:
    """Token save, information loss, and adjusted save, in that order."""
    saves = [float(r["token_savings_pct"]) for r in rows]
    parts = [
        _fmt(_mean(saves), "%"),
        _fmt(_info_loss(rows), "%"),
        _fmt(_combo_of(rows), "%"),
    ]
    if ci:
        parts = [parts[0], _ci_fmt(saves), parts[1], parts[2], _combo_ci(rows)]
    return " | ".join(parts)


def _cell_line(rows: list[dict[str, Any]]) -> str:
    return (
        f"{len(rows)} | {_kpi(rows, ci=True)} | "
        f"{_fmt(_weighted(rows, 'anchor_retained', 'anchor_words'), '%')} | "
        f"{_fmt(_weighted(rows, 'numbers_retained', 'numbers_total'), '%')} | "
        f"{_fmt(_weighted(rows, 'names_retained', 'names_total'), '%')}"
    )


def _write(rows: list[dict[str, Any]], sources: list[dict[str, str]], errors: list[str]) -> None:
    pub = _public(rows)
    lines = [
        "# Rich long-document benchmark",
        "",
        f"Measured with the working tree of contextpress **{__version__}**. "
        "This file does not bump the package version.",
        "",
        "[`LONGFORM.md`](LONGFORM.md) is the smaller gate study: 12 works, one "
        "question in the first fifth, anchor words and numbers. This study is "
        "the broader cut.",
        "",
        "## What is richer",
        "",
        "- More works, split into fiction, science, history, politics, philosophy, and essays.",
        "- Lengths **4k, 8k, 16k, and 32k** tokens (cl100k), not only 2k/8k/20k.",
        "- The question is planted **early, in the middle, and late**.",
        "  The main grid uses the middle.",
        "- Every table reports three numbers together: token save, information",
        "  loss, and adjusted save.",
        "- Save means and adjusted save means have a percentile bootstrap 95%",
        "  interval across works (2,000 resamples, seed 0).",
        "",
        "Profile `rag_doc`, `token_budget=None`, no LLM. Full text is not committed.",
        "Re-run: `python -m benchmarks.run_rich`.",
        "",
        "## The three KPIs",
        "",
        "Critical facts are pooled, not averaged as percents: content words from "
        "the asked sentence, distinct numbers (3+ digits, decimals, ISO dates), "
        "and distinct two-word names on the same line (`Elizabeth Bennet`). "
        "Filler words the `low` preset removes (`pretty`, `absolutely`) are "
        "not facts. A line break does not glue two capitalized words into a "
        "name. Ordinary sentences that are not one of those facts are allowed "
        "to go. Dropping them is the compression, not the information loss.",
        "",
        "| KPI | Meaning | Better |",
        "| --- | --- | --- |",
        "| **Token save** | Percent of input tokens removed. | Higher |",
        "| **Information loss** | Percent of critical facts no longer in the passage. "
        "Counts are pooled across works. | Lower |",
        "| **Adjusted save** | `token save − information loss`. Can be negative. | Higher |",
        "",
        "A point of critical-fact loss cancels a point of token save. "
        "A 6% save that loses 2% of facts scores 4. A 57% save that loses "
        "49% of facts scores 8. A cut that loses more facts than tokens "
        "scores below zero.",
        "",
        "### Sources used",
        "",
        "| id | title | domain |",
        "| --- | --- | --- |",
    ]
    for src in sources:
        lines.append(f"| `{src['id']}` | {src['title']} | {src['domain']} |")
    if errors:
        lines.extend(["", "### Skipped", ""])
        for err in errors:
            lines.append(f"- {err}")

    header = (
        "| length | preset | n | token save | save CI | info loss | "
        "adjusted save | adj. CI | anchor kept | numbers kept | names kept |"
    )
    rule = "| --- | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: |"
    for packing, title in (
        ("chunked", "## Chunked passage, question in the middle"),
        ("monolith", "## Pasted passage, question in the middle"),
    ):
        lines.extend(["", title, "", header, rule])
        for length, _n in LENGTHS:
            for preset in PRESETS:
                sub = _subset(pub, packing=packing, length=length, position="middle", preset=preset)
                if not sub:
                    continue
                lines.append(f"| {length} | `{preset}` | {_cell_line(sub)} |")

    lines.extend(
        [
            "",
            "## Question position (8k tokens)",
            "",
            "Early is the first fifth. Late is near the end, which for a chunked "
            "thread sits in the tail trim is not allowed to drop. Middle is the "
            "harder case.",
            "",
            "| packing | position | preset | n | token save | info loss | adjusted save |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for packing in ("chunked", "monolith"):
        for position, _frac in POSITIONS:
            for preset in PRESETS:
                sub = _subset(pub, packing=packing, length="8k", position=position, preset=preset)
                if not sub:
                    continue
                lines.append(
                    f"| {packing} | {position} | `{preset}` | {len(sub)} | {_kpi(sub)} |"
                )

    lines.extend(
        [
            "",
            "## Domain (chunked, 8k, question in the middle)",
            "",
            "| domain | preset | n | token save | info loss | adjusted save |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    domains = sorted({r["domain"] for r in pub})
    for domain in domains:
        for preset in PRESETS:
            sub = [
                r
                for r in pub
                if r["domain"] == domain
                and r["packing"] == "chunked"
                and r["length"] == "8k"
                and r["position"] == "middle"
                and r["preset"] == preset
            ]
            if not sub:
                continue
            lines.append(
                f"| {domain} | `{preset}` | {len(sub)} | {_kpi(sub)} |"
            )

    lines.extend(
        [
            "",
            "## Each work at 8k, question in the middle",
            "",
            "Each cell is **token save / information loss / adjusted save**.",
            "",
            "| work | domain | chunked low | chunked medium | chunked high | pasted medium |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    ids = sorted({r["id"] for r in pub})
    for sid in ids:
        def one(packing: str, preset: str, work: str = sid) -> dict[str, Any] | None:
            hit = _subset(
                pub,
                packing=packing,
                preset=preset,
                id=work,
                length="8k",
                position="middle",
            )
            return hit[0] if hit else None

        low = one("chunked", "low")
        med = one("chunked", "medium")
        high = one("chunked", "high")
        paste = one("monolith", "medium")
        if not low or not med or not high or not paste:
            continue
        lines.append(
            f"| `{sid}` | {low['domain']} | {_trio(low)} | {_trio(med)} | "
            f"{_trio(high)} | {_trio(paste)} |"
        )

    usd_rows = _subset(pub, packing="chunked", length="8k", position="middle", preset="high")
    usd = sum(float(r["usd_saved"]) for r in usd_rows)
    q_bad = [r for r in pub if not r["question_intact"]]
    lines.extend(
        [
            "",
            "## Notes",
            "",
            f"- Question turn byte-identical: **{len(pub) - len(q_bad)}/{len(pub)}** public runs.",
            f"- Approximate gpt-4o-mini input dollars saved on chunked 8k `high`, "
            f"summed across {len(usd_rows)} works: **${usd:.4f}**.",
            "- At 4k–16k, `low` is filler: about 5–9% saved, numbers nearly all kept.",
            "  At 32k chunked, `low` jumps because repetition drops near-duplicate",
            "  sections in long books. Most Wikipedia extracts were shorter than",
            "  32k and are not in that row.",
            "- Pasted `medium` / `high` cut inside the single turn (0.7.3). "
            "Chunked `high` drops other sections and keeps the one that matches "
            "the question (0.7.4).",
            "- A synthetic control is not mixed into the tables above.",
            "",
        ]
    )
    synth = [r for r in rows if r["domain"] == "synthetic"]
    if synth:
        lines.extend(
            [
                "## Synthetic control (8k technical prose, middle question)",
                "",
                "Repeated module sentences with a unique figure in each, plus one "
                "asked sentence. Not a published book.",
                "",
                "| packing | preset | token save | info loss | adjusted save |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for packing in ("chunked", "monolith"):
            for preset in PRESETS:
                hit = _subset(synth, packing=packing, preset=preset)
                if not hit:
                    continue
                lines.append(f"| {packing} | `{preset}` | {_kpi(hit)} |")
        lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def _rate(row: dict[str, Any], num: str, den: str) -> float | None:
    if int(row[den]) <= 0:
        return None
    return round(100.0 * int(row[num]) / int(row[den]), 1)


def _synthetic() -> str:
    parts: list[str] = []
    for i in range(420):
        if i == 210:
            parts.append(
                "The brass sextant showed a bearing of 214 degrees toward "
                "the island of Zephyra during survey 1859."
            )
        else:
            parts.append(
                f"Module {i} records valve pressure {1000 + i} kilopascals "
                f"during cycle {1800 + i} after the coolant loop at station {i} stabilizes."
            )
    return " ".join(parts)


def _load_sources(*, refresh: bool) -> tuple[list[dict[str, Any]], list[str]]:
    found: list[dict[str, Any]] = []
    errors: list[str] = []
    for spec in SOURCES:
        try:
            if "gid" in spec:
                text = _load_gutenberg(spec, refresh=refresh)
                license_name = "Public domain (Project Gutenberg)"
            else:
                text = _load_wiki(spec, refresh=refresh)
                license_name = "CC BY-SA (Wikipedia extract; text not republished)"
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            OSError,
        ) as exc:
            errors.append(f"{spec['id']}: {type(exc).__name__}: {exc}")
            continue
        found.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "domain": spec["domain"],
                "license": license_name,
                "text": text,
            }
        )
    return found, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    sources, errors = _load_sources(refresh=args.refresh)
    if len(sources) < 8:
        print("ERROR: fewer than 8 sources", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    enc = _encoding()
    rows: list[dict[str, Any]] = []

    def add(src: dict[str, Any], passage: str, length: str, position: str) -> None:
        for packing in ("monolith", "chunked"):
            for preset in PRESETS:
                row = _run(
                    src=src,
                    passage=passage,
                    length=length,
                    position=position,
                    packing=packing,
                    preset=preset,
                    enc=enc,
                )
                rows.append(row)
                print(
                    f"{src['id']:22} {length:4} {position:6} {packing:8} {preset:6} "
                    f"save={row['token_savings_pct']:6.1f}% "
                    f"anchor={_rate(row, 'anchor_retained', 'anchor_words')} "
                    f"nums={_rate(row, 'numbers_retained', 'numbers_total')}",
                    flush=True,
                )

    for src in sources:
        for length, n_tok in LENGTHS:
            if len(enc.encode(src["text"])) < int(n_tok * 0.7):
                errors.append(f"{src['id']} {length}: source shorter than 70% of target")
                continue
            passage = _slice_tokens(src["text"], n_tok, enc)
            if len(enc.encode(passage)) < int(n_tok * 0.7):
                errors.append(f"{src['id']} {length}: window shorter than 70% of target")
                continue
            for position, _frac in POSITIONS:
                if length != "8k" and position != "middle":
                    continue
                add(src, passage, length, position)

    synthetic = {
        "id": "synthetic-modules",
        "title": "Synthetic technical modules",
        "domain": "synthetic",
        "license": "generated for this study",
        "text": _synthetic(),
    }
    window = _slice_tokens(synthetic["text"], 8_000, enc)
    add(synthetic, window, "8k", "middle")

    meta = [{"id": s["id"], "title": s["title"], "domain": s["domain"]} for s in sources]
    _write(rows, meta, errors)
    print(f"\nwrote {REPORT} ({len(rows)} runs, {len(sources)} public sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
