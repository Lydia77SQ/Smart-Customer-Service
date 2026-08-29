# 测试报告：T-002 员工咨询工作台 Mock（/employee）

**测试时间**：2026-08-29 16:50 (UTC+8)
**Tester Agent ID**：tester-T-002-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F003-01] 用户在员工咨询工作台顶栏点击「坐席接待」「知识维护」再返回，页面切换正常且仍显示当前 Mock 用户身份 | PASS | `AppHeader.vue` 提供三端 `RouterLink`（员工咨询/坐席接待/知识维护），右侧渲染 `authStore.user.display_name`；`onMounted` 调 `fetchMe()` 刷新身份。`AgentPage.vue` / `KnowledgePage.vue` 均挂载同一顶栏。路由仍带 `meta.requiresAuth`，守卫未破坏。Mock 登录用户显示名为「王丽」。 |
| 2 | [AC-F004-01] 用户点击「新咨询」并发送问题，对话区出现员工气泡与一条系统答复气泡 | PASS | `startNewConsult` → `sendEmployeeMessage({ticket_id:null})`；Mock 建 `ai_assisting` 工单并追加 `employee_message` + `system_message`。SSR 抽检：新咨询「会议室…」返回 `qa_result_type=generated_answer`，双气泡均存在；`clarification`/`direct_answer`/`degraded` 关键词样例均可触发。 |
| 3 | [AC-F005-01] 左侧「我的咨询」列表只展示 Mock 数据中属于当前用户的咨询条目 | PASS | `mockListMine` 按 `requester_id === user.id` 过滤；预置 requester_id=99 的异账号工单不出现。抽检列表仅 2 条：VPN（in_progress）、工牌（closed），与原型一致。 |
| 4 | [AC-F005-03] 用户打开状态为已完结的咨询，输入框与「发送」「转人工」为禁用态 | PASS | `isClosed` 禁用 textarea；`canSend` 对 `closed` 为 false；`canTransfer` 仅 `ai_assisting`。Mock 对 closed 发送/转人工均 409。占位文案「已完结，不能再发送」与原型一致。 |
| 5 | [AC-F006-01] 用户在 AI 接待中咨询点击「转人工」，状态条变为待处理并显示等待对接人提示 | PASS | `mockTransferTicket`：`ai_assisting`→`pending`，追加系统消息「已提交，等待对接人」。页面状态条文案「待处理 · 已提交，等待对接人」。抽检 transfer 后 `AFTER_STATUS=pending`。 |
| 6 | 页面布局、配色与全部文案与 docs/prototypes/employee.html 一致 | PASS | 顶栏/侧栏/状态条/气泡角色名/底栏/空态/列表示例文案与原型逐字对齐；结构为顶栏 + 左列表 + 主对话 + composer。错误条仅失败时出现，符合 ui-design-spec「错误用文案说明」。坐席/知识完整页属后续任务，本任务仅占位+顶栏身份。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | Typecheck passes | PASS | `npm run type-check`（vue-tsc）退出码 0（本轮独立执行） |
| 2 | Lint passes | PASS | Developer 已声明通过；本轮对新增/修改相关文件抽检 `npm run lint` 退出码 0（无 error） |
| 3 | Mock 数据字段与 api-contracts.md 中 TicketSummary、MessageOut、qa_result_type 枚举一致 | PASS | Summary 键：`category,created_at,id,status,title,updated_at`；Message 键：`content,created_at,id,sender_type`；`qa_result_type` ∈ `direct_answer/clarification/generated_answer/degraded/none`。handler 经 `toTicketSummary`/`toMessageOut`/`toTicketDetail` 显式 DTO，内部 `requester_id` 不外泄。 |
| 4 | 样式取值与 docs/prototypes/design-tokens.md 逐项一致 | PASS | `styles.css` `:root` 色值/字体/字号/间距/圆角 8px/阴影与取值表一致；状态条 `--color-focus-bar`、已完结 `--color-muted`。 |
| 5 | 底栏「转人工」与「发送」同一行不换行 | PASS | `.composer { flex-wrap: nowrap }`；`.btn { white-space: nowrap }`；按钮 `flex-shrink: 0`。对齐 ui-design-spec 与技术检查。 |

## 环境与命令证据

- `npm run type-check` / 抽检 `npm run lint` / `npm run build` 均退出码 0
- Mock 行为：Vite SSR 加载 `mocks/auth.ts` + `mocks/tickets.ts` 验证列表隔离、新咨询双气泡、qa 四类、转人工 pending、已完结 409
- 列表时间格式：`今天 14:12` / `昨天 09:40`（与原型一致）
- 短时 Vite：`npm run dev -- --host 127.0.0.1 --port 5199` → `/login` `/employee` HTTP 200；`styles.css` 含 nowrap 与 token；测完已关闭 5199 进程
- Mock 阶段：`VITE_USE_MOCK=true`，未要求真实后端；未使用 Playwright/Puppeteer/Cypress

## 规范对照摘要

- rules_files（`harness-core/specification/default/...` 与项目 `docs/...`）均存在，未静默降级
- Mock 数据集中于 `frontend/src/mocks/`；service 在 Mock 开启时走本地 handler
- T-001 登录/守卫：`router/index.ts` 三工作台 `requiresAuth` 仍在；未发现密钥泄露
- 未发现新增代码中的 TODO/FIXME/HACK 或硬编码真实密钥

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `/agent`、`/knowledge` 仍为占位页（仅顶栏+占位文案） | T-003 / T-004 | 按后续任务实现完整坐席台/知识台 |
