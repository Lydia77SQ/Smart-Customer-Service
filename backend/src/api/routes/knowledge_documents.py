"""知识文档资源路由。API-F012-01 上传、API-F012-02 列表、API-F013-01 启停。"""

from typing import Annotated

from fastapi import Depends, File, Query, UploadFile
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
from src.models.knowledge import KnowledgeDocumentStatusUpdate
from src.repositories.knowledge import (
    KnowledgeChunkRepository,
    KnowledgeDocumentRepository,
    QaPairRepository,
)
from src.services.knowledge import KnowledgeService

router = APIRouter(prefix="/api/knowledge_documents", tags=["knowledge_documents"])


def _knowledge_service(db: AsyncSession) -> KnowledgeService:
    return KnowledgeService(
        KnowledgeDocumentRepository(db),
        KnowledgeChunkRepository(db),
        QaPairRepository(db),
    )


@router.post("")
async def upload_knowledge_document(
    file: Annotated[UploadFile, File()],
    _current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F012-01 上传 Markdown 入库。处理失败返回 200 且 status=failed。"""
    content = await file.read()
    document = await _knowledge_service(db).upload(filename=file.filename, content=content)
    return contract_success_response(document.model_dump(mode="json"))


@router.get("")
async def list_knowledge_documents(
    page: Annotated[int | None, Query(ge=1)] = None,
    page_size: Annotated[int | None, Query(ge=1)] = None,
    _current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F012-02 知识文档列表，含启用、停用、失败、处理中。"""
    settings = get_settings()
    current_page = page if page is not None else settings.knowledge_list_page_default
    current_size = page_size if page_size is not None else settings.knowledge_list_page_size
    items, total = await _knowledge_service(db).list_documents(
        page=current_page,
        page_size=current_size,
    )
    return contract_paginated_response(
        [item.model_dump(mode="json") for item in items],
        page=current_page,
        page_size=current_size,
        total_items=total,
    )


@router.patch("/{document_id}")
async def patch_knowledge_document(
    document_id: int,
    body: KnowledgeDocumentStatusUpdate,
    _current: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F013-01 整篇启用或停用。不删除切片、问答与原文。"""
    document = await _knowledge_service(db).toggle(document_id, body.enabled)
    return contract_success_response(document.model_dump(mode="json"))
