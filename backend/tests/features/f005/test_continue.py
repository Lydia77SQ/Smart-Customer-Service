"""AC-F005-02：未完结咨询续聊写入同一工单对话。"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Ticket
from src.services.qa_pipeline import QaResult

from .conftest import (
    DETAIL_PATH,
    MESSAGES_PATH,
    MINE_PATH,
    NOT_FOUND_BODY,
    OWN_OPEN_TITLE,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)

CLARIFY_TEXT = "请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。"
FOLLOW_UP = "Windows。今天早上开始的。"


async def _fake_qa(
    _self: object,
    *,
    query: str,
    profile_json: str,
    recent_messages: Sequence[Message],
) -> QaResult:
    del query, profile_json, recent_messages
    return QaResult("clarification", CLARIFY_TEXT)


async def test_continue_ai_assisting_appends_to_same_ticket(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.QaPipeline.run", _fake_qa)
    user_a, _user_b = users
    first = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": "公司 VPN 连不上，提示认证失败。", "ticket_id": None},
    )
    assert first.status_code == 200
    ticket_id = first.json()["data"]["ticket"]["id"]
    assert first.json()["data"]["ticket"]["status"] == "ai_assisting"

    second = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": FOLLOW_UP, "ticket_id": ticket_id},
    )
    assert second.status_code == 200
    payload = second.json()["data"]
    assert payload["ticket"]["id"] == ticket_id
    assert payload["employee_message"]["content"] == FOLLOW_UP
    assert payload["employee_message"]["sender_type"] == "employee"
    assert payload["system_message"]["content"] == CLARIFY_TEXT

    detail = await client.get(DETAIL_PATH.format(ticket_id=ticket_id), headers=user_a["headers"])
    assert detail.status_code == 200
    messages = detail.json()["data"]["messages"]
    assert [item["sender_type"] for item in messages] == [
        "employee",
        "system",
        "employee",
        "system",
    ]
    assert messages[2]["content"] == FOLLOW_UP
    assert messages[3]["content"] == CLARIFY_TEXT

    listed = await client.get(MINE_PATH, headers=user_a["headers"])
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert listed.json()["data"]["total_items"] == 1
    assert items[0]["id"] == ticket_id

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "ai_assisting"


@pytest.mark.parametrize("status", ["pending", "in_progress"])
async def test_continue_manual_statuses_do_not_create_system_reply(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    status: str,
) -> None:
    user_a, _user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status=status,
        messages=[("employee", "公司 VPN 连不上，提示认证失败。")],
    )
    response = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": FOLLOW_UP, "ticket_id": ticket_id},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ticket"]["id"] == ticket_id
    assert data["ticket"]["status"] == status
    assert data["system_message"] is None
    assert data["qa_result_type"] == "none"
    assert data["employee_message"]["content"] == FOLLOW_UP

    detail = await client.get(DETAIL_PATH.format(ticket_id=ticket_id), headers=user_a["headers"])
    messages = detail.json()["data"]["messages"]
    assert [item["sender_type"] for item in messages] == ["employee", "employee"]
    assert messages[1]["content"] == FOLLOW_UP


async def test_continue_other_users_ticket_not_found(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    other_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_b["id"],
        title="他不该看见的咨询",
        status="ai_assisting",
        messages=[("employee", "这是其他账号的咨询。")],
    )
    posted = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": FOLLOW_UP, "ticket_id": other_id},
    )
    assert posted.status_code == 404
    assert posted.json() == NOT_FOUND_BODY
