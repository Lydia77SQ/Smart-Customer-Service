"""员工发消息、答疑、转人工、坐席队列、接入、回复、智能建议、分类与结单。"""

from __future__ import annotations

from datetime import UTC, datetime

from pycore.core import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models import Account, Message, Suggestion, Ticket
from src.models.auth import UserPublic
from src.models.ticket import (
    AgentQueueStatus,
    AgentTicketSummary,
    EmployeeMessageResponse,
    MessageOut,
    QaResultType,
    SuggestionOut,
    TicketDetail,
    TicketSummary,
)
from src.repositories.account import AccountRepository
from src.repositories.ticket import MessageRepository, SuggestionRepository, TicketRepository
from src.services.qa_pipeline import QaPipeline, apply_profile_rules

logger = get_logger()

_NOT_FOUND_MESSAGE = "资源不存在"
_CLOSED_MESSAGE = "已完结，不能再发送"
_CLOSED_TRANSFER_MESSAGE = "已完结，不能转人工"
_ALREADY_HUMAN_MESSAGE = "已在人工流程中"
_ACCEPT_CONFLICT_MESSAGE = "当前状态不可接入"
_NEED_ACCEPT_MESSAGE = "请先接入后再回复"
_SUGGEST_CONFLICT_MESSAGE = "仅处理中可获取建议"
_CLOSED_CATEGORY_MESSAGE = "已完结不能改分类"
_NEED_ACCEPT_CLOSE_MESSAGE = "未接入不能结单"
_CLOSE_CONFLICT_MESSAGE = "当前状态不可结单"
_ALLOWED_CATEGORIES = frozenset({"IT-网络", "IT-账号", "行政-工牌", "行政-场地"})
_AI_ASSISTING = "ai_assisting"
_PENDING = "pending"
_IN_PROGRESS = "in_progress"
_CLOSED = "closed"


class TicketValidationError(Exception):
    def __init__(self, message: str = "参数验证失败") -> None:
        self.message = message
        super().__init__(message)


class TicketNotFoundError(Exception):
    def __init__(self, message: str = _NOT_FOUND_MESSAGE) -> None:
        self.message = message
        super().__init__(message)


