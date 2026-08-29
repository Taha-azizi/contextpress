"""Run Tier-1 compression and write a marketing savings brief.

No LLM. Only in-scope jobs (long chats, files in the prompt, pretty tool JSON)
are kept in the write-up. Usage:

    python -m benchmarks.run_savings --rebuild-corpus
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RESULTS = ROOT / "results"
REPORT = ROOT / "SAVINGS.md"
RIGOROUS = ROOT / "RESULTS.md"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.corpus import build_corpus, load_corpus  # noqa: E402
from contextpress import ContextManager  # noqa: E402
from contextpress.stats import CompressionStats  # noqa: E402

COST_MODELS = (
    ("openai", "gpt-4o-mini"),
    ("openai", "gpt-4o"),
    ("anthropic", "claude-sonnet-4-5"),
)

VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "name": "low",
        "compression": "low",
        "stages": None,
        "budget": None,
        "lossy": False,
        "risk": "low",
        "label": "low — structure, lexical, filler, abbrev, alias, repetition",
    },
    {
        "name": "medium",
        "compression": "medium",
        "stages": None,
        "budget": None,
        "lossy": True,
        "risk": "low–medium",
        "label": "medium — low + trim + recency",
    },
    {
        "name": "high",
        "compression": "high",
        "stages": None,
        "budget": None,
        "lossy": True,
        "risk": "medium",
        "label": "high — medium + resolution collapse",
    },
)

# Jobs where contextpress is worth running (not 2-turn FAQ, not already-minified JSON).
MIN_SAVE_PCT = 5.0
INPUT_SHARE = 0.70  # share of an LLM bill that is prompt/input tokens


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


def _text_blob(messages: Any) -> str:
    parts: list[str] = []
    if not isinstance(messages, list):
        return str(messages)
    for m in messages:
        if isinstance(m, dict):
            parts.append(json.dumps(m, ensure_ascii=False))
        else:
            parts.append(str(m))
    return "\n".join(parts)


def _sanity(item: dict[str, Any], original: list[dict[str, Any]], compressed: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(compressed, list):
        return ["output is not a list"]
    sys_in = [m for m in original if isinstance(m, dict) and m.get("role") == "system"]
    sys_out = [m for m in compressed if isinstance(m, dict) and m.get("role") == "system"]
    if sys_in and sys_out:
        if (sys_in[0].get("content") or "") != (sys_out[0].get("content") or ""):
            issues.append("system content changed")
    last_user = None
    for m in reversed(original):
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            last_user = m["content"]
            break
    if last_user:
        tokens = [t for t in re_split_words(last_user) if len(t) >= 5][:8]
        blob = _text_blob(compressed).lower()
        if tokens and not any(t.lower() in blob for t in tokens):
            issues.append("last user keywords missing from output")
    for m in original:
        if not isinstance(m, dict):
            continue
        if m.get("tool_calls"):
            ids = {c.get("id") for c in m["tool_calls"] if isinstance(c, dict)}
            out_ids = set()
            for om in compressed:
                if isinstance(om, dict):
                    for c in om.get("tool_calls") or []:
                        if isinstance(c, dict) and c.get("id"):
                            out_ids.add(c["id"])
            if ids and not ids.issubset(out_ids):
                issues.append("openai tool_call id dropped")
        if m.get("role") == "tool" and m.get("tool_call_id"):
            tids = {
                om.get("tool_call_id")
                for om in compressed
                if isinstance(om, dict) and om.get("role") == "tool"
            }
            if m["tool_call_id"] not in tids:
                issues.append("openai tool result id dropped")
    return issues


def re_split_words(text: str) -> list[str]:
    return [w for w in text.replace("\n", " ").split(" ") if w]


def _cost_fields(stats: CompressionStats) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for provider, model in COST_MODELS:
        snap = CompressionStats(
            tokens_before=stats.tokens_before,
            tokens_after=stats.tokens_after,
        )
        snap.attach_cost(provider=provider, model=model)
        key = f"{provider}:{model}"
        out[key] = {
            "usd_before": snap.estimated_input_cost_before_usd,
            "usd_after": snap.estimated_input_cost_after_usd,
            "usd_saved": snap.estimated_cost_saved_usd,
        }
    return out


def run_one(item: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    messages = item["messages"]
    cm = ContextManager(type=item["type"], model="gpt-4o-mini", cost_provider="openai")
    kwargs: dict[str, Any] = {
        "token_budget": None,
        "compression": variant["compression"],
        "return_stats": True,
    }
    if variant["stages"] is not None:
        kwargs["stages"] = list(variant["stages"])
    if variant["budget"] == "half":
        before = cm.estimate_tokens(messages)
        kwargs["token_budget"] = max(32, before // 2)
    t0 = time.perf_counter()
    result = cm.compress(messages, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    stats: CompressionStats = result.stats
    issues = _sanity(item, messages, result.messages)
    row = {
        "id": item["id"],
        "bucket": item["bucket"],
        "type": item["type"],
        "source": item["source"],
        "quotable": item.get("quotable", False),
        "variant": variant["name"],
        "lossy": variant["lossy"],
        "turns_before": stats.turns_before,
        "turns_after": stats.turns_after,
        "tokens_before": stats.tokens_before,
        "tokens_after": stats.tokens_after,
        "tokens_saved": stats.tokens_saved,
        "token_savings_pct": stats.token_savings_pct,
        "stages_run": list(stats.stages_run),
        "turn_delta_by_stage": dict(stats.turn_delta_by_stage),
        "token_delta_by_stage": dict(stats.token_delta_by_stage),
        "elapsed_ms": round(elapsed_ms, 2),
        "token_budget": kwargs["token_budget"],
        "sanity": issues,
        "costs": _cost_fields(stats),
    }
    return row


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}%"


def _fmt_num(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "—"
    if digits == 0:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


def _agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pcts = [float(r["token_savings_pct"]) for r in rows]
    toks_before = [float(r["tokens_before"]) for r in rows]
    saved = [float(r["tokens_saved"]) for r in rows]
    usd = [
        float((r.get("costs") or {}).get("openai:gpt-4o", {}).get("usd_saved") or 0.0) for r in rows
    ]
    ms = [float(r["elapsed_ms"]) for r in rows]
    return {
        "n": len(rows),
        "median_pct": _percentile(pcts, 50),
        "p10_pct": _percentile(pcts, 10),
        "p90_pct": _percentile(pcts, 90),
        "mean_pct": statistics.fmean(pcts) if pcts else None,
        "median_tokens_before": _percentile(toks_before, 50),
        "median_tokens_saved": _percentile(saved, 50),
        "median_usd_gpt4o": _percentile(usd, 50),
        "mean_usd_gpt4o": statistics.fmean(usd) if usd else None,
        "median_ms": _percentile(ms, 50),
    }


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([line, sep, body])


def _payload_excerpt(item: dict[str, Any] | None, limit: int = 480) -> str | None:
    if not item:
        return None
    candidates: list[str] = []
    for m in item.get("messages") or []:
        if not isinstance(m, dict) or m.get("role") == "system":
            continue
        content = m.get("content")
        if isinstance(content, str) and len(content) >= 40:
            candidates.append(content)
    if not candidates:
        return None
    pick = None
    for text in candidates:
        stripped = text.lstrip()
        if stripped.startswith("Tool result") or "```json" in text or stripped.startswith("{"):
            pick = text
            break
    if pick is None:
        pick = max(candidates, key=len)
    return pick[:limit] + ("…" if len(pick) > limit else "")


def _in_scope_ids(rows: list[dict[str, Any]]) -> set[str]:
    by_id: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_id[r["id"]].append(float(r["token_savings_pct"]))
    return {iid for iid, pcts in by_id.items() if pcts and max(pcts) >= MIN_SAVE_PCT}


def _money(usd: float) -> str:
    return f"${round(usd):,}"


def _round_pct(value: float | None) -> int:
    if not value:
        return 0
    return int(round(value))


def _pick_heroes(
    rows: list[dict[str, Any]], items_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    by_var: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_var[r["variant"]].append(r)

    def best(predicate, variant: str) -> dict[str, Any] | None:
        cands = [r for r in by_var.get(variant, []) if predicate(r)]
        if not cands:
            return None
        return max(cands, key=lambda r: (r["token_savings_pct"], r["tokens_saved"]))

    def best_saved(predicate, variant: str) -> dict[str, Any] | None:
        cands = [r for r in by_var.get(variant, []) if predicate(r)]
        if not cands:
            return None
        return max(cands, key=lambda r: (r["tokens_saved"], r["token_savings_pct"]))

    heroes = [
        (
            "Long chat / support thread",
            best(
                lambda r: r["bucket"] == "chat" and r.get("quotable") and "flask#" in r["id"],
                "medium",
            )
            or best(lambda r: r["bucket"] == "chat" and r.get("quotable"), "medium"),
        ),
        (
            "Files in the prompt",
            best(lambda r: str(r["id"]).startswith("files:"), "medium")
            or best(lambda r: r["bucket"] == "files", "medium"),
        ),
        (
            "Agent tool JSON (safe preset)",
            best_saved(
                lambda r: r["bucket"] == "agent" and r["tokens_before"] >= 400,
                "low",
            )
            or best(lambda r: r["bucket"] == "agent", "low"),
        ),
    ]
    out = []
    for title, row in heroes:
        if not row:
            continue
        out.append({"title": title, "row": row, "item": items_by_id.get(row["id"])})
    return out


def _turn_line(message: dict[str, Any], width: int = 220) -> str:
    role = str(message.get("role") or "?")
    content = message.get("content")
    if content is None:
        extra = {k: v for k, v in message.items() if k != "role"}
        content = json.dumps(extra, ensure_ascii=False)
    text = str(content).replace("\r\n", "\n").replace("\n", " / ")
    if len(text) > width:
        text = text[:width] + "…"
    return f"{role}: {text}"


def _dump_thread(messages: list[dict[str, Any]], *, head: int = 3, tail: int = 3) -> str:
    n = len(messages)
    if n <= head + tail:
        return "\n".join(_turn_line(m) for m in messages)
    parts = [_turn_line(m) for m in messages[:head]]
    parts.append(f"… {n - head - tail} turns omitted in this listing …")
    parts.extend(_turn_line(m) for m in messages[-tail:])
    return "\n".join(parts)


def _chat_gallery_rows(scoped: list[dict[str, Any]]) -> list[list[str]]:
    by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in scoped:
        if r["bucket"] != "chat":
            continue
        by_id[r["id"]][r["variant"]] = r
    packed = [vs for vs in by_id.values() if "low" in vs and "medium" in vs]

    def sort_key(vs: dict[str, dict[str, Any]]) -> tuple:
        r = vs["medium"]
        quotable = 0 if r.get("quotable") else 1
        return (quotable, -int(r["tokens_before"]))

    packed.sort(key=sort_key)
    rows: list[list[str]] = []
    for vs in packed[:10]:
        lo, md = vs["low"], vs["medium"]
        rows.append(
            [
                lo["id"],
                str(lo["turns_before"]),
                f"{lo['tokens_before']:,}→{lo['tokens_after']:,} ({lo['token_savings_pct']}%)",
                f"{md['tokens_before']:,}→{md['tokens_after']:,} ({md['token_savings_pct']}%)",
            ]
        )
    return rows


def _flask_4494_dump(items_by_id: dict[str, dict[str, Any]]) -> str:
    item = items_by_id.get("github:pallets/flask#4494")
    if not item:
        return ""
    messages = item["messages"]
    cm = ContextManager(type="chat", model="gpt-4o-mini")
    low = cm.compress(messages, token_budget=None, compression="low", return_stats=True)
    med = cm.compress(messages, token_budget=None, compression="medium", return_stats=True)
    chunks = [
        "### Flask #4494 — `low` vs `medium` (full compressed threads)",
        "",
        (
            f"Original: {low.stats.turns_before} turns, "
            f"{low.stats.tokens_before:,} tokens. "
            f"[Issue](https://github.com/pallets/flask/issues/4494)."
        ),
        "",
        "Original (head/tail listing):",
        "",
        "```",
        _dump_thread(messages, head=4, tail=3),
        "```",
        "",
        (
            f"**low:** {low.stats.tokens_before:,} → {low.stats.tokens_after:,} "
            f"({low.stats.token_savings_pct}%), "
            f"turns {low.stats.turns_before} → {low.stats.turns_after}. "
            f"stages: {', '.join(low.stats.stages_run)}"
        ),
        "",
        "```",
        _dump_thread(low.messages, head=20, tail=20),
        "```",
        "",
        (
            f"**medium:** {med.stats.tokens_before:,} → {med.stats.tokens_after:,} "
            f"({med.stats.token_savings_pct}%), "
            f"turns {med.stats.turns_before} → {med.stats.turns_after}. "
            f"stages: {', '.join(med.stats.stages_run)}"
        ),
        "",
        "```",
        _dump_thread(med.messages, head=20, tail=20),
        "```",
    ]
    return "\n".join(chunks)


def write_report(
    *,
    items: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    errors: list[str],
    elapsed_s: float,
) -> str:
    items_by_id = {i["id"]: i for i in items}
    keep = _in_scope_ids(rows)
    scoped = [r for r in rows if r["id"] in keep]
    dropped = sorted({r["id"] for r in rows if r["id"] not in keep})
    variants = [v["name"] for v in VARIANTS]
    med = {name: _agg([r for r in scoped if r["variant"] == name]) for name in variants}
    low_pct = _round_pct(med["low"]["median_pct"])
    mid_pct = _round_pct(med["medium"]["median_pct"])
    high_pct = _round_pct(med["high"]["median_pct"])
    agent_low_pct = _round_pct(
        _agg([r for r in scoped if r["bucket"] == "agent" and r["variant"] == "low"])["median_pct"]
    )
    bill_pct = _round_pct(mid_pct * INPUT_SHARE)
    by_bucket = sorted({r["bucket"] for r in scoped})

    lines: list[str] = []
    lines.append("# Cut LLM input cost where context actually bloats")
    lines.append("")
    lines.append(
        "Contextpress is for **long chats, files stuffed into the prompt, and "
        "pretty-printed tool JSON** — the work that repeats on every API call. "
        "It is not for a two-line FAQ. Those jobs are out of this report."
    )
    lines.append("")
    n_keep = len(keep)
    lines.append(
        f"On **{n_keep} in-scope workloads**, `medium` cut about "
        f"**{mid_pct}% of input tokens**. `low` (minify JSON, lexical word "
        f"swaps, drop filler) cut about **{low_pct}%** overall, and about "
        f"**{agent_low_pct}%** on pretty tool JSON."
    )
    lines.append("")
    lines.append("## What that is worth in a real month")
    lines.append("")
    lines.append(
        "Assume **70% of an LLM bill is input** (history, files, tools) and "
        "30% is the completion. Savings below use the in-scope "
        f"**{mid_pct}%** input cut at `medium` (about **{bill_pct}% off the "
        "whole invoice** under that split). List prices: gpt-4o input "
        "$2.50 / 1M tokens; Claude Sonnet ~$3 / 1M. Your mix will differ; "
        "the shape of the math will not."
    )
    lines.append("")

    scenarios = [
        (
            "Solo / freelancer already spending ~$150/month on API",
            150,
            "a month of ChatGPT Plus, or two extra long coding sessions "
            "you no longer have to truncate",
        ),
        (
            "Small startup at ~$5,000/month LLM",
            5000,
            "a year of a seat like Linear/Notion, or a contractor day each month",
        ),
        (
            "Product with agents at ~$20,000/month LLM",
            20000,
            "a junior-engineer intern month, or a dedicated staging GPU you "
            "were about to rent to 'just use a bigger context model'",
        ),
    ]
    scene_rows = []
    for label, bill, equals in scenarios:
        monthly = bill * INPUT_SHARE * (mid_pct / 100.0)
        yearly = monthly * 12
        scene_rows.append(
            [
                label,
                _money(bill) + "/mo",
                _money(monthly) + "/mo",
                _money(yearly) + "/yr",
                equals,
            ]
        )
    lines.append(
        _md_table(
            [
                "who",
                "LLM bill",
                f"saved at {mid_pct}% input",
                "per year",
                "that money is",
            ],
            scene_rows,
        )
    )
    lines.append("")
    lines.append("### Opportunity cost (usually the better pitch)")
    lines.append("")
    lines.append(
        f"Keep the same bill and buy **~{mid_pct}% more context** instead of " "a smaller invoice:"
    )
    lines.append("")
    lines.append(
        f"- A developer who hits the wall at turn 20 can keep ~{mid_pct}% more "
        "of the thread and stop pasting 'summary so far' by hand."
    )
    lines.append(
        f"- A startup can attach ~{mid_pct}% more retrieved files per question "
        "before jumping to a 128k/1M model tier."
    )
    lines.append(
        "- An agent product can retain pretty tool traces instead of dropping "
        "them, without paying another model to summarize first. "
        "Contextpress itself is **$0 API** — it runs on CPU."
    )
    lines.append("")
    if low_pct and low_pct != mid_pct:
        low_mo = 5000 * INPUT_SHARE * (low_pct / 100.0)
        lines.append(
            f"`low` does not drop mid-thread turns, but it does swap wording "
            f"and strip hedges. Same $5k/month startup at `low` is about "
            f"**{_money(low_mo)}/month** ({_money(low_mo * 12)}/year). "
            "`medium` adds trim (drop the middle of long chats) plus recency."
        )
        lines.append("")

    lines.append("## Answer-quality risk (rough, no judge model)")
    lines.append("")
    lines.append(
        "We did not A/B the model's final reply. Risk is what the pipeline is "
        "**allowed to delete**, plus the contract: system prompt stays; "
        "the last 3 non-system turns stay verbatim. Trim (on `medium` / `high`) "
        "drops the middle of long threads and leaves a stub."
    )
    lines.append("")
    lines.append(
        _md_table(
            ["preset", "input cut (in-scope median)", "risk to the final answer"],
            [
                [
                    "`low`",
                    f"~{low_pct}%",
                    "**Low.** Does not drop turns. Lexical may change wording "
                    "(utilize → use); filler strips empty hedges. "
                    "Skip on tone-sensitive or quote-verbatim threads.",
                ],
                [
                    "`medium`",
                    f"~{mid_pct}%",
                    "**Low–medium.** Long chats drop the middle (opening + last "
                    "3 stay). Older leftover turns may also be extractively "
                    "shortened. Fine for 'continue this work'. Not for audits "
                    "that need every old number verbatim.",
                ],
                [
                    "`high`",
                    f"~{high_pct}%",
                    "**Medium.** Finished threads can collapse to a stub. "
                    "Use when old resolved topics should leave the window.",
                ],
            ],
        )
    )
    lines.append("")
    lines.append(
        "Do not use a hard `token_budget` as a 'savings' number — that is "
        "truncation. It can drop tools and, as a last resort, the system prompt."
    )
    lines.append("")

    lines.append("## Where the cut actually comes from")
    lines.append("")
    bucket_rows = []
    labels = {"chat": "Long chats", "files": "Files in the prompt", "agent": "Agent / tool JSON"}
    for bucket in by_bucket:
        n_items = len({r["id"] for r in scoped if r["bucket"] == bucket})
        cells = [labels.get(bucket, bucket), str(n_items)]
        for name in variants:
            subset = [r for r in scoped if r["bucket"] == bucket and r["variant"] == name]
            cells.append(_fmt_pct(_agg(subset)["median_pct"]))
        bucket_rows.append(cells)
    lines.append(_md_table(["job", "n", "low", "medium", "high"], bucket_rows))
    lines.append("")
    lines.append(
        _md_table(
            ["preset", "median", "p10", "p90"],
            [
                [
                    name,
                    _fmt_pct(med[name]["median_pct"]),
                    _fmt_pct(med[name]["p10_pct"]),
                    _fmt_pct(med[name]["p90_pct"]),
                ]
                for name in variants
            ],
        )
    )
    lines.append("")
    lines.append(
        "**Chats:** `low` does not drop turns. Lexical swaps multi-token "
        "words; filler strips hedges. `medium` **trims the middle** "
        "(opening + last 3 + a stub) and may recency-shrink the leftover opening."
    )
    lines.append("")
    chat_table = _chat_gallery_rows(scoped)
    if chat_table:
        lines.append("Long chats in this run (not a single example):")
        lines.append("")
        lines.append(
            _md_table(
                ["id", "turns in", "low", "medium"],
                chat_table,
            )
        )
        lines.append("")
    flask_block = _flask_4494_dump(items_by_id)
    if flask_block:
        lines.append(flask_block)
        lines.append("")
    lines.append(
        "**Files:** several docs pasted into one prompt (project README + "
        "roadmap + changelog, Flask/Requests docs, OpenAPI, long SO threads). "
        "Same pattern: `low` if the files are pretty JSON; `medium` if they "
        "are long prose you only need the relevant parts of."
    )
    lines.append("")
    lines.append(
        "**Agents:** pretty-printed tool JSON. `low` is the whole product "
        "here — whitespace and duplicate log lines — **risk ignore**."
    )
    lines.append("")

    lines.append("## Proof points")
    lines.append("")
    for hero in _pick_heroes(scoped, items_by_id):
        row, item = hero["row"], hero["item"]
        lines.append(f"### {hero['title']}")
        lines.append("")
        lines.append(
            f"{row['tokens_before']:,} → {row['tokens_after']:,} tokens "
            f"(**{row['token_savings_pct']}%** at `{row['variant']}`; "
            f"turns {row['turns_before']} → {row['turns_after']})."
        )
        if item and item.get("url"):
            lines.append(f"Source: {item['url']}")
        if item and item.get("notes"):
            lines.append(item["notes"])
        excerpt = _payload_excerpt(item) if item and item.get("quotable") else None
        if excerpt:
            lines.append("")
            lines.append("```")
            lines.append(excerpt)
            lines.append("```")
        lines.append("")

    lines.append("## What we left out on purpose")
    lines.append("")
    lines.append(
        "Two-turn support FAQs, already-minified JSON, and short dense "
        "encyclopedia pages barely move. They are **not** the customer. "
        f"This write-up keeps jobs that saved at least **{MIN_SAVE_PCT:.0f}%** "
        "on some preset (the jobs you would actually turn it on for)."
    )
    if dropped:
        lines.append("")
        lines.append(
            f"{len(dropped)} items were measured and dropped from the story " "(under the cut)."
        )
    lines.append("")
    lines.append("## How this was measured")
    lines.append("")
    lines.append(
        f"Tier 1 only (no LLM compressor). {len(items)} raw items → "
        f"{n_keep} in-scope. {len(rows)} compressions in {elapsed_s:.0f}s. "
        "Re-run: `python -m benchmarks.run_savings --rebuild-corpus`."
    )
    if errors:
        lines.append("Fetch notes: " + "; ".join(errors))
    lines.append("")
    text = "\n".join(lines)
    REPORT.write_text(text, encoding="utf-8")
    return text


def _source_family(source: str) -> str:
    s = (source or "").lower()
    if "wildchat" in s:
        return "WildChat"
    if "sharegpt" in s or "vicuna" in s:
        return "ShareGPT"
    if "guanaco" in s:
        return "Guanaco"
    if "ultrachat" in s:
        return "UltraChat"
    if "oasst2" in s:
        return "OASST2"
    if "oasst" in s:
        return "OASST1"
    if "capybara" in s:
        return "Capybara"
    if "hh-rlhf" in s or "anthropic/hh" in s:
        return "HH-RLHF"
    if "github issue" in s:
        return "GitHub issues"
    if "github rest" in s:
        return "GitHub API JSON"
    if "glaive" in s:
        return "Glaive tools"
    if "stack overflow" in s:
        return "Stack Overflow"
    if "in-repo" in s:
        return "In-repo examples"
    if "local contextpress" in s or "flask/requests" in s or "openapi" in s or "swagger" in s:
        return "Files / docs"
    return source.split("(")[0].strip()[:40] or "other"


def write_rigorous_report(
    *,
    items: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    errors: list[str],
    elapsed_s: float,
) -> dict[str, Any]:
    """Full measurement dump: every item × preset, plus per-stage token savings."""
    variants = [v["name"] for v in VARIANTS]
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_variant[r["variant"]].append(r)

    # Per-stage: sum of (-delta) tokens and mean % of tokens_before for that run.
    stage_stats: dict[str, dict[str, Any]] = {}
    for variant in variants:
        saved_by_stage: dict[str, list[int]] = defaultdict(list)
        pct_by_stage: dict[str, list[float]] = defaultdict(list)
        for r in by_variant[variant]:
            before = max(1, int(r["tokens_before"]))
            for stage, delta in (r.get("token_delta_by_stage") or {}).items():
                saved = max(0, -int(delta))
                saved_by_stage[stage].append(saved)
                pct_by_stage[stage].append(100.0 * saved / before)
        stage_stats[variant] = {
            stage: {
                "n_nonzero": sum(1 for x in saved if x > 0),
                "sum_tokens_saved": int(sum(saved)),
                "median_tokens_saved": _percentile([float(x) for x in saved], 50),
                "mean_pct_of_input": (
                    round(statistics.fmean(pct_by_stage[stage]), 3) if pct_by_stage[stage] else 0.0
                ),
                "median_pct_of_input": _percentile(pct_by_stage[stage], 50),
            }
            for stage, saved in sorted(saved_by_stage.items())
        }

    by_source: dict[str, dict[str, Any]] = {}
    for family in sorted({_source_family(r["source"]) for r in rows}):
        fam_rows = [r for r in rows if _source_family(r["source"]) == family]
        entry: dict[str, Any] = {"n_items": len({r["id"] for r in fam_rows}), "presets": {}}
        for variant in variants:
            subset = [r for r in fam_rows if r["variant"] == variant]
            entry["presets"][variant] = _agg(subset)
        by_source[family] = entry

    by_bucket: dict[str, dict[str, Any]] = {}
    for bucket in sorted({r["bucket"] for r in rows}):
        b_rows = [r for r in rows if r["bucket"] == bucket]
        entry = {"n_items": len({r["id"] for r in b_rows}), "presets": {}}
        for variant in variants:
            entry["presets"][variant] = _agg([r for r in b_rows if r["variant"] == variant])
        by_bucket[bucket] = entry

    summary = {
        "n_items": len(items),
        "n_runs": len(rows),
        "elapsed_s": round(elapsed_s, 2),
        "fetch_errors": errors,
        "overall": {v: _agg(by_variant[v]) for v in variants},
        "by_bucket": by_bucket,
        "by_source_family": by_source,
        "by_stage": stage_stats,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines: list[str] = [
        "# Contextpress savings — full measurement report",
        "",
        f"Tier-1 only. **{len(items)}** corpus items × **{len(variants)}** presets "
        f"= **{len(rows)}** compressions in **{elapsed_s:.0f}s**.",
        "",
        "Raw rows: `benchmarks/results/runs.jsonl`. Aggregates: "
        "`benchmarks/results/summary.json`.",
        "",
        "## Overall (all items, no marketing filter)",
        "",
    ]
    lines.append(
        _md_table(
            ["preset", "n", "mean %", "median %", "p10", "p90", "median tokens saved"],
            [
                [
                    v,
                    str(summary["overall"][v]["n"]),
                    _fmt_pct(summary["overall"][v]["mean_pct"]),
                    _fmt_pct(summary["overall"][v]["median_pct"]),
                    _fmt_pct(summary["overall"][v]["p10_pct"]),
                    _fmt_pct(summary["overall"][v]["p90_pct"]),
                    _fmt_num(summary["overall"][v]["median_tokens_saved"]),
                ]
                for v in variants
            ],
        )
    )
    lines.append("")
    lines.append("## By job bucket")
    lines.append("")
    bucket_rows = []
    for bucket, entry in by_bucket.items():
        cells = [bucket, str(entry["n_items"])]
        for v in variants:
            cells.append(_fmt_pct(entry["presets"][v]["median_pct"]))
        bucket_rows.append(cells)
    lines.append(_md_table(["bucket", "n", "low med%", "medium med%", "high med%"], bucket_rows))
    lines.append("")
    lines.append("## By source family")
    lines.append("")
    src_rows = []
    for family, entry in by_source.items():
        cells = [family, str(entry["n_items"])]
        for v in variants:
            cells.append(_fmt_pct(entry["presets"][v]["median_pct"]))
        src_rows.append(cells)
    lines.append(_md_table(["source", "n", "low", "medium", "high"], src_rows))
    lines.append("")
    lines.append("## What each method saved (token Δ by stage)")
    lines.append("")
    lines.append(
        "For each preset, stages that changed tokens. "
        "`sum_saved` is total tokens removed by that stage across all items; "
        "`median %` is that stage's savings as a share of the item's input tokens."
    )
    lines.append("")
    for variant in variants:
        lines.append(f"### Preset `{variant}`")
        lines.append("")
        stage_rows = []
        for stage, st in stage_stats.get(variant, {}).items():
            stage_rows.append(
                [
                    stage,
                    str(st["n_nonzero"]),
                    str(st["sum_tokens_saved"]),
                    _fmt_num(st["median_tokens_saved"]),
                    _fmt_pct(st["median_pct_of_input"]),
                    f"{st['mean_pct_of_input']:.2f}%",
                ]
            )
        if stage_rows:
            lines.append(
                _md_table(
                    ["stage", "n>0", "sum tokens saved", "median tok", "median %", "mean %"],
                    stage_rows,
                )
            )
        else:
            lines.append("_No stage-level token deltas recorded._")
        lines.append("")

    lines.append("## Every item × preset")
    lines.append("")
    by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        by_id[r["id"]][r["variant"]] = r
    detail_rows: list[list[str]] = []
    for iid in sorted(by_id.keys()):
        vs = by_id[iid]
        lo = vs.get("low") or next(iter(vs.values()))
        cells = [
            iid,
            lo["bucket"],
            _source_family(lo["source"]),
            str(lo["turns_before"]),
            str(lo["tokens_before"]),
        ]
        for v in variants:
            r = vs.get(v)
            cells.append(_fmt_pct(r["token_savings_pct"] if r else None))
        # Top stages on low (by tokens saved)
        deltas = (lo.get("token_delta_by_stage") or {}) if lo else {}
        ranked = sorted(deltas.items(), key=lambda kv: kv[1])[:3]
        top = ", ".join(f"{s}:{-d}" for s, d in ranked if d < 0) or "—"
        cells.append(top)
        detail_rows.append(cells)
    lines.append(
        _md_table(
            [
                "id",
                "bucket",
                "source",
                "turns",
                "tok in",
                "low %",
                "med %",
                "high %",
                "low top stages (tok)",
            ],
            detail_rows,
        )
    )
    lines.append("")
    if errors:
        lines.append("## Fetch errors")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")
    lines.append(
        "Re-run: `python -m benchmarks.run_savings --rebuild-corpus` "
        "(add `--refresh` to re-download HF caches)."
    )
    lines.append("")
    RIGOROUS.write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Tier-1 savings study (no LLM).")
    parser.add_argument("--refresh", action="store_true", help="re-fetch remote sources")
    parser.add_argument("--rebuild-corpus", action="store_true", help="rebuild corpus.jsonl")
    args = parser.parse_args()
    if args.refresh or args.rebuild_corpus:
        items, errors = build_corpus(refresh=args.refresh)
    else:
        items, errors = load_corpus(refresh=False)
    print(f"corpus: {len(items)} items; fetch_errors={len(errors)}")
    for err in errors:
        print("  warn:", err)
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    total = len(items) * len(VARIANTS)
    n = 0
    for item in items:
        for variant in VARIANTS:
            n += 1
            row = run_one(item, variant)
            rows.append(row)
            if n % 10 == 0 or n == total:
                print(
                    f"  [{n}/{total}] {item['id']} {variant['name']}: "
                    f"{row['token_savings_pct']}% ({row['tokens_before']}->{row['tokens_after']})"
                )
    elapsed_s = time.perf_counter() - t0
    out_path = RESULTS / "runs.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_rigorous_report(items=items, rows=rows, errors=errors, elapsed_s=elapsed_s)
    write_report(items=items, rows=rows, errors=errors, elapsed_s=elapsed_s)
    print(f"wrote {out_path}")
    print(f"wrote {RESULTS / 'summary.json'}")
    print(f"wrote {RIGOROUS}")
    print(f"wrote {REPORT}")
    print(f"elapsed {elapsed_s:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
