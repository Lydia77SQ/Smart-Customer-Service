"""F-004 停用文档不得作为本轮答复依据。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import KnowledgeChunk, KnowledgeDocument, QaPair
from src.services.knowledge import pack_embedding

from .conftest import MESSAGES_PATH

pytestmark = pytest.mark.timeout(300)

DISABLED_FILENAME = "工牌补办流程.md"
DISABLED_ANSWER = "请到行政前台提交补办申请，携带身份证复印件。文档名工牌补办流程.md"
CLARIFY_TEXT = "请补充你要办理的是工牌还是门禁，以及丢失还是损坏。"


def _unit_vector(index: int) -> list[float]:
    dim = get_settings().embedding_dimensions
    vector = [0.0] * dim
    vector[index] = 1.0
    return vector


async def _query_matches_disabled(_self: object, texts: list[str]) -> list[list[float]]:
    del texts
    return [_unit_vector(1)]


async def _fake_intent(_self: object, messages: list[dict[str, str]], *, temperature: float) -> str:
    del messages, temperature
    return f'{{"intent":"ambiguous","question":"{CLARIFY_TEXT}"}}'


async def test_disabled_document_not_used_as_answer(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.services.qa_pipeline.EmbeddingClient.embed_texts",
        _query_matches_disabled,
    )
    monkeypatch.setattr("src.services.qa_pipeline.LlmClient.complete", _fake_intent)

    async with isolated_session_maker() as db:
        enabled = KnowledgeDocument(
            filename="VPN接入说明.md",
            storage_path="vpn.md",
            status="enabled",
        )
        disabled = KnowledgeDocument(
            filename=DISABLED_FILENAME,
            storage_path="badge.md",
            status="disabled",
        )
        db.add_all([enabled, disabled])
        await db.flush()
        db.add(
            QaPair(
                document_id=enabled.id,
                question="VPN 连不上怎么办",
                answer="请使用公司门户的 VPN 客户端。",
                embedding=pack_embedding(_unit_vector(0)),
            )
        )
        db.add(
            QaPair(
                document_id=disabled.id,
                question="工牌补办要找谁",
                answer=DISABLED_ANSWER,
                embedding=pack_embedding(_unit_vector(1)),
            )
        )
        db.add(
            KnowledgeChunk(
                document_id=disabled.id,
                chunk_index=0,
                content=f"{DISABLED_FILENAME} 补办流程正文",
                embedding=pack_embedding(_unit_vector(1)),
            )
        )
        await db.commit()

    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "工牌丢了补办要找谁？", "ticket_id": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    content = data["system_message"]["content"]
    assert DISABLED_FILENAME not in content
    assert DISABLED_ANSWER not in content
    assert data["qa_result_type"] != "direct_answer"
