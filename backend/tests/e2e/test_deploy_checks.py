"""部署前检查与联调静态门禁：.env 不入库、无 reopen、无 [Mock]、百炼 fallback 标注。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.core.config import get_settings
from src.main import app as runtime_app
from src.services.embedding import is_embedding_key_configured

from .conftest import FRONTEND_SRC, PROJECT_ROOT, RUNTIME_DB

pytestmark = pytest.mark.timeout(600)

PAGES = [
    FRONTEND_SRC / "pages" / "LoginPage.vue",
    FRONTEND_SRC / "pages" / "EmployeePage.vue",
    FRONTEND_SRC / "pages" / "AgentPage.vue",
    FRONTEND_SRC / "pages" / "KnowledgePage.vue",
]
HEADER = FRONTEND_SRC / "components" / "AppHeader.vue"
AUTH_SERVICE = FRONTEND_SRC / "services" / "authService.ts"
TICKET_SERVICE = FRONTEND_SRC / "services" / "ticketService.ts"
KNOWLEDGE_SERVICE = FRONTEND_SRC / "services" / "knowledgeService.ts"
STARTUP_MD = PROJECT_ROOT / "docs" / "startup.md"
GITIGNORE = PROJECT_ROOT / ".gitignore"


def test_gitignore_excludes_backend_env() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    assert "backend/.env" in text
    assert ".env" in text


def test_backend_env_not_tracked_by_git() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--", "backend/.env", "frontend/.env"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_runtime_app_has_no_reopen_route() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    reopen_paths = [path for path in paths if path is not None and "reopen" in path.lower()]
    assert reopen_paths == []
    assert "/api/tickets/{ticket_id}/close" in paths


def test_frontend_pages_have_no_mock_label() -> None:
    for path in [*PAGES, HEADER]:
        text = path.read_text(encoding="utf-8")
        assert "[Mock]" not in text
        assert "重新打开" not in text


def test_workbench_header_has_three_entries() -> None:
    text = HEADER.read_text(encoding="utf-8")
    assert 'to="/employee"' in text
    assert 'to="/agent"' in text
    assert 'to="/knowledge"' in text
    assert "员工咨询" in text
    assert "坐席接待" in text
    assert "知识维护" in text


def test_frontend_services_hit_real_api_when_mock_disabled() -> None:
    auth = AUTH_SERVICE.read_text(encoding="utf-8")
    tickets = TICKET_SERVICE.read_text(encoding="utf-8")
    knowledge = KNOWLEDGE_SERVICE.read_text(encoding="utf-8")
    assert "isMockEnabled" in auth
    assert "isMockEnabled" in tickets
    assert "isMockEnabled" in knowledge
    assert "/auth/register" in auth
    assert "/auth/login" in auth
    assert "/auth/me" in auth
    assert "/tickets/messages" in tickets
    assert "/transfer" in tickets
    assert "/accept" in tickets
    assert "/suggestions" in tickets
    assert "/agent-replies" in tickets
    assert "/category" in tickets
    assert "/close" in tickets
    assert "/knowledge_documents" in knowledge
    assert "reopen" not in tickets.lower()


def test_startup_md_records_ports_and_env_field_names() -> None:
    assert STARTUP_MD.is_file()
    text = STARTUP_MD.read_text(encoding="utf-8")
    for token in ("5199", "8099", "5175", "8003", "VITE_USE_MOCK=false"):
        assert token in text
    for field in ("SECRET_KEY", "DASHSCOPE_API_KEY", "VITE_API_BASE_URL", "VITE_BACKEND_PROXY_TARGET"):
        assert field in text
    assert "sk-" not in text
    assert "Bearer " not in text
    assert "fallback" in text.lower() or "降级" in text
    assert "不宣称" in text or "不得宣称" in text


def test_bailian_fallback_annotation() -> None:
    configured = is_embedding_key_configured(get_settings().dashscope_api_key)
    if configured:
        print(
            "\n===== 百炼配置状态 =====\n"
            "DASHSCOPE_API_KEY：已配置于 backend/.env（key_configured=True）。\n"
            "本 E2E 对 Embedding / Chat / Rerank 使用 monkeypatch，走确定性主链路，"
            "不宣称百炼 Chat Completions / Embedding / Rerank 完整联调。\n"
            "========================\n"
        )
    else:
        print(
            "\n===== FALLBACK =====\n"
            "DASHSCOPE_API_KEY：字段存在但未配置或为占位值（key_configured=False）。\n"
            "本 E2E 走已有 DEGRADED / monkeypatch 路径，不宣称百炼完整联调。\n"
            "缺 Key 时入库 failed、答疑/建议降级，见 docs/startup.md。\n"
            "====================\n"
        )
    # 只记录配置状态，禁止打印密钥。E2E 始终 monkeypatch，不替代 T-014/T-016/T-021。
    assert configured in {True, False}


def test_runtime_sqlite_not_the_e2e_tmp_path(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()
    if RUNTIME_DB.is_file():
        assert RUNTIME_DB.stat().st_size >= 0
