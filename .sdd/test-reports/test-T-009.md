# 测试报告：T-009 路由级认证依赖 deps.py

**测试时间**：2026-08-29 18:23
**Tester Agent ID**：tester

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | backend/src/api/deps.py 基于 pycore 模板扩展 | PASS | 对照 `pycore/api/deps.py`：保留 `HTTPBearer(auto_error=False)`、`get_current_user(credentials, db)` 签名骨架；扩展为 opaque session HMAC 校验、项目 `Account`/`Session` 模型、`UnauthorizedError` + 统一信封，未从零手写依赖层 |
| 2 | get_current_user 作为路由级 Depends 依赖实现 | PASS | `get_current_user` 参数使用 `Depends(security)` / `Depends(get_db)`；测试夹具受保护路由 `Depends(get_current_user)`；`main.py` 仅注册异常处理器，未注册全局 AuthMiddleware |
| 3 | 无 Authorization 或无效 token 访问受保护路由返回 401 统一错误格式 | PASS | 单测覆盖 missing / invalid / expired：HTTP 401，信封 `{"code":"UNAUTHORIZED","message":"未认证","data":null}`；有效 token 返回 200 与当前账号字段 |
| 4 | 认证逻辑使用项目 DB 会话，非 pycore 模板默认会话 | PASS | `from src.db.session import get_db`；源码无 `pycore.integrations.db.session`；签名绑定 `get_db` 已由 `test_get_current_user_binds_project_get_db` 确认 |

## technicalChecks

| # | 检查 | 结果 | 说明 |
|---|------|------|------|
| 1 | python -m pytest backend/tests --timeout=120 通过（含 deps 401 单测） | PASS | `29 passed`（约 3.05s），带 `--timeout=120`；含 missing/invalid/expired 401 与 valid 200 |
| 2 | python -m ruff check backend/src backend/tests 通过 | PASS | Developer 声明通过；抽检 deps/main/test_deps：`All checks passed!` |
| 3 | python -m mypy backend/src backend/tests 通过 | PASS | Developer 声明通过；抽检上述三文件：`Success: no issues found` |
| 4 | 不要求 app.user_middleware 出现认证中间件 | PASS | `app.user_middleware` 仅 `CORSMiddleware`；无 Auth* 中间件（CORS 允许） |

## 强制补充验证

| # | 项 | 结果 | 说明 |
|---|-----|------|------|
| A | pytest 后真实业务库表仍在 | PASS | 跑前/跑后 `backend/data/service_robot.db` 均含 accounts、sessions、tickets、messages、suggestions、knowledge_documents、knowledge_chunks、qa_pairs、knowledge_chunks_fts；size 102400 未清空 |
| B | 测试隔离 | PASS | `test_deps.py` 使用 `tmp_path` 独立库 + `dependency_overrides[get_db]`；`backend/tests` 无对运行时 `engine`/`async_session_maker` 的 `drop_all`；httpx `trust_env=False` |
| C | 规范对齐（rules_files → specification/default） | PASS | 符合 tech-stack（pycore 模板扩展 deps）、api-design（路由级认证、UNAUTHORIZED 信封）、error-handling（统一信封）；未要求全局 AuthMiddleware |
| D | 密钥泄露检查 | PASS | Developer 产出 `.md`/测试中未见真实密钥；报告未复述密钥 |

## 证据摘要

- deps：基于 pycore 模板；`get_db` 来自 `src.db.session`；401 统一信封
- middleware：仅 CORS，无认证中间件
- pytest：29 passed，`--timeout=120`；业务库表完整
- 未改 Developer 代码；范围未因 T-011/T-012 未实现判 FAIL

## 超出范围发现（不影响当前任务判定）

无。