class TicketConflictError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TicketService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.tickets = TicketRepository(db)
        self.messages = MessageRepository(db)
        self.suggestions = SuggestionRepository(db)
        self.accounts = AccountRepository(db)
        self.pipeline = QaPipeline(db)

    def to_summary(self, ticket: Ticket) -> TicketSummary:
        return TicketSummary.model_validate(ticket)

    def to_message(self, message: Message) -> MessageOut:
        return MessageOut.model_validate(message)

    def to_agent_summary(self, ticket: Ticket, requester: Account) -> AgentTicketSummary:
        queue_status: AgentQueueStatus
        if ticket.status == _PENDING:
            queue_status = "pending"
        elif ticket.status == _IN_PROGRESS:
            queue_status = "in_progress"
        else:
            raise TicketValidationError()
        return AgentTicketSummary(
            id=ticket.id,
            title=ticket.title,
            status=queue_status,
            requester=UserPublic.model_validate(requester),
            waiting_minutes=_waiting_minutes(ticket.updated_at),
            updated_at=ticket.updated_at,
        )

    async def list_mine(
        self, user: Account, *, page: int, page_size: int
    ) -> tuple[list[TicketSummary], int]:
        rows, total = await self.tickets.list_mine(
            requester_id=user.id,
            page=page,
            page_size=page_size,
        )
        return [self.to_summary(row) for row in rows], total

    async def list_agent_queue(
        self,
        _user: Account,
        *,
        status: str,
        page: int,
        page_size: int,
    ) -> tuple[list[AgentTicketSummary], int]:
        if status not in {_PENDING, _IN_PROGRESS}:
            raise TicketValidationError()
        rows, total = await self.tickets.list_agent_queue(
            status=status,
            page=page,
            page_size=page_size,
        )
        return [self.to_agent_summary(ticket, requester) for ticket, requester in rows], total

    async def get_detail(self, user: Account, ticket_id: int) -> TicketDetail:
        ticket = await self._visible_ticket(user, ticket_id)
        requester = await self.accounts.get_by_id(ticket.requester_id)
        if requester is None:
            raise TicketNotFoundError()
        messages = await self.messages.list_by_ticket(ticket.id)
        summary = self.to_summary(ticket)
        return TicketDetail(
            **summary.model_dump(),
            requester=UserPublic.model_validate(requester),
            messages=[self.to_message(item) for item in messages],
        )

    async def send_employee_message(
        self,
        user: Account,
        *,
        content: str,
        ticket_id: int | None,
    ) -> EmployeeMessageResponse:
        settings = get_settings()
        text = content.strip()
        if not text or len(text) > settings.employee_message_max_length:
            raise TicketValidationError()

        if ticket_id is None:
            title = text[: settings.ticket_title_max_length]
            ticket = await self.tickets.create(requester_id=user.id, title=title)
        else:
            ticket = await self._own_ticket(user, ticket_id)
            if ticket.status == _CLOSED:
                raise TicketConflictError(_CLOSED_MESSAGE)

        employee = await self.messages.add(
            ticket_id=ticket.id,
            sender_type="employee",
            content=text,
        )
        await self.tickets.touch(ticket)

        system_message: Message | None = None
        qa_result_type: QaResultType = "none"
        if ticket.status == _AI_ASSISTING:
            history = await self.messages.list_by_ticket(ticket.id)
            prior = [item for item in history if item.id != employee.id]
            result = await self.pipeline.run(
                query=text,
                profile_json=user.profile_json,
                recent_messages=prior,
            )
            system_message = await self.messages.add(
                ticket_id=ticket.id,
                sender_type="system",
                content=result.content,
            )
            qa_result_type = result.result_type
            await self.accounts.update_profile_json(
                user,
                apply_profile_rules(user.profile_json, text, result.result_type),
            )
            await self.tickets.touch(ticket)
            logger.info(
                "员工提问已答复",
                ticket_id=ticket.id,
                qa_result_type=result.result_type,
            )
        elif ticket.status not in {_PENDING, _IN_PROGRESS}:
            raise TicketConflictError(_CLOSED_MESSAGE)

        ticket = await self.tickets.get_by_id(ticket.id) or ticket
        return EmployeeMessageResponse(
            ticket=self.to_summary(ticket),
            employee_message=self.to_message(employee),
            system_message=self.to_message(system_message) if system_message else None,
            qa_result_type=qa_result_type,
        )

    async def transfer_to_human(self, user: Account, ticket_id: int) -> TicketSummary:
        ticket = await self._own_ticket(user, ticket_id)
        if ticket.status == _CLOSED:
            raise TicketConflictError(_CLOSED_TRANSFER_MESSAGE)
        if ticket.status != _AI_ASSISTING:
            raise TicketConflictError(_ALREADY_HUMAN_MESSAGE)
        settings = get_settings()
        await self.messages.add(
            ticket_id=ticket.id,
            sender_type="system",
            content=settings.transfer_success_message,
        )
        ticket.status = _PENDING
        ticket = await self.tickets.touch(ticket)
        logger.info("工单已转人工", ticket_id=ticket.id)
        return self.to_summary(ticket)

    async def accept_ticket(self, user: Account, ticket_id: int) -> TicketDetail:
        ticket = await self._visible_ticket(user, ticket_id)
        if ticket.status == _PENDING:
            ticket.status = _IN_PROGRESS
            ticket = await self.tickets.touch(ticket)
            logger.info("工单已接入", ticket_id=ticket.id)
        elif ticket.status != _IN_PROGRESS:
            raise TicketConflictError(_ACCEPT_CONFLICT_MESSAGE)
        return await self.get_detail(user, ticket.id)

    async def send_agent_reply(
        self, user: Account, ticket_id: int, *, content: str
    ) -> MessageOut:
        settings = get_settings()
        text = content.strip()
        if not text or len(text) > settings.agent_message_max_length:
            raise TicketValidationError()
        ticket = await self._visible_ticket(user, ticket_id)
        if ticket.status == _CLOSED:
            raise TicketConflictError(_CLOSED_MESSAGE)
        if ticket.status != _IN_PROGRESS:
            raise TicketConflictError(_NEED_ACCEPT_MESSAGE)
        agent_message = await self.messages.add(
            ticket_id=ticket.id,
            sender_type="agent",
            content=text,
        )
        await self.tickets.touch(ticket)
        logger.info("坐席已回复", ticket_id=ticket.id)
        return self.to_message(agent_message)

    def to_suggestion(self, row: Suggestion) -> SuggestionOut:
        return SuggestionOut.model_validate(row)

    async def create_suggestion(
        self,
        user: Account,
        ticket_id: int,
        *,
        focus_message_id: int | None = None,
    ) -> SuggestionOut:
        ticket = await self._visible_ticket(user, ticket_id)
        if ticket.status != _IN_PROGRESS:
            raise TicketConflictError(_SUGGEST_CONFLICT_MESSAGE)

        history = await self.messages.list_by_ticket(ticket.id)
        focus = _resolve_focus_message(history, focus_message_id)
        query = (focus.content if focus is not None else ticket.title).strip()
        if not query:
            raise TicketValidationError()

        requester = await self.accounts.get_by_id(ticket.requester_id)
        if requester is None:
            raise TicketNotFoundError()

        prior = [item for item in history if focus is None or item.id != focus.id]
        result = await self.pipeline.run(
            query=query,
            profile_json=requester.profile_json,
            recent_messages=prior,
        )
        settings = get_settings()
        content = result.content
        if result.result_type == "degraded":
            content = settings.degraded_suggestion_message

        row = await self.suggestions.add(
            ticket_id=ticket.id,
            content=content,
            result_type=result.result_type,
        )
        logger.info(
            "坐席建议已生成",
            ticket_id=ticket.id,
            result_type=result.result_type,
        )
        return self.to_suggestion(row)

    async def update_category(
        self, user: Account, ticket_id: int, *, category: str
    ) -> TicketSummary:
        if category not in _ALLOWED_CATEGORIES:
            raise TicketValidationError()
        ticket = await self._visible_ticket(user, ticket_id)
        if ticket.status not in {_PENDING, _IN_PROGRESS}:
            raise TicketConflictError(_CLOSED_CATEGORY_MESSAGE)
        if ticket.category == category:
            return self.to_summary(ticket)
        ticket.category = category
        ticket = await self.tickets.touch(ticket)
        logger.info("工单已分类", ticket_id=ticket.id)
        return self.to_summary(ticket)

    async def close_ticket(self, user: Account, ticket_id: int) -> TicketSummary:
        ticket = await self._visible_ticket(user, ticket_id)
        if ticket.status == _CLOSED:
            return self.to_summary(ticket)
        if ticket.status == _PENDING:
            raise TicketConflictError(_NEED_ACCEPT_CLOSE_MESSAGE)
        if ticket.status != _IN_PROGRESS:
            raise TicketConflictError(_CLOSE_CONFLICT_MESSAGE)
        ticket.status = _CLOSED
        ticket = await self.tickets.touch(ticket)
        logger.info("工单已结单", ticket_id=ticket.id)
        return self.to_summary(ticket)

    async def _own_ticket(self, user: Account, ticket_id: int) -> Ticket:
        ticket = await self.tickets.get_by_id(ticket_id)
        if ticket is None or ticket.requester_id != user.id:
            raise TicketNotFoundError()
        return ticket

    async def _visible_ticket(self, user: Account, ticket_id: int) -> Ticket:
        ticket = await self.tickets.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError()
        if ticket.requester_id == user.id:
            return ticket
        if ticket.status == _AI_ASSISTING:
            raise TicketNotFoundError()
        return ticket


def _waiting_minutes(updated_at: datetime) -> int:
    aware = updated_at if updated_at.tzinfo is not None else updated_at.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - aware.astimezone(UTC)
    return max(0, int(delta.total_seconds() // 60))


def _resolve_focus_message(
    history: list[Message],
    focus_message_id: int | None,
) -> Message | None:
    if focus_message_id is not None:
        matched = next((item for item in history if item.id == focus_message_id), None)
        if matched is None:
            raise TicketValidationError()
        return matched
    return next(
        (item for item in reversed(history) if item.sender_type == "employee"),
        None,
    )
