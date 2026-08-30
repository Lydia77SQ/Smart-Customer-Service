"""AC-F009-02：未发送的建议不得写入 messages。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Message, Suggestion
from src.services.qa_pipeline import QaResult

from .conftest import (
    DETAIL_PATH,
    HISTORY,
    OWN_OPEN_TITLE,
    SUGGEST_PATH,
    SUGGESTION_TEXT,
    AuthUser,
    add_ticket,
)

pytestmark = pytest.mark.timeout(120)


async def _fake_generated(
    _self: object,
    *,
    query: str,
    profile_json: str,
    recent_messages: list[object],
) -> QaResult:
    del query, profile_json, recent_messages
    return QaResult("generated_answer", SUGGESTION_TEXT)


async def test_suggestion_does_not_add_message_row(
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

    async with isolated_session_maker() as db:
        message_before = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        suggestion_before = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Suggestion)
                    .where(Suggestion.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
    assert message_before == 3
    assert suggestion_before == 0

    created = await client.post(
        SUGGEST_PATH.format(ticket_id=ticket_id),
        headers=user_b["headers"],
        json={"focus_message_id": None},
    )
    assert created.status_code == 200
    assert created.json()["data"]["content"] == SUGGESTION_TEXT

    employee_detail = await client.get(
        DETAIL_PATH.format(ticket_id=ticket_id),
        headers=user_a["headers"],
    )
    assert employee_detail.status_code == 200
    contents = [item["content"] for item in employee_detail.json()["data"]["messages"]]
    assert SUGGESTION_TEXT not in contents
    assert len(contents) == message_before

    async with isolated_session_maker() as db:
        message_after = int(
            (
                await db.execute(
                    select(func.count()).select_from(Message).where(Message.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        suggestion_after = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Suggestion)
                    .where(Suggestion.ticket_id == ticket_id)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await db.execute(select(Suggestion).where(Suggestion.ticket_id == ticket_id))
            ).scalars()
        )
    assert message_after == message_before
    assert suggestion_after == 1
    assert rows[0].content == SUGGESTION_TEXT
    assert rows[0].result_type == "generated_answer"
