"""AC-F011-02：无 reopen 路由；已完结结单幂等且不能恢复发言。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Ticket
from src.main import app as runtime_app

from .conftest import (
    AGENT_REPLY,
    CLOSE_PATH,
    CLOSED_SEND_BODY,
    DETAIL_PATH,
    EMPLOYEE_FOLLOW,
    MESSAGE_KEYS,
    MESSAGES_PATH,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    REPLY_PATH,
    SUMMARY_KEYS,
    TARGET_CATEGORY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


def test_runtime_app_has_no_reopen_route() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    reopen_paths = [path for path in paths if path is not None and "reopen" in path]
    assert reopen_paths == []
    assert "/api/tickets/{ticket_id}/close" in paths


async def test_closed_close_is_idempotent_and_cannot_resume(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    history = [
        ("employee", "工牌丢了，补办要找谁？"),
        ("system", "请到行政前台提交补办申请，携带身份证复印件。"),
    ]
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_CLOSED_TITLE,
        status="closed",
        category="行政-工牌",
        messages=history,
    )

    first = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert first.status_code == 200
    summary = first.json()["data"]
    assert set(summary.keys()) == SUMMARY_KEYS
    assert summary["status"] == "closed"
    first_updated = summary["updated_at"]

    second = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "closed"
    assert second.json()["data"]["updated_at"] == first_updated

    employee_send = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": EMPLOYEE_FOLLOW, "ticket_id": ticket_id},
    )
    assert employee_send.status_code == 409
    assert employee_send.json() == CLOSED_SEND_BODY

    agent_reply = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert agent_reply.status_code == 409
    assert agent_reply.json() == CLOSED_SEND_BODY

    reopen = await client.post(
        f"/api/tickets/{ticket_id}/reopen",
        headers=user_b["headers"],
    )
    assert reopen.status_code in {400, 404, 405}
    assert reopen.json().get("data") is None or reopen.status_code == 405

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "closed"
    assert [item["sender_type"] for item in detail.json()["data"]["messages"]] == [
        "employee",
        "system",
    ]
    for item in detail.json()["data"]["messages"]:
        assert set(item.keys()) == MESSAGE_KEYS

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "closed"
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == 2


async def test_in_progress_close_then_stays_closed(
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
        category=TARGET_CATEGORY,
        messages=[("employee", "公司 VPN 连不上，提示认证失败。")],
    )
    closed = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert closed.status_code == 200
    first_updated = closed.json()["data"]["updated_at"]

    again = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "closed"
    assert again.json()["data"]["updated_at"] == first_updated
