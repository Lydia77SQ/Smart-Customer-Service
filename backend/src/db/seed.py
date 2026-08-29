"""运行时预置账号。凭证与 docs/api-contracts.md 示例、前端 Mock 对齐。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.repositories.account import AccountRepository

DEMO_ACCOUNTS: tuple[dict[str, str], ...] = (
    {
        "account": "wang.li",
        "password": "pass-word-6",
        "display_name": "王丽",
    },
    {
        "account": "chen.hao",
        "password": "pass-word-6",
        "display_name": "陈浩",
    },
)


async def seed_demo_accounts(session: AsyncSession) -> list[str]:
    """若账号不存在则创建；已存在则跳过，不覆盖密码。"""
    repo = AccountRepository(session)
    created: list[str] = []
    for item in DEMO_ACCOUNTS:
        account = item["account"]
        existing = await repo.get_by_account(account)
        if existing is not None:
            continue
        try:
            await repo.create(
                account=account,
                password_hash=hash_password(item["password"]),
                display_name=item["display_name"],
            )
        except ValueError:
            continue
        created.append(account)
    return created
