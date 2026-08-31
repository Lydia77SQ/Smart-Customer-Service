# 测试报告：T-024 全系统 E2E 回归与启动文档

**测试时间**：2026-08-31 21:35 (UTC+8)
**Tester Agent ID**：tester-T-024-20260831

## 结果：PASS

## 外部服务联调口径（强制）

- **真实外部服务未验收 / fallback**：E2E 对 Embedding / `QaPipeline.run`（覆盖 Chat + Rerank 语义路径）使用 monkeypatch；`test_bailian_fallback_annotation` 打印「`DASHSCOPE_API_KEY`：已配置于 backend/.env（key_configured=True）」并明确「不宣称百炼 Chat Completions / Embedding / Rerank 完整联调」。
- 本任务 **不得** 标为百炼完整联调通过；在 fallback 标注齐全前提下，T-024 仍可 PASS（与 technicalChecks 一致）。
- 报告未写入、未复述任何真实 Key。

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | 用户可完成 Plan.md §7 主链路：注册/登录→上传知识→员工提问→转人工→坐席接入→获取建议（员工不可见）→坐席回复→分类→结单→双方无法再发 | PASS | 独立重跑 `test_plan_section7_main_path`：ASGI 真实路由完成全链路；建议文本不在员工 messages；结单后双方 409；reopen 无有效路由 |
| 2 | 全链路 VITE_USE_MOCK=false，各步骤命中真实后端 API | PASS | 前端 `authService`/`ticketService`/`knowledgeService` 在 `isMockEnabled()===false`（即 `VITE_USE_MOCK=false`）时调用 `/auth/*`、`/tickets/*`、`/knowledge_documents`；E2E 命中同一批后端路由；四页与 `AppHeader` 静态无 `[Mock]` |
| 3 | startup.md 已记录前后端启动命令、端口与 .env 配置要点（不含真实密钥） | PASS | `docs/startup.md` 含 5199/8099、5175/8003、PowerShell/POSIX 启动命令、字段名表、fallback 说明；无 `sk-` / Bearer 明文 |

## technicalChecks

| # | 检查 | 结果 | 说明 |
|---|------|------|------|
| 1 | `python -m pytest backend/tests/e2e --timeout=600` | PASS | 独立执行：12 passed（1.56s）；命令：`.\.venv\Scripts\python.exe -m pytest backend/tests/e2e --timeout=600 -v` |
| 2 | Typecheck passes | PASS | 后端抽检 `mypy backend/tests/e2e` Success；前端 `npm run type-check` 通过 |
| 3 | Lint passes | PASS | 后端抽检 `ruff check backend/tests/e2e` All checks passed；前端 `npm run lint` 通过 |
| 4 | 部署前检查：backend/.env 不入库、无 reopen API、停用知识不删除 | PASS | `git ls-files backend/.env` 为空；`.gitignore` 含 `backend/.env`；运行时路由与前端无 reopen/「重新打开」；`KnowledgeService.toggle` 仅 `mark_status`，E2E 断言停用后列表/切片/QA/原文仍在 |
| 5 | 外部服务 Key 缺失时 E2E 报告标注 fallback，不宣称百炼完整联调 | PASS | 本机 Key 已配置，但 E2E 仍 monkeypatch + 打印「不宣称…完整联调」；startup.md §7 同步标注 fallback |
| 6 | 本任务不替代 T-011～T-023 各 Feature 首次真实联调 | PASS | 报告与 E2E docstring / startup 均声明不替代；未因历史任务重验全部 Feature AC |

## frontendIntegration

| 项 | 结果 | 说明 |
|---|------|------|
| pages `/login` `/employee` `/agent` `/knowledge` | PASS | 四页存在；静态无 `[Mock]` /「重新打开」；顶栏三端入口在 `AppHeader.vue` |
| services 真实 API | PASS | 实际文件为 `authService.ts` / `ticketService.ts` / `knowledgeService.ts`；`VITE_USE_MOCK=false` 走真实相对路径 API |
| Vite 代理 | PASS | `vite.config.ts` 代理 `/api`→`VITE_BACKEND_PROXY_TARGET` 默认 8099，`/ws` 含 `ws: true` |
| E2E 形态 | PASS | 采用 pytest+ASGI 等价套件（任务允许「或等价 Playwright」），非浏览器自动化；主链路与部署门禁由 `backend/tests/e2e` 覆盖 |

## 测试隔离

| 项 | 结果 | 说明 |
|---|------|------|
| 独立测试库 | PASS | `tmp_path/e2e.db` + `dependency_overrides[get_db]`；断言路径 ≠ `backend/data/service_robot.db` |
| 运行时库未污染 | PASS | 主路径重跑前后业务库 size 均为 282624；表 `accounts/tickets/messages/knowledge_*` 仍在且有数据；无 `drop_all` 运行时 engine |

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `.sdd/experience.md` T-024 写「不要用 `.venv\Scripts\python.exe`」，与本机 Harness/门禁「后端验证用项目 venv python」不一致 | 文档/经验 | 后续修订 experience，避免误导后续 Tester |

## 如果 FAIL，详情如下

（无）
