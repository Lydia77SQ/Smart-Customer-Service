"""AC-F006-02：坐席待处理队列可见已转人工单，看不到从未转人工的 AI 接待中单。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .conftest import (
    ACCOUNT_A,
    AI_ONLY_TITLE,
    DISPLAY_A,
    EMPLOYEE_TEXT,
    NOT_FOUND_BODY,
    OWN_OPEN_TITLE,
    QUEUE_ITEM_KEYS,
    QUEUE_PATH,
    REQUESTER_KEYS,
    SYSTEM_TEXT,
    TRANSFER_PATH,
    UNAUTHORIZED_BODY,
    VALIDATION_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


async def test_agent_queue_requires_auth(client: AsyncClient) -> None:
    response = await client.get(QUEUE_PATH, params={"status": "pending"})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_agent_queue_rejects_ai_assisting_status(client: AsyncClient, users: tuple[AuthUser, AuthUser]) -> None:
    user_a, _user_b = users
    response = await client.get(
        QUEUE_PATH,
        headers=user_a["headers"],
        params={"status": "ai_assisting"},
    )
    assert response.status_code == 400
    assert response.json() == VALIDATION_BODY


async def test_agent_queue_requires_status(client: AsyncClient, users: tuple[AuthUser, AuthUser]) -> None:
    user_a, _user_b = users
    response = await client.get(QUEUE_PATH, headers=user_a["headers"])
    assert response.status_code == 400
    assert response.json() == VALIDATION_BODY


async def test_pending_queue_shows_transferred_hides_never_transferred(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    waited = datetime.now(UTC) - timedelta(minutes=12)
    transferred_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="ai_assisting",
        messages=[
            ("employee", EMPLOYEE_TEXT),
            ("system", SYSTEM_TEXT),
        ],
        updated_at=waited,
    )
    ai_only_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=AI_ONLY_TITLE,
        status="ai_assisting",
        messages=[("employee", "这是从未转人工的咨询。")],
    )
    other_ai_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_b["id"],
        title="坐席不该看见的 AI 单",
        status="ai_assisting",
        messages=[("employee", "其他账号的 AI 接待中咨询。")],
    )

    before = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "pending"},
    )
    assert before.status_code == 200
    before_ids = [item["id"] for item in before.json()["data"]["items"]]
    assert transferred_id not in before_ids
    assert ai_only_id not in before_ids
    assert other_ai_id not in before_ids
    assert before.json()["data"]["total_items"] == 0

    transferred = await client.post(
        TRANSFER_PATH.format(ticket_id=transferred_id),
        headers=user_a["headers"],
    )
    assert transferred.status_code == 200
    assert transferred.json()["data"]["status"] == "pending"

    queued = await client.get(
        QUEUE_PATH,
        headers=user_b["headers"],
        params={"status": "pending", "page": 1, "page_size": 20},
    )
    assert queued.status_code == 200
    payload = queued.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_items"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert set(item.keys()) == QUEUE_ITEM_KEYS
    assert item["id"] == transferred_id
    assert item["title"] == OWN_OPEN_TITLE
    assert item["status"] == "pending"
    assert set(item["requester"].keys()) == REQUESTER_KEYS
    assert item["requester"]["id"] == user_a["id"]
    assert item["requester"]["account"] == ACCOUNT_A
    assert item["requester"]["display_name"] == DISPLAY_A
    assert isinstance(item["waiting_minutes"], int)
    assert item["waiting_minutes"] >= 0
    ids = [row["id"] for row in data["items"]]
    assert ai_only_id not in ids
    assert other_ai_id not in ids
    assert all(row["status"] != "ai_assisting" for row in data["items"])

    hidden_detail = await client.get(
        f"/api/tickets/{ai_only_id}",
        headers=user_b["headers"],
    )
    assert hidden_detail.status_code == 404
    assert hidden_detail.json() == NOT_FOUND_BODY

    visible_detail = await client.get(
        f"/api/tickets/{transferred_id}",
        headers=user_b["headers"],
    )
    assert visible_detail.status_code == 200
    assert visible_detail.json()["data"]["status"] == "pending"
    assert visible_detail.json()["data"]["id"] == transferred_id


async def test_in_progress_queue_excludes_pending_and_ai(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    pending_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="pending",
        messages=[("employee", EMPLOYEE_TEXT)],
    )
    await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=AI_ONLY_TITLE,
        status="ai_assisting",
        messages=[("employee", "从未转人工")],
    )
    in_progress_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_b["id"],
        title="会议室投影仪没有画面",
        status="in_progress",
        messages=[("employee", "会议室投影仪没有画面。")],
    )

    pending_page = await client.get(
        QUEUE_PATH,
        headers=user_a["headers"],
        params={"status": "pending"},
    )
    assert pending_page.status_code == 200
    pending_ids = [item["id"] for item in pending_page.json()["data"]["items"]]
    assert pending_ids == [pending_id]
    assert in_progress_id not in pending_ids

    doing_page = await client.get(
        QUEUE_PATH,
        headers=user_a["headers"],
        params={"status": "in_progress"},
    )
    assert doing_page.status_code == 200
    doing_ids = [item["id"] for item in doing_page.json()["data"]["items"]]
    assert doing_ids == [in_progress_id]
    assert pending_id not in doing_ids
    assert all(item["status"] == "in_progress" for item in doing_page.json()["data"]["items"])
