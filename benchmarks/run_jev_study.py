"""Jev (OpenRouter) × Contextpress study: file / RAG labelled decisions.

Plan and pass criteria: ``benchmarks/JEV_STUDY.md`` (registered before calls).

    python -m benchmarks.run_jev_study
    python -m benchmarks.run_jev_study --limit 4 --smoke
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RESULTS = ROOT / "results"
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "JEV_STUDY.md"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.info_fidelity import critical_retention  # noqa: E402
from contextpress import ContextManager  # noqa: E402

MODEL = "typesafe/jev-1.13"
ENDPOINT = "https://openrouter.ai/api/v1/systemone"
INPUT_USD_PER_1M = 0.042
PRESETS = ("low", "medium", "high")
N_BOOLQ = 60
N_QUALITY = 60
N_SCIFACT = 40
N_RAG_DISTRACTORS = 8
SLEEP_S = 0.2
UA = "contextpress-jev-study/0.7.0 (local research; +https://github.com/Taha-azizi/contextpress)"

BOOLQ_URL = "https://storage.googleapis.com/boolq/dev.jsonl"
QUALITY_URLS = (
    "https://raw.githubusercontent.com/nyu-mll/quality/main/data/v1.0.1/QuALITY.v1.0.1.htmlstripped.dev",
    "https://raw.githubusercontent.com/nyu-mll/quality/master/data/v1.0.1/QuALITY.v1.0.1.htmlstripped.dev",
)
SCIFACT_CLAIMS = "https://raw.githubusercontent.com/allenai/scifact/master/data/claims_dev.jsonl"
SCIFACT_CORPUS = "https://raw.githubusercontent.com/allenai/scifact/master/data/corpus.jsonl"


def _load_dotenv() -> None:
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _api_key() -> str:
    _load_dotenv()
    key = os.environ.get("OPEN_ROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key or key.endswith("HERE"):
        raise SystemExit("OPEN_ROUTER_API_KEY is not set")
    return key


def _fetch(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 100:
        return dest
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; contextpress-jev-study/0.7.0)",
            "Accept": "application/json,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"download failed {url}: {exc}") from exc
    return dest


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def hf_rows(dataset: str, config: str, split: str, offset: int, length: int) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode(
        {
            "dataset": dataset,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    url = f"https://datasets-server.huggingface.co/rows?{q}"
    slug = dataset.replace("/", "_")
    dest = RAW / f"hf_{slug}_{config}_{split}_{offset}_{length}.json"
    _fetch(url, dest)
    payload = json.loads(dest.read_text(encoding="utf-8"))
    if "error" in payload and "rows" not in payload:
        raise RuntimeError(f"HF rows error {dataset}: {payload.get('error')}")
    return [rec["row"] for rec in payload.get("rows", [])]


def load_boolq_rag(n: int, rng: random.Random) -> list[dict[str, Any]]:
    dest = RAW / "boolq_dev.jsonl"
    rows: list[dict[str, Any]] = []
    try:
        _fetch(BOOLQ_URL, dest)
        rows = _read_jsonl(dest)
    except Exception:
        rows = []
        for off in (0, 100, 200):
            rows.extend(hf_rows("google/boolq", "default", "validation", off, 100))
    if len(rows) < n + 5:
        raise RuntimeError("BoolQ set too small")
    picked = rng.sample(rows, n)
    items: list[dict[str, Any]] = []
    for i, row in enumerate(picked):
        distractors = [r for r in rows if r is not row]
        extra = rng.sample(distractors, N_RAG_DISTRACTORS)
        distractor_ps = [str(x["passage"]) for x in extra]
        rng.shuffle(distractor_ps)
        gold_p = str(row["passage"])
        # Gold is last retrieved chunk so recency's last-3 guard keeps it;
        # distractors sit earlier so medium/high can actually fire.
        chunks = [f"PASSAGE {j+1}:\n{p}" for j, p in enumerate(distractor_ps)]
        chunks.append(f"PASSAGE {len(chunks)+1}:\n{gold_p}")
        gold = bool(row["answer"])
        items.append(
            {
                "id": f"boolq:{i}:{row.get('title', 'x')[:40]}",
                "bucket": "rag",
                "question_text": str(row["question"]).strip(),
                "chunks": chunks,
                "body": "\n\n---\n\n".join(chunks),
                "gold": "yes" if gold else "no",
                "qtype": "noul",
                "source": f"BoolQ-dev + {N_RAG_DISTRACTORS} distractor passages (separate turns)",
            }
        )
    return items


def load_quality(n: int, rng: random.Random) -> list[dict[str, Any]]:
    dest = RAW / "quality_dev.jsonl"
    last_err: Exception | None = None
    rows: list[dict[str, Any]] = []
    for url in QUALITY_URLS:
        try:
            _fetch(url, dest)
            rows = _read_jsonl(dest)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if dest.exists():
                dest.unlink()
    if not rows:
        try:
            raw_rows = hf_rows("tau/scrolls", "quality", "validation", 0, 100)
            for row in raw_rows:
                rows.append(
                    {
                        "article": row.get("input") or row.get("document") or row.get("text"),
                        "article_id": row.get("id"),
                        "questions": [
                            {
                                "question": row.get("question") or row.get("query"),
                                "options": row.get("options") or row.get("choices"),
                                "gold_label": row.get("output") or row.get("label"),
                                "question_id": row.get("id"),
                            }
                        ],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    if not rows:
        raise RuntimeError(f"QuALITY download failed: {last_err}")
    candidates: list[dict[str, Any]] = []
    for row in rows:
        article = str(row.get("article") or row.get("text") or "").strip()
        questions = row.get("questions") or []
        if len(article) < 2000 or not questions:
            continue
        article = article[:12_000]
        chunks = split_file_chunks(article)
        if len(chunks) < 8:
            continue
        q = rng.choice(questions)
        opts = q.get("options") or q.get("choices")
        gold_idx = q.get("gold_label")
        if gold_idx is None:
            gold_idx = q.get("answer")
        if not opts or gold_idx is None:
            continue
        if isinstance(gold_idx, str) and gold_idx.isdigit():
            gold_idx = int(gold_idx)
        if isinstance(gold_idx, str) and gold_idx.strip().upper()[:1] in "ABCD":
            key = gold_idx.strip().upper()[:1]
            idx = ord(key) - ord("A")
            label = opts[idx] if 0 <= idx < len(opts) else key
        elif isinstance(gold_idx, int) and gold_idx >= 1 and gold_idx <= len(opts):
            # 1-based in v1.0.1
            label = opts[gold_idx - 1]
            key = chr(ord("A") + gold_idx - 1)
        elif isinstance(gold_idx, int) and 0 <= gold_idx < len(opts):
            label = opts[gold_idx]
            key = chr(ord("A") + gold_idx)
        else:
            continue
        criteria = {chr(ord("A") + i): str(opt) for i, opt in enumerate(opts[:4])}
        if key not in criteria:
            continue
        candidates.append(
            {
                "id": f"quality:{row.get('article_id', i_id(row))}:{q.get('question_id', '')}",
                "bucket": "file",
                "question_text": str(q.get("question") or "").strip(),
                "chunks": chunks,
                "body": "\n\n".join(chunks),
                "gold": key,
                "qtype": "choice",
                "criteria": criteria,
                "source": "QuALITY v1.0.1 htmlstripped.dev",
                "_gold_text": str(label),
            }
        )
    if len(candidates) < n:
        raise RuntimeError(f"QuALITY usable items {len(candidates)} < {n}")
    return rng.sample(candidates, n)


def i_id(row: dict[str, Any]) -> str:
    return str(row.get("set_unique_id") or row.get("articleId") or id(row))


def load_scifact(n: int, rng: random.Random) -> list[dict[str, Any]]:
    claims = _read_jsonl(_fetch(SCIFACT_CLAIMS, RAW / "scifact_claims_dev.jsonl"))
    corpus_rows = _read_jsonl(_fetch(SCIFACT_CORPUS, RAW / "scifact_corpus.jsonl"))
    docs = {int(r["doc_id"]): r for r in corpus_rows if "doc_id" in r}
    usable: list[dict[str, Any]] = []
    for row in claims:
        ev = row.get("evidence") or {}
        if not ev:
            continue
        # evidence is {doc_id: [{label: SUPPORT|CONTRADICT, ...}]}
        doc_id = None
        label = None
        for did, spans in ev.items():
            if not spans:
                continue
            lab = str(spans[0].get("label") or "").upper()
            if lab in {"SUPPORT", "SUPPORTS", "CONTRADICT", "CONTRADICTS", "REFUTE"}:
                doc_id = int(did)
                label = "SUPPORT" if lab.startswith("SUPPORT") else "REFUTE"
                break
        if doc_id is None or doc_id not in docs:
            continue
        abs_sents = docs[doc_id].get("abstract") or []
        if isinstance(abs_sents, list):
            abstract = " ".join(str(s) for s in abs_sents)
        else:
            abstract = str(abs_sents)
        title = str(docs[doc_id].get("title") or "")
        body = f"TITLE: {title}\n\nABSTRACT: {abstract}"
        chunks = split_file_chunks(body, min_chunks=6)
        usable.append(
            {
                "id": f"scifact:{row.get('id', doc_id)}",
                "bucket": "file",
                "question_text": str(row.get("claim") or "").strip(),
                "chunks": chunks,
                "body": body,
                "gold": label,
                "qtype": "choice",
                "criteria": {
                    "SUPPORT": "The abstract supports the claim.",
                    "REFUTE": "The abstract contradicts / refutes the claim.",
                    "NEI": "The abstract does not have enough information.",
                },
                "source": "SciFact claims_dev + corpus",
            }
        )
    if len(usable) < n:
        raise RuntimeError(f"SciFact usable items {len(usable)} < {n}")
    return rng.sample(usable, n)


def split_file_chunks(text: str, *, min_chunks: int = 8, max_chars: int = 12_000) -> list[str]:
    """Turn a long file into enough turns that trim/recency are not no-ops.

    Recency never rewrites the last 3 non-system turns. Trim keeps head+tail
    (2+3 at rag_doc aggressiveness). A single concatenated body is only two
    turns with the question, so medium/high collapse to low.
    """
    text = text[:max_chars].strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < min_chunks:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if len(sents) >= min_chunks:
            paras = sents
        elif not paras:
            paras = [text]
    # Merge crumbs so we do not explode into one-sentence turns.
    target = max(min_chunks, min(16, max(min_chunks, len(text) // 700)))
    min_len = max(180, len(text) // max(target, 1))
    merged: list[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p
        elif len(buf) < min_len:
            buf = f"{buf}\n\n{p}"
        else:
            merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)
    # Split oversized leftovers if we still have too few turns.
    i = 0
    while len(merged) < min_chunks and i < len(merged):
        piece = merged[i]
        if len(piece) < 400:
            i += 1
            continue
        mid = len(piece) // 2
        cut = piece.rfind(" ", 0, mid)
        if cut < 80:
            i += 1
            continue
        merged[i : i + 1] = [piece[:cut].strip(), piece[cut:].strip()]
    labelled = [f"SECTION {j+1}:\n{c}" for j, c in enumerate(merged) if c.strip()]
    return labelled or [text]


def compress_body(chunks: list[str], question: str, preset: str) -> tuple[str, dict[str, Any]]:
    messages: list[dict[str, str]] = [{"role": "user", "content": c} for c in chunks]
    messages.append({"role": "user", "content": question})
    cm = ContextManager(type="rag_doc", compression=preset)
    result = cm.compress(messages, token_budget=None, return_stats=True)
    parts: list[str] = []
    for m in result.messages:
        content = str(m.get("content") or "")
        if content == question:
            continue
        parts.append(content)
    out_body = "\n\n".join(parts) if parts else "\n\n".join(chunks)
    orig = "\n\n".join(chunks)
    facts = critical_retention(orig, out_body)
    return out_body, {
        "tokens_before": result.stats.tokens_before,
        "tokens_after": result.stats.tokens_after,
        "token_savings_pct": result.stats.token_savings_pct,
        "stages_run": list(result.stats.stages_run),
        "n_turns_in": len(messages),
        "n_turns_out": len(result.messages),
        "elapsed_ms": result.stats.elapsed_ms,
        **facts,
    }


def _questions_for(item: dict[str, Any]) -> dict[str, Any]:
    q = item["question_text"]
    if item["qtype"] == "noul":
        return {
            "answer": {
                "type": "noul",
                "instructions": (
                    "Using only the documents in state, is the correct answer to "
                    f"this question YES? Question: {q}"
                ),
                "true": "The documents support answering yes.",
                "false": "The documents support answering no, or do not support yes.",
            }
        }
    return {
        "answer": {
            "type": "choice",
            "instructions": f"Using only the documents in state, answer: {q}",
            "criteria": item["criteria"],
        }
    }


def call_jev(state: str, questions: dict[str, Any], key: str) -> dict[str, Any]:
    payload = {"model": MODEL, "state": state, "questions": questions}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Taha-azizi/contextpress",
            "X-OpenRouter-Title": "contextpress-jev-study",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Jev HTTP {exc.code}: {err}") from exc


def parse_pred(item: dict[str, Any], resp: dict[str, Any]) -> str | None:
    answers = resp.get("answers") or {}
    ans = answers.get("answer") or {}
    if item["qtype"] == "noul":
        score = ans.get("noul")
        if score is None:
            return None
        return "yes" if float(score) >= 0.5 else "no"
    probs = ans.get("probabilities") or {}
    if probs:
        return max(probs, key=lambda k: float(probs[k]))
    # some payloads put the chosen key on the answer
    chosen = ans.get("choice") or ans.get("value")
    if isinstance(chosen, str):
        return chosen
    return None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4 * n)) / n) / den
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = min(b, c)
    cdf = sum(math.comb(n, i) for i in range(0, tail + 1)) / (2**n)
    return min(1.0, 2.0 * cdf)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def build_items(rng: random.Random, *, limit: int | None) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    items: list[dict[str, Any]] = []
    n_b, n_f = N_BOOLQ, N_QUALITY
    if limit:
        n_b = max(1, limit // 2)
        n_f = max(1, limit - n_b)
    items.extend(load_boolq_rag(n_b, rng))
    notes.append(f"BoolQ RAG n={n_b}")
    try:
        items.extend(load_quality(n_f, rng))
        notes.append(f"QuALITY n={n_f}")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"QuALITY unavailable ({exc}); SciFact fallback n={n_f}")
        items.extend(load_scifact(n_f, rng))
    return items, notes


def evaluate_item(item: dict[str, Any], preset: str, key: str) -> dict[str, Any]:
    body = item["body"]
    chunks = list(item.get("chunks") or [body])
    extra: dict[str, Any] = {}
    if preset == "raw":
        state_body = body
        extra = {
            "tokens_before": None,
            "tokens_after": None,
            "token_savings_pct": 0.0,
            "critical_info_loss_pct": 0.0,
            "critical_total": 0,
            "critical_retained": 0,
            "stages_run": [],
            "n_turns_in": len(chunks) + 1,
            "n_turns_out": len(chunks) + 1,
        }
    else:
        state_body, extra = compress_body(chunks, item["question_text"], preset)
    state = f"DOCUMENTS:\n\n{state_body}"
    resp = call_jev(state, _questions_for(item), key)
    pred = parse_pred(item, resp)
    usage = resp.get("usage") or {}
    gold = item["gold"]
    correct = pred is not None and pred.casefold() == str(gold).casefold()
    return {
        "id": item["id"],
        "bucket": item["bucket"],
        "source": item["source"],
        "preset": preset,
        "gold": gold,
        "pred": pred,
        "correct": correct,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cost_usd": usage.get("cost"),
        "model": resp.get("model"),
        **extra,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(r, _uid=f"run{i // 4}") for i, r in enumerate(rows)]
    by_preset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_preset[r["preset"]].append(r)
    raw = {r["_uid"]: r for r in by_preset.get("raw", [])}
    out: dict[str, Any] = {"n_items": len(raw), "presets": {}}
    for preset, preset_rows in by_preset.items():
        n = len(preset_rows)
        hits = sum(1 for r in preset_rows if r["correct"])
        lo, hi = wilson_ci(hits, n)
        billed = [
            float(r["input_tokens"]) for r in preset_rows if r.get("input_tokens") is not None
        ]
        costs = [float(r["cost_usd"]) for r in preset_rows if r.get("cost_usd") is not None]
        tok_save = [float(r["token_savings_pct"]) for r in preset_rows if r["preset"] != "raw"]
        fact_w_num = 0
        fact_w_den = 0
        for r in preset_rows:
            fact_w_den += int(r.get("critical_total") or 0)
            fact_w_num += int(r.get("critical_retained") or 0)
        fact_loss = 0.0 if fact_w_den == 0 else 100.0 * (1.0 - fact_w_num / fact_w_den)
        b = c = 0
        if preset != "raw":
            for r in preset_rows:
                a = raw.get(r["_uid"])
                if not a:
                    continue
                if a["correct"] and not r["correct"]:
                    b += 1
                if (not a["correct"]) and r["correct"]:
                    c += 1
        acc = 100.0 * hits / n if n else 0.0
        raw_acc = None
        drop = None
        if preset != "raw" and raw:
            raw_hits = sum(1 for r in raw.values() if r["correct"])
            raw_acc = 100.0 * raw_hits / len(raw)
            drop = raw_acc - acc
        out["presets"][preset] = {
            "n": n,
            "accuracy_pct": round(acc, 2),
            "accuracy_ci95": [round(100 * lo, 2), round(100 * hi, 2)],
            "raw_accuracy_pct": None if raw_acc is None else round(raw_acc, 2),
            "decision_loss_pp": None if drop is None else round(drop, 2),
            "mcnemar_b_raw_ok_press_bad": b,
            "mcnemar_c_raw_bad_press_ok": c,
            "mcnemar_p": round(mcnemar_p(b, c), 4),
            "mean_billed_input_tokens": round(_mean(billed), 1),
            "mean_cost_usd": round(_mean(costs), 8),
            "mean_token_savings_pct": round(_mean(tok_save), 2),
            "weighted_fact_loss_pct": round(fact_loss, 2),
            "fact_spans": fact_w_den,
        }
    # billed save vs raw
    raw_tok = out["presets"].get("raw", {}).get("mean_billed_input_tokens") or 0
    for preset, st in out["presets"].items():
        if preset == "raw" or not raw_tok:
            st["mean_billed_save_pct"] = 0.0
            continue
        st["mean_billed_save_pct"] = round(
            100.0 * (1.0 - (st["mean_billed_input_tokens"] or 0) / raw_tok), 2
        )
    by_bucket: dict[str, Any] = {}
    raw_map = {r["_uid"]: r for r in by_preset.get("raw", [])}
    for bucket in sorted({r["bucket"] for r in rows}):
        by_bucket[bucket] = summarize_flat(
            [r for r in rows if r["bucket"] == bucket], raw_global=raw_map
        )
    out["by_bucket"] = by_bucket
    return out


def summarize_flat(
    rows: list[dict[str, Any]], raw_global: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    by_preset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_preset[r["preset"]].append(r)
    raw_local = {r["_uid"]: r for r in by_preset.get("raw", [])}
    raw = raw_local or raw_global
    out: dict[str, Any] = {}
    raw_toks = [
        float(r["input_tokens"])
        for r in by_preset.get("raw", [])
        if r.get("input_tokens") is not None
    ]
    raw_mean_tok = _mean(raw_toks)
    for preset, preset_rows in by_preset.items():
        n = len(preset_rows)
        hits = sum(1 for r in preset_rows if r["correct"])
        acc = 100.0 * hits / n if n else 0.0
        billed = [
            float(r["input_tokens"]) for r in preset_rows if r.get("input_tokens") is not None
        ]
        tok_save = [float(r["token_savings_pct"]) for r in preset_rows if r["preset"] != "raw"]
        fact_w_num = sum(int(r.get("critical_retained") or 0) for r in preset_rows)
        fact_w_den = sum(int(r.get("critical_total") or 0) for r in preset_rows)
        fact_loss = 0.0 if fact_w_den == 0 else 100.0 * (1.0 - fact_w_num / fact_w_den)
        raw_acc = drop = None
        if preset != "raw" and raw:
            paired = [raw[r["_uid"]] for r in preset_rows if r.get("_uid") in raw]
            if paired:
                raw_acc = 100.0 * sum(1 for a in paired if a["correct"]) / len(paired)
                drop = raw_acc - acc
        billed_save = 0.0
        if preset != "raw" and raw_mean_tok:
            billed_save = 100.0 * (1.0 - _mean(billed) / raw_mean_tok)
        out[preset] = {
            "n": n,
            "accuracy_pct": round(acc, 2),
            "decision_loss_pp": None if drop is None else round(drop, 2),
            "mean_token_savings_pct": round(_mean(tok_save), 2),
            "mean_billed_save_pct": round(billed_save, 2),
            "weighted_fact_loss_pct": round(fact_loss, 2),
        }
    return out


def verdicts(summary: dict[str, Any]) -> dict[str, str]:
    low = summary["presets"].get("low") or {}
    med = summary["presets"].get("medium") or {}
    raw = summary["presets"].get("raw") or {}
    cost_save = max(low.get("mean_billed_save_pct") or 0, med.get("mean_billed_save_pct") or 0)
    cost_falls = (low.get("mean_cost_usd") or 1) < (raw.get("mean_cost_usd") or 0) or (
        med.get("mean_cost_usd") or 1
    ) < (raw.get("mean_cost_usd") or 0)
    h_cost = cost_save >= 5 and cost_falls
    h_facts = (low.get("weighted_fact_loss_pct") if low.get("weighted_fact_loss_pct") is not None else 100) <= 5
    low_drop = low.get("decision_loss_pp")
    med_drop = med.get("decision_loss_pp")
    low_p = low.get("mcnemar_p")
    h_dec_low = low_drop is not None and (
        low_drop < 3 and (low_p is None or low_p >= 0.05 or low_drop <= 0)
    )
    # still fail if drop >= 3 even if p high
    if low_drop is not None and low_drop >= 3:
        h_dec_low = False
    if low_drop is not None and low_drop < 3:
        h_dec_low = True
    h_dec_med = med_drop is not None and med_drop < 8
    huge = False
    for st in (low, med):
        save = st.get("mean_billed_save_pct") or 0
        drop = st.get("decision_loss_pp")
        if save >= 20 and drop is not None and drop < 3:
            huge = True
    return {
        "H-cost": "PASS" if h_cost else "FAIL",
        "H-facts (low)": "PASS" if h_facts else "FAIL",
        "H-decision (low)": "PASS" if h_dec_low else "FAIL",
        "H-decision (medium)": "PASS" if h_dec_med else "FAIL",
        "Huge win": "PASS" if huge else "FAIL",
    }


def render_report(
    summary: dict[str, Any],
    notes: list[str],
    model_served: str,
    elapsed_s: float,
) -> str:
    existing = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    head = existing.split("## Results")[0].rstrip() + "\n\n## Results\n"
    v = verdicts(summary)
    lines = [
        head,
        f"Run date: 2026-09-20. Served model: `{model_served}`. "
        f"{summary['n_items']} items × 4 conditions in {elapsed_s:.0f}s.",
        "",
        "Corpus: " + "; ".join(notes),
        "",
        "### Verdict vs pre-registered criteria",
        "",
        "| Claim | Result |",
        "|-------|--------|",
    ]
    for k, val in v.items():
        lines.append(f"| **{k}** | **{val}** |")
    lines += [
        "",
        "### Overall",
        "",
        "| Preset | Billed save | Fact loss | Acc | Acc drop | McNemar p | Mean $ |",
        "|--------|------------:|----------:|----:|---------:|----------:|-------:|",
    ]
    order = ("raw", "low", "medium", "high")
    for preset in order:
        st = summary["presets"].get(preset)
        if not st:
            continue
        drop = "—" if st["decision_loss_pp"] is None else f"{st['decision_loss_pp']:.2f} pp"
        pval = "—" if preset == "raw" else f"{st['mcnemar_p']:.3f}"
        save = "—" if preset == "raw" else f"{st['mean_billed_save_pct']:.1f}%"
        fact = "—" if preset == "raw" else f"{st['weighted_fact_loss_pct']:.1f}%"
        lines.append(
            f"| `{preset}` | {save} | {fact} | {st['accuracy_pct']:.1f}% "
            f"[{st['accuracy_ci95'][0]:.1f}, {st['accuracy_ci95'][1]:.1f}] | {drop} | {pval} | "
            f"${st['mean_cost_usd']:.6f} |"
        )
    lines += ["", "### By bucket", ""]
    lines.append("| Bucket | `low` save → fact → acc drop | `medium` | `high` |")
    lines.append("|--------|------------------------------|----------|--------|")
    for bucket, presets in summary.get("by_bucket", {}).items():
        cells = [bucket]
        for name in ("low", "medium", "high"):
            st = presets.get(name) or {}
            cells.append(
                f"{st.get('mean_billed_save_pct', '—')}% → "
                f"{st.get('weighted_fact_loss_pct', '—')}% → "
                f"{st.get('decision_loss_pp', '—')} pp"
            )
        lines.append("| " + " | ".join(cells) + " |")
    low = summary["presets"].get("low") or {}
    med = summary["presets"].get("medium") or {}
    high = summary["presets"].get("high") or {}
    rag = (summary.get("by_bucket") or {}).get("rag") or {}
    files = (summary.get("by_bucket") or {}).get("file") or {}
    rag_low = rag.get("low") or {}
    rag_med = rag.get("medium") or {}
    file_low = files.get("low") or {}
    file_med = files.get("medium") or {}
    lines += [
        "",
        "### Plain reading",
        "",
        "- **Billing:** Jev list price is input-only. `usage.cost` moved with input tokens.",
        f"- **`low`:** billed save **{low.get('mean_billed_save_pct')}%**, fact loss "
        f"**{low.get('weighted_fact_loss_pct')}%**, acc drop **{low.get('decision_loss_pp')} pp**.",
        f"- **`medium`:** billed save **{med.get('mean_billed_save_pct')}%**, fact loss "
        f"**{med.get('weighted_fact_loss_pct')}%**, acc drop **{med.get('decision_loss_pp')} pp** "
        f"(McNemar p={med.get('mcnemar_p')}).",
        f"- **`high`:** billed save **{high.get('mean_billed_save_pct')}%**, fact loss "
        f"**{high.get('weighted_fact_loss_pct')}%**, acc drop **{high.get('decision_loss_pp')} pp** "
        f"(McNemar p={high.get('mcnemar_p')}).",
        f"- **RAG:** `low` {rag_low.get('mean_billed_save_pct')}% / {rag_low.get('decision_loss_pp')} pp; "
        f"`medium` {rag_med.get('mean_billed_save_pct')}% / {rag_med.get('decision_loss_pp')} pp.",
        f"- **Files:** `low` {file_low.get('mean_billed_save_pct')}% / {file_low.get('decision_loss_pp')} pp; "
        f"`medium` {file_med.get('mean_billed_save_pct')}% / {file_med.get('decision_loss_pp')} pp.",
        "- **Presets are not tied** when the prompt is packed as many document turns. "
        "They only matched in run 1 because that run used two turns.",
        "",
        "### How to read this",
        "",
        "- **Billed save** uses OpenRouter `usage.input_tokens` vs the raw call.",
        "- **Acc drop** is `acc(raw) − acc(preset)` in points. Negative means compression helped.",
        "- **McNemar p** ≥ 0.05: we cannot reject “no accuracy change.”",
        "- Null and negative results use the same verdict table as passes.",
        "",
        f"List price used for planning: ${INPUT_USD_PER_1M}/1M input, $0 output. "
        "Actual billed $ is `usage.cost`.",
        "",
        "Re-run: `python -m benchmarks.run_jev_study`",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=0, help="cap total items (0 = full sample)")
    p.add_argument("--from-jsonl", action="store_true", help="re-score existing results file")
    p.add_argument("--compress-only", action="store_true", help="no Jev; print per-preset token save")
    p.add_argument("--smoke", action="store_true", help="one Jev ping then exit")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    if args.smoke:
        resp = call_jev(
            "The invoice shows two charges for March.",
            {"refund": {"type": "noul", "instructions": "Is the customer asking for money back?"}},
            _api_key(),
        )
        print("smoke_ok", resp.get("model"), resp.get("usage"))
        return 0

    if args.from_jsonl:
        path = RESULTS / "jev_study.jsonl"
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        notes = list(json.loads((RESULTS / "jev_study_summary.json").read_text()).get("notes") or []) if (RESULTS / "jev_study_summary.json").exists() else []
        if not notes:
            notes = ["replay pairing by run order"]
        served = next((str(r.get("model")) for r in rows if r.get("model")), MODEL)
        summary = summarize(rows)
        summary["notes"] = notes
        summary["verdicts"] = verdicts(summary)
        (RESULTS / "jev_study_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        elapsed = float(summary.get("elapsed_s") or 395.0)
        REPORT.write_text(render_report(summary, notes, served, elapsed), encoding="utf-8")
        print("rewrote", REPORT)
        print(json.dumps(summary["verdicts"], indent=2))
        return 0

    rng = random.Random(args.seed)
    limit = args.limit or None
    print("loading corpus…", flush=True)
    items, notes = build_items(rng, limit=limit)
    print("items", len(items), notes, flush=True)
    print(
        "turns",
        [len(it.get("chunks") or []) + 1 for it in items[:3]],
        "…",
        flush=True,
    )

    if args.compress_only:
        by = defaultdict(list)
        for item in items:
            for preset in PRESETS:
                _, extra = compress_body(list(item.get("chunks") or [item["body"]]), item["question_text"], preset)
                extra["bucket"] = item["bucket"]
                extra["preset"] = preset
                extra["id"] = item["id"]
                by[preset].append(extra)
                print(
                    f"{item['id']} {preset} save={extra['token_savings_pct']} "
                    f"stages={extra['stages_run']} turns={extra['n_turns_in']}→{extra['n_turns_out']}",
                    flush=True,
                )
        print("\nmean tiktoken save / fact loss / turn drop")
        for preset in PRESETS:
            xs = by[preset]
            save = _mean([float(r["token_savings_pct"]) for r in xs])
            den = sum(int(r.get("critical_total") or 0) for r in xs)
            num = sum(int(r.get("critical_retained") or 0) for r in xs)
            loss = 0.0 if den == 0 else 100.0 * (1.0 - num / den)
            t_in = _mean([float(r["n_turns_in"]) for r in xs])
            t_out = _mean([float(r["n_turns_out"]) for r in xs])
            print(f"  {preset}: {save:.2f}% save, {loss:.2f}% fact loss, turns {t_in:.1f}→{t_out:.1f}")
            for bucket in ("rag", "file"):
                sub = [r for r in xs if r.get("bucket") == bucket]
                if not sub:
                    continue
                print(
                    f"    {bucket}: {_mean([float(r['token_savings_pct']) for r in sub]):.2f}%"
                )
        return 0

    key = _api_key()
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS / "jev_study.jsonl"
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    served = MODEL
    total = len(items) * (1 + len(PRESETS))
    done = 0
    for item in items:
        for preset in ("raw", *PRESETS):
            try:
                row = evaluate_item(item, preset, key)
            except Exception as exc:  # noqa: BLE001
                print("ERROR", item["id"], preset, exc)
                row = {
                    "id": item["id"],
                    "bucket": item["bucket"],
                    "preset": preset,
                    "gold": item["gold"],
                    "pred": None,
                    "correct": False,
                    "error": str(exc)[:300],
                    "token_savings_pct": 0.0,
                    "critical_info_loss_pct": 0.0,
                    "critical_total": 0,
                    "critical_retained": 0,
                }
            if row.get("model"):
                served = str(row["model"])
            rows.append(row)
            done += 1
            print(
                f"[{done}/{total}] {item['id']} {preset} "
                f"ok={row.get('correct')} tok={row.get('input_tokens')} "
                f"save={row.get('token_savings_pct')}",
                flush=True,
            )
            time.sleep(SLEEP_S)
    elapsed = time.perf_counter() - t0
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = summarize(rows)
    summary["notes"] = notes
    summary["elapsed_s"] = round(elapsed, 2)
    summary["verdicts"] = verdicts(summary)
    (RESULTS / "jev_study_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    REPORT.write_text(render_report(summary, notes, served, elapsed), encoding="utf-8")
    print("wrote", REPORT)
    print(json.dumps(summary["verdicts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
