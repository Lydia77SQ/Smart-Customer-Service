"""AC-F005-01：员工列表与详情只含本人工单，他人工单对外不存在。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.main import app as runtime_app

from .conftest import (
    ACCOUNT_A,
    DETAIL_PATH,
    DISPLAY_A,
    MINE_PATH,
    NOT_FOUND_BODY,
    OTHER_TITLE,
    OWN_CLOSED_TITLE,
    OWN_OPEN_TITLE,
    RUNTIME_DB,
    UNAUTHORIZED_BODY,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


def test_ticket_list_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert MINE_PATH in paths
    assert "/api/tickets/{ticket_id}" in paths


def test_mine_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_mine_requires_auth(client: AsyncClient) -> None:
    response = await client.get(MINE_PATH)
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_detail_requires_auth(client: AsyncClient) -> None:
    response = await client.get(DETAIL_PATH.format(ticket_id=1))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


async def test_mine_and_detail_hide_other_users_tickets(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_a, user_b = users
    own_open_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_a["id"],
        title=OWN_OPEN_TITLE,
        status="in_progress",
        category="IT-网络",
        messages=[
            ("employee", "公司 VPN 连不上，提示认证失败。"),
            ("system", "请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。"),
        ],
    )
    own_closed_id = await add_ticket(
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
    other_id = await add_ticket(
        isolated_session_maker,
        requester_id=user_b["id"],
        title=OTHER_TITLE,
        status="ai_assisting",
        messages=[("employee", "这是其他账号的咨询。")],
    )

    listed = await client.get(MINE_PATH, headers=user_a["headers"])
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["code"] == 200
    data = payload["data"]
    titles = [item["title"] for item in data["items"]]
    ids = [item["id"] for item in data["items"]]
    assert data["total_items"] == 2
    assert OTHER_TITLE not in titles
    assert other_id not in ids
    assert set(ids) == {own_open_id, own_closed_id}
    summary_keys = {"id", "title", "status", "category", "created_at", "updated_at"}
    for item in data["items"]:
        assert set(item.keys()) == summary_keys
        assert "requester_id" not in item

    own_detail = await client.get(
        DETAIL_PATH.format(ticket_id=own_open_id),
        headers=user_a["headers"],
    )
    assert own_detail.status_code == 200
    own_data = own_detail.json()["data"]
    assert own_data["id"] == own_open_id
    assert own_data["requester"]["id"] == user_a["id"]
    assert own_data["requester"]["account"] == ACCOUNT_A
    assert own_data["requester"]["display_name"] == DISPLAY_A
    assert "这是其他账号的咨询。" not in [msg["content"] for msg in own_data["messages"]]

    hidden = await client.get(
        DETAIL_PATH.format(ticket_id=other_id),
        headers=user_a["headers"],
    )
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND_BODY

    listed_b = await client.get(MINE_PATH, headers=user_b["headers"])
    assert listed_b.status_code == 200
    b_items = listed_b.json()["data"]["items"]
    assert listed_b.json()["data"]["total_items"] == 1
    assert b_items[0]["id"] == other_id
    assert b_items[0]["title"] == OTHER_TITLE
    assert own_open_id not in [item["id"] for item in b_items]


async def test_empty_history_is_empty_list_not_others(
    client: AsyncClient,
    users: tuple[AuthUser, AuthUser],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    _user_a, user_b = users
    await add_ticket(
        isolated_session_maker,
        requester_id=user_b["id"],
        title=OTHER_TITLE,
        status="ai_assisting",
        messages=[("employee", "这是其他账号的咨询。")],
    )
    listed = await client.get(MINE_PATH, headers=users[0]["headers"])
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert data["items"] == []
    assert data["total_items"] == 0
