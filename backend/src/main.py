"""应用入口：基于 pycore.api.APIServer 创建 FastAPI 应用。"""

from pycore.api import APIConfig, APIServer
from pycore.core import Logger, LoggerConfig, LogLevel, get_logger

from src.api.deps import register_auth_exception_handlers
from src.api.routes import auth_router, knowledge_documents_router, tickets_router
from src.core.config import get_settings
from src.db.session import close_db, init_db

Logger.configure(
    LoggerConfig(level=LogLevel.INFO, app_name="service_robot", json_format=False)
)
logger = get_logger()

settings = get_settings()

server = APIServer(
    APIConfig(
        title="智能客服系统",
        version="1.0.0",
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        cors_origins=settings.cors_origins,
    )
)

server.on_startup(init_db)
server.on_shutdown(close_db)
server.include_router(auth_router)
server.include_router(tickets_router)
server.include_router(knowledge_documents_router)

logger.info("API application created", host=settings.host, port=settings.port)

app = server.app
register_auth_exception_handlers(app)
