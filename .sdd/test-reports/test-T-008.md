# 测试报告：T-008 SQLite 建表、FTS5 与 init_db

**测试时间**：2026-08-29 18:15
**Tester Agent ID**：tester

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | backend/src/db/models.py 与 backend/src/db/session.py 基于 pycore 模板扩展 | PASS | 对照 `pycore/integrations/db/models.py` / `session.py`：保留 `DeclarativeBase`/`Base`、`get_db`/`get_db_context`/`init_db`/`close_db`/`async_session_maker` 骨架；业务表替换模板 `User`；session 扩展 `resolve_database_file`、`make_async_engine`、`create_schema_sync`（含 FTS5）与 `apply_schema`，未从零手写会话层 |
| 2 | cd backend && PYTHONPATH=.. python scripts/init_db.py 执行成功 | PASS | 使用项目 `.venv`：`Database initialized: .../backend/data/service_robot.db`，exit 0 |
| 3 | 真实 SQLite 文件 backend/data/service_robot.db 存在且含 data-model.md 全部业务表 | PASS | 文件存在（约 102400 bytes）。`sqlite_master` 含 accounts、sessions、tickets、messages、suggestions、knowledge_documents、knowledge_chunks、qa_pairs |
| 4 | knowledge_chunks_fts FTS5 虚表已创建 | PASS | `CREATE VIRTUAL TABLE knowledge_chunks_fts USING fts5(content, chunk_id UNINDEXED)`；并有 ai/ad/au 同步触发器 |

## technicalChecks

| # | 检查 | 结果 | 说明 |
|---|------|------|------|
| 1 | python -m pytest backend/tests --timeout=120 通过 | PASS | `21 passed`（约 1.89s）；带 `--timeout=120` |
| 2 | cd backend && PYTHONPATH=.. python scripts/init_db.py 通过 | PASS | 同上真实脚本执行 |
| 3 | SQLite 目标表与索引真实落盘（非仅测试夹具） | PASS | 查询运行时库非临时夹具；索引含 data-model §5 命名索引（测试与 ORM `__table_args__` 一致） |
| 4 | python -m ruff check backend/src backend/tests 通过 | PASS | Developer 声明通过；抽检 models/session/init_db/test_db_schema：`All checks passed!`；mypy 抽检 db 模块：`Success: no issues found` |

## 强制补充验证

| # | 项 | 结果 | 说明 |
|---|-----|------|------|
| A | pytest 后真实业务库表仍在 | PASS | pytest 后复查 8 张业务表 + knowledge_chunks_fts 均在，库文件未清空 |
| B | 测试隔离：禁止对运行时 engine drop_all | PASS | `backend/tests` 无 `drop_all` 调用；`test_db_schema.py` 仅对 `tmp_path` 临时库 `apply_schema`；`conftest.py` 为空骨架 |
| C | deps.py 使用 `from src.db.session import get_db` | PASS | `backend/src/api/deps.py:7` 已按项目会话导入；认证实现属 T-009，未因占位逻辑判 FAIL |

## 证据摘要

- init_db：成功落盘 `backend/data/service_robot.db`
- 真实库表：accounts / sessions / tickets / messages / suggestions / knowledge_documents / knowledge_chunks / qa_pairs / knowledge_chunks_fts
- pytest：21 passed，`--timeout=120`
- 未改 Developer 代码；报告未含密钥

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | deps.py 中 get_current_user 为占位（无效 token 仍可返回 placeholder） | T-009 认证 | 由 T-009 实现，本任务不判 FAIL |
| 2 | pytest 汇总含 pycore Pydantic V2 ConfigDict deprecation warnings | pycore | 框架侧，不纳入本任务 |
