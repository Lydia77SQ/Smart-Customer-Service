# 测试报告：T-020 F-008 坐席回复闭环

**测试时间**：2026-08-30 11:25 (UTC+8)
**Tester Agent ID**：tester-T-020-20260830

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F008-01] 坐席在处理中工单发送回复后，员工在同一咨询对话中看到该坐席消息气泡 | PASS | 后端 `send_agent_reply` 仅 `in_progress` 写入 `sender_type=agent` 消息；`get_detail` 从 messages 返回。前端 `AgentPage.onSend`→`useAgentStore.send`→`sendAgentReply`；`EmployeePage` 按 `sender_type` 渲染「坐席」气泡。pytest `test_agent_reply_visible_to_employee` 通过。真实联调 ticket#12：agent-replies 200，员工 GET 详情含 agent 气泡。Vite 代理 ticket#14 同样可见。 |
| 2 | [AC-F008-02] 坐席在已完结工单尝试发送，操作被拒绝，对话不新增消息 | PASS | closed→409 CONFLICT「已完结，不能再发送」；store 前端兜底禁用 composer。pytest `test_closed_ticket_reply_rejected_no_new_message` 通过。真实联调：将 ticket#12 置 closed 后 POST agent-replies 409，messages 计数不变且无尝试内容。 |
| 3 | [AC-F008-03] 坐席已生成但未发送的智能建议文本，员工对话中不可见 | PASS | 详情只读 MessageRepository，不 JOIN suggestions。pytest `test_no_leak.py` 两用例通过。真实库插入 suggestions 行后员工 GET `/api/tickets/{id}` messages 不含建议文本。 |
| 4 | VITE_USE_MOCK=false 时坐席回复命中真实后端 API，页面无 [Mock] 文案 | PASS | 前端以 `VITE_USE_MOCK=false` 启动；`isMockEnabled()` 为 false 时 `sendAgentReply` 走 `api.post('/tickets/{id}/agent-replies')`。经 5199 代理 POST/GET 均 200。`/agent`、`/employee` 与相关源码无 `[Mock]`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m pytest backend/tests/features/f008 --timeout=120 | PASS | 项目 `.venv` python：`11 passed`（约 11.7s）；含 reply + no_leak（目录全绿，不因旧文件结构 FAIL） |
| 2 | Typecheck passes | PASS | 后端 mypy 抽检 ticket models/services/routes：Success；前端 `npm run type-check` 退出码 0 |
| 3 | Lint passes | PASS | `ruff check` 目标文件 + f008 tests 通过；前端 eslint 抽检 store/service/pages 退出码 0 |
| 4 | VITE_USE_MOCK=false 时 agent-replies 不走 Mock 分支 | PASS | `ticketService.sendAgentReply` 仅 mock 开启时调 `mockSendAgentReply`；实测走真实 API |
| 5 | messages 不含 suggestions 表内容 | PASS | 契约与实现一致；pytest + 真实库插入建议后详情 messages 无泄漏 |

## frontendIntegration

| 项 | 结果 | 说明 |
|---|------|------|
| pages `/agent` `/employee` | PASS | 页面存在；5199 返回 200；坐席发送 / 员工气泡链路完整 |
| services `ticketService.ts` / `useAgentStore.ts` | PASS | `sendAgentReply` 真实路径；store `send` 追加 agent 消息并处理 closed |
| realApiEndpoints POST agent-replies / GET ticket | PASS | 8099 与 5199 代理均打通 |
| mockExitCriteria sendAgentReply 真实 API | PASS | Mock 关闭且代理命中后端 |
| mockExitCriteria 员工刷新详情可见 agent 气泡 | PASS | 员工 GET 详情可见 `sender_type=agent` |

## 环境与命令证据

- 后端：`$env:PYTHONPATH=<project_root>` + `.venv` uvicorn `127.0.0.1:8099` 启动成功
- 前端：`VITE_USE_MOCK=false` vite `127.0.0.1:5199`，`VITE_API_BASE_URL=/api`，proxy → `8099`
- CORS：含 `localhost/127.0.0.1:5199` 与 `:5175`
- 测试隔离：f008 用 `tmp_path` + `dependency_overrides[get_db]` + `trust_env=False`；运行时库表与 seed 账号仍在（未 drop_all）
- 未安装 Playwright / 未下载浏览器；未宣称百炼答疑完整联调；未因未实现获取建议/分类/结单判 FAIL

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 获取建议 / 分类 / 结单 API 与 UI 完整闭环属 T-021+ | F-009～F-011 | 后续任务验证 |
| 2 | 运行时库留有本轮联调工单与 1 条测试 suggestions 行 | 测试数据 | 不影响 AC；无需清库 |
