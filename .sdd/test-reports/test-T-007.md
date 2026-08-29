# 测试报告：T-007 配置加载与 backend/.env.example

**测试时间**：2026-08-29 18:05 (UTC+8)
**Tester Agent ID**：tester-T-007-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | backend/src/core/config.py 使用 pycore.core.ConfigManager | PASS | `from pycore.core import … ConfigManager`；`load_settings` 注册 `DotEnvFileLoader` 后 `ConfigManager.load(AppSettings, path, use_env=False)` |
| 2 | tech-spec §4 所列键均可从环境变量读取 | PASS | `AppSettings` 字段与 tech-spec §4 后端 45 键一致；经 `backend/.env` / 临时 `.env` 可加载；`test_tech_spec_keys_are_readable` 通过；不依赖进程环境覆盖（符合 env-policy / 项目经验） |
| 3 | backend/.env.example 已生成且不含真实密钥值 | PASS | 文件存在；`SECRET_KEY=change-me`、`DASHSCOPE_API_KEY=your-dashscope-api-key`；无 `sk-` / Bearer；与 `.env` 键集合 45 项一一对应 |
| 4 | SECRET_KEY 无默认值，缺失时启动报错清晰 | PASS | `secret_key: str = Field(min_length=1)`；缺失时抛 `ConfigurationError`，文案含「SECRET_KEY」「无默认值」；`test_secret_key_missing_raises_clear_error` / empty 用例通过；`main.py` 导入时 `get_settings()` 会走同一加载路径 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m ruff check backend/src backend/tests 通过 | PASS | `.venv` 全量：`All checks passed!`；抽检 config/main/test_config 亦通过 |
| 2 | python -m mypy backend/src backend/tests 通过 | PASS | `.venv` 全量：`Success: no issues found in 17 source files` |
| 3 | 配置单测覆盖关键默认值（DATABASE_PATH、PORT、DEGRADED_* 文案等） | PASS | `test_default_database_path`、`test_default_port_and_host`、`test_default_degraded_messages`、CORS / trust_env 等；`pytest backend/tests/test_config.py --timeout=120` → 13 passed |
| 4 | 不硬编码 DASHSCOPE_API_KEY 或 SECRET_KEY | PASS | `config.py` / `main.py` 无密钥字面量；密钥仅从 `.env` 加载；报告/经验未泄露真实值 |

## 强制项抽检

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | pytest 带 --timeout=120 | PASS | `pytest backend/tests --timeout=120 -q` → **14 passed**（含 smoke + config） |
| 2 | SECRET_KEY / DASHSCOPE 配置状态 | PASS | `SECRET_KEY` 已配置于 `backend/.env`；`DASHSCOPE_API_KEY` 为空占位（可降级联调） |
| 3 | 测试隔离 | PASS | `backend/tests` 无对运行时 engine/`drop_all`；config 单测用临时 `.env` + `ConfigManager.reset()` |
| 4 | 范围收敛 | PASS | 未因 T-008 未建表判 FAIL |

## 规范对照（rules_files → default）

| 规范 | 结果 | 说明 |
|------|------|------|
| shared/env-policy.md | PASS | 前后端独立 `.env`；`DATABASE_PATH=data/service_robot.db`、`UPLOAD_DIR=data/uploads`；PORT 默认 8099；CORS 四 origin |
| shared/security.md | PASS | `.env.example` 占位齐全；敏感值未写入 docs/.sdd |
| backend/tech-stack.md 等 | PASS | 使用 pycore ConfigManager；质量门覆盖 `backend/src`/`backend/tests` |

## Feature 对齐（F-001）

T-007 为基础设施配置任务，未弱化 F-001 AC；`SESSION_EXPIRE_HOURS` 等登录相关键已纳入 config，供后续认证任务消费。

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 业务 SQLite 表尚未落盘 | T-008 | 由后续建表任务处理，本任务不判定 |
