"""F-004 首问建单：员工问题 + 系统答复 + 列表出现新咨询。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import Ticket
from src.main import app as runtime_app

from .conftest import MESSAGES_PATH, MINE_PATH, RUNTIME_DB

pytestmark = pytest.mark.timeout(300)

DETAIL_PATH = "/api/tickets/{ticket_id}"
CLARIFY_TEXT = "请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。"


def test_ticket_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert MESSAGES_PATH in paths
    assert MINE_PATH in paths


def test_ask_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


def _unit_vector() -> list[float]:
    dim = get_settings().embedding_dimensions
    return [1.0] + [0.0] * (dim - 1)


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    return [_unit_vector() for _ in texts]


async def _fake_intent(_self: object, messages: list[dict[str, str]], *, temperature: float) -> str:
    del messages, temperature
    return f'{{"intent":"ambiguous","question":"{CLARIFY_TEXT}"}}'


async def test_send_requires_auth(client: AsyncClient) -> None:
    response = await client.post(MESSAGES_PATH, json={"content": "VPN 连不上", "ticket_id": None})
    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHORIZED", "message": "未认证", "data": None}


async def test_empty_content_validation(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "   ", "ticket_id": None},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_first_question_creates_ticket_and_system_reply(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fake_embed)
    monkeypatch.setattr("src.services.qa_pipeline.LlmClient.complete", _fake_intent)

    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "公司 VPN 连不上，提示认证失败。", "ticket_id": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ticket"]["status"] == "ai_assisting"
    assert data["ticket"]["title"].startswith("公司 VPN")
    assert data["employee_message"]["sender_type"] == "employee"
    assert "VPN" in data["employee_message"]["content"]
    assert data["system_message"]["sender_type"] == "system"
    assert data["system_message"]["content"] == CLARIFY_TEXT
    assert data["qa_result_type"] == "clarification"

    listed = await client.get(MINE_PATH, headers=auth_headers)
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert listed.json()["data"]["total_items"] == 1
    assert items[0]["id"] == data["ticket"]["id"]
    assert items[0]["title"] == data["ticket"]["title"]

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=data["ticket"]["id"]),
        headers=auth_headers,
    )
    assert detail.status_code == 200
    messages = detail.json()["data"]["messages"]
    assert [item["sender_type"] for item in messages] == ["employee", "system"]
    assert messages[0]["content"] == data["employee_message"]["content"]
    assert messages[1]["content"] == CLARIFY_TEXT

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, data["ticket"]["id"])
        assert ticket is not None
        assert ticket.status == "ai_assisting"

    closed_id = data["ticket"]["id"]
    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, closed_id)
        assert ticket is not None
        ticket.status = "closed"
        await db.commit()

    closed = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "还是连不上", "ticket_id": closed_id},
    )
    assert closed.status_code == 409
    assert closed.json() == {
        "code": "CONFLICT",
        "message": "已完结，不能再发送",
        "data": None,
    }


async def _fake_generated_llm(
    _self: object, messages: list[dict[str, str]], *, temperature: float
) -> str:
    del temperature
    joined = " ".join(item["content"] for item in messages)
    if "意图分类器" in joined:
        return '{"intent":"clear"}'
    if "改写成" in joined:
        return "VPN 认证失败怎么办"
    return "当前知识不足以作答，请转人工或补充描述。"


async def test_clear_intent_without_knowledge_degrades(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fake_embed)
    monkeypatch.setattr("src.services.qa_pipeline.LlmClient.complete", _fake_generated_llm)

    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "公司 VPN 连不上，提示认证失败。", "ticket_id": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["qa_result_type"] == "degraded"
    assert data["system_message"]["content"] == get_settings().degraded_qa_message


async def test_unknown_ticket_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    missing = await client.get(DETAIL_PATH.format(ticket_id=9999), headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json() == {"code": "NOT_FOUND", "message": "资源不存在", "data": None}

    posted = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "你好", "ticket_id": 9999},
    )
    assert posted.status_code == 404
    assert posted.json() == {"code": "NOT_FOUND", "message": "资源不存在", "data": None}
