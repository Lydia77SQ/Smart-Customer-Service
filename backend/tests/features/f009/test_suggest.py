"""AC-F009-01：处理中工单获取建议仅坐席可见，不进入员工消息流。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Suggestion, Ticket
from src.main import app as runtime_app
from src.services.qa_pipeline import QaResult

from .conftest import (
    DETAIL_PATH,
    HISTORY,
    MESSAGE_KEYS,
    NOT_FOUND_BODY,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    OWN_PENDING_TITLE,
    QUEUE_PATH,
    RUNTIME_DB,
    SUGGEST_CONFLICT_BODY,
    SUGGEST_PATH,
    SUGGESTION_KEYS,
    SUGGESTION_TEXT,
    UNAUTHORIZED_BODY,
    VALIDATION_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(300)


async def _fake_generated(
    _self: object,
    *,
    query: str,
    profile_json: str,
    recent_messages: list[object],
) -> QaResult:
    del query, profile_json, recent_messages
    return QaResult("generated_answer", SUGGESTION_TEXT)


def test_suggest_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert "/api/tickets/agent-queue" in paths
    assert "/api/tickets/{ticket_id}/suggestions" in paths
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


def test_suggest_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_suggest_requires_auth(client: AsyncClient) -> None:
    response = await client.post(SUGGEST_PATH.format(ticket_id=1), json={"focus_message_id": None})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_in_progress_suggestion_visible_only_in_payload(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.ticket.QaPipeline.run", _fake_generated)
    user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="in_progress",
        messages=HISTORY,
    )

    created = await client.post(
        SUGGEST_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert set(data.keys()) == SUGGESTION_KEYS
    assert data["content"] == SUGGESTION_TEXT
    assert data["result_type"] == "generated_answer"
    assert "ticket_id" not in data
    assert data["id"] > 0

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

    agent_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
    )
    assert agent_detail.status_code == 200
    agent_messages = agent_detail.json()["data"]["messages"]
    assert SUGGESTION_TEXT not in [item["content"] for item in agent_messages]
    assert len(agent_messages) == 3
    assert agent_detail.json()["data"]["status"] == "in_progress"

    queued = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "in_progress"},
    )
    assert queued.status_code == 200
    assert any(item["id"] == ticket_id for item in queued.json()["data"]["items"])


async def test_pending_and_closed_cannot_get_suggestion(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.ticket.QaPipeline.run", _fake_generated)
    user_a, user_b = users
    pending_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_PENDING_TITLE,
        status="pending",
        messages=HISTORY,
    )
    closed_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_CLOSED_TITLE,
        status="closed",
        messages=HISTORY,
    )

    pending = await client.post(
        SUGGEST_PATH.format(ticket_id=pending_id),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert pending.status_code == 409
    assert pending.json() == SUGGEST_CONFLICT_BODY

    closed = await client.post(
        SUGGEST_PATH.format(ticket_id=closed_id),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert closed.status_code == 409
    assert closed.json() == SUGGEST_CONFLICT_BODY

    async with isolated_session_maker() as db:
        suggestion_count = int(
            (await db.execute(select(func.count()).select_from(Suggestion))).scalar_one()
        )
        assert suggestion_count == 0
        pending_status = (
            await db.execute(select(Ticket.status).where(Ticket.id == pending_id))
        ).scalar_one()
        closed_status = (
            await db.execute(select(Ticket.status).where(Ticket.id == closed_id))
        ).scalar_one()
        assert pending_status == "pending"
        assert closed_status == "closed"


async def test_missing_ticket_and_invalid_focus_message(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.ticket.QaPipeline.run", _fake_generated)
    _user_a, user_b = users
    ticket_id = await add_ticket(
        isolated_session_maker,
        requester_id=_user_a["id"],
        title=OWN_OPEN_TITLE,
        status="in_progress",
        messages=HISTORY,
    )

    missing = await client.post(
        SUGGEST_PATH.format(ticket_id=99999),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert missing.status_code == 404
    assert missing.json() == NOT_FOUND_BODY

    invalid_focus = await client.post(
        SUGGEST_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"focus_message_id": 99999},
    )
    assert invalid_focus.status_code == 400
    assert invalid_focus.json() == VALIDATION_BODY


async def test_ai_assisting_other_user_is_not_found(
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
        messages=HISTORY,
    )
    hidden = await client.post(
        SUGGEST_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY
