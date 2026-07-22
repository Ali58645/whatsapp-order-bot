"""Company Knowledge Base — validation, migration, search, grounded answers."""

from __future__ import annotations

import pytest

from app.knowledge import (
    _UNAVAILABLE,
    answer_from_knowledge,
    build_published_corpus,
    empty_knowledge_base,
    invalidate_knowledge_cache,
    knowledge_char_count,
    knowledge_faq_list,
    migrate_faq_into_knowledge,
    preview_knowledge_answer,
    search_knowledge,
    strip_rich_text,
    validate_knowledge_base,
)


def test_strip_rich_text_removes_tags():
    assert "Hello world" in strip_rich_text("<p>Hello <b>world</b></p>", max_len=100)
    assert "<" not in strip_rich_text("<script>x</script>ok", max_len=100)


def test_migrate_faq_into_knowledge():
    cfg = {
        "faq": [{"question": "Hours?", "answer": "9–5"}],
    }
    out = migrate_faq_into_knowledge(cfg)
    kb = out["knowledge_base"]
    assert kb["faq"][0]["question"] == "Hours?"
    assert out["faq"][0]["answer"] == "9–5"


def test_migrate_does_not_overwrite_existing_kb_faq():
    cfg = {
        "faq": [{"question": "Old?", "answer": "Old"}],
        "knowledge_base": {
            **empty_knowledge_base(),
            "faq": [{"question": "New?", "answer": "New"}],
        },
    }
    out = migrate_faq_into_knowledge(cfg)
    assert out["knowledge_base"]["faq"][0]["question"] == "New?"


def test_validate_knowledge_base_status_and_sections():
    kb = validate_knowledge_base(
        {
            "enabled": True,
            "status": "published",
            "sections": {"overview": "We sell POS", "bogus": "ignored"},
            "complete_knowledge": "<p>Full story</p>",
            "faq": [{"question": "Price?", "answer": "Ask sales"}],
        }
    )
    assert kb["status"] == "published"
    assert "bogus" not in kb["sections"]
    assert "Full story" in kb["complete_knowledge"]
    assert "<p>" not in kb["complete_knowledge"]
    assert knowledge_char_count(kb) > 0


def test_validate_rejects_bad_status():
    with pytest.raises(ValueError, match="status"):
        validate_knowledge_base({"status": "live"})


def test_build_published_corpus_respects_draft():
    kb = validate_knowledge_base(
        {
            "enabled": True,
            "status": "draft",
            "complete_knowledge": "Secret draft",
            "sections": {},
            "faq": [],
        }
    )
    assert build_published_corpus(kb) == ""
    kb["status"] = "published"
    assert "Secret draft" in build_published_corpus(kb)


def test_search_knowledge_prefers_overlap():
    corpus = "## Pricing\nPlans start at 5000\n\n## Hours\nOpen 9 to 5"
    hit = search_knowledge(corpus, "what is pricing")
    assert "5000" in hit


@pytest.mark.asyncio
async def test_answer_from_knowledge_disabled_returns_none():
    class T:
        phone_number_id = "t1"
        faq_list = []
        _raw_config = {
            "knowledge_base": {
                **empty_knowledge_base(),
                "enabled": False,
                "status": "published",
                "complete_knowledge": "We open at 9",
            }
        }

    invalidate_knowledge_cache("t1")
    ans = await answer_from_knowledge("hours?", T(), client=None, model="x")
    assert ans is None


@pytest.mark.asyncio
async def test_answer_from_knowledge_no_client_unavailable():
    class T:
        phone_number_id = "t2"
        faq_list = []
        _raw_config = {
            "knowledge_base": {
                **empty_knowledge_base(),
                "enabled": True,
                "status": "published",
                "complete_knowledge": "Delivery fee is 100 PKR",
            }
        }

    invalidate_knowledge_cache("t2")
    ans = await answer_from_knowledge(
        "delivery fee?", T(), client=None, model="x", miss_policy="unavailable"
    )
    assert ans == _UNAVAILABLE
    ans2 = await answer_from_knowledge(
        "delivery fee?", T(), client=None, model="x", miss_policy="none"
    )
    assert ans2 is None


@pytest.mark.asyncio
async def test_preview_uses_draft_content():
    class FakeClient:
        class messages:
            @staticmethod
            async def create(**kwargs):
                class R:
                    content = [type("B", (), {"text": "We open at 9am."})()]

                return R()

    kb = {
        **empty_knowledge_base(),
        "enabled": True,
        "status": "draft",
        "complete_knowledge": "Open 9am to 5pm daily",
    }
    result = await preview_knowledge_answer(
        "When do you open?",
        kb,
        client=FakeClient(),
        model="test",
    )
    assert result["matched"] is True
    assert "9" in result["answer"]


def test_knowledge_faq_list_prefers_kb():
    class T:
        faq_list = [{"question": "A", "answer": "1"}]
        _raw_config = {
            "knowledge_base": {
                **empty_knowledge_base(),
                "faq": [{"question": "B", "answer": "2"}],
            }
        }

    assert knowledge_faq_list(T())[0]["question"] == "B"


def test_validate_config_patch_knowledge_base():
    from app.dashboard.config_validate import validate_config_patch

    out = validate_config_patch(
        "lead",
        {
            "knowledge_base": {
                "enabled": True,
                "status": "published",
                "sections": {"overview": "Hello"},
                "complete_knowledge": "",
                "faq": [{"question": "Q", "answer": "A"}],
            }
        },
    )
    assert out["knowledge_base"]["status"] == "published"
    assert out["faq"][0]["question"] == "Q"
