"""Quantify token savings vs information loss for Tier-1 presets.

Method (deterministic, no LLM, no new deps):

1. **Critical fact retention** (headline "information loss") —
   Extract high-signal factoids from *non-system* turns: URLs, emails, file
   paths, versions / decimals / 3+ digit numbers, ISO dates, ``snake_case``
   / ``CamelCase`` identifiers. After compression, count how many still
   appear as whole tokens (not substrings). Skip quotes and 1–2 digit
   integers — those were discourse false positives.

   ``critical_info_loss_pct = 100 * (1 - retained / total)``

   The number to quote is **weighted** loss (by fact count), not the
   unweighted mean of chats (a 1-span miss otherwise equals dropping 30 IDs).

2. **TF-IDF soft loss** — bulk wording / deleted turns
   ``soft_info_loss_pct = 100 * (1 - cosine)``. This moves when filler
   rewrites hedges even if every ID survives.

3. **Contract checks** — system prompt unchanged; last-user keywords present.

Usage::

    python -m benchmarks.info_fidelity
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RESULTS = ROOT / "results"
REPORT = ROOT / "INFO_FIDELITY.md"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.corpus import load_corpus  # noqa: E402
from contextpress import ContextManager  # noqa: E402
from contextpress.text_sim import tfidf_cosine  # noqa: E402

PRESETS = ("low", "medium", "high")

_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_FILE = re.compile(
    r"\b[\w./\\-]+\.(?:py|json|md|txt|yml|yaml|toml|js|ts|tsx|jsx|go|rs|java|c|cpp|h)\b",
    re.IGNORECASE,
)
# Versions (2.4.1), decimals (3.14), ISO dates, integers with 3+ digits.
# Two-digit integers (10, 20) are too often list indexes / round numbers.
_NUM = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|" r"\b\d+\.\d+(?:\.\d+)*\b|" r"\b\d{3,}\b")
_SNAKE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
_CAMEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b")
_WORD = re.compile(r"[A-Za-z]{5,}")
_TRAIL_PUNCT = re.compile(r"[.,;:)+]+$")
# Discourse / product names that CamelCase regex hits but are not thread facts.
_CAMEL_SKIP = frozenset(
    {
        "chatgpt",
        "openai",
        "youtube",
        "github",
        "javascript",
        "typescript",
        "postgresql",
        "mongodb",
        "graphql",
        "linkedin",
        "facebook",
        "whatsapp",
    }
)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    idx = (p / 100.0) * (len(ordered) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def _message_text(messages: list[dict[str, Any]], *, include_system: bool = True) -> str:
    parts: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or ""
        if not include_system and role == "system":
            continue
        content = m.get("content")
        if content is None and m.get("tool_calls"):
            content = json.dumps(m.get("tool_calls"), ensure_ascii=False)
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)
        parts.append(f"{role}: {content or ''}")
    return "\n".join(parts)


def _clean_span(span: str) -> str:
    return _TRAIL_PUNCT.sub("", (span or "").strip())


def extract_critical_spans(text: str) -> list[str]:
    """High-signal factoids: URLs, emails, paths, versions/large numbers, identifiers.

    Intentionally excludes short quotes and 1–2 digit integers — those were
    mostly filler/discourse false positives (``I'm sorry``, ``20``).
    """
    found: list[str] = []
    for pattern in (_URL, _EMAIL, _FILE, _NUM, _SNAKE, _CAMEL):
        found.extend(pattern.findall(text))
    seen: set[str] = set()
    out: list[str] = []
    for span in found:
        cleaned = _clean_span(span)
        key = cleaned.casefold()
        if len(key) < 2 or key in seen:
            continue
        if key in _CAMEL_SKIP:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _span_present(span: str, haystack_cf: str) -> bool:
    """True if ``span`` still occurs; digits cannot hide inside a longer number."""
    key = span.casefold()
    if not key:
        return False
    if "://" in key or "@" in key or "/" in key or "\\" in key:
        return key in haystack_cf
    # Allow hyphen neighbors (evt-001) but not 8080 inside 80800.
    return re.search(rf"(?<![0-9a-z]){re.escape(key)}(?![0-9a-z])", haystack_cf) is not None


def critical_retention(original: str, compressed: str) -> dict[str, Any]:
    spans = extract_critical_spans(original)
    if not spans:
        return {
            "critical_total": 0,
            "critical_retained": 0,
            "critical_retention_pct": 100.0,
            "critical_info_loss_pct": 0.0,
            "lost_examples": [],
        }
    blob = compressed.casefold()
    retained = 0
    lost: list[str] = []
    for span in spans:
        if _span_present(span, blob):
            retained += 1
        elif len(lost) < 5:
            lost.append(span)
    rate = retained / len(spans)
    return {
        "critical_total": len(spans),
        "critical_retained": retained,
        "critical_retention_pct": round(100.0 * rate, 2),
        "critical_info_loss_pct": round(100.0 * (1.0 - rate), 2),
        "lost_examples": lost,
    }


def contract_checks(
    original: list[dict[str, Any]], compressed: list[dict[str, Any]]
) -> dict[str, Any]:
    sys_in = next(
        (m.get("content") for m in original if isinstance(m, dict) and m.get("role") == "system"),
        None,
    )
    sys_out = next(
        (m.get("content") for m in compressed if isinstance(m, dict) and m.get("role") == "system"),
        None,
    )
    system_ok = True
    if isinstance(sys_in, str) and sys_in:
        system_ok = sys_out == sys_in

    last_user = None
    for m in reversed(original):
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            last_user = m["content"]
            break
    last_user_ok = True
    if last_user:
        keys = [w for w in _WORD.findall(last_user) if len(w) >= 5][:8]
        blob = _message_text(compressed, include_system=True).casefold()
        if keys:
            last_user_ok = any(k.casefold() in blob for k in keys)
    return {"system_unchanged": system_ok, "last_user_keywords_present": last_user_ok}


def evaluate_one(item: dict[str, Any], preset: str) -> dict[str, Any]:
    messages = item["messages"]
    cm = ContextManager(type=item["type"], model="gpt-4o-mini")
    before = cm.estimate_tokens(messages)
    result = cm.compress(messages, token_budget=None, compression=preset, return_stats=True)
    after = result.stats.tokens_after
    orig_text = _message_text(messages, include_system=True)
    orig_facts = _message_text(messages, include_system=False)
    comp_text = _message_text(result.messages, include_system=True)
    # Facts in the system prompt always survive; score only non-system content.
    crit = critical_retention(orig_facts, comp_text)
    cosine = tfidf_cosine(orig_text, comp_text)
    soft_loss = round(100.0 * (1.0 - cosine), 2)
    checks = contract_checks(messages, result.messages)
    saved = max(0, before - after)
    save_pct = round(100.0 * saved / before, 2) if before else 0.0
    return {
        "id": item["id"],
        "bucket": item["bucket"],
        "type": item["type"],
        "source": item["source"],
        "preset": preset,
        "tokens_before": before,
        "tokens_after": after,
        "token_savings_pct": save_pct,
        "tfidf_cosine": round(cosine, 4),
        "soft_info_loss_pct": soft_loss,
        **crit,
        **checks,
        "stages_run": list(result.stats.stages_run),
    }


def _agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def col(key: str) -> list[float]:
        return [float(r[key]) for r in rows]

    # Weighted critical loss by span count (items with more facts count more).
    w_loss = 0.0
    w_total = 0
    with_facts = [r for r in rows if int(r["critical_total"]) > 0]
    for r in with_facts:
        n = int(r["critical_total"])
        w_loss += float(r["critical_info_loss_pct"]) * n
        w_total += n
    weighted_critical_loss = round(w_loss / w_total, 2) if w_total else 0.0
    fact_loss = [float(r["critical_info_loss_pct"]) for r in with_facts]
    fact_ret = [float(r["critical_retention_pct"]) for r in with_facts]

    return {
        "n": len(rows),
        "n_with_critical_spans": len(with_facts),
        "mean_token_savings_pct": (
            round(statistics.fmean(col("token_savings_pct")), 2) if rows else None
        ),
        "median_token_savings_pct": _percentile(col("token_savings_pct"), 50),
        "mean_critical_info_loss_pct": (
            round(statistics.fmean(fact_loss), 2) if fact_loss else 0.0
        ),
        "median_critical_info_loss_pct": _percentile(fact_loss, 50) if fact_loss else 0.0,
        "weighted_critical_info_loss_pct": weighted_critical_loss,
        "mean_soft_info_loss_pct": (
            round(statistics.fmean(col("soft_info_loss_pct")), 2) if rows else None
        ),
        "median_soft_info_loss_pct": _percentile(col("soft_info_loss_pct"), 50),
        "mean_critical_retention_pct": (
            round(statistics.fmean(fact_ret), 2) if fact_ret else 100.0
        ),
        "system_ok_rate": (
            round(100.0 * sum(1 for r in rows if r["system_unchanged"]) / len(rows), 1)
            if rows
            else None
        ),
        "last_user_ok_rate": (
            round(
                100.0 * sum(1 for r in rows if r["last_user_keywords_present"]) / len(rows),
                1,
            )
            if rows
            else None
        ),
    }


def _fmt(v: float | None, digits: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}%"


def write_report(
    *,
    rows: list[dict[str, Any]],
    items: list[dict[str, Any]],
    elapsed_s: float,
) -> dict[str, Any]:
    by_preset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_preset[r["preset"]].append(r)

    chat_rows = [r for r in rows if r["bucket"] == "chat"]
    chat_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in chat_rows:
        chat_by[r["preset"]].append(r)

    summary = {
        "n_items": len(items),
        "n_runs": len(rows),
        "elapsed_s": round(elapsed_s, 2),
        "method": {
            "critical": (
                "Retention of numbers/versions, URLs, emails, file paths, "
                "snake_case/CamelCase ids, short quotes. "
                "loss = 100*(1 - retained/total)."
            ),
            "soft": "100*(1 - TF-IDF cosine) of full conversation text.",
        },
        "overall": {p: _agg(by_preset[p]) for p in PRESETS},
        "chat_only": {p: _agg(chat_by[p]) for p in PRESETS},
        "by_bucket": {},
    }
    for bucket in sorted({r["bucket"] for r in rows}):
        summary["by_bucket"][bucket] = {
            p: _agg([r for r in rows if r["bucket"] == bucket and r["preset"] == p])
            for p in PRESETS
        }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "info_fidelity_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    lines: list[str] = [
        "# Token savings vs information loss",
        "",
        "Deterministic fidelity study (no LLM judge). "
        f"**{len(items)}** items × **{len(PRESETS)}** presets = **{len(rows)}** runs "
        f"in **{elapsed_s:.0f}s**.",
        "",
        "## Method",
        "",
        "1. **Critical information loss** (headline) — extract factoids from "
        "non-system turns: URLs, emails, paths, versions/decimals/3+ digit "
        "numbers, ISO dates, `snake_case` / `CamelCase` ids. Retention uses "
        "token boundaries (so `10` does not count as kept inside `2010`). "
        "Quotes and 1–2 digit integers are excluded (too much discourse noise). "
        "`critical_info_loss_pct = 100 × (1 − retained/total)`. "
        "**Quote the weighted figure** (facts pooled across items).",
        "2. **Soft information loss** — `100 × (1 − TF-IDF cosine)` of the full "
        "thread (hedges, deleted turns, synonym swaps). Not the same as lost IDs.",
        "3. **Contract checks** — system prompt unchanged; last-user keywords present.",
        "",
        "Wording stages (`low`) should show **token save >> critical loss**. "
        "Recency (`medium`) may drop IDs in shortened older sentences. "
        "Trim (`high`) removes mid-thread turns.",
        "",
        "## Headline (all items)",
        "",
        "| preset | mean token save | mean **critical** info loss | "
        "weighted critical loss | mean soft info loss | critical retained |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for p in PRESETS:
        a = summary["overall"][p]
        lines.append(
            f"| `{p}` | {_fmt(a['mean_token_savings_pct'])} | "
            f"**{_fmt(a['mean_critical_info_loss_pct'])}** | "
            f"{_fmt(a['weighted_critical_info_loss_pct'])} | "
            f"{_fmt(a['mean_soft_info_loss_pct'])} | "
            f"{_fmt(a['mean_critical_retention_pct'])} |"
        )
    lines.extend(
        [
            "",
            "### Soundbite form",
            "",
            "Quote **mean token save** + **weighted critical loss** "
            "(facts pooled). Median is the typical chat.",
            "",
        ]
    )
    for p in PRESETS:
        a = summary["overall"][p]
        c = summary["chat_only"][p]
        preserve = 100.0 - float(a["weighted_critical_info_loss_pct"] or 0.0)
        lines.append(
            f"- **`{p}`**: about **{_fmt(a['mean_token_savings_pct'], 1)}** tokens saved, "
            f"**{_fmt(a['weighted_critical_info_loss_pct'], 1)}** critical-information "
            f"loss (**{preserve:.1f}%** of factoids retained). "
            f"Soft/bulk wording loss ≈ {_fmt(a['mean_soft_info_loss_pct'], 1)}."
        )
        lines.append(
            f"  - Chats: **{_fmt(c['mean_token_savings_pct'], 1)}** tokens saved, "
            f"**{_fmt(c['weighted_critical_info_loss_pct'], 1)}** weighted / "
            f"**{_fmt(c['median_critical_info_loss_pct'], 1)}** median critical loss."
        )

    lines.extend(
        [
            "",
            "## Chat-only (long threads — main product story)",
            "",
            "| preset | mean token save | mean critical loss | median critical loss | "
            "mean soft loss | system OK | last-user OK |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for p in PRESETS:
        a = summary["chat_only"][p]
        lines.append(
            f"| `{p}` | {_fmt(a['mean_token_savings_pct'])} | "
            f"**{_fmt(a['mean_critical_info_loss_pct'])}** | "
            f"{_fmt(a['median_critical_info_loss_pct'])} | "
            f"{_fmt(a['mean_soft_info_loss_pct'])} | "
            f"{a['system_ok_rate']}% | {a['last_user_ok_rate']}% |"
        )

    lines.extend(["", "## By bucket × preset (mean token save → **weighted** critical loss)", ""])
    lines.append("| bucket | n | low | medium | high |")
    lines.append("| --- | --- | --- | --- | --- |")
    for bucket, presets in summary["by_bucket"].items():
        n_items = presets["low"]["n"]
        cells = [bucket, str(n_items)]
        for p in PRESETS:
            a = presets[p]
            cells.append(
                f"{_fmt(a['mean_token_savings_pct'], 1)} → "
                f"{_fmt(a['weighted_critical_info_loss_pct'], 1)}"
            )
        lines.append("| " + " | ".join(cells) + " |")

    # Worst critical-loss chats at medium (illustrative)
    med_chat = sorted(
        [r for r in chat_rows if r["preset"] == "medium" and r["critical_total"] >= 5],
        key=lambda r: (-r["critical_info_loss_pct"], -r["token_savings_pct"]),
    )[:8]
    lines.extend(
        [
            "",
            "## Highest critical loss examples (`medium`, chats with ≥5 critical spans)",
            "",
            "| id | tok save | critical loss | retained/total | lost examples |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for r in med_chat:
        lost = ", ".join(r.get("lost_examples") or []) or "—"
        if len(lost) > 60:
            lost = lost[:57] + "…"
        lines.append(
            f"| {r['id']} | {r['token_savings_pct']}% | {r['critical_info_loss_pct']}% | "
            f"{r['critical_retained']}/{r['critical_total']} | `{lost}` |"
        )

    lines.extend(
        [
            "",
            "## How to read this",
            "",
            "- **Critical loss near 0% on `low`** means versions, URLs, and IDs "
            "almost always survive wording stages (filler/lexical/abbrev/alias).",
            "- **Higher critical + soft loss on `medium`** is mostly **recency** "
            "shortening older turns (IDs in dropped sentences). **`high`** also "
            "**trims** the middle of long threads — that is the large fact drop.",
            "- Soft loss can exceed critical loss when hedges/prose are deleted but "
            "the remaining text still contains the IDs/numbers.",
            "- This is **not** an LLM-as-judge of answer quality. It answers: "
            "*are the hard facts still in the prompt?*",
            "",
            "Raw rows: `benchmarks/results/info_fidelity.jsonl`. "
            "Aggregates: `benchmarks/results/info_fidelity_summary.json`.",
            "",
            "Re-run: `python -m benchmarks.info_fidelity`",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Token savings vs information loss.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="optional cap on corpus items (0 = all)",
    )
    args = parser.parse_args()
    items, errors = load_corpus(refresh=False)
    if args.limit and args.limit > 0:
        items = items[: args.limit]
    print(f"corpus: {len(items)} items; fetch_errors={len(errors)}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    total = len(items) * len(PRESETS)
    n = 0
    for item in items:
        for preset in PRESETS:
            n += 1
            row = evaluate_one(item, preset)
            rows.append(row)
            if n % 20 == 0 or n == total:
                print(
                    f"  [{n}/{total}] {item['id']} {preset}: "
                    f"save={row['token_savings_pct']}% "
                    f"crit_loss={row['critical_info_loss_pct']}% "
                    f"soft_loss={row['soft_info_loss_pct']}%"
                )
    elapsed = time.perf_counter() - t0
    out = RESULTS / "info_fidelity.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = write_report(rows=rows, items=items, elapsed_s=elapsed)
    print(f"wrote {out}")
    print(f"wrote {REPORT}")
    for p in PRESETS:
        a = summary["overall"][p]
        print(
            f"  {p}: token_save~{a['mean_token_savings_pct']}%  "
            f"critical_loss~{a['mean_critical_info_loss_pct']}%  "
            f"soft_loss~{a['mean_soft_info_loss_pct']}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
