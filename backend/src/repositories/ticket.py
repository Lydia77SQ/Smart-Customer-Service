"""咨询工单与消息数据访问。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Account, Message, Suggestion, Ticket


class TicketRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        requester_id: int,
        title: str,
        status: str = "ai_assisting",
    ) -> Ticket:
        now = datetime.now(UTC)
        row = Ticket(
            requester_id=requester_id,
            title=title,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get_by_id(self, ticket_id: int) -> Ticket | None:
        result = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def list_mine(
        self, *, requester_id: int, page: int, page_size: int
    ) -> tuple[list[Ticket], int]:
        filters = Ticket.requester_id == requester_id
        total = int(
            (
                await self.db.execute(select(func.count()).select_from(Ticket).where(filters))
            ).scalar_one()
        )
        result = await self.db.execute(
            select(Ticket)
            .where(filters)
            .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_agent_queue(
        self, *, status: str, page: int, page_size: int
    ) -> tuple[list[tuple[Ticket, Account]], int]:
        filters = Ticket.status == status
        total = int(
            (
                await self.db.execute(select(func.count()).select_from(Ticket).where(filters))
            ).scalar_one()
        )
        result = await self.db.execute(
            select(Ticket, Account)
            .join(Account, Account.id == Ticket.requester_id)
            .where(filters)
            .order_by(Ticket.updated_at.asc(), Ticket.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [(row[0], row[1]) for row in result.all()], total

    async def touch(self, ticket: Ticket) -> Ticket:
        ticket.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(
        self,
        *,
        ticket_id: int,
        sender_type: str,
        content: str,
    ) -> Message:
        row = Message(
            ticket_id=ticket_id,
            sender_type=sender_type,
            content=content,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_by_ticket(self, ticket_id: int) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.ticket_id == ticket_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(result.scalars().all())


class SuggestionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(
        self,
        *,
        ticket_id: int,
        content: str,
        result_type: str,
    ) -> Suggestion:
        row = Suggestion(
            ticket_id=ticket_id,
            content=content,
            result_type=result_type,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row
