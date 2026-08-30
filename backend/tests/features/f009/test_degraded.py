"""AC-F009-03：外部能力不可用时返回 DEGRADED_SUGGESTION_MESSAGE，不写员工系统消息。

成功路径由 monkeypatch 覆盖；本文件只验证降级。不得宣称 Chat/Embedding/Rerank 全路径完整联调通过。
"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import Message, Suggestion
from src.services.embedding import EmbeddingError, is_embedding_key_configured
from src.services.llm import parse_chat_content
from src.services.rerank import parse_rerank_indices

from .conftest import (
    DETAIL_PATH,
    HISTORY,
    OWN_OPEN_TITLE,
    SUGGEST_PATH,
    SUGGESTION_KEYS,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(300)


async def _fail_embed(_self: object, texts: list[str]) -> list[list[float]]:
    del texts
    raise EmbeddingError("向量化服务未配置")


def test_parse_helpers_reuse_t016_shapes() -> None:
    content = parse_chat_content(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {"content": "好", "role": "assistant"},
                }
            ],
            "object": "chat.completion",
        }
    )
    assert content == "好"
    ranked = parse_rerank_indices(
        {
            "output": {
                "results": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.2},
                ]
            }
        }
    )
    assert ranked[0][0] == 1


def test_dashscope_key_status_without_exposing_secret() -> None:
    settings = get_settings()
    configured = is_embedding_key_configured(settings.dashscope_api_key)
    assert isinstance(configured, bool)


async def test_external_unavailable_returns_degraded_suggestion(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fail_embed)
    expected = get_settings().degraded_suggestion_message
    qa_fallback = get_settings().degraded_qa_message
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="in_progress",
        messages=HISTORY,
    )

    created = await client.post(
        SUGGEST_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert created.status_code == 200
    data = created.json()["data"]
    assert set(data.keys()) == SUGGESTION_KEYS
    assert data["result_type"] == "degraded"
    assert data["content"] == expected
    assert data["content"] == "暂时无法生成建议。请手写回复，不要向员工发送自动消息。"
    assert data["content"] != qa_fallback

    employee_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert employee_detail.status_code == 200
    employee_messages = employee_detail.json()["data"]["messages"]
    contents = [item["content"] for item in employee_messages]
    assert expected not in contents
    assert qa_fallback not in contents
    assert [item["sender_type"] for item in employee_messages] == [
        "employee",
        "system",
        "employee",
    ]

    async with isolated_session_maker() as db:
        message_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        suggestion_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Suggestion)
                    .where(Suggestion.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        row = (
            await db.execute(select(Suggestion).where(Suggestion.ticket_id == ticket_id))
        ).scalar_one()
    assert message_count == 3
    assert suggestion_count == 1
    assert row.content == expected
    assert row.result_type == "degraded"


@pytest.mark.skipif(not os.getenv("REAL_API_TEST"), reason="REAL_API_TEST not set")
async def test_real_chat_structure_when_enabled() -> None:
    """仅 REAL_API_TEST=1 时打真实 Chat；默认 pytest 不调用，不得宣称完整联调通过。"""
    settings = get_settings()
    assert is_embedding_key_configured(settings.dashscope_api_key) is True
    from src.services.llm import LlmClient

    text = await LlmClient().complete(
        [{"role": "user", "content": "只回复一个字：好"}],
        temperature=0.1,
    )
    assert isinstance(text, str)
    assert len(text) >= 1
