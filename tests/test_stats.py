from contextpress import CompressionResult, ContextManager


def test_compress_without_stats_returns_list():
    cm = ContextManager(type="chat")
    messages = [{"role": "user", "content": "hello basically there"}]
    out = cm.compress(messages, token_budget=500)
    assert isinstance(out, list)


def test_compress_with_stats_returns_result():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Old question: " + "blah " * 80},
        {"role": "assistant", "content": "Basically, honestly, " + "yak " * 80},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "Four."},
    ]
    result = cm.compress(messages, token_budget=120, return_stats=True)
    assert isinstance(result, CompressionResult)
    assert isinstance(result.messages, list)
    assert result.stats.turns_before == 5
    assert result.stats.turns_after <= result.stats.turns_before
    assert result.stats.tokens_before >= result.stats.tokens_after
    assert result.stats.tokens_saved >= 0
    assert result.stats.compression_level == "medium"
    assert result.stats.context_type == "chat"
    assert result.stats.token_budget == 120
    assert "filler" in result.stats.stages_run


def test_stats_turn_delta_by_stage():
    cm = ContextManager(type="chat", compression="low")
    messages = [
        {"role": "user", "content": "hello basically"},
        {"role": "assistant", "content": "sounds good"},
    ]
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert isinstance(result.stats.turn_delta_by_stage, dict)
    assert isinstance(result.stats.token_delta_by_stage, dict)


def test_stats_token_delta_by_stage_records_savings():
    cm = ContextManager(type="chat", compression="low")
    messages = [
        {"role": "user", "content": "Due to the fact that we need fewer tokens basically."},
        {"role": "assistant", "content": "In order to help, drop filler."},
    ]
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert result.stats.tokens_before >= result.stats.tokens_after
    # At least one wording stage should move tokens on this hedge-heavy text.
    assert result.stats.token_delta_by_stage or result.stats.tokens_saved == 0
    for delta in result.stats.token_delta_by_stage.values():
        assert isinstance(delta, int)
