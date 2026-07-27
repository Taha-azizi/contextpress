import json

from contextpress import ContextManager
from contextpress.costs import estimate_token_cost
from contextpress.models import Conversation, Turn
from contextpress.strategies.structure import StructureStrategy, compact_structure_text


def test_minify_json_blob():
    raw = '{\n  "a": 1,\n  "b": [2, 3]\n}'
    out = compact_structure_text(raw, aggressiveness=0.5)
    assert out == '{"a":1,"b":[2,3]}'
    assert json.loads(out) == {"a": 1, "b": [2, 3]}


def test_dedupe_consecutive_log_lines():
    text = "ok\nerror x\nerror x\nerror x\ndone\n"
    out = compact_structure_text(text, aggressiveness=0.5)
    assert out.count("error x") == 1


def test_structure_stage_leaves_system():
    turns = [
        Turn(role="system", content='{\n  "keep": true\n}'),
        Turn(role="user", content='{\n  "a": 1\n}'),
    ]
    out = StructureStrategy(aggressiveness=0.8).process(Conversation(turns=turns, type="agent"))
    assert out.turns[0].content == '{\n  "keep": true\n}'
    assert out.turns[1].content == '{"a":1}'


def test_structure_in_default_pipeline():
    cm = ContextManager(type="agent", compression="low")
    messages = [
        {"role": "user", "content": json.dumps({"id": 1, "name": "x"}, indent=2)},
    ]
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert "structure" in result.stats.stages_run
    assert result.messages[0]["content"] == '{"id":1,"name":"x"}'


def test_estimate_cost_positive():
    cm = ContextManager(type="chat", model="gpt-4o-mini")
    messages = [{"role": "user", "content": "hello " * 50}]
    est = cm.estimate_cost(messages, provider="openai", output_tokens=100)
    assert est.input_tokens > 0
    assert est.total_cost_usd > 0
    assert est.to_dict()["provider"] == "openai"


def test_estimate_token_cost_local_zero():
    est = estimate_token_cost(10_000, provider="local", model="llama3.2", output_tokens=500)
    assert est.total_cost_usd == 0.0
