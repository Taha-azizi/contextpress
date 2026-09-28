"""0.7.4: rag_doc keeps the question and the section it points at."""

from __future__ import annotations

from contextpress import ContextManager

_QUESTION = (
    "What is very quite specific in the part that begins "
    "“The brass sextant showed a bearing”?"
)
_ANCHOR = "The brass sextant showed a bearing of 214 degrees toward the island of Zephyra."
_OFFTOPIC = "Warehouse clerks counted nutmeg crates beside tar barrels in the quiet loft."


_DISTINCT = (
    "Oak ships sailed past the granite lighthouse during a spring storm.",
    "Bakers folded cinnamon dough before sunrise in the market street.",
    "Miners mapped a copper vein under the northern ridge last winter.",
    "Potters glazed blue bowls and set them along the sunny wall.",
    "Shepherds moved wool flocks toward the high meadow at dawn.",
    "Printers stacked damp pamphlets beside the courthouse door.",
    "Fishers mended hemp nets after the river flood receded.",
    "Masons raised a limestone arch over the narrow canal.",
)


def _sections() -> list[dict[str, str]]:
    bodies = list(_DISTINCT)
    bodies.insert(3, _ANCHOR)
    bodies.insert(6, _OFFTOPIC)
    messages = [
        {"role": "user", "content": f"SECTION {i + 1}.\n{body}"} for i, body in enumerate(bodies)
    ]
    messages.append({"role": "user", "content": _QUESTION})
    return messages


def test_rag_doc_question_with_filler_words_stays_intact() -> None:
    messages = _sections()
    for preset in ("low", "high"):
        out = ContextManager(type="rag_doc", compression=preset).compress(messages)
        assert out[-1]["content"] == _QUESTION


def test_rag_doc_high_keeps_pointed_section_and_drops_offtopic() -> None:
    out = ContextManager(type="rag_doc", compression="high").compress(_sections())
    body = "\n".join(str(m.get("content") or "") for m in out)
    assert "Zephyra" in body
    assert "nutmeg" not in body
    assert out[-1]["content"] == _QUESTION


def test_chat_still_strips_filler_from_an_older_user_turn() -> None:
    messages = [
        {
            "role": "user",
            "content": "This is very quite important context about the database migration.",
        },
        {"role": "assistant", "content": "Understood the migration plan."},
        {"role": "user", "content": "Thanks."},
    ]
    out = ContextManager(type="chat", compression="low").compress(messages)
    older = out[0]["content"].lower()
    assert "very" not in older
    assert "quite" not in older
    assert "database" in older
