# 测试报告：T-017 F-005 查看续聊闭环

**测试时间**：2026-08-30 10:25 (UTC+8)
**Tester Agent ID**：tester-T-017-20260830-r2

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F005-01] 用户在员工咨询页左侧列表只看到自己的咨询，看不到他人咨询 | PASS | 后端 `TicketRepository.list_mine` 按 `requester_id` 过滤；`_own_ticket`/`get_detail` 对他人工单抛 `TicketNotFoundError`→404「资源不存在」。pytest `test_mine_and_detail_hide_other_users_tickets` 通过。真实联调：wang.li mine ids=[6,4,3,2,1]，chen.hao mine ids=[5]，集合不相交；A 打开 B 工单详情 HTTP 404。前端 store `openTicket` 额外校验 requester。 |
| 2 | [AC-F005-02] 用户打开未完结咨询并发送新消息，消息出现在同一对话中 | PASS | pytest `test_continue_ai_assisting_appends_to_same_ticket` / pending·in_progress 续聊无系统答复 通过。真实联调：对 wang.li 的 ai_assisting 工单 `POST /api/tickets/messages` 后 `ticket.id` 不变，详情 messages 由 4 增至 6。前端 `useTicketStore.send` 带 `ticket_id` 并刷新详情。 |
| 3 | [AC-F005-03] 用户打开已完结咨询，输入框禁用且发送被拒绝并提示已完结 | PASS | 前端：`isClosed` 时 textarea `:disabled`、发送/转人工 disabled，placeholder「已完结，不能再发送」；store 本地拦截同文案。后端：`status==closed`→`TicketConflictError`→409 `CONFLICT`/「已完结，不能再发送」。pytest `test_closed_ticket_detail_is_readable_and_send_rejected` 通过。运行时库本轮无 closed 样例，closed 写入拒绝以独立库 pytest + 静态 UI 绑定验收。 |
| 4 | 列表与对话布局与 docs/prototypes/employee.html 一致 | PASS | 结构：顶栏 `AppHeader`（品牌「智能客服系统」、员工咨询/坐席接待/知识维护、显示名+退出）+ `shell` 左 `sidebar`「我的咨询」列表/空态/「新咨询」+ 右 `main` 状态条/气泡线程/composer（输入+转人工+发送）。文案与原型一致（含空态、状态条四态、已完结 placeholder）。无擅自添加的原型外元素；无 `[Mock]`。 |
| 5 | VITE_USE_MOCK=false 时列表与详情命中真实后端 API，页面无 [Mock] 文案 | PASS | 启动前端时环境变量 `VITE_USE_MOCK=false`；Vite 内联 `import.meta.env.VITE_USE_MOCK==="false"`，`isMockEnabled()` 为 false。`ticketService.listMyTickets`/`getTicket`/`sendEmployeeMessage` 走 `api.get/post`。经 5199 代理实测 `GET /api/tickets/mine`、`GET /api/tickets/{id}` 返回真实信封 code=200。页面与源码无 `[Mock]`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m pytest backend/tests/features/f005 --timeout=120 | PASS | 项目 `.venv` python：`11 passed`（约 11.3s） |
| 2 | Typecheck passes | PASS | `npm run type-check`（vue-tsc）退出码 0 |
| 3 | Lint passes | PASS | 后端 `ruff check` 目标文件通过；`mypy` tickets 路由/service/repository 无问题；前端 `npm run lint` 退出码 0 |
| 4 | VITE_USE_MOCK=false 时 mine/detail 不走 Mock 分支 | PASS | 见 AC#5；Vite 已内联 `VITE_USE_MOCK=false`，不调用 `mockListMine`/`mockGetTicket` |
| 5 | 样式取值与 docs/prototypes/design-tokens.md 一致 | PASS | `frontend/src/assets/styles.css` `:root` 色值/字体/字号/圆角/间距/阴影与 design-tokens 一致；员工页复用全局 shell/sidebar/bubble/composer，无自造近似色 |

## frontendIntegration

| 项 | 结果 | 说明 |
|---|------|------|
| pages `/employee` | PASS | 路由页存在；5199 返回 200 |
| realApiEndpoints mine/detail/messages | PASS | 8099 与 5199 代理均打通；messages 续聊 200 |
| mockExitCriteria list/detail 真实 API | PASS | Mock 关闭且代理命中后端 |
| mockExitCriteria closed 输入区 Disabled | PASS | `EmployeePage.vue` closed 绑定 disabled + placeholder |

## 环境与命令证据

- 后端：`PYTHONPATH=<project_root>` + `.venv` uvicorn `127.0.0.1:8099` 启动成功
- 前端：`VITE_USE_MOCK=false` vite `127.0.0.1:5199`，`VITE_API_BASE_URL=/api`，proxy → `8099`
- CORS 允许 `http://127.0.0.1:5199`
- pytest 后运行时库 `backend/data/service_robot.db` 表仍在（accounts/tickets/messages/sessions），未 drop_all；f005 测试用 `tmp_path` + `dependency_overrides[get_db]` + `trust_env=False`
- 验证后已停止 8099/5199 短时服务
- 未宣称百炼答疑完整联调；续聊复用已有 POST `/messages`

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 运行时业务库当前无 `closed` 工单，且 `POST /api/tickets/{id}/close` 尚未实现（属 F-011） | F-011 / 种子数据 | 结单闭环任务交付后再做用户门禁的 closed 真机点选 |
