"""数据库会话管理。基于 pycore/integrations/db/session.py 模板扩展。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from pycore.core.logger import get_logger
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import get_settings

logger = get_logger()

BACKEND_ROOT = Path(__file__).resolve().parents[2]

_FTS_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
    content,
    chunk_id UNINDEXED
)
"""

_FTS_TRIGGER_SQLS = (
    """
    CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_ai
    AFTER INSERT ON knowledge_chunks
    BEGIN
        INSERT INTO knowledge_chunks_fts(content, chunk_id)
        VALUES (new.content, new.id);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_ad
    AFTER DELETE ON knowledge_chunks
    BEGIN
        DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS knowledge_chunks_fts_au
    AFTER UPDATE ON knowledge_chunks
    BEGIN
        DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id;
        INSERT INTO knowledge_chunks_fts(content, chunk_id)
        VALUES (new.content, new.id);
    END
    """,
)


def resolve_database_file(
    database_path: str | None = None,
    *,
    base_dir: Path | None = None,
) -> Path:
    """把 DATABASE_PATH 解析为绝对路径，并创建父目录。"""
    root = base_dir if base_dir is not None else BACKEND_ROOT
    raw = database_path if database_path is not None else get_settings().database_path
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def sqlite_url(db_file: Path) -> str:
    """生成 aiosqlite URL。"""
    return "sqlite+aiosqlite:///" + db_file.as_posix()


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_async_engine(db_file: Path) -> AsyncEngine:
    """为指定 SQLite 文件创建异步引擎（测试可传入临时库路径）。"""
    engine = create_async_engine(sqlite_url(db_file), echo=False, future=True)
    event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_schema_sync(connection: Connection) -> None:
    """在同步连接上创建全部业务表、FTS5 虚表与切片同步触发器。"""
    from src.db.models import Base

    Base.metadata.create_all(connection)
    connection.exec_driver_sql(_FTS_TABLE_SQL)
    for sql in _FTS_TRIGGER_SQLS:
        connection.exec_driver_sql(sql)


async def apply_schema(target_engine: AsyncEngine) -> None:
    """在指定引擎上建表（测试传入临时库引擎，禁止对运行时 engine drop_all）。"""
    async with target_engine.begin() as conn:
        await conn.run_sync(create_schema_sync)


_DB_FILE = resolve_database_file()
DATABASE_URL = sqlite_url(_DB_FILE)

engine = make_async_engine(_DB_FILE)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（用于 FastAPI Depends）。成功提交，失败回滚。"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """上下文管理器形式的数据库会话。"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """初始化运行时业务库（创建表与 FTS5，并幂等预置演示账号）。"""
    from src.db.seed import seed_demo_accounts

    db_file = resolve_database_file()
    logger.info("Initializing database", path=str(db_file))
    await apply_schema(engine)
    async with async_session_maker() as session:
        created = await seed_demo_accounts(session)
        await session.commit()
    if created:
        logger.info("Demo accounts seeded", accounts=created)
    logger.info("Database initialized", path=str(db_file))


async def close_db() -> None:
    """关闭数据库连接。"""
    await engine.dispose()
    logger.info("Database connection closed")
