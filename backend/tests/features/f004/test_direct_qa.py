"""F-004 高置信标准问答直接作答，不走反问或生成。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import KnowledgeDocument, QaPair
from src.services.knowledge import pack_embedding

from .conftest import MESSAGES_PATH

pytestmark = pytest.mark.timeout(300)

DIRECT_ANSWER = "请到行政前台提交补办申请，携带身份证复印件。"


def _unit_vector(index: int = 0) -> list[float]:
    dim = get_settings().embedding_dimensions
    vector = [0.0] * dim
    vector[index] = 1.0
    return vector


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    return [_unit_vector(0) for _ in texts]


async def _llm_must_not_run(
    _self: object, messages: list[dict[str, str]], *, temperature: float
) -> str:
    del messages, temperature
    raise AssertionError("高置信直出不得调用意图或生成")


async def test_high_confidence_qa_direct_answer(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fake_embed)
    monkeypatch.setattr("src.services.qa_pipeline.LlmClient.complete", _llm_must_not_run)

    async with isolated_session_maker() as db:
        document = KnowledgeDocument(
            filename="工牌补办流程.md",
            storage_path="badge.md",
            status="enabled",
        )
        db.add(document)
        await db.flush()
        db.add(
            QaPair(
                document_id=document.id,
                question="工牌补办要找谁",
                answer=DIRECT_ANSWER,
                embedding=pack_embedding(_unit_vector(0)),
            )
        )
        await db.commit()

    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "工牌丢了，补办要找谁？", "ticket_id": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["qa_result_type"] == "direct_answer"
    assert data["system_message"]["content"] == DIRECT_ANSWER
    assert "请补充" not in data["system_message"]["content"]
