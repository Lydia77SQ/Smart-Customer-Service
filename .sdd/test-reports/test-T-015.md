# 测试报告：T-015 F-013 启用停用知识文档闭环

**测试时间**：2026-08-29 23:55 (UTC+8)
**Tester Agent ID**：tester-T-015-20260829

## 结果：PASS

独立验证；未信任 Developer 声明。未安装 Playwright / Chromium；页面项以静态对照 + `VITE_USE_MOCK=false` 下 Vite 代理真实 PATCH 判定。未清空运行时业务库，未复述密钥。未宣称百炼答疑完整联调通过（答疑影响留给 T-016）。

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F013-01] 停用后行仍在列表且为已停用（答疑影响留给 T-016） | PASS | 运行时 `PATCH /api/knowledge_documents/{id}` `enabled=false` → `status=disabled`；随后 `GET` 列表仍含该 `id` 且为已停用。pytest `test_disable_keeps_row_chunks_and_file` / `test_disabled_document_excluded_from_retrieval_ids` 同步通过。答疑流水线未在本任务验收（notes / T-016）。 |
| 2 | [AC-F013-02] 再次启用后列表为启用（答疑影响留给 T-016） | PASS | 同文档再 `PATCH enabled=true` → `status=enabled`，列表同行恢复启用。pytest `test_reenable_after_disable` 通过。未跑员工提问，不宣称答疑恢复。 |
| 3 | [AC-F013-03] 停用后文档行仍在列表，不会消失 | PASS | 停用后 `total_items` 不变、同行仍在；切片/原文文件仍在（pytest 断言）。服务层 `toggle` 仅 `mark_status`，无删除。 |
| 4 | 启停开关尺寸 52×32px | PASS | `frontend/src/assets/styles.css` `.switch`：`width: 52px; height: 32px;`，圆角 `8px`，与原型 `styles.css` / `design-tokens.md`「知识启停开关」一致。`KnowledgePage.vue` 使用 `label.switch`。 |
| 5 | VITE_USE_MOCK=false 时 PATCH 命中真实 API，无 [Mock] | PASS | `knowledgeService.toggleKnowledgeDocument` 在 `isMockEnabled()===false` 时 `api.patch('/knowledge_documents/{id}')`。本轮 Vite `VITE_USE_MOCK=false` 启动 5199：经代理 `PATCH` 返回与 8099 相同契约信封。`/knowledge` HTML 无 `[Mock]`；页面源码无 Mock 文案。 |

## technicalChecks

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | pytest backend/tests/features/f013 --timeout=120 | PASS | 项目 `.venv`：`13 passed`。夹具 `tmp_path` 库 + 独立 `UPLOAD_DIR` + `dependency_overrides[get_db]`，未触碰运行时库。 |
| 2 | Typecheck passes | PASS | 后端抽检相关模块 `mypy` Success；前端 `npm run type-check` 退出码 0。 |
| 3 | Lint passes | PASS | 后端抽检 `ruff check` All checks passed；前端 `npm run lint` 退出码 0。 |
| 4 | VITE_USE_MOCK=false 时 PATCH 不走 Mock | PASS | 见验收第 5 条。 |
| 5 | 样式与 design-tokens.md 一致 | PASS | 开关 52×32、圆角 8px、成功色 `--color-success: #059669`；主色等与取值表一致。 |
| 6 | failed/processing 开关 Disabled | PASS | 前端 `canToggle` 仅 `enabled`/`disabled`；`failed`/`processing` 的 checkbox `:disabled`。后端对 failed/processing PATCH → 409 `CONFLICT`（运行时实测 failed id=7；pytest 覆盖 processing）。 |

## frontendIntegration / mockExitCriteria

| # | 项 | 结果 | 说明 |
|---|----|------|------|
| 1 | pages /knowledge | PASS | 列表绑定 store；行内开关 `onToggle` → `knowledgeStore.toggle`。 |
| 2 | PATCH /api/knowledge_documents/{document_id} | PASS | 8099 直连 + 5199 代理均 200，`data.status` 正确切换；失败文档 409。 |
| 3 | 列表刷新展示 enabled/disabled 标签 | PASS | store toggle 后 `listKnowledgeDocuments` 刷新；`statusLabel`：「启用」/「已停用」；`tag-on`/`tag-off`。 |
| 4 | Vite 代理 | PASS | `vite.config.ts` `/api` → `VITE_BACKEND_PROXY_TARGET`（本轮 8099）；`VITE_API_BASE_URL=/api`。 |
| 5 | CORS 四 origin | PASS | `backend/src/core/config.py` 含 5199/5175 的 localhost 与 127.0.0.1。 |

## 验证证据摘要

- 后端：`uvicorn` `127.0.0.1:8099`（项目 `.venv`，`PYTHONPATH`=项目根）。
- 前端：`VITE_USE_MOCK=false`，`npm run dev -- --host 127.0.0.1 --port 5199`。
- 登录：预置账号 `wang.li`（token 已脱敏）。
- 目标文档：id=10 `README.md`：启用→停用（仍在列表）→再启用。
- failed 文档 id=7：PATCH 409 CONFLICT。
- pytest 后运行时库仍在：`accounts`/`knowledge_documents`/`knowledge_chunks` 记录未清空。
- 浏览器：未装 Chromium；未跑 Playwright。
- 验证后已停止本轮 8099/5199 进程。

## 代码核对（独立打开）

- `backend/src/models/knowledge.py`：`KnowledgeDocumentStatusUpdate.enabled`
- `backend/src/repositories/knowledge.py`：`mark_status` / `list_enabled_ids`
- `backend/src/services/knowledge.py`：`toggle`；failed/processing → conflict；`is_enabled_for_retrieval`
- `backend/src/api/routes/knowledge_documents.py`：PATCH 路由
- `backend/src/api/deps.py`：`KnowledgeToggleConflictError` → 409
- `backend/tests/features/f013/{conftest,test_toggle,test_toggle_qa}.py`
- `frontend/src/services/knowledgeService.ts`、`useKnowledgeStore.ts`、`KnowledgePage.vue`、`assets/styles.css`
- `.sdd/experience.md`：未见密钥泄露

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `frontend/.env` 默认仍为 `VITE_USE_MOCK=true`；本轮用启动环境变量覆盖 | frontend env | 用户门禁须显式 `VITE_USE_MOCK=false` 并重启 Vite |
| 2 | `tasks.json` 写 `frontend/src/services/knowledge.ts`，仓库实际为 `knowledgeService.ts` | Planner 路径 | 不挡验收 |
| 3 | AC 原文含答疑影响；按任务 notes 收敛到列表启停，答疑归 T-016 | 范围 | 已按 notes 判定，不得因未实现员工提问 FAIL |
