"""AC-F006-01 / AC-F006-03：转人工成功写系统消息；已完结拒绝且状态不变。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import Message, Ticket
from src.main import app as runtime_app

from .conftest import (
    ALREADY_HUMAN_BODY,
    CLOSED_TRANSFER_BODY,
    DETAIL_PATH,
    EMPLOYEE_TEXT,
    MESSAGES_PATH,
    NOT_FOUND_BODY,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    RUNTIME_DB,
    SYSTEM_TEXT,
    TRANSFER_PATH,
    TRANSFER_SUCCESS_MESSAGE,
    UNAUTHORIZED_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)

SUMMARY_KEYS = {"id", "title", "status", "category", "created_at", "updated_at"}


def test_transfer_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert "/api/tickets/{ticket_id}/transfer" in paths
    assert "/api/tickets/agent-queue" in paths


def test_transfer_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


def test_transfer_success_message_matches_config() -> None:
    assert get_settings().transfer_success_message == TRANSFER_SUCCESS_MESSAGE


async def test_transfer_requires_auth(client: AsyncClient) -> None:
    response = await client.post(TRANSFER_PATH.format(ticket_id=1))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_transfer_ai_assisting_keeps_context_and_writes_system_message(
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
    payload = transferred.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert set(data.keys()) == SUMMARY_KEYS
    assert data["id"] == ticket_id
    assert data["status"] == "pending"
    assert data["title"] == OWN_OPEN_TITLE

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["status"] == "pending"
    contents = [item["content"] for item in detail_data["messages"]]
    assert contents[:2] == [EMPLOYEE_TEXT, SYSTEM_TEXT]
    assert contents[-1] == TRANSFER_SUCCESS_MESSAGE
    assert detail_data["messages"][-1]["sender_type"] == "system"

    async with isolated_session_maker() as db:
        ticket = await db.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.status == "pending"
        count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        assert count == 3


async def test_transfer_then_employee_send_has_no_auto_reply(
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
    transferred = await client.post(
        TRANSFER_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert transferred.status_code == 200

    follow = await client.post(
        MESSAGES_PATH,
        headers=user_a["headers"],
        json={"content": "还在等对接人", "ticket_id": ticket_id},
    )
    assert follow.status_code == 200
    body = follow.json()["data"]
    assert body["ticket"]["status"] == "pending"
    assert body["system_message"] is None
    assert body["qa_result_type"] == "none"


async def test_closed_ticket_transfer_rejected_status_unchanged(
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
            ("employee", "工牌丢了，补办要找谁？"),
            ("system", "请到行政前台提交补办申请，携带身份证复印件。"),
        ],
    )

    rejected = await client.post(
        TRANSFER_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert rejected.status_code == 409
    assert rejected.json() == CLOSED_TRANSFER_BODY

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
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


async def test_pending_or_in_progress_transfer_is_conflict(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, _user_b = users
    pending_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="pending",
        messages=[("employee", EMPLOYEE_TEXT)],
    )
    in_progress_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title="处理中不能再转",
        status="in_progress",
        messages=[("employee", EMPLOYEE_TEXT)],
    )

    pending_res = await client.post(
        TRANSFER_PATH.format(ticket_id=pending_id),
        headers=user_a["headers"],
    )
    assert pending_res.status_code == 409
    assert pending_res.json() == ALREADY_HUMAN_BODY

    in_progress_res = await client.post(
        TRANSFER_PATH.format(ticket_id=in_progress_id),
        headers=user_a["headers"],
    )
    assert in_progress_res.status_code == 409
    assert in_progress_res.json() == ALREADY_HUMAN_BODY


async def test_transfer_other_users_ticket_is_not_found(
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
        TRANSFER_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY

    detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "ai_assisting"
