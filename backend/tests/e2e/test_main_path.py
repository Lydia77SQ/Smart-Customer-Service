"""Plan.md §7 主链路回归：注册→登录→上传→启停→提问→转人工→接入→建议不泄漏→回复→分类→结单。

不替代 T-011～T-023 各 Feature 首次联调。外部百炼调用一律 monkeypatch，见 fallback 标注。
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import KnowledgeChunk, KnowledgeDocument, Message, QaPair, Suggestion, Ticket
from src.main import app as runtime_app
from src.services.qa_pipeline import QaResult

from .conftest import (
    ACCEPT_PATH,
    AGENT_ACCOUNT,
    AGENT_REPLY,
    CATEGORY_PATH,
    CLOSE_PATH,
    CLOSED_SEND_BODY,
    DETAIL_PATH,
    EMPLOYEE_ACCOUNT,
    EMPLOYEE_QUESTION,
    LIST_KNOWLEDGE_PATH,
    LOGIN_PATH,
    ME_PATH,
    MESSAGES_PATH,
    MINE_PATH,
    PASSWORD,
    PATCH_KNOWLEDGE_PATH,
    QUEUE_PATH,
    REGISTER_PATH,
    REPLY_PATH,
    RUNTIME_DB,
    SUGGEST_PATH,
    SUGGESTION_TEXT,
    SYSTEM_ANSWER,
    TARGET_CATEGORY,
    TRANSFER_PATH,
    UPLOAD_PATH,
    VPN_MARKDOWN,
)

pytestmark = pytest.mark.timeout(600)


class AuthUser(TypedDict):
    id: int
    account: str
    headers: dict[str, str]


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    dim = get_settings().embedding_dimensions
    return [[0.01] * dim for _ in texts]


async def _register_and_login(
    client: AsyncClient, account: str, password: str
) -> AuthUser:
    registered = await client.post(
        REGISTER_PATH,
        json={"account": account, "password": password},
    )
    assert registered.status_code == 200
    user = registered.json()["data"]
    assert user["account"] == account
    assert "password" not in user

    login = await client.post(LOGIN_PATH, json={"account": account, "password": password})
    assert login.status_code == 200
    session = login.json()["data"]
    token = session["token"]
    assert token
    assert session["user"]["id"] == user["id"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get(ME_PATH, headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["id"] == user["id"]
    assert me.json()["data"]["account"] == account
    return {"id": int(user["id"]), "account": account, "headers": headers}


def test_e2e_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


def test_main_path_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    required = {
        REGISTER_PATH,
        LOGIN_PATH,
        ME_PATH,
        UPLOAD_PATH,
        "/api/knowledge_documents/{document_id}",
        MESSAGES_PATH,
        "/api/tickets/{ticket_id}/transfer",
        "/api/tickets/agent-queue",
        "/api/tickets/{ticket_id}/accept",
        "/api/tickets/{ticket_id}/suggestions",
        "/api/tickets/{ticket_id}/agent-replies",
        "/api/tickets/{ticket_id}/category",
        "/api/tickets/{ticket_id}/close",
    }
    assert required.issubset(paths)
    reopen_paths = [path for path in paths if path is not None and "reopen" in path]
    assert reopen_paths == []


async def test_plan_section7_main_path(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
    isolated_upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.knowledge.EmbeddingClient.embed_texts", _fake_embed)
    qa_results = [
        QaResult("clarification", SYSTEM_ANSWER),
        QaResult("generated_answer", SUGGESTION_TEXT),
    ]

    async def _fake_qa(
        _self: object,
        *,
        query: str,
        profile_json: str,
        recent_messages: list[object],
    ) -> QaResult:
        del query, profile_json, recent_messages
        assert qa_results, "unexpected extra QaPipeline.run call"
        return qa_results.pop(0)

    monkeypatch.setattr("src.services.ticket.QaPipeline.run", _fake_qa)

    employee = await _register_and_login(client, EMPLOYEE_ACCOUNT, PASSWORD)
    agent = await _register_and_login(client, AGENT_ACCOUNT, PASSWORD)

    uploaded = await client.post(
        UPLOAD_PATH,
        headers=agent["headers"],
        files={"file": ("VPN接入说明.md", VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert uploaded.status_code == 200
    document = uploaded.json()["data"]
    document_id = int(document["id"])
    assert document["status"] == "enabled"
    assert document["filename"] == "VPN接入说明.md"
    stored = isolated_upload_dir / f"{document_id}.md"
    assert stored.is_file()

    async with isolated_session_maker() as db:
        chunk_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == document_id)
                )
            ).scalar_one()
        )
        qa_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(QaPair).where(QaPair.document_id == document_id)
                )
            ).scalar_one()
        )
        assert chunk_count >= 1
        assert qa_count >= 1

    disabled = await client.patch(
        PATCH_KNOWLEDGE_PATH.format(document_id=document_id),
        headers=agent["headers"],
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == "disabled"

    listed_disabled = await client.get(LIST_KNOWLEDGE_PATH, headers=agent["headers"])
    assert listed_disabled.status_code == 200
    items = listed_disabled.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == document_id
    assert items[0]["status"] == "disabled"
    assert stored.is_file()
    assert stored.read_text(encoding="utf-8") == VPN_MARKDOWN

    async with isolated_session_maker() as db:
        row = (
            await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        ).scalar_one()
        assert row.status == "disabled"
        chunks_after = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == document_id)
                )
            ).scalar_one()
        )
        qa_after = int(
            (
                await db.execute(
                    select(func.count()).select_from(QaPair).where(QaPair.document_id == document_id)
                )
            ).scalar_one()
        )
        assert chunks_after == chunk_count
        assert qa_after == qa_count

    enabled = await client.patch(
        PATCH_KNOWLEDGE_PATH.format(document_id=document_id),
        headers=agent["headers"],
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["status"] == "enabled"

    asked = await client.post(
        MESSAGES_PATH,
        headers=employee["headers"],
        json={"content": EMPLOYEE_QUESTION, "ticket_id": None},
    )
    assert asked.status_code == 200
    asked_data = asked.json()["data"]
    ticket_id = int(asked_data["ticket"]["id"])
    assert asked_data["ticket"]["status"] == "ai_assisting"
    assert asked_data["qa_result_type"] == "clarification"
    assert asked_data["system_message"]["content"] == SYSTEM_ANSWER

    transferred = await client.post(
        TRANSFER_PATH.format(ticket_id=ticket_id),
        headers=employee["headers"],
    )
    assert transferred.status_code == 200
    assert transferred.json()["data"]["status"] == "pending"

    queued = await client.get(
        QUEUE_PATH,
        headers=agent["headers"],
        params={"status": "pending"},
    )
    assert queued.status_code == 200
    assert any(item["id"] == ticket_id for item in queued.json()["data"]["items"])

    accepted = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=agent["headers"],
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "in_progress"

    suggested = await client.post(
        SUGGEST_PATH.format(ticket_id=ticket_id),
        headers=agent["headers"],
        json={"focus_message_id": None},
    )
    assert suggested.status_code == 200
    suggestion = suggested.json()["data"]
    assert suggestion["content"] == SUGGESTION_TEXT
    assert suggestion["result_type"] == "generated_answer"
    assert "ticket_id" not in suggestion

    employee_after_suggest = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=employee["headers"],
    )
    assert employee_after_suggest.status_code == 200
    employee_messages = employee_after_suggest.json()["data"]["messages"]
    employee_contents = [item["content"] for item in employee_messages]
    assert SUGGESTION_TEXT not in employee_contents
    assert SYSTEM_ANSWER in employee_contents
    assert get_settings().transfer_success_message in employee_contents

    async with isolated_session_maker() as db:
        suggestion_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Suggestion).where(Suggestion.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert suggestion_count == 1

    replied = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=agent["headers"],
        json={"content": AGENT_REPLY},
    )
    assert replied.status_code == 200
    assert replied.json()["data"]["sender_type"] == "agent"
    assert replied.json()["data"]["content"] == AGENT_REPLY

    classified = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=agent["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert classified.status_code == 200
    assert classified.json()["data"]["category"] == TARGET_CATEGORY
    assert classified.json()["data"]["status"] == "in_progress"

    closed = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=agent["headers"],
    )
    assert closed.status_code == 200
    assert closed.json()["data"]["status"] == "closed"
    assert closed.json()["data"]["category"] == TARGET_CATEGORY

    employee_send = await client.post(
        MESSAGES_PATH,
        headers=employee["headers"],
        json={"content": "还是连不上，请再帮我看一下。", "ticket_id": ticket_id},
    )
    assert employee_send.status_code == 409
    assert employee_send.json() == CLOSED_SEND_BODY

    agent_send = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=agent["headers"],
        json={"content": AGENT_REPLY},
    )
    assert agent_send.status_code == 409
    assert agent_send.json() == CLOSED_SEND_BODY

    reopen = await client.post(
        f"/api/tickets/{ticket_id}/reopen",
        headers=agent["headers"],
    )
    assert reopen.status_code in {400, 404, 405}

    employee_final = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=employee["headers"],
    )
    assert employee_final.status_code == 200
    final_detail = employee_final.json()["data"]
    assert final_detail["status"] == "closed"
    assert final_detail["category"] == TARGET_CATEGORY
    final_contents = [item["content"] for item in final_detail["messages"]]
    assert SUGGESTION_TEXT not in final_contents
    assert AGENT_REPLY in final_contents
    assert [item["sender_type"] for item in final_detail["messages"]] == [
        "employee",
        "system",
        "system",
        "agent",
    ]

    mine = await client.get(MINE_PATH, headers=employee["headers"])
    assert mine.status_code == 200
    listed = next(item for item in mine.json()["data"]["items"] if item["id"] == ticket_id)
    assert listed["status"] == "closed"

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "closed"
        message_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert message_count == 4
        still_there = await db.get(KnowledgeDocument, document_id)
        assert still_there is not None
        assert still_there.status == "enabled"
