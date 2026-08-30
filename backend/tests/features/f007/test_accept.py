"""AC-F007-01 / AC-F007-03：接入后变为处理中并可见历史；已完结拒绝且状态不变。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Ticket
from src.main import app as runtime_app

from .conftest import (
    ACCEPT_CONFLICT_BODY,
    ACCEPT_PATH,
    ACCOUNT_A,
    DETAIL_KEYS,
    DETAIL_PATH,
    DISPLAY_A,
    EMPLOYEE_TEXT,
    FOLLOW_UP,
    MESSAGE_KEYS,
    NOT_FOUND_BODY,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    QUEUE_PATH,
    REQUESTER_KEYS,
    RUNTIME_DB,
    SYSTEM_TEXT,
    UNAUTHORIZED_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)

HISTORY = [
    ("employee", EMPLOYEE_TEXT),
    ("system", SYSTEM_TEXT),
    ("employee", FOLLOW_UP),
]


def test_accept_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert "/api/tickets/agent-queue" in paths
    assert "/api/tickets/{ticket_id}/accept" in paths
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


def test_accept_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_accept_requires_auth(client: AsyncClient) -> None:
    response = await client.post(ACCEPT_PATH.format(ticket_id=1))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_accept_pending_becomes_in_progress_with_full_history(
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

    queued = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "pending"},
    )
    assert queued.status_code == 200
    assert [item["id"] for item in queued.json()["data"]["items"]] == [ticket_id]

    accepted = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert set(data.keys()) == DETAIL_KEYS
    assert data["id"] == ticket_id
    assert data["title"] == OWN_OPEN_TITLE
    assert data["status"] == "in_progress"
    assert data["category"] is None
    assert set(data["requester"].keys()) == REQUESTER_KEYS
    assert data["requester"]["id"] == user_a["id"]
    assert data["requester"]["account"] == ACCOUNT_A
    assert data["requester"]["display_name"] == DISPLAY_A
    assert [item["content"] for item in data["messages"]] == [
        EMPLOYEE_TEXT,
        SYSTEM_TEXT,
        FOLLOW_UP,
    ]
    assert [item["sender_type"] for item in data["messages"]] == [
        "employee",
        "system",
        "employee",
    ]
    for item in data["messages"]:
        assert set(item.keys()) == MESSAGE_KEYS

    pending_after = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "pending"},
    )
    assert pending_after.status_code == 200
    assert ticket_id not in [item["id"] for item in pending_after.json()["data"]["items"]]

    doing = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "in_progress"},
    )
    assert doing.status_code == 200
    doing_ids = [item["id"] for item in doing.json()["data"]["items"]]
    assert doing_ids == [ticket_id]
    assert doing.json()["data"]["items"][0]["status"] == "in_progress"

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
        assert count == 3


async def test_accept_in_progress_is_idempotent(
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

    first = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "in_progress"
    first_updated = first.json()["data"]["updated_at"]
    first_message_ids = [item["id"] for item in first.json()["data"]["messages"]]

    second = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "in_progress"
    assert second.json()["data"]["updated_at"] == first_updated
    assert [item["id"] for item in second.json()["data"]["messages"]] == first_message_ids

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
        assert count == 3


async def test_closed_ticket_accept_rejected_status_unchanged(
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
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert rejected.status_code == 409
    assert rejected.json() == ACCEPT_CONFLICT_BODY

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "closed"
    assert len(detail.json()["data"]["messages"]) == 2

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


async def test_ai_assisting_accept_is_conflict_for_owner(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, _user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="ai_assisting",
        messages=[("employee", EMPLOYEE_TEXT)],
    )
    rejected = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert rejected.status_code == 409
    assert rejected.json() == ACCEPT_CONFLICT_BODY

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "ai_assisting"


async def test_ai_assisting_accept_hidden_from_other_user(
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
        messages=[("employee", EMPLOYEE_TEXT)],
    )
    hidden = await client.post(
        ACCEPT_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY


async def test_accept_missing_ticket_is_not_found(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
) -> None:
    _user_a, user_b = users
    missing = await client.post(
        ACCEPT_PATH.format(ticket_id=99999),
        headers=user_b["headers"],
    )
    assert missing.status_code == 404
    assert missing.json() == NOT_FOUND_BODY
