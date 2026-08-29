"""初始化 SQLite 业务库。

真实运行路径（在 backend/ 目录下）：

    PYTHONPATH=.. python scripts/init_db.py

脚本把 backend/ 插入 sys.path，统一使用 src.* 导入（不把 backend/src 加入 path）。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

for _path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.db.session import init_db, resolve_database_file  # noqa: E402


async def main() -> None:
    db_file = resolve_database_file()
    await init_db()
    print(f"Database initialized: {db_file}")


if __name__ == "__main__":
    asyncio.run(main())
