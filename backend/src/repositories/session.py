"""登录会话数据访问。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Session


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        account_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> Session:
        row = Session(
            account_id=account_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_by_token_hash(self, token_hash: str) -> int:
        result = await self.db.execute(delete(Session).where(Session.token_hash == token_hash))
        return int(result.rowcount or 0)
