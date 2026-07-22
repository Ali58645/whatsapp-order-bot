"""End-to-end knowledge-base flow coverage (offline + clear AI-error path)."""

from __future__ import annotations

import pytest

from app.dashboard.config_validate import validate_config_patch
from app.faq import match_faq
from app.knowledge import (
    _UNAVAILABLE,
    answer_from_knowledge,
    build_published_corpus,
    empty_knowledge_base,
    grounding_excerpts,
    invalidate_knowledge_cache,
    knowledge_char_count,
    migrate_faq_into_knowledge,
    preview_knowledge_answer,
    validate_knowledge_base,
)

REALISTIC_KB = {
    "enabled": True,
    "status": "published",
    "complete_knowledge": (
        "AccellionX is a US-registered software and AI automation agency specializing in "
        "senior living and healthcare operations. We build custom EHR integrations, "
        "operational dashboards, and AI voice/chat agents for senior care communities."
    ),
    "sections": {
        "overview": (
            "AccellionX is based in Sheridan, Wyoming, USA with an engineering hub in Lahore, "
            "Pakistan. We eliminate manual administrative friction for senior living providers."
        ),
        "products_services": (
            "• EHR Integration & Reporting Automation (PointClickCare, MatrixCare, Eldermark)\n"
            "• Operational dashboards for occupancy and staffing\n"
            "• AI voice and chat agents for family and resident intake"
        ),
        "pricing": "Custom quotes based on facility size — contact sales for packages.",
        "business_hours": "Mon–Fri 9am–6pm PKT / overlapping US hours.",
        "locations": "Sheridan WY (HQ) · Lahore (delivery) · remote US clients",
        "contact": "WhatsApp bot or email hello@accellionx.example",
        "payment_methods": "Invoice / wire for enterprise contracts.",
        "delivery_booking": "Book a demo via WhatsApp — we confirm a slot with your team.",
        "policies": "NDA available. Data handled under BAA-ready processes for healthcare.",
        "additional": "Focus: senior living and care facilities only.",
    },
    "faq": [
        {
            "question": "Do you work with PointClickCare?",
            "answer": "Yes — we automate PCC reporting and integrations.",
        },
        {
            "question": "Where are you based?",
            "answer": "HQ in Sheridan, Wyoming with engineering in Lahore.",
        },
    ],
}


class GoodClient:
    class messages:
        @staticmethod
        async def create(**kwargs):
            user = kwargs["messages"][0]["content"]
            assert "COMPANY KNOWLEDGE" in user
            # Only score the customer question, not the knowledge blob
            cust = user.split("Customer message:", 1)[-1].lower()
            if "pizza" in cust:
                text = _UNAVAILABLE
            elif "pointclickcare" in cust or "pcc" in cust:
                text = "Yes — we automate PointClickCare (PCC) reporting and integrations."
            elif "based" in cust or ("where" in cust and "you" in cust):
                text = "Our HQ is in Sheridan, Wyoming, with engineering in Lahore, Pakistan."
            elif "pric" in cust:
                text = "Pricing is custom by facility size — contact sales for a package quote."
            else:
                text = (
                    "We automate EHR reporting (PointClickCare, MatrixCare, Eldermark), "
                    "operational dashboards for occupancy/staffing, and AI voice/chat agents "
                    "for resident and family intake."
                )

            class R:
                content = [type("B", (), {"text": text})()]

            return R()


class AuthFailClient:
    class messages:
        @staticmethod
        async def create(**kwargs):
            raise RuntimeError("Error code: 401 - authentication_error: invalid x-api-key")


def test_full_validate_migrate_corpus_faq():
    kb = validate_knowledge_base(REALISTIC_KB)
    assert kb["status"] == "published"
    assert knowledge_char_count(kb) > 500
    corpus = build_published_corpus(kb)
    assert "PointClickCare" in corpus
    assert "Sheridan" in corpus

    draft = validate_knowledge_base({**REALISTIC_KB, "status": "draft"})
    assert build_published_corpus(draft) == ""

    cfg = migrate_faq_into_knowledge({"faq": [{"question": "Hours?", "answer": "9-5"}]})
    assert cfg["knowledge_base"]["faq"][0]["answer"] == "9-5"

    faq_ans = match_faq("do you work with pointclickcare?", kb["faq"])
    assert faq_ans and "PCC" in faq_ans

    patched = validate_config_patch("lead", {"knowledge_base": REALISTIC_KB})
    assert patched["knowledge_base"]["enabled"] is True
    assert patched["faq"]


