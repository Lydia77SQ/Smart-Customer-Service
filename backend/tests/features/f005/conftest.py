"""F-005 测试夹具：独立库 + dependency_overrides[get_db]，禁止操作运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TypedDict

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.deps import register_auth_exception_handlers
from src.api.routes.auth import router as auth_router
from src.api.routes.tickets import router as tickets_router
from src.core.security import hash_password
from src.db.models import Account, Message, Ticket
from src.db.session import apply_schema, get_db, make_async_engine

RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"
ACCOUNT_A = "wang.li"
ACCOUNT_B = "chen.hao"
PASSWORD = "pass-word-6"
DISPLAY_A = "王丽"
DISPLAY_B = "陈浩"
LOGIN_PATH = "/api/auth/login"
MESSAGES_PATH = "/api/tickets/messages"
MINE_PATH = "/api/tickets/mine"
DETAIL_PATH = "/api/tickets/{ticket_id}"
OTHER_TITLE = "他不该看见的咨询"
OWN_OPEN_TITLE = "VPN 连不上公司内网"
OWN_CLOSED_TITLE = "工牌补办要找谁"
CLOSED_MESSAGE = "已完结，不能再发送"
NOT_FOUND_BODY = {"code": "NOT_FOUND", "message": "资源不存在", "data": None}
UNAUTHORIZED_BODY = {"code": "UNAUTHORIZED", "message": "未认证", "data": None}


class AuthUser(TypedDict):
    id: int
    headers: dict[str, str]


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "f005.db"
    assert db_file.resolve() != RUNTIME_DB.resolve()
    return db_file


@pytest.fixture
async def isolated_engine(isolated_db_file: Path) -> AsyncGenerator[AsyncEngine, None]:
    engine = make_async_engine(isolated_db_file)
    await apply_schema(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def isolated_session_maker(isolated_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(isolated_engine, expire_on_commit=False)


@pytest.fixture
def ticket_app(isolated_session_maker: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = FastAPI()
    register_auth_exception_handlers(app)
    app.include_router(auth_router.router)
    app.include_router(tickets_router.router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with isolated_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
async def client(ticket_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=ticket_app),
        base_url="http://test",
        trust_env=False,
    ) as ac:
        yield ac


async def _login(client: AsyncClient, account: str, password: str) -> dict[str, str]:
    login = await client.post(LOGIN_PATH, json={"account": account, "password": password})
    token = login.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def users(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> tuple[AuthUser, AuthUser]:
    async with isolated_session_maker() as db:
        user_a = Account(
            account=ACCOUNT_A,
            password_hash=hash_password(PASSWORD),
            display_name=DISPLAY_A,
        )
        user_b = Account(
            account=ACCOUNT_B,
            password_hash=hash_password(PASSWORD),
            display_name=DISPLAY_B,
        )
        db.add(user_a)
        db.add(user_b)
        await db.commit()
        await db.refresh(user_a)
        await db.refresh(user_b)
        a_id = user_a.id
        b_id = user_b.id
    headers_a = await _login(client, ACCOUNT_A, PASSWORD)
    headers_b = await _login(client, ACCOUNT_B, PASSWORD)
    return (
        {"id": a_id, "headers": headers_a},
        {"id": b_id, "headers": headers_b},
    )


async def add_ticket(
    isolated_session_maker: async_sessionmaker[AsyncSession],
    *,
    requester_id: int,
    title: str,
    status: str,
    category: str | None = None,
    messages: list[tuple[str, str]] | None = None,
) -> int:
    async with isolated_session_maker() as db:
        ticket = Ticket(
            requester_id=requester_id,
            title=title,
            status=status,
            category=category,
        )
        db.add(ticket)
        await db.flush()
        for sender_type, content in messages or []:
            db.add(
                Message(
                    ticket_id=ticket.id,
                    sender_type=sender_type,
                    content=content,
                )
            )
        ticket_id = ticket.id
        await db.commit()
        return ticket_id
