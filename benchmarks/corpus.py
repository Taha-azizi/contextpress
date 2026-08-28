"""Build a local, gitignored corpus for the savings study.

Network fetches are cached under ``benchmarks/data/raw/``. Failed sources are
skipped so a partial corpus still runs. Do not commit ``data/``.
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CORPUS_PATH = DATA / "corpus.jsonl"
FIXTURES = ROOT.parent / "tests" / "fixtures" / "chats"

UA = {
    "User-Agent": "contextpress-savings-research/0.6.9 (local benchmark; +https://github.com/Taha-azizi/contextpress)"
}
MAX_ITEM_CHARS = 80_000
MAX_TURNS = 40

_TAG = re.compile(r"<[^>]+>", re.DOTALL)
_GLAIVE_SPLIT = re.compile(r"\n(?=USER:|ASSISTANT:|FUNCTION RESPONSE:)")


def _item(
    *,
    id: str,
    bucket: str,
    type: str,
    source: str,
    license: str,
    messages: list[dict[str, Any]],
    url: str | None = None,
    quotable: bool = False,
    notes: str = "",
) -> dict[str, Any] | None:
    if not messages:
        return None
    messages = messages[:MAX_TURNS]
    total = _message_chars(messages)
    if total > MAX_ITEM_CHARS:
        return None
    if total < 8:
        return None
    return {
        "id": id,
        "bucket": bucket,
        "type": type,
        "source": source,
        "license": license,
        "url": url,
        "quotable": quotable,
        "notes": notes,
        "messages": messages,
    }


def _message_chars(messages: list[dict[str, Any]]) -> int:
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)


def _strip_html(text: str) -> str:
    text = _TAG.sub(" ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _http_json(url: str, *, gzip_ok: bool = True) -> Any:
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = resp.read()
    if gzip_ok and data[:2] == b"\x1f\x8b":
        import gzip

        data = gzip.decompress(data)
    return json.loads(data)


def cached_json(name: str, url: str, *, refresh: bool = False) -> Any:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    payload = _http_json(url)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def cached_text(name: str, url: str, *, refresh: bool = False) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.txt"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def _try(name: str, fn, errors: list[str]) -> list[dict[str, Any]]:
    try:
        items = fn()
        return [x for x in items if x]
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        KeyError,
        ValueError,
        OSError,
    ) as exc:
        errors.append(f"{name}: {type(exc).__name__}: {exc}")
        return []


def load_synthetic_fixtures() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            _item(
                id=f"synthetic:{path.stem}",
                bucket="synthetic_control",
                type=data.get("type", "chat"),
                source=data.get("source", "synthetic fixture"),
                license="in-repo test fixture (not a real transcript)",
                messages=data["messages"],
                url=None,
                quotable=False,
                notes="Designed to trip pipeline stages; ceiling, not typical savings.",
            )
        )
    return items


def _inrepo_openai() -> dict[str, Any]:
    arguments = json.dumps({"service": "api-v2", "environment": "staging", "limit": 20}, indent=2)
    tool_result = json.dumps(
        {
            "service": "api-v2",
            "events": [{"id": "evt-001", "version": "2.4.1", "status": "healthy"}],
        },
        indent=2,
    )
    messages = [
        {"role": "system", "content": "You are a deploy agent with function tools."},
        {"role": "user", "content": "Find recent staging deploys for api-v2."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_search_1",
                    "type": "function",
                    "function": {"name": "search_deploys", "arguments": arguments},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_search_1",
            "name": "search_deploys",
            "content": tool_result,
        },
        {"role": "assistant", "content": "Staging is healthy on 2.4.1."},
    ]
    return _item(
        id="inrepo:openai_tools",
        bucket="agent",
        type="agent",
        source="in-repo example (openai_tools_compress.py)",
        license="Apache-2.0 (this repo)",
        messages=messages,
        url=None,
        quotable=True,
        notes="Cookbook-shaped OpenAI tool_calls; pretty-printed JSON strings.",
    )


def _inrepo_agent_json() -> dict[str, Any]:
    payload = {
        "tool": "search_deploys",
        "service": "api-v2",
        "environment": "staging",
        "events": [
            {
                "id": f"evt-{i:03d}",
                "version": f"2.4.{i % 3}",
                "status": "healthy" if i % 2 else "superseded",
                "details": {"replicas": 3, "region": "us-east-1"},
            }
            for i in range(12)
        ],
        "meta": {"query_ms": 38, "truncated": False},
    }
    messages = [
        {"role": "system", "content": "You are a deploy agent with tools."},
        {"role": "user", "content": "Summarize recent staging deploys for api-v2."},
        {
            "role": "assistant",
            "content": "Fetching deploy history <tool_call> search_deploys(api-v2, staging)",
        },
        {"role": "user", "content": "Tool result:\n" + json.dumps(payload, indent=2)},
        {
            "role": "assistant",
            "content": "Staging has multiple recent releases; latest is healthy.",
        },
    ]
    return _item(
        id="inrepo:agent_json",
        bucket="agent",
        type="agent",
        source="in-repo example (agent_json_compress.py)",
        license="Apache-2.0 (this repo)",
        messages=messages,
        quotable=True,
        notes="Pretty-printed tool JSON in a user turn.",
    )


def _inrepo_fenced() -> dict[str, Any]:
    payload = {
        "service": "api-v2",
        "environment": "staging",
        "events": [{"id": f"evt-{i:03d}", "version": f"2.4.{i % 3}"} for i in range(8)],
    }
    messages = [
        {"role": "system", "content": "Answer using the provided document chunks."},
        {
            "role": "user",
            "content": "Chunk:\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n",
        },
        {"role": "user", "content": "Which versions appear in the deploy index?"},
    ]
    return _item(
        id="inrepo:fenced_json",
        bucket="files",
        type="rag_doc",
        source="in-repo example (fenced_json_compress.py)",
        license="Apache-2.0 (this repo)",
        messages=messages,
        quotable=True,
    )


def load_inrepo_examples() -> list[dict[str, Any]]:
    return [x for x in (_inrepo_openai(), _inrepo_agent_json(), _inrepo_fenced()) if x]


def _hf_rows(
    dataset: str, config: str, split: str, offset: int, length: int, *, refresh: bool
) -> list[dict[str, Any]]:
    slug = dataset.replace("/", "__")
    name = f"hf_{slug}_{split}_{offset}_{length}"
    url = (
        "https://datasets-server.huggingface.co/rows"
        f"?dataset={dataset}&config={config}&split={split}&offset={offset}&length={length}"
    )
    payload = cached_json(name, url, refresh=refresh)
    return [rec["row"] for rec in payload.get("rows", [])]


def load_ultrachat(*, refresh: bool) -> list[dict[str, Any]]:
    """Long multi-turn chats only — short 2–4 turn Q&A is out of scope."""
    rows: list[dict[str, Any]] = []
    for offset in (0, 40, 80, 120):
        rows.extend(
            _hf_rows(
                "HuggingFaceH4/ultrachat_200k",
                "default",
                "train_sft",
                offset,
                40,
                refresh=refresh,
            )
        )
    items: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        msgs = row.get("messages") or []
        if not isinstance(msgs, list) or len(msgs) < 8:
            continue
        clean = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            role = m.get("role") or "user"
            content = m.get("content") or ""
            if role not in {"user", "assistant", "system"}:
                role = "user"
            clean.append({"role": role, "content": str(content)})
        if len(clean) < 8:
            continue
        chars = sum(len(m["content"]) for m in clean)
        if chars < 2500:
            continue
        item = _item(
            id=f"ultrachat:{i}",
            bucket="chat",
            type="chat",
            source="HuggingFaceH4/ultrachat_200k",
            license="UltraChat dataset card (model-generated; measure, do not reprint)",
            messages=clean,
            url="https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k",
            quotable=False,
            notes="Long assistant session (8+ turns). Typical coding/support history shape.",
        )
        if item:
            items.append(item)
        if len(items) >= 34:
            break
    return items


def load_oasst(*, refresh: bool) -> list[dict[str, Any]]:
    """Flatten English trees in time order (OASST is a tree, not a single thread)."""
    rows: list[dict[str, Any]] = []
    for offset in (0, 100, 200, 300, 400):
        rows.extend(
            _hf_rows("OpenAssistant/oasst1", "default", "train", offset, 100, refresh=refresh)
        )
    trees: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("deleted") or row.get("lang") != "en":
            continue
        trees[row["message_tree_id"]].append(row)
    items: list[dict[str, Any]] = []
    for tid, nodes in trees.items():
        nodes = sorted(nodes, key=lambda n: n.get("created_date") or "")
        if len(nodes) < 6:
            continue
        messages = []
        for n in nodes:
            role = "user" if n.get("role") == "prompter" else "assistant"
            messages.append({"role": role, "content": n.get("text") or ""})
        item = _item(
            id=f"oasst:{tid[:8]}",
            bucket="chat",
            type="chat",
            source="OpenAssistant/oasst1 (English tree, chronological flatten)",
            license="Apache-2.0",
            messages=messages,
            url="https://huggingface.co/datasets/OpenAssistant/oasst1",
            quotable=False,
            notes="Human volunteer messages; sibling branches interleaved by time. Do not reprint.",
        )
        if item:
            items.append(item)
        if len(items) >= 16:
            break
    return items


def _parse_glaive(system: str, chat: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    sys = (system or "").strip()
    if sys.upper().startswith("SYSTEM:"):
        sys = sys[7:].strip()
    if sys:
        messages.append({"role": "system", "content": sys})
    chunks = _GLAIVE_SPLIT.split((chat or "").strip())
    if len(chunks) == 1 and chat:
        chunks = [chat.strip()]
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        body = chunk.replace("<|endoftext|>", "").strip()
        if body.startswith("USER:"):
            messages.append({"role": "user", "content": body[5:].strip()})
        elif body.startswith("ASSISTANT:"):
            messages.append({"role": "assistant", "content": body[10:].strip()})
        elif body.startswith("FUNCTION RESPONSE:"):
            payload = body[len("FUNCTION RESPONSE:") :].strip()
            messages.append({"role": "user", "content": "Tool result:\n" + payload})
    return messages


def load_glaive(*, refresh: bool) -> list[dict[str, Any]]:
    rows = _hf_rows(
        "glaiveai/glaive-function-calling-v2", "default", "train", 0, 30, refresh=refresh
    )
    items: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        chat = row.get("chat") or ""
        if "<functioncall>" not in chat and "FUNCTION RESPONSE" not in chat:
            continue
        messages = _parse_glaive(row.get("system") or "", chat)
        item = _item(
            id=f"glaive:{i}",
            bucket="agent_tools",
            type="agent",
            source="glaiveai/glaive-function-calling-v2",
            license="Apache-2.0 (dataset card)",
            messages=messages,
            url="https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2",
            quotable=False,
            notes="Function responses left compact (as published).",
        )
        if item:
            items.append(item)
        if len(items) >= 8:
            break
    return items


def load_bitext(*, refresh: bool) -> list[dict[str, Any]]:
    rows = _hf_rows(
        "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        "default",
        "train",
        0,
        12,
        refresh=refresh,
    )
    items: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        inst = row.get("instruction") or ""
        resp = row.get("response") or ""
        item = _item(
            id=f"bitext:{i}",
            bucket="chat_short",
            type="chat",
            source="bitext/Bitext-customer-support-llm-chatbot-training-dataset",
            license="see dataset card (short synthetic support pairs)",
            messages=[
                {"role": "user", "content": str(inst)},
                {"role": "assistant", "content": str(resp)},
            ],
            url="https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset",
            quotable=False,
            notes="Two-turn support; expect near-zero savings on low.",
        )
        if item:
            items.append(item)
        if len(items) >= 6:
            break
    return items


def _github_thread(owner: str, repo: str, number: int, *, refresh: bool) -> dict[str, Any] | None:
    issue = cached_json(
        f"gh_{owner}_{repo}_issue_{number}",
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}",
        refresh=refresh,
    )
    comments = cached_json(
        f"gh_{owner}_{repo}_comments_{number}",
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments?per_page=80",
        refresh=refresh,
    )
    if not isinstance(comments, list):
        comments = []
    if issue.get("pull_request"):
        return None
    title = issue.get("title") or f"Issue {number}"
    body = issue.get("body") or ""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You track public GitHub issues and summarize status."},
        {
            "role": "user",
            "content": f"Issue #{number}: {title}\n\n{body}",
        },
    ]
    for c in comments:
        login = (c.get("user") or {}).get("login") or "user"
        messages.append({"role": "user", "content": f"Comment by {login}:\n{c.get('body') or ''}"})
    messages.append(
        {"role": "user", "content": "What is the current status and likely resolution?"}
    )
    return _item(
        id=f"github:{owner}/{repo}#{number}",
        bucket="chat",
        type="chat",
        source=f"GitHub issue {owner}/{repo}#{number} + comments",
        license="Public GitHub content; measure locally, quote only with attribution",
        messages=messages,
        url=issue.get("html_url"),
        quotable=True,
        notes="Real public issue thread (all comment turns are user-authored).",
    )


def _wrap_api_json(
    *,
    id: str,
    payload: Any,
    indent: int | None,
    query: str,
    url: str,
    notes: str,
) -> dict[str, Any] | None:
    blob = json.dumps(payload, indent=indent, ensure_ascii=False)
    messages = [
        {"role": "system", "content": "You are an agent that reads API payloads."},
        {"role": "user", "content": query},
        {
            "role": "assistant",
            "content": "Fetching <tool_call> http_get()",
        },
        {"role": "user", "content": "Tool result:\n" + blob},
        {"role": "assistant", "content": "I have the payload."},
        {"role": "user", "content": "Summarize the most recent items."},
    ]
    bucket = "agent"
    return _item(
        id=id,
        bucket=bucket,
        type="agent",
        source="GitHub REST API JSON wrapped as a tool result",
        license="GitHub API terms; public repo metadata",
        messages=messages,
        url=url,
        quotable=True,
        notes=notes,
    )


def load_github(*, refresh: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for owner, repo, num in (
        ("pallets", "flask", 4027),
        ("pallets", "flask", 4494),
        ("pallets", "flask", 5881),
        ("pallets", "click", 2800),
        ("psf", "requests", 5642),
        ("pallets", "jinja", 1589),
    ):
        try:
            item = _github_thread(owner, repo, num, refresh=refresh)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError):
            continue
        if item:
            items.append(item)
    events = cached_json(
        "gh_flask_events",
        "https://api.github.com/repos/pallets/flask/events?per_page=5",
        refresh=refresh,
    )
    commits = cached_json(
        "gh_requests_commits",
        "https://api.github.com/repos/psf/requests/commits?per_page=5",
        refresh=refresh,
    )
    issue_list = cached_json(
        "gh_flask_issues",
        "https://api.github.com/repos/pallets/flask/issues?state=open&per_page=8",
        refresh=refresh,
    )
    pretty = _wrap_api_json(
        id="github:flask_events_pretty",
        payload=events,
        indent=2,
        query="List recent public events on pallets/flask.",
        url="https://api.github.com/repos/pallets/flask/events",
        notes="Pretty-printed API JSON, as in notebooks and agent logs.",
    )
    commits_pretty = _wrap_api_json(
        id="github:requests_commits_pretty",
        payload=commits,
        indent=2,
        query="Summarize recent commits on psf/requests.",
        url="https://api.github.com/repos/psf/requests/commits",
        notes="Pretty-printed GitHub commits payload.",
    )
    issues_pretty = _wrap_api_json(
        id="github:flask_issues_pretty",
        payload=issue_list,
        indent=2,
        query="List open issues on pallets/flask.",
        url="https://api.github.com/repos/pallets/flask/issues",
        notes="Pretty-printed issue list a coding agent would paste back into context.",
    )
    for item in (pretty, commits_pretty, issues_pretty):
        if item:
            items.append(item)
    return items


def load_stackexchange(*, refresh: bool) -> list[dict[str, Any]]:
    # Classic CC BY-SA threads: question + top answers as rag_doc chunks.
    ids = "231767;3940128;82831;11227809;17950384"
    questions = cached_json(
        "se_questions",
        "https://api.stackexchange.com/2.3/questions/"
        f"{ids}?site=stackoverflow&filter=withbody&pagesize=5",
        refresh=refresh,
    )
    items: list[dict[str, Any]] = []
    for q in questions.get("items") or []:
        qid = q.get("question_id")
        answers = cached_json(
            f"se_answers_{qid}",
            f"https://api.stackexchange.com/2.3/questions/{qid}/answers"
            "?site=stackoverflow&filter=withbody&pagesize=3&sort=votes",
            refresh=refresh,
        )
        title = _strip_html(q.get("title") or "")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Answer using the provided document chunks."},
            {
                "role": "user",
                "content": f"Chunk (question): {title}\n\n{_strip_html(q.get('body') or '')}",
            },
        ]
        for j, ans in enumerate((answers.get("items") or [])[:3], start=1):
            messages.append(
                {
                    "role": "user",
                    "content": f"Chunk (answer {j}): {_strip_html(ans.get('body') or '')}",
                }
            )
        messages.append({"role": "user", "content": f"In one paragraph, answer: {title}"})
        item = _item(
            id=f"so:{qid}",
            bucket="files",
            type="rag_doc",
            source=f"Stack Overflow question {qid} + top answers",
            license="CC BY-SA (Stack Exchange)",
            messages=messages,
            url=q.get("link"),
            quotable=True,
            notes="HTML stripped to text. Dense Q&A; expect modest low-preset savings.",
        )
        if item:
            items.append(item)
    return items


def load_openapi(*, refresh: bool) -> list[dict[str, Any]]:
    spec = cached_json(
        "petstore_openapi",
        "https://petstore3.swagger.io/api/v3/openapi.json",
        refresh=refresh,
    )
    pretty = json.dumps(spec, indent=2, ensure_ascii=False)
    if len(pretty) > MAX_ITEM_CHARS:
        # Keep paths + info only so the item still fits.
        slim = {
            "openapi": spec.get("openapi"),
            "info": spec.get("info"),
            "paths": spec.get("paths"),
        }
        pretty = json.dumps(slim, indent=2, ensure_ascii=False)
    messages = [
        {"role": "system", "content": "Answer using the provided API specification."},
        {
            "role": "user",
            "content": "Chunk:\n\n```json\n" + pretty[: MAX_ITEM_CHARS - 200] + "\n```\n",
        },
        {"role": "user", "content": "Which HTTP methods exist on /pet, and what do they do?"},
    ]
    item = _item(
        id="openapi:petstore3",
        bucket="files",
        type="rag_doc",
        source="Swagger Petstore 3 OpenAPI document (pretty-printed)",
        license="Apache-2.0 (swagger-petstore)",
        messages=messages,
        url="https://petstore3.swagger.io/api/v3/openapi.json",
        quotable=True,
        notes="Pretty-printed spec pasted as a retrieved JSON fence.",
    )
    return [item] if item else []


def load_local_files() -> list[dict[str, Any]]:
    """Project files sitting in a coding-agent context window."""
    repo = ROOT.parent
    names = (
        "README.md",
        "ROADMAP.md",
        "AGENTS.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "AUDIT.md",
    )
    chunks: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "You are a coding assistant. Answer using the attached project files.",
        }
    ]
    for name in names:
        path = repo / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")[:12_000]
        chunks.append({"role": "user", "content": f"FILE {name}\n\n{text}"})
    chunks.append(
        {
            "role": "user",
            "content": (
                "How do I add a compression stage, and what did the 0.6 line ship? "
                "Cite the files."
            ),
        }
    )
    item = _item(
        id="files:contextpress_docs",
        bucket="files",
        type="rag_doc",
        source="Local contextpress docs (README, ROADMAP, AGENTS, CHANGELOG, …)",
        license="Apache-2.0 (this repo)",
        messages=chunks,
        url="https://github.com/Taha-azizi/contextpress",
        quotable=True,
        notes="Multi-file dump a coding agent would attach before answering.",
    )
    return [item] if item else []


def load_remote_files(*, refresh: bool) -> list[dict[str, Any]]:
    specs = (
        (
            "flask_readme",
            "https://raw.githubusercontent.com/pallets/flask/main/README.md",
            "README.md",
        ),
        (
            "flask_contributing",
            "https://raw.githubusercontent.com/pallets/flask/main/CONTRIBUTING.rst",
            "CONTRIBUTING.rst",
        ),
        (
            "flask_quickstart",
            "https://raw.githubusercontent.com/pallets/flask/main/docs/quickstart.rst",
            "docs/quickstart.rst",
        ),
        (
            "requests_readme",
            "https://raw.githubusercontent.com/psf/requests/main/README.md",
            "README.md",
        ),
        (
            "pep8",
            "https://raw.githubusercontent.com/python/peps/main/peps/pep-0008.rst",
            "pep-0008.rst",
        ),
    )
    fetched: list[tuple[str, str]] = []
    for name, url, label in specs:
        try:
            text = cached_text(name, url, refresh=refresh)[:14_000]
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            continue
        if len(text.strip()) < 200:
            continue
        fetched.append((label, text))
    if len(fetched) < 2:
        return []
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "You are a coding assistant. Use the attached library files.",
        }
    ]
    for label, text in fetched:
        messages.append({"role": "user", "content": f"FILE {label}\n\n{text}"})
    messages.append(
        {
            "role": "user",
            "content": (
                "Summarize how a new contributor installs the library and where "
                "the project documents contribution rules."
            ),
        }
    )
    item = _item(
        id="files:flask_requests_docs",
        bucket="files",
        type="rag_doc",
        source="Public Flask/Requests/PEP 8 files (raw.githubusercontent.com)",
        license="BSD / PSF / CC; public project docs",
        messages=messages,
        url="https://github.com/pallets/flask",
        quotable=True,
        notes="Several docs pasted into one prompt — file-summarization job.",
    )
    return [item] if item else []

    return [item] if item else []


def build_corpus(*, refresh: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    items.extend(load_inrepo_examples())
    items.extend(load_local_files())
    items.extend(_try("ultrachat", lambda: load_ultrachat(refresh=refresh), errors))
    items.extend(_try("oasst", lambda: load_oasst(refresh=refresh), errors))
    items.extend(_try("github", lambda: load_github(refresh=refresh), errors))
    items.extend(_try("stackexchange", lambda: load_stackexchange(refresh=refresh), errors))
    items.extend(_try("openapi", lambda: load_openapi(refresh=refresh), errors))
    items.extend(_try("remote_files", lambda: load_remote_files(refresh=refresh), errors))
    DATA.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    (DATA / "corpus_errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    return items, errors


def load_corpus(*, refresh: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    if CORPUS_PATH.exists() and not refresh:
        items = [
            json.loads(line)
            for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        err_path = DATA / "corpus_errors.json"
        errors = json.loads(err_path.read_text(encoding="utf-8")) if err_path.exists() else []
        return items, errors
    return build_corpus(refresh=refresh)
