"""AC-F010-01 / AC-F010-02：处理中可写分类；已完结拒绝且分类不变。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Ticket
from src.main import app as runtime_app

from .conftest import (
    CATEGORY_PATH,
    CLOSED_CATEGORY,
    CLOSED_CATEGORY_BODY,
    DETAIL_KEYS,
    DETAIL_PATH,
    HISTORY,
    MESSAGE_KEYS,
    MINE_PATH,
    NOT_FOUND_BODY,
    OTHER_CATEGORY,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    OWN_PENDING_TITLE,
    QUEUE_PATH,
    RUNTIME_DB,
    SUMMARY_KEYS,
    TARGET_CATEGORY,
    UNAUTHORIZED_BODY,
    VALIDATION_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


def test_category_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert "/api/tickets/agent-queue" in paths
    assert "/api/tickets/{ticket_id}/category" in paths
    queue_order = None
    category_order = None
    detail_order = None
    for index, route in enumerate(runtime_app.routes):
        path = getattr(route, "path", None)
        if path == "/api/tickets/agent-queue":
            queue_order = index
        if path == "/api/tickets/{ticket_id}/category":
            category_order = index
        if path == "/api/tickets/{ticket_id}":
            detail_order = index
    assert queue_order is not None
    assert category_order is not None
    assert detail_order is not None
    assert queue_order < detail_order
    assert category_order < detail_order


def test_category_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_category_requires_auth(client: AsyncClient) -> None:
    response = await client.put(
        CATEGORY_PATH.format(ticket_id=1),
        json={"category": TARGET_CATEGORY},
    )
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_in_progress_category_shown_on_detail_and_mine_list(
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

    updated = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["code"] == 200
    summary = payload["data"]
    assert set(summary.keys()) == SUMMARY_KEYS
    assert summary["id"] == ticket_id
    assert summary["status"] == "in_progress"
    assert summary["category"] == TARGET_CATEGORY
    assert summary["title"] == OWN_OPEN_TITLE
    assert summary["created_at"].endswith("Z")
    assert summary["updated_at"].endswith("Z")

    agent_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert agent_detail.status_code == 200
    detail = agent_detail.json()["data"]
    assert set(detail.keys()) == DETAIL_KEYS
    assert detail["category"] == TARGET_CATEGORY
    assert detail["status"] == "in_progress"
    assert [item["content"] for item in detail["messages"]] == [row[1] for row in HISTORY]
    for item in detail["messages"]:
        assert set(item.keys()) == MESSAGE_KEYS

    mine = await client.get(MINE_PATH, headers=user_a["headers"])
    assert mine.status_code == 200
    listed = next(item for item in mine.json()["data"]["items"] if item["id"] == ticket_id)
    assert set(listed.keys()) == SUMMARY_KEYS
    assert listed["category"] == TARGET_CATEGORY
    assert listed["status"] == "in_progress"

    queued = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "in_progress"},
    )
    assert queued.status_code == 200
    queue_item = next(item for item in queued.json()["data"]["items"] if item["id"] == ticket_id)
    assert "category" not in queue_item

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "in_progress"
        assert ticket.category == TARGET_CATEGORY
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == 3


async def test_closed_ticket_category_rejected_unchanged(
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
        category=CLOSED_CATEGORY,
        messages=[
            ("employee", "工牌丢了，补办要找谁？"),
            ("system", "请到行政前台提交补办申请，携带身份证复印件。"),
        ],
    )

    rejected = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert rejected.status_code == 409
    assert rejected.json() == CLOSED_CATEGORY_BODY

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "closed"
    assert detail.json()["data"]["category"] == CLOSED_CATEGORY

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "closed"
        assert ticket.category == CLOSED_CATEGORY


async def test_pending_ticket_can_set_category(
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
    updated = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": OTHER_CATEGORY},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "pending"
    assert updated.json()["data"]["category"] == OTHER_CATEGORY


async def test_same_category_is_idempotent(
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
    first = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert first.status_code == 200
    first_updated = first.json()["data"]["updated_at"]
    second = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert second.status_code == 200
    assert second.json()["data"]["category"] == TARGET_CATEGORY
    assert second.json()["data"]["status"] == "in_progress"
    assert second.json()["data"]["updated_at"] == first_updated


async def test_invalid_category_is_validation_error(
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
    invalid = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": "财务-报销"},
    )
    assert invalid.status_code == 400
    assert invalid.json() == VALIDATION_BODY

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.category is None


async def test_ai_assisting_category_hidden_from_other_user(
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
    hidden = await client.put(
        CATEGORY_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY


async def test_category_missing_ticket_is_not_found(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
) -> None:
    _user_a, user_b = users
    missing = await client.put(
        CATEGORY_PATH.format(ticket_id=99999),
        headers=user_b["headers"],
        json={"category": TARGET_CATEGORY},
    )
    assert missing.status_code == 404
    assert missing.json() == NOT_FOUND_BODY
