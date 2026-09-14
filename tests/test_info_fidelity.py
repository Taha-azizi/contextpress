"""Unit tests for critical-span fidelity helpers."""

from __future__ import annotations

from benchmarks.info_fidelity import critical_retention, extract_critical_spans


def test_extract_critical_spans_finds_ids_and_urls():
    text = (
        "See https://example.com/api and user_id=abc_def. "
        "Version 2.4.1 and CamelCaseName. Call search_deploys."
    )
    spans = extract_critical_spans(text)
    joined = " ".join(spans).lower()
    assert "https://example.com/api" in joined
    assert "2.4.1" in joined
    assert "abc_def" in joined or "user_id" in joined
    assert any("CamelCase" in s for s in spans)


def test_extract_skips_discourse_noise():
    text = "I'm sorry — I apologize. There are 20 items and ChatGPT said hi."
    spans = {s.casefold() for s in extract_critical_spans(text)}
    assert "m sorry" not in spans
    assert "i apologize" not in spans
    assert "20" not in spans
    assert "chatgpt" not in spans


def test_extract_keeps_real_factoids():
    text = "Pin Flask 2.4.1, see https://pypi.org/p/flask and error 404."
    spans = {s.casefold() for s in extract_critical_spans(text)}
    assert "2.4.1" in spans
    assert any(s.startswith("https://") for s in spans)
    assert "404" in spans


def test_critical_retention_detects_loss():
    original = "Deploy api_v2 version 2.4.1 to https://staging.example.com now."
    kept = critical_retention(original, original)
    assert kept["critical_info_loss_pct"] == 0.0
    assert kept["critical_total"] >= 2
    dropped = critical_retention(original, "Deploy something now.")
    assert dropped["critical_info_loss_pct"] > 50.0


def test_hyphenated_ids_keep_embedded_numbers():
    original = 'Tool result: {"id": "evt-001", "n": 404}'
    kept = critical_retention(original, '{"id":"evt-001","n":404}')
    assert kept["critical_info_loss_pct"] == 0.0
    assert "001" in extract_critical_spans(original) or "404" in extract_critical_spans(original)


def test_number_not_retained_as_substring():
    original = "Need port 8080 and build 10.2."
    lost = critical_retention(original, "Need port 80800.")
    assert lost["critical_info_loss_pct"] > 0
    assert any(s == "8080" for s in extract_critical_spans(original))
