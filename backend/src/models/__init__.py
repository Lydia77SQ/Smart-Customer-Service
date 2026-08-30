"""Pydantic API / 领域模型。"""

from src.models.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
    UserPublic,
)
from src.models.knowledge import KnowledgeDocumentOut, KnowledgeDocumentStatusUpdate
from src.models.ticket import (
    AgentReplyCreate,
    AgentTicketSummary,
    EmployeeMessageCreate,
    EmployeeMessageResponse,
    MessageOut,
    SuggestionCreate,
    SuggestionOut,
    TicketCategoryUpdate,
    TicketDetail,
    TicketSummary,
)

__all__ = [
    "AuthLoginRequest",
    "AuthRegisterRequest",
    "AuthSessionResponse",
    "AgentReplyCreate",
    "AgentTicketSummary",
    "EmployeeMessageCreate",
    "EmployeeMessageResponse",
    "KnowledgeDocumentOut",
    "KnowledgeDocumentStatusUpdate",
    "MessageOut",
    "SuggestionCreate",
    "SuggestionOut",
    "TicketCategoryUpdate",
    "TicketDetail",
    "TicketSummary",
    "UserPublic",
]
