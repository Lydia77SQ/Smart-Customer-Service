"""AC-F007-02：接入后员工续发不产生系统自动答复。"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Ticket
from src.services.qa_pipeline import QaResult

from .conftest import (
    ACCEPT_PATH,
    DETAIL_PATH,
    EMPLOYEE_TEXT,
    FOLLOW_UP,
    MESSAGES_PATH,
    OWN_OPEN_TITLE,
    SYSTEM_TEXT,
    TRANSFER_PATH,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


async def _pipeline_must_not_run(
    _self: object,
    *,
    query: str,
    profile_json: str,
    recent_messages: Sequence[Message],
) -> QaResult:
    del query, profile_json, recent_messages
    raise AssertionError("接入后员工续发不得走答疑流水线")


async def test_employee_followup_after_accept_has_no_auto_reply(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.QaPipeline.run", _pipeline_must_not_run)
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="ai_assisting",
        messages=[
            ("employee", EMPLOYEE_TEXT),
            ("system", SYSTEM_TEXT),
        ],
    )

    transferred = await client.post(
        TRANSFER_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert transferred.status_code == 200
    assert transferred.json()["data"]["status"] == "pending"

    accepted = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "in_progress"
    history_before = [item["content"] for item in accepted.json()["data"]["messages"]]

    follow = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": FOLLOW_UP, "ticket_id": ticket_id},
    )
    assert follow.status_code == 200
    body = follow.json()["data"]
    assert body["ticket"]["id"] == ticket_id
    assert body["ticket"]["status"] == "in_progress"
    assert body["employee_message"]["content"] == FOLLOW_UP
    assert body["employee_message"]["sender_type"] == "employee"
    assert body["system_message"] is None
    assert body["qa_result_type"] == "none"

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    messages = detail.json()["data"]["messages"]
    assert [item["content"] for item in messages] == [*history_before, FOLLOW_UP]
    assert messages[-1]["sender_type"] == "employee"
    assert messages[-1]["content"] == FOLLOW_UP
    system_after_history = [
        item for item in messages[len(history_before) :] if item["sender_type"] == "system"
    ]
    assert system_after_history == []

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "in_progress"
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == len(history_before) + 1
