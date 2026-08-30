# 测试报告：T-018 F-006 员工转人工闭环

**测试时间**：2026-08-30 10:46 (UTC+8)
**Tester Agent ID**：tester-T-018-20260830

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F006-01] 用户在 AI 接待中咨询点击「转人工」，状态变为待处理，对话保留且出现等待对接人提示 | PASS | 后端 `transfer_to_human`：仅 `ai_assisting`→`pending`，写入 `settings.transfer_success_message`（「已提交，等待对接人」）系统消息。前端 `canTransfer` 仅 `ai_assisting`；转成功后状态条「待处理 · 已提交，等待对接人」。pytest `test_transfer_ai_assisting_keeps_context_and_writes_system_message` 通过。真实联调：ticket#7 transfer→pending，详情末条系统消息为等待对接人文案，原消息保留。 |
| 2 | [AC-F006-02] 坐席在坐席接待页待处理列表能看到该工单，看不到从未转人工的 AI 接待中单 | PASS | `list_agent_queue` 仅 `status=pending|in_progress`；`ai_assisting` 不入队。pytest `test_pending_queue_shows_transferred_hides_never_transferred` 通过。真实联调：转前队列不含 ticket#7；转后含 #7；另建 AI-only 单不在 pending 队列。坐席页 `useAgentStore.loadQueue`→`listAgentQueue('pending')`。 |
| 3 | [AC-F006-03] 用户在已完结咨询点击「转人工」，操作被拒绝，状态仍为已完结 | PASS | 后端 closed→409 CONFLICT「已完结，不能转人工」，不插消息。前端 closed/非 ai_assisting 时转人工按钮 disabled。pytest `test_closed_ticket_transfer_rejected_status_unchanged` 通过。真实联调：closed 工单 transfer 409，详情 status 仍为 closed。 |
| 4 | VITE_USE_MOCK=false 时转人工与坐席队列命中真实后端 API，页面无 [Mock] 文案 | PASS | 启动前端 `VITE_USE_MOCK=false`；Vite 内联 `VITE_USE_MOCK==="false"`，`isMockEnabled()` 为 false。`transferTicket`/`listAgentQueue` 走 `api.post/get`。经 5199 代理实测 transfer/agent-queue 均 200。`/employee`、`/agent` 与源码无 `[Mock]`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m pytest backend/tests/features/f006 --timeout=120 | PASS | 项目 `.venv` python：`14 passed`（约 13.7s） |
| 2 | Typecheck passes | PASS | 后端 mypy 抽检 tickets/service/repository/models 无问题；前端 `npm run type-check` 退出码 0 |
| 3 | Lint passes | PASS | `ruff check` 目标文件 + f006 tests 通过；前端 `npm run lint` 退出码 0 |
| 4 | VITE_USE_MOCK=false 时 transfer/agent-queue 不走 Mock 分支 | PASS | 见 AC#4；不调用 `mockTransferTicket`/`mockListAgentQueue` |
| 5 | 转人工写入 TRANSFER_SUCCESS_MESSAGE 系统消息 | PASS | config `transfer_success_message` 默认「已提交，等待对接人」；pytest 与真实联调详情末条均命中 |

## frontendIntegration

| 项 | 结果 | 说明 |
|---|------|------|
| pages `/employee` `/agent` | PASS | 路由页存在；5199 返回 200 |
| services `ticketService.ts` | PASS | `transferTicket` / `listAgentQueue` 真实路径已实现（任务里 tickets.ts 为旧名，以仓库实际为准） |
| realApiEndpoints transfer / agent-queue | PASS | 8099 与 5199 代理均打通 |
| mockExitCriteria 真实 API | PASS | Mock 关闭且代理命中后端 |
| mockExitCriteria 仅 ai_assisting 可转 | PASS | `EmployeePage.vue` `canTransfer` + 按钮 disabled 绑定 |

## 环境与命令证据

- 后端：`PYTHONPATH=<project_root>` + `.venv` uvicorn `127.0.0.1:8099` 启动成功
- 前端：`VITE_USE_MOCK=false` vite `127.0.0.1:5199`，`VITE_API_BASE_URL=/api`，proxy → `8099`
- CORS：含 `localhost/127.0.0.1:5199` 与 `:5175`
- 测试隔离：f006 用 `tmp_path` + `dependency_overrides[get_db]`；运行时库表与 seed 账号仍在（未 drop_all）
- 未安装 Playwright / 未下载浏览器；未宣称百炼答疑完整联调；未因未实现接入/回复/结单判 FAIL

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 坐席接入/回复/结单属 T-019+，本任务未验收 | F-007+ | 后续任务验证 |
