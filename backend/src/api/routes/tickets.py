"""咨询工单资源路由。业务端点由后续任务实现。"""

from pycore.api import APIRouter

router = APIRouter(prefix="/api/tickets", tags=["tickets"])
