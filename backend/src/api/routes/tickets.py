"""咨询工单资源路由。API-F004 发消息；API-F005 列表详情；API-F006 转人工；API-F007 队列与接入；API-F008 坐席回复；API-F009 智能建议；API-F010 分类；API-F011 结单。"""

from typing import Annotated, Literal

from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    contract_paginated_response,
    contract_success_response,
    get_current_user,
)
from src.core.config import get_settings
from src.db.models import Account
from src.db.session import get_db
from src.models.ticket import (
    AgentReplyCreate,
    EmployeeMessageCreate,
    SuggestionCreate,
    TicketCategoryUpdate,
)
from src.services.ticket import TicketService

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _ticket_service(db: AsyncSession) -> TicketService:
    return TicketService(db)


@router.get("/mine")
async def list_my_tickets(
    page: Annotated[int | None, Query(ge=1)] = None,
    page_size: Annotated[int | None, Query(ge=1, le=100)] = None,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F005-01：仅 requester_id 等于当前用户的工单。"""
    settings = get_settings()
    current_page = page if page is not None else settings.ticket_list_page_default
    current_size = page_size if page_size is not None else settings.ticket_list_page_size
    if current_size > settings.ticket_list_page_size_max:
        current_size = settings.ticket_list_page_size_max
    items, total = await _ticket_service(db).list_mine(
        current,
        page=current_page,
        page_size=current_size,
    )
    return contract_paginated_response(
        [item.model_dump(mode="json") for item in items],
        page=current_page,
        page_size=current_size,
        total_items=total,
    )


@router.get("/agent-queue")
async def list_agent_queue(
    status: Annotated[Literal["pending", "in_progress"], Query()],
    page: Annotated[int | None, Query(ge=1)] = None,
    page_size: Annotated[int | None, Query(ge=1, le=100)] = None,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F007-01 / AC-F006-02：待处理或处理中队列，不含 AI 接待中。"""
    settings = get_settings()
    current_page = page if page is not None else settings.ticket_list_page_default
    current_size = page_size if page_size is not None else settings.ticket_list_page_size
    if current_size > settings.ticket_list_page_size_max:
        current_size = settings.ticket_list_page_size_max
    items, total = await _ticket_service(db).list_agent_queue(
        current,
        status=status,
        page=current_page,
        page_size=current_size,
    )
    return contract_paginated_response(
        [item.model_dump(mode="json") for item in items],
        page=current_page,
        page_size=current_size,
        total_items=total,
    )


@router.post("/messages")
async def send_employee_message(
    body: EmployeeMessageCreate,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F004-01 发送员工消息并走答疑链路。"""
    result = await _ticket_service(db).send_employee_message(
        current,
        content=body.content,
        ticket_id=body.ticket_id,
    )
    return contract_success_response(result.model_dump(mode="json"))


@router.post("/{ticket_id}/transfer")
async def transfer_ticket(
    ticket_id: int,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F006-01：AI 接待中工单转为待处理，并写入转人工系统消息。"""
    summary = await _ticket_service(db).transfer_to_human(current, ticket_id)
    return contract_success_response(summary.model_dump(mode="json"))


@router.post("/{ticket_id}/accept")
async def accept_ticket(
    ticket_id: int,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F007-02：待处理 → 处理中；已处理中幂等返回详情。"""
    detail = await _ticket_service(db).accept_ticket(current, ticket_id)
    return contract_success_response(detail.model_dump(mode="json"))


@router.post("/{ticket_id}/agent-replies")
async def send_agent_reply(
    ticket_id: int,
    body: AgentReplyCreate,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F008-01：向处理中工单写入坐席消息。"""
    message = await _ticket_service(db).send_agent_reply(
        current,
        ticket_id,
        content=body.content,
    )
    return contract_success_response(message.model_dump(mode="json"))


@router.post("/{ticket_id}/suggestions")
async def create_suggestion(
    ticket_id: int,
    body: SuggestionCreate,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F009-01：为处理中工单生成仅坐席可见的建议，不写 messages。"""
    suggestion = await _ticket_service(db).create_suggestion(
        current,
        ticket_id,
        focus_message_id=body.focus_message_id,
    )
    return contract_success_response(suggestion.model_dump(mode="json"))


@router.put("/{ticket_id}/category")
async def update_ticket_category(
    ticket_id: int,
    body: TicketCategoryUpdate,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F010-01：为未完结工单写入分类；已完结 CONFLICT。"""
    summary = await _ticket_service(db).update_category(
        current,
        ticket_id,
        category=body.category,
    )
    return contract_success_response(summary.model_dump(mode="json"))


@router.post("/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F011-01：处理中 → 已完结；已完结幂等；待处理 CONFLICT。"""
    summary = await _ticket_service(db).close_ticket(current, ticket_id)
    return contract_success_response(summary.model_dump(mode="json"))


@router.get("/{ticket_id}")
async def get_ticket_detail(
    ticket_id: int,
    current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F005-02：本人工单；未转人工的他人工单对外 NOT_FOUND。"""
    detail = await _ticket_service(db).get_detail(current, ticket_id)
    return contract_success_response(detail.model_dump(mode="json"))
