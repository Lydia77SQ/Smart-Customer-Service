"""AC-F008-01 / AC-F008-02：处理中回复对员工可见；已完结拒绝且不新增消息。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Ticket
from src.main import app as runtime_app

from .conftest import (
    AGENT_REPLY,
    CLOSED_REPLY_BODY,
    DETAIL_KEYS,
    DETAIL_PATH,
    HISTORY,
    MESSAGE_KEYS,
    NEED_ACCEPT_BODY,
    NOT_FOUND_BODY,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    QUEUE_PATH,
    REPLY_PATH,
    RUNTIME_DB,
    UNAUTHORIZED_BODY,
    VALIDATION_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


def test_reply_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert "/api/tickets/agent-queue" in paths
    assert "/api/tickets/{ticket_id}/agent-replies" in paths
    queue_order = None
    detail_order = None
    for index, route in enumerate(runtime_app.routes):
        path = getattr(route, "path", None)
        if path == "/api/tickets/agent-queue":
            queue_order = index
        if path == "/api/tickets/{ticket_id}":
            detail_order = index
    assert queue_order is not None
    assert detail_order is not None
    assert queue_order < detail_order


def test_reply_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_reply_requires_auth(client: AsyncClient) -> None:
    response = await client.post(REPLY_PATH.format(ticket_id=1), json={"content": AGENT_REPLY})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_agent_reply_visible_to_employee(
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
        category="IT-网络",
        messages=HISTORY,
    )

    queued = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "in_progress"},
    )
    assert queued.status_code == 200
    assert [item["id"] for item in queued.json()["data"]["items"]] == [ticket_id]

    replied = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert replied.status_code == 200
    payload = replied.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert set(data.keys()) == MESSAGE_KEYS
    assert data["sender_type"] == "agent"
    assert data["content"] == AGENT_REPLY
    assert data["id"] > 0
    assert data["created_at"].endswith("Z")

    employee_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert employee_detail.status_code == 200
    envelope = employee_detail.json()
    assert envelope["code"] == 200
    detail = envelope["data"]
    assert set(detail.keys()) == DETAIL_KEYS
    assert detail["id"] == ticket_id
    assert detail["status"] == "in_progress"
    assert [item["content"] for item in detail["messages"]] == [
        HISTORY[0][1],
        HISTORY[1][1],
        HISTORY[2][1],
        AGENT_REPLY,
    ]
    assert [item["sender_type"] for item in detail["messages"]] == [
        "employee",
        "system",
        "employee",
        "agent",
    ]
    for item in detail["messages"]:
        assert set(item.keys()) == MESSAGE_KEYS

    agent_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert agent_detail.status_code == 200
    assert agent_detail.json()["data"]["messages"][-1]["content"] == AGENT_REPLY
    assert agent_detail.json()["data"]["messages"][-1]["sender_type"] == "agent"

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
        assert count == 4


async def test_closed_ticket_reply_rejected_no_new_message(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_CLOSED_TITLE,
        status="closed",
        category="行政-工牌",
        messages=[
            ("employee", "工牌丢了，补办要找谁？"),
            ("system", "请到行政前台提交补办申请，携带身份证复印件。"),
        ],
    )

    rejected = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert rejected.status_code == 409
    assert rejected.json() == CLOSED_REPLY_BODY

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
    assert AGENT_REPLY not in [item["content"] for item in detail.json()["data"]["messages"]]

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


async def test_pending_ticket_reply_requires_accept(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="pending",
        messages=HISTORY,
    )
    rejected = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert rejected.status_code == 409
    assert rejected.json() == NEED_ACCEPT_BODY

    async with isolated_session_maker() as db:
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == 3


async def test_empty_reply_is_validation_error(
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
    empty = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": ""},
    )
    assert empty.status_code == 400
    assert empty.json() == VALIDATION_BODY

    whitespace = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": "   "},
    )
    assert whitespace.status_code == 400
    assert whitespace.json() == VALIDATION_BODY

    async with isolated_session_maker() as db:
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == 3


async def test_ai_assisting_reply_hidden_from_other_user(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="ai_assisting",
        messages=[("employee", HISTORY[0][1])],
    )
    hidden = await client.post(
        REPLY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY


async def test_reply_missing_ticket_is_not_found(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
) -> None:
    _user_a, user_b = users
    missing = await client.post(
        REPLY_PATH.format(ticket_id=99999),
        headers=user_b["headers"],
        json={"content": AGENT_REPLY},
    )
    assert missing.status_code == 404
    assert missing.json() == NOT_FOUND_BODY
