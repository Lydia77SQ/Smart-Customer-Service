# 测试报告：T-023 F-011 坐席结单闭环

**测试时间**：2026-08-30 23:59（UTC+8）
**Tester Agent ID**：tester-T-023-20260830

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F011-01] 坐席在处理中工单点击「结束工单」，工单变为已完结，员工与坐席发送入口均禁用 | PASS | 后端 `POST /api/tickets/{id}/close`：in_progress→closed（HTTP 200）；双方再发消息均 409「已完结，不能再发送」。前端 `AgentPage`：「结束工单」+ `btn-danger`，closed 后 composer/发送 disabled；`EmployeePage`：closed 后输入/发送/转人工 disabled，placeholder「已完结，不能再发送」。真实联调（8099）与 Vite 代理（5199，`VITE_USE_MOCK=false`）均复现。 |
| 2 | [AC-F011-02] 已完结工单无「重新打开」按钮，员工与坐席均无法恢复发言 | PASS | 运行时路由无 reopen；`POST .../reopen`→404。前端 src 无「重新打开」文案/入口。已 closed 再 close 幂等 200 且仍为 closed；双方发送仍 409。pytest `test_no_reopen.py` 覆盖。 |
| 3 | [AC-F011-03] 坐席对仍为待处理的工单尝试结单，操作被拒绝 | PASS | pending close→409 CONFLICT「未接入不能结单」，状态仍 pending（真实联调 + pytest）。前端 `canClose` 仅 in_progress；store `close()` 对 pending 前置拒绝。 |
| 4 | 结单按钮样式与 docs/prototypes/agent.html 危险按钮一致 | PASS | 原型：`class="btn btn-danger"` + 文案「结束工单」+ `width:100%;margin-top:12px`。实现同结构。`styles.css` 中 `.btn-danger` 使用 `--color-danger:#DC2626`，与 design-tokens 一致；disabled 底 `#fecaca` 与原型 styles.css 一致。 |
| 5 | VITE_USE_MOCK=false 时结单命中真实后端 API，页面无 [Mock] 文案 | PASS | `ticketService.closeTicket`：`isMockEnabled()` 为 false 时 `api.post(/tickets/{id}/close)`。5199 以 `VITE_USE_MOCK=false` 启动；经代理 close 返回真实 closed。`/agent`、`/employee` HTML 无 `[Mock]`。 |

## technicalChecks

| # | 检查 | 结果 | 说明 |
|---|------|------|------|
| 1 | pytest backend/tests/features/f011 --timeout=120 | PASS | 10 passed（约 7.5s）；夹具使用独立 tmp 库 + `dependency_overrides[get_db]`，未污染 `backend/data/service_robot.db` |
| 2 | Typecheck passes | PASS | 后端 mypy 抽检 T-023 相关 7 文件 Success；前端 `npm run type-check` exit 0 |
| 3 | Lint passes | PASS | ruff 抽检 T-023 文件 All checks passed；`npm run lint` exit 0 |
| 4 | VITE_USE_MOCK=false 时 close 不走 Mock 分支 | PASS | service 源码分支 + 代理联调命中后端 |
| 5 | 无 reopen API 与前端入口 | PASS | 路由与前端静态扫描均无 reopen |

## frontendIntegration

| 项 | 结果 | 说明 |
|----|------|------|
| pages /agent、/employee | PASS | 结单危险按钮、完结只读、无重开；文案对齐原型 closed 态 |
| service（实际 ticketService.ts） | PASS | closeTicket 真实 POST |
| POST /api/tickets/{ticket_id}/close | PASS | 8099 与 5199 代理均 200→closed |
| closed 后双方输入 Disabled | PASS | Agent/Employee 页面 `:disabled` 绑定已验证 |

## 真实联调证据摘要

- 后端：`127.0.0.1:8099`；前端：`127.0.0.1:5199` + `VITE_USE_MOCK=false` + `VITE_BACKEND_PROXY_TARGET=http://localhost:8099`
- Vite 代理 `/api`→8099 已配置；`VITE_API_BASE_URL=/api`；CORS 含 5199/5175
- 联调脚本 24 项全 PASS（含 AC01/02/03、proxy close、页面无 Mock、UI 静态对齐）
- 联调后业务库仍在：accounts/tickets/messages 等表存在（未 drop）

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `frontend/.env` 默认 `VITE_USE_MOCK=true`；本任务验收以进程环境 `VITE_USE_MOCK=false` 为准 | 前端 env | 用户门禁/E2E（T-024）启动时继续显式覆盖 |
