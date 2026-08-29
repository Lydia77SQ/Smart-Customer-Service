"""账号数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Account


class AccountRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_account(self, account: str) -> Account | None:
        result = await self.db.execute(select(Account).where(Account.account == account))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        account: str,
        password_hash: str,
        display_name: str,
    ) -> Account:
        row = Account(
            account=account,
            password_hash=password_hash,
            display_name=display_name,
        )
        self.db.add(row)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ValueError("该账号名已被占用") from exc
        await self.db.refresh(row)
        return row
