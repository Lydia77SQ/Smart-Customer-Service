"""咨询工单 Pydantic 模型，对齐 docs/api-contracts.md API-F004～API-F010。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from src.core.config import get_settings
from src.models.auth import UserPublic
from src.models.knowledge import to_iso_z

_settings = get_settings()

TicketStatus = Literal["ai_assisting", "pending", "in_progress", "closed"]
AgentQueueStatus = Literal["pending", "in_progress"]
TicketCategory = Literal["IT-网络", "IT-账号", "行政-工牌", "行政-场地"]
MessageSenderType = Literal["employee", "system", "agent"]
QaResultType = Literal[
    "direct_answer",
    "clarification",
    "generated_answer",
    "degraded",
    "none",
]
SuggestionResultType = Literal[
    "direct_answer",
    "clarification",
    "generated_answer",
    "degraded",
]


class EmployeeMessageCreate(BaseModel):
    """POST /api/tickets/messages 请求体。"""

    content: str = Field(
        min_length=1,
        max_length=_settings.employee_message_max_length,
    )
    ticket_id: int | None = None


class AgentReplyCreate(BaseModel):
    """POST /api/tickets/{ticket_id}/agent-replies 请求体。"""

    content: str = Field(
        min_length=1,
        max_length=_settings.agent_message_max_length,
    )


class SuggestionCreate(BaseModel):
    """POST /api/tickets/{ticket_id}/suggestions 请求体。"""

    focus_message_id: int | None = None


class TicketCategoryUpdate(BaseModel):
    """PUT /api/tickets/{ticket_id}/category 请求体。"""

    category: TicketCategory


class SuggestionOut(BaseModel):
    """智能回答建议出参，不含 ticket_id。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    result_type: SuggestionResultType
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return to_iso_z(value)


class MessageOut(BaseModel):
    """工单消息出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_type: MessageSenderType
    content: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return to_iso_z(value)


class TicketSummary(BaseModel):
    """工单列表摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: TicketStatus
    category: TicketCategory | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return to_iso_z(value)

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return to_iso_z(value)


class TicketDetail(TicketSummary):
    """工单详情，含消息与发起人。"""

    requester: UserPublic
    messages: list[MessageOut]


class AgentTicketSummary(BaseModel):
    """坐席队列条目，对齐 API-F007-01。"""

    id: int
    title: str
    status: AgentQueueStatus
    requester: UserPublic
    waiting_minutes: int
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return to_iso_z(value)


class EmployeeMessageResponse(BaseModel):
    """POST /api/tickets/messages 成功 data。"""

    ticket: TicketSummary
    employee_message: MessageOut
    system_message: MessageOut | None
    qa_result_type: QaResultType