def test_grounding_includes_full_realistic_kb():
    kb = validate_knowledge_base(REALISTIC_KB)
    corpus = build_published_corpus(kb)
    ex = grounding_excerpts(corpus, "What operational workflows can AccellionX automate?")
    assert "EHR Integration" in ex
    assert "AI voice" in ex
    assert "Wyoming" in ex


@pytest.mark.asyncio
async def test_preview_flow_realistic_questions():
    questions = [
        ("What operational workflows can AccellionX automate?", True, ("EHR", "dashboard", "AI")),
        ("Do you integrate with PointClickCare?", True, ("PointClickCare", "PCC", "Yes")),
        ("Where are you based?", True, ("Wyoming", "Lahore", "Sheridan")),
        ("What is your pricing?", True, ("custom", "sales", "quote")),
        ("Do you sell pizza?", False, ()),
    ]
    for q, expect_match, needles in questions:
        r = await preview_knowledge_answer(
            q, REALISTIC_KB, client=GoodClient(), model="test", lang_hint="en"
        )
        assert r["matched"] is expect_match, (q, r)
        assert r.get("used_ai") is True
        if expect_match:
            assert any(n.lower() in r["answer"].lower() for n in needles), (q, r["answer"])
        else:
            assert "confirmed information" in r["answer"].lower()


@pytest.mark.asyncio
async def test_preview_surfaces_ai_auth_failure():
    r = await preview_knowledge_answer(
        "What do you automate?",
        REALISTIC_KB,
        client=AuthFailClient(),
        model="test",
    )
    assert r["matched"] is False
    assert r["used_ai"] is False
    assert "API key" in (r.get("detail") or "") or "authentication" in (r.get("detail") or "").lower()
    assert "could not reach the AI" in r["answer"]


@pytest.mark.asyncio
async def test_whatsapp_path_respects_enable_and_draft():
    class T:
        phone_number_id = "flow-t"
        faq_list = []
        _raw_config = {
            "knowledge_base": validate_knowledge_base({**REALISTIC_KB, "enabled": False}),
            "faq": [],
        }

    invalidate_knowledge_cache("flow-t")
    assert (
        await answer_from_knowledge(
            "What do you automate?", T(), client=GoodClient(), model="t", miss_policy="unavailable"
        )
        is None
    )

    T._raw_config = {
        "knowledge_base": validate_knowledge_base({**REALISTIC_KB, "status": "draft"}),
        "faq": [],
    }
    invalidate_knowledge_cache("flow-t")
    assert (
        await answer_from_knowledge(
            "What do you automate?", T(), client=GoodClient(), model="t", miss_policy="unavailable"
        )
        is None
    )


@pytest.mark.asyncio
async def test_cache_invalidation_picks_up_updates():
    class T:
        phone_number_id = "cache-t"
        faq_list = []
        _raw_config = {
            "knowledge_base": validate_knowledge_base(
                {
                    **empty_knowledge_base(),
                    "enabled": True,
                    "status": "published",
                    "complete_knowledge": "We only sell hats.",
                }
            )
        }

    class Client:
        class messages:
            @staticmethod
            async def create(**kwargs):
                user = kwargs["messages"][0]["content"]

                class R:
                    content = [
                        type(
                            "B",
                            (),
                            {"text": "hats" if "hats" in user.lower() else "shoes"},
                        )()
                    ]

                return R()

    invalidate_knowledge_cache("cache-t")
    a1 = await answer_from_knowledge(
        "What do you sell?", T(), client=Client(), model="t", miss_policy="unavailable"
    )
    assert a1 and "hat" in a1.lower()

    T._raw_config = {
        "knowledge_base": validate_knowledge_base(
            {
                **empty_knowledge_base(),
                "enabled": True,
                "status": "published",
                "complete_knowledge": "We only sell shoes.",
            }
        )
    }
    invalidate_knowledge_cache("cache-t")
    a2 = await answer_from_knowledge(
        "What do you sell?", T(), client=Client(), model="t", miss_policy="unavailable"
    )
    assert a2 and "shoe" in a2.lower()


@pytest.mark.asyncio
async def test_disabled_and_empty_preview():
    r = await preview_knowledge_answer(
        "Hi", {**REALISTIC_KB, "enabled": False}, client=GoodClient(), model="t"
    )
    assert "disabled" in r["answer"].lower()

    r2 = await preview_knowledge_answer(
        "Hi", empty_knowledge_base(), client=GoodClient(), model="t"
    )
    assert r2["matched"] is False
