"""F-002 本地账号注册：独立测试库，禁止 drop_all 运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.deps import register_auth_exception_handlers
from src.api.routes.auth import router as auth_router
from src.core.security import verify_password
from src.db.models import Account, Session
from src.db.session import apply_schema, get_db, make_async_engine
from src.main import app as runtime_app

RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"
REGISTER_PATH = "/api/auth/register"


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "f002.db"
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
def register_app(isolated_session_maker: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = FastAPI()
    register_auth_exception_handlers(app)
    app.include_router(auth_router.router)

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
async def client(register_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=register_app),
        base_url="http://test",
        trust_env=False,
    ) as ac:
        yield ac


def test_register_route_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert REGISTER_PATH in paths


def test_register_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_register_success_writes_bcrypt_hash(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.post(
        REGISTER_PATH,
        json={"account": "new.user", "password": "pass-word-6"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["message"] == "ok"
    data = payload["data"]
    assert data["account"] == "new.user"
    assert data["display_name"] == "new.user"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data

    async with isolated_session_maker() as db:
        account = (
            await db.execute(select(Account).where(Account.account == "new.user"))
        ).scalar_one()
        session_count = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
        assert account.display_name == "new.user"
        assert account.profile_json == "{}"
        assert "pass-word-6" not in account.password_hash
        assert account.password_hash.startswith("$2")
        assert verify_password("pass-word-6", account.password_hash)
        assert session_count == 0
        assert data["id"] == account.id


async def test_register_conflict_keeps_original_account(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    first = await client.post(
        REGISTER_PATH,
        json={"account": "wang.li", "password": "pass-word-6"},
    )
    assert first.status_code == 200
    first_id = first.json()["data"]["id"]

    async with isolated_session_maker() as db:
        original = (
            await db.execute(select(Account).where(Account.account == "wang.li"))
        ).scalar_one()
        original_hash = original.password_hash

    second = await client.post(
        REGISTER_PATH,
        json={"account": "wang.li", "password": "another-pass"},
    )
    assert second.status_code == 409
    payload = second.json()
    assert payload == {
        "code": "CONFLICT",
        "message": "该账号名已被占用",
        "data": None,
    }

    async with isolated_session_maker() as db:
        rows = (await db.execute(select(Account).where(Account.account == "wang.li"))).scalars().all()
        assert len(rows) == 1
        assert rows[0].id == first_id
        assert rows[0].password_hash == original_hash
        assert verify_password("pass-word-6", rows[0].password_hash)


@pytest.mark.parametrize(
    "body",
    [
        {"account": "ab", "password": "pass-word-6"},
        {"account": "valid.account", "password": "12345"},
        {"account": "wang.li"},
        {"password": "pass-word-6"},
        {},
    ],
)
async def test_register_validation_error(client: AsyncClient, body: dict[str, str]) -> None:
    response = await client.post(REGISTER_PATH, json=body)
    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "data": None,
    }
