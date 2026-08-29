"""F-012 测试夹具：独立库 + 独立上传目录，禁止操作运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.deps import register_auth_exception_handlers
from src.api.routes.auth import router as auth_router
from src.api.routes.knowledge_documents import router as knowledge_router
from src.core.config import get_settings
from src.core.security import hash_password
from src.db.models import Account
from src.db.session import apply_schema, get_db, make_async_engine

RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"
ACCOUNT = "wang.li"
PASSWORD = "pass-word-6"
DISPLAY_NAME = "王丽"
UPLOAD_PATH = "/api/knowledge_documents"
LIST_PATH = "/api/knowledge_documents"
LOGIN_PATH = "/api/auth/login"


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "f012.db"
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
def isolated_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(get_settings(), "upload_dir", str(upload_dir))
    return upload_dir


@pytest.fixture
def knowledge_app(
    isolated_session_maker: async_sessionmaker[AsyncSession],
    isolated_upload_dir: Path,
) -> FastAPI:
    assert isolated_upload_dir.is_dir()
    app = FastAPI()
    register_auth_exception_handlers(app)
    app.include_router(auth_router.router)
    app.include_router(knowledge_router.router)

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
async def client(knowledge_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=knowledge_app),
        base_url="http://test",
        trust_env=False,
    ) as ac:
        yield ac


@pytest.fixture
async def auth_headers(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> dict[str, str]:
    async with isolated_session_maker() as db:
        db.add(
            Account(
                account=ACCOUNT,
                password_hash=hash_password(PASSWORD),
                display_name=DISPLAY_NAME,
            )
        )
        await db.commit()
    login = await client.post(LOGIN_PATH, json={"account": ACCOUNT, "password": PASSWORD})
    token = login.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}
