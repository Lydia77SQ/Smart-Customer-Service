# 测试报告：T-005 后端 pycore 接入与项目骨架

**测试时间**：2026-08-29 17:50 (UTC+8)
**Tester Agent ID**：tester-T-005-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | backend/src/main.py 使用 pycore.api.APIServer，未自行 new FastAPI() | PASS | `main.py` 从 `pycore.api` 导入 `APIServer`/`APIConfig`，`server = APIServer(APIConfig(...))`，`app = server.app`。全量扫描 `backend/src/**/*.py` 无业务代码自行 `FastAPI(`。 |
| 2 | backend/ 目录结构符合 specification/default/backend/layers.md | PASS | 已存在 `backend/src/models/`、`db/`（含 `models.py`/`session.py`）、`repositories/`、`services/`、`api/`（含 `routes/`）、`core/`，与 layers.md 自下而上分层一致；骨架占位包齐全。 |
| 3 | CORS 中间件已注册，允许 tech-spec §4 中 CORS_ORIGINS 来源 | PASS | `main.py` 将四个 origin 传入 `APIConfig.cors_origins`；pycore `APIServer` 注册 `CORSMiddleware`。短时启动后对四源 GET/OPTIONS 均回显 `Access-Control-Allow-Origin`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m ruff check backend/src backend/tests 通过 | PASS | `.venv` 内 `python -m ruff check backend/src backend/tests` 退出码 0（All checks passed）。 |
| 2 | python -m mypy backend/src backend/tests 通过 | PASS | `.venv` 内 `python -m mypy backend/src backend/tests` 退出码 0（13 source files, no issues）。 |
| 3 | cd backend && PYTHONPATH=.. python -m uvicorn src.main:app --host 127.0.0.1 --port 8099 可短时启动 | PASS | 使用绝对 `PYTHONPATH=<项目根>` + `.venv` 的 `python -m uvicorn`；`/health` → 200 `{"status":"healthy","version":"1.0.0"}`。验证后已关闭进程。 |
| 4 | pycore/ 未被纳入 ruff/mypy 门禁范围 | PASS | `pyproject.toml`：`[tool.ruff] exclude` 含 `pycore`；`[tool.mypy] exclude` 含 `pycore/`，且 `pycore.*` override `ignore_errors`/`follow_imports=skip`。命令仅覆盖 `backend/src`/`backend/tests`。 |

## 环境与命令证据

- 本机指令：`python`（3.14.7），经项目 `.venv\Scripts\python.exe` 执行
- 启动：`cd backend` + `PYTHONPATH=<项目根>` + `python -m uvicorn src.main:app --host 127.0.0.1 --port 8099`
- `/health` HTTP 200；CORS 四源（5199/5175 的 localhost 与 127.0.0.1）GET/OPTIONS 均回显来源
- SECRET_KEY 已配置于 backend/.env（报告不复述密钥）
- 可读产物（`.md`/`.json`/`.toml`/源码等，排除 `.env`/`pycore`/`.venv`）抽检：未发现真实密钥泄露
- 验证结束后服务已停止（8099 不再响应）

## 规范对照摘要

- `rules_files` 解析到 `harness-core/specification/default/...`（集名 default），文件存在
- `docs/tech-spec.md` §4 `CORS_ORIGINS` 四源与实现一致
- 分层目录符合 `layers.md`；入口基于 pycore，未重写 FastAPI 工厂

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `pytest`/`pytest-timeout` 未在本任务正式化 | T-006 | 由 T-006 验收 |
| 2 | 完整 ConfigManager / 全部 config 键 / `.env.example` 未做 | T-007 | 由 T-007 验收 |
| 3 | `db/models.py` 仅有 `Base`，全表与 FTS5 未建 | T-008 | 由 T-008 验收 |
