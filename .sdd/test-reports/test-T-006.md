# 测试报告：T-006 工具链配置与 pytest-timeout

**测试时间**：2026-08-29 17:53 (UTC+8)
**Tester Agent ID**：tester-T-006-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | 项目根 pyproject.toml 已配置 ruff、mypy、pytest | PASS | 存在 `[tool.ruff]`、`[tool.mypy]`、`[tool.pytest.ini_options]`；`testpaths=["backend/tests"]`、`timeout=120`；`pycore` 已从 ruff/mypy exclude |
| 2 | .venv 内 pytest-timeout 已安装可用 | PASS | `.venv\Scripts\python.exe -m pip show pytest-timeout` → Version 2.4.0；带 `--timeout=120` 的 collect/run 均成功识别插件 |
| 3 | backend/tests/ 目录存在且可被 pytest 发现 | PASS | `pytest backend/tests --timeout=120 --collect-only -q` 收集到 `test_smoke.py::test_pytest_discovers_backend_tests`（1 test） |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m ruff check backend/src backend/tests 通过 | PASS | `.venv` 内执行，退出码 0：`All checks passed!` |
| 2 | python -m mypy backend/src backend/tests 通过 | PASS | `.venv` 内执行，退出码 0：`Success: no issues found in 15 source files` |
| 3 | python -m pytest backend/tests --timeout=120 通过 | PASS | `.venv` 内执行：`1 passed in 0.01s`（smoke） |

## 强制项抽检

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | pytest 带 --timeout=120，禁止裸跑 | PASS | 已用 `--timeout=120`；插件已安装，未降级裸跑 |
| 2 | pycore/ 未纳入门禁 | PASS | pyproject 排除 pycore；命令仅覆盖 `backend/src` / `backend/tests` |
| 3 | 测试隔离：未对运行时业务库 drop_all/清表 | PASS | `conftest.py` / `test_smoke.py` 无 engine/session/drop_all；smoke 仅 `assert True`；尚无 `backend/data` 业务库被测触碰 |
| 4 | 无真实密钥泄露 | PASS | 产出文件与 experience 抽检未见真实 Key/Token |
| 5 | 本机 Python / .venv | PASS | 解释器为项目根 `.venv`（Python 3.14.7），指令为 `python` |

## 环境与命令证据

```
.\.venv\Scripts\python.exe -m pip show pytest-timeout  → 2.4.0
.\.venv\Scripts\python.exe -m pytest backend/tests --timeout=120 --collect-only -q  → 1 test collected
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests  → All checks passed!
.\.venv\Scripts\python.exe -m mypy backend/src backend/tests  → Success: no issues found in 15 source files
.\.venv\Scripts\python.exe -m pytest backend/tests --timeout=120 -q  → 1 passed
```

## 规范对照摘要

- `docs/tech-spec.md` 声明 `specification: default`；rules_files 解析至 `harness-core/specification/default/...`，所列文件均存在
- 对齐 `tech-stack.md`：项目根 pyproject 含 ruff/mypy/pytest；门禁范围 `backend/src`+`backend/tests`；pytest-timeout + `--timeout=120`
- 范围收敛：未因 T-007/T-008 未完成判 FAIL

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 项目内未见独立 `features/F-001/spec.md` | 产品文档 | 不影响本任务 AC；后续按 feature-map / Plan 继续 |
| 2 | `backend/data` 尚未落盘 | T-008 | 属后续建表任务，不判本任务 FAIL |
