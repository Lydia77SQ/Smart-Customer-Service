"""运行时预置账号：只操作临时库，禁止 drop_all 运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.security import verify_password
from src.db.seed import DEMO_ACCOUNTS, seed_demo_accounts
from src.db.session import apply_schema, make_async_engine
from src.repositories.account import AccountRepository

RUNTIME_DB = Path(__file__).resolve().parents[1] / "data" / "service_robot.db"


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "seed.db"
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


async def test_seed_creates_contract_example_accounts(
    isolated_session_maker: async_sessionmaker[AsyncSession],
    isolated_db_file: Path,
) -> None:
    async with isolated_session_maker() as session:
        created = await seed_demo_accounts(session)
        await session.commit()
    assert set(created) == {item["account"] for item in DEMO_ACCOUNTS}

    async with isolated_session_maker() as session:
        repo = AccountRepository(session)
        for item in DEMO_ACCOUNTS:
            row = await repo.get_by_account(item["account"])
            assert row is not None
            assert row.display_name == item["display_name"]
            assert verify_password(item["password"], row.password_hash)

    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_seed_is_idempotent_and_does_not_overwrite_password(
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with isolated_session_maker() as session:
        await seed_demo_accounts(session)
        await session.commit()

    async with isolated_session_maker() as session:
        repo = AccountRepository(session)
        first = await repo.get_by_account("wang.li")
        assert first is not None
        original_hash = first.password_hash

    async with isolated_session_maker() as session:
        created_again = await seed_demo_accounts(session)
        await session.commit()
    assert created_again == []

    async with isolated_session_maker() as session:
        repo = AccountRepository(session)
        again = await repo.get_by_account("wang.li")
        assert again is not None
        assert again.password_hash == original_hash
        assert again.id == first.id
