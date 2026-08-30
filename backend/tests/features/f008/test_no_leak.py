"""AC-F008-03：未发送的 suggestions 不进入 messages / 员工详情。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Suggestion

from .conftest import (
    AGENT_REPLY,
    DETAIL_PATH,
    HISTORY,
    MESSAGE_KEYS,
    OWN_OPEN_TITLE,
    REPLY_PATH,
    SUGGESTION_TEXT,
    AuthUser,
    add_suggestion,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


async def test_unsent_suggestion_not_in_employee_or_agent_messages(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="in_progress",
        messages=HISTORY,
    )
    suggestion_id = await add_suggestion(
        isolated_session_maker,
        ticket_id=ticket_id,
        content=SUGGESTION_TEXT,
    )
    assert suggestion_id > 0

    employee_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert employee_detail.status_code == 200
    employee_messages = employee_detail.json()["data"]["messages"]
    assert SUGGESTION_TEXT not in [item["content"] for item in employee_messages]
    assert [item["sender_type"] for item in employee_messages] == [
        "employee",
        "system",
        "employee",
    ]
    for item in employee_messages:
        assert set(item.keys()) == MESSAGE_KEYS
        assert "result_type" not in item
        assert "ticket_id" not in item

    agent_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert agent_detail.status_code == 200
    agent_messages = agent_detail.json()["data"]["messages"]
    assert SUGGESTION_TEXT not in [item["content"] for item in agent_messages]
    assert len(agent_messages) == 3

    async with isolated_session_maker() as db:
        suggestion_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Suggestion)
                    .where(Suggestion.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        message_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert suggestion_count == 1
        assert message_count == 3


async def test_agent_reply_does_not_copy_unsent_suggestion(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="in_progress",
        messages=HISTORY,
    )
    await add_suggestion(
        isolated_session_maker,
        ticket_id=ticket_id,
        content=SUGGESTION_TEXT,
    )

    replied = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert replied.status_code == 200
    assert replied.json()["data"]["content"] == AGENT_REPLY

    employee_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert employee_detail.status_code == 200
    contents = [item["content"] for item in employee_detail.json()["data"]["messages"]]
    assert AGENT_REPLY in contents
    assert SUGGESTION_TEXT not in contents
    assert contents.count(AGENT_REPLY) == 1
