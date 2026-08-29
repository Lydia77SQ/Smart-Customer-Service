"""按资源拆分的路由模块。"""

from src.api.routes.auth import router as auth_router
from src.api.routes.knowledge_documents import router as knowledge_documents_router
from src.api.routes.tickets import router as tickets_router

__all__ = [
    "auth_router",
    "knowledge_documents_router",
    "tickets_router",
]
