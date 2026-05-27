import warnings

from contextpress.models import ContentBlock, Turn
from contextpress.normalizer import apply_text_to_turn, denormalize_output, normalize_messages


class _FakeMsg:
    def __init__(self, typ: str, content: str):
        self.type = typ
        self.content = content


def test_dict_list_plain_string():
    raw = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    conv, ctx = normalize_messages(raw)
    assert len(conv.turns) == 2
    assert conv.turns[0].role == "user"
    assert conv.turns[0].content == "Hello"
    out = denormalize_output(conv, ctx)
    assert out == raw


def test_dict_multimodal_blocks():
    raw = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is this?"},
                {"type": "image_url", "image_url": {"url": "http://x"}},
            ],
        }
    ]
    conv, ctx = normalize_messages(raw)
    assert isinstance(conv.turns[0].content, list)
    out = denormalize_output(conv, ctx)
    assert isinstance(out[0]["content"], list)
    assert out[0]["content"][0]["type"] == "text"


def test_string_list_alternating_roles():
    raw = ["Hello", "Hi there"]
    conv, ctx = normalize_messages(raw)
    assert conv.turns[0].role == "user"
    assert conv.turns[1].role == "assistant"
    out = denormalize_output(conv, ctx)
    assert out == raw


def test_tuple_list():
    raw = [("user", "Hello"), ("assistant", "Hi there")]
    conv, ctx = normalize_messages(raw)
    assert len(conv.turns) == 2
    out = denormalize_output(conv, ctx)
    assert out == raw


def test_system_role_identified():
    raw = [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}]
    conv, _ = normalize_messages(raw)
    assert conv.turns[0].role == "system"


def test_unknown_role_warning():
    raw = [{"role": "custom_role", "content": "x"}]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        conv, _ = normalize_messages(raw)
        assert conv.turns[0].role == "custom_role"
        assert any("unknown role" in str(x.message).lower() for x in w)


def test_timestamp_metadata():
    from datetime import datetime

    ts = datetime(2020, 1, 1, 12, 0, 0)
    raw = [{"role": "user", "content": "a", "timestamp": ts}]
    conv, _ = normalize_messages(raw)
    assert conv.turns[0].timestamp == ts

    raw2 = [{"role": "user", "content": "a", "created_at": ts}]
    conv2, _ = normalize_messages(raw2)
    assert conv2.turns[0].timestamp == ts

    raw3 = [{"role": "user", "content": "a", "ts": ts}]
    conv3, _ = normalize_messages(raw3)
    assert conv3.turns[0].timestamp == ts


def test_empty_list():
    conv, ctx = normalize_messages([])
    assert conv.turns == []
    assert denormalize_output(conv, ctx) == []


def test_langchain_style_objects():
    objs = [_FakeMsg("human", "hello"), _FakeMsg("ai", "hi")]
    conv, ctx = normalize_messages(objs)
    assert conv.turns[0].role == "user"
    out = denormalize_output(conv, ctx)
    assert len(out) == 2
    assert out[0].content == "hello"


def test_apply_text_multimodal_preserves_image_block():
    turn = Turn(
        role="user",
        content=[
            ContentBlock(type="text", content="old text"),
            ContentBlock(type="image", content="http://img", metadata={"type": "image_url"}),
        ],
    )
    out = apply_text_to_turn(turn, "new text")
    assert isinstance(out.content, list)
    assert out.content[0].type == "text"
    assert out.content[0].content == "new text"
    assert out.content[1].type == "image"
