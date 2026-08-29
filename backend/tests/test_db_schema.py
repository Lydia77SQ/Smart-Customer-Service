"""SQLite 建表与 FTS5：只操作临时库，禁止 drop_all 运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from src.db.models import KnowledgeChunk, KnowledgeDocument
from src.db.session import (
    apply_schema,
    make_async_engine,
    resolve_database_file,
    sqlite_url,
)

EXPECTED_TABLES = {
    "accounts",
    "sessions",
    "tickets",
    "messages",
    "suggestions",
    "knowledge_documents",
    "knowledge_chunks",
    "qa_pairs",
}

EXPECTED_INDEXES = {
    "ix_tickets_requester_updated",
    "ix_tickets_status_updated",
    "ix_messages_ticket_created",
    "ix_suggestions_ticket_created",
    "ix_knowledge_documents_status",
    "ix_knowledge_chunks_document",
}

RUNTIME_DB = Path(__file__).resolve().parents[1] / "data" / "service_robot.db"


def test_resolve_relative_path_is_absolute_and_creates_parent(tmp_path: Path) -> None:
    resolved = resolve_database_file("nested/dir/test.db", base_dir=tmp_path)
    assert resolved.is_absolute()
    assert resolved.parent.is_dir()
    assert resolved.parent == (tmp_path / "nested" / "dir").resolve()
    assert resolved.name == "test.db"


def test_resolve_absolute_path_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "abs" / "custom.db"
    resolved = resolve_database_file(str(target), base_dir=tmp_path / "ignored")
    assert resolved == target.resolve()
    assert resolved.parent.is_dir()


def test_sqlite_url_uses_posix_path(tmp_path: Path) -> None:
    db_file = tmp_path / "x.db"
    url = sqlite_url(db_file)
    assert url.startswith("sqlite+aiosqlite:///")
    assert db_file.as_posix() in url


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "isolated.db"
    assert db_file.resolve() != RUNTIME_DB.resolve()
    return db_file


@pytest.fixture
async def isolated_engine(isolated_db_file: Path) -> AsyncGenerator[AsyncEngine, None]:
    engine = make_async_engine(isolated_db_file)
    try:
        yield engine
    finally:
        await engine.dispose()


async def test_schema_creates_all_business_tables(isolated_engine: AsyncEngine) -> None:
    await apply_schema(isolated_engine)
    async with isolated_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        names = {row[0] for row in result}
    assert names >= EXPECTED_TABLES
    assert "knowledge_chunks_fts" in names


async def test_schema_creates_named_indexes(isolated_engine: AsyncEngine) -> None:
    await apply_schema(isolated_engine)
    async with isolated_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index'")
        )
        names = {row[0] for row in result if row[0] is not None}
    assert names >= EXPECTED_INDEXES


async def test_fts5_virtual_table_and_chunk_sync_trigger(
    isolated_engine: AsyncEngine,
) -> None:
    await apply_schema(isolated_engine)
    session_maker = async_sessionmaker(isolated_engine, expire_on_commit=False)
    async with session_maker() as session:
        doc = KnowledgeDocument(
            filename="VPN接入说明.md",
            storage_path="vpn.md",
            status="enabled",
        )
        session.add(doc)
        await session.flush()
        chunk = KnowledgeChunk(
            document_id=doc.id,
            chunk_index=0,
            content="vpn 接入说明",
        )
        session.add(chunk)
        await session.commit()
        chunk_id = chunk.id

    async with isolated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT chunk_id FROM knowledge_chunks_fts "
                    "WHERE knowledge_chunks_fts MATCH 'vpn'"
                )
            )
        ).all()
    assert len(rows) == 1
    assert rows[0][0] == chunk_id


async def test_apply_schema_does_not_touch_runtime_db(
    isolated_engine: AsyncEngine, isolated_db_file: Path
) -> None:
    existed = RUNTIME_DB.is_file()
    runtime_mtime_before = RUNTIME_DB.stat().st_mtime_ns if existed else None
    await apply_schema(isolated_engine)
    assert isolated_db_file.is_file()
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()
    if existed:
        assert RUNTIME_DB.stat().st_mtime_ns == runtime_mtime_before
    else:
        assert not RUNTIME_DB.is_file()
