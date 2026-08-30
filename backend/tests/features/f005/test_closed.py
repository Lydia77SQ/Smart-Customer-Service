"""AC-F005-03：已完结咨询只读，发送被拒绝并提示已完结。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message

from .conftest import (
    CLOSED_MESSAGE,
    DETAIL_PATH,
    MESSAGES_PATH,
    OWN_CLOSED_TITLE,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)

CLOSED_CONFLICT = {"code": "CONFLICT", "message": CLOSED_MESSAGE, "data": None}
EMPLOYEE_TEXT = "工牌丢了，补办要找谁？"
SYSTEM_TEXT = "请到行政前台提交补办申请，携带身份证复印件。"


async def test_closed_ticket_detail_is_readable_and_send_rejected(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, _user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_CLOSED_TITLE,
        status="closed",
        category="行政-工牌",
        messages=[
            ("employee", EMPLOYEE_TEXT),
            ("system", SYSTEM_TEXT),
        ],
    )

    detail = await client.get(DETAIL_PATH.format(ticket_id=ticket_id), headers=user_a["headers"])
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["status"] == "closed"
    assert data["title"] == OWN_CLOSED_TITLE
    assert [item["content"] for item in data["messages"]] == [EMPLOYEE_TEXT, SYSTEM_TEXT]

    rejected = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": "还想再问一句", "ticket_id": ticket_id},
    )
    assert rejected.status_code == 409
    assert rejected.json() == CLOSED_CONFLICT

    after = await client.get(DETAIL_PATH.format(ticket_id=ticket_id), headers=user_a["headers"])
    assert after.status_code == 200
    assert after.json()["data"]["status"] == "closed"
    assert len(after.json()["data"]["messages"]) == 2

    async with isolated_session_maker() as db:
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == 2
