"""AC-F011-01 / AC-F011-03：处理中可结单且双方拒发；待处理拒绝结单。"""

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
    AI_CLOSE_BODY,
    CLOSE_PATH,
    CLOSED_SEND_BODY,
    DETAIL_KEYS,
    DETAIL_PATH,
    EMPLOYEE_FOLLOW,
    HISTORY,
    MESSAGE_KEYS,
    MESSAGES_PATH,
    MINE_PATH,
    NOT_FOUND_BODY,
    OWN_OPEN_TITLE,
    OWN_PENDING_TITLE,
    PENDING_CLOSE_BODY,
    QUEUE_PATH,
    REPLY_PATH,
    RUNTIME_DB,
    SUMMARY_KEYS,
    TARGET_CATEGORY,
    UNAUTHORIZED_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


def test_close_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert "/api/tickets/agent-queue" in paths
    assert "/api/tickets/{ticket_id}/close" in paths
    queue_order = None
    close_order = None
    detail_order = None
    for index, route in enumerate(runtime_app.routes):
        path = getattr(route, "path", None)
        if path == "/api/tickets/agent-queue":
            queue_order = index
        if path == "/api/tickets/{ticket_id}/close":
            close_order = index
        if path == "/api/tickets/{ticket_id}":
            detail_order = index
    assert queue_order is not None
    assert close_order is not None
    assert detail_order is not None
    assert queue_order < detail_order
    assert close_order < detail_order


def test_close_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_close_requires_auth(client: AsyncClient) -> None:
    response = await client.post(CLOSE_PATH.format(ticket_id=1))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_in_progress_close_blocks_both_sides(
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
        messages=HISTORY,
    )

    closed = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert closed.status_code == 200
    payload = closed.json()
    assert payload["code"] == 200
    summary = payload["data"]
    assert set(summary.keys()) == SUMMARY_KEYS
    assert summary["id"] == ticket_id
    assert summary["status"] == "closed"
    assert summary["category"] == TARGET_CATEGORY
    assert summary["title"] == OWN_OPEN_TITLE
    assert summary["created_at"].endswith("Z")
    assert summary["updated_at"].endswith("Z")

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

    employee_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert employee_detail.status_code == 200
    detail = employee_detail.json()["data"]
    assert set(detail.keys()) == DETAIL_KEYS
    assert detail["status"] == "closed"
    assert [item["content"] for item in detail["messages"]] == [row[1] for row in HISTORY]
    for item in detail["messages"]:
        assert set(item.keys()) == MESSAGE_KEYS

    mine = await client.get(MINE_PATH, headers=user_a["headers"])
    assert mine.status_code == 200
    listed = next(item for item in mine.json()["data"]["items"] if item["id"] == ticket_id)
    assert listed["status"] == "closed"

    queued = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "in_progress"},
    )
    assert queued.status_code == 200
    assert all(item["id"] != ticket_id for item in queued.json()["data"]["items"])

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
        assert count == 3


async def test_pending_ticket_close_rejected(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_PENDING_TITLE,
        status="pending",
        messages=HISTORY,
    )
    rejected = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert rejected.status_code == 409
    assert rejected.json() == PENDING_CLOSE_BODY

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "pending"

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "pending"


async def test_ai_assisting_close_rejected(
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
    owner_rejected = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert owner_rejected.status_code == 409
    assert owner_rejected.json() == AI_CLOSE_BODY

    hidden = await client.post(
        CLOSE_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "ai_assisting"


async def test_close_missing_ticket_is_not_found(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
) -> None:
    _user_a, user_b = users
    missing = await client.post(
        CLOSE_PATH.format(ticket_id=99999),
        headers=user_b["headers"],
    )
    assert missing.status_code == 404
    assert missing.json() == NOT_FOUND_BODY
