# 测试报告：T-016 F-004 员工提问答疑闭环

**测试时间**：2026-08-30 00:26 (UTC+8)
**Tester Agent ID**：tester-T-016-20260830

## 结果：PASS

独立验证；未信任 Developer 声明。未安装 Playwright / Chromium；页面项以静态对照 + `VITE_USE_MOCK=false` 下 Vite 代理真实 POST 判定。未清空运行时业务库。外部服务：`key_configured=True`；成功路径以 pytest monkeypatch 验证；本轮真实 POST 观察到 `degraded` / `clarification`，**不宣称**真实百炼 Chat/Embedding/Rerank 全路径联调通过。报告未打印密钥。

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F004-01] 首问后对话区出现员工问题与系统答复，左侧列表出现新咨询 | PASS | pytest `test_first_question_creates_ticket_and_system_reply`：`status=ai_assisting`，employee+system 消息，`GET /mine` 含新单。运行时 8099：登录后 `POST /api/tickets/messages`（ticket_id=null）→ 200，含双方气泡；`GET /mine` 出现新 ticket。 |
| 2 | [AC-F004-02] 高置信标准问答直接返回答案，不出现反问 | PASS | pytest `test_high_confidence_qa_direct_answer`：夹具向量 ≥ 阈值 → `qa_result_type=direct_answer`，答案为标准答；LLM 被断言不得调用。 |
| 3 | [AC-F004-03] 意图模糊只反问，不给知识生成答案 | PASS | pytest `test_ambiguous_intent_only_clarifies`：`qa_result_type=clarification`，进入改写/生成会 AssertionError。 |
| 4 | [AC-F004-04] 已停用文档不作为本轮答复依据（答复区不出现该文档名） | PASS | pytest `test_disabled_document_not_used_as_answer`：停用文档 QA/切片与查询同向向量仍不直出；答复不含停用文档名。仓库 `QaPairRepository.list_enabled` / `KnowledgeChunkRepository.list_enabled` 仅 JOIN `status=enabled`。 |
| 5 | [AC-F004-05] 外部能力不可用时降级说明，非伪装答案 | PASS | pytest `test_external_unavailable_returns_degraded_message`：Embedding 失败 → `qa_result_type=degraded`，content=`DEGRADED_QA_MESSAGE`（配置文案），工单仍 `ai_assisting`。运行时直连亦曾返回 degraded。 |
| 6 | 页面布局与 docs/prototypes/employee.html 对话区一致 | PASS | `EmployeePage.vue` 结构：sidebar「我的咨询」+ list/empty/新咨询；main status-bar + thread（bubble-me/sys/agent）+ composer（textarea/转人工/发送）。文案与原型逐字一致。`styles.css` token 与 `design-tokens.md` / 原型 `styles.css` 一致（主色 #2563EB、圆角 8px、sidebar 280px、对话气泡样式）。 |
| 7 | VITE_USE_MOCK=false 时发送命中真实 POST /api/tickets/messages，无 [Mock] | PASS | 运行中 Vite 注入 `VITE_USE_MOCK=false`；经 `127.0.0.1:5199/api/tickets/messages` POST 返回真实契约（含 `qa_result_type`）。`ticketService.sendEmployeeMessage` 在 mock 关闭时 `api.post('/tickets/messages')`。`/employee` HTML 与页面源无 `[Mock]`。 |

## technicalChecks

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | pytest backend/tests/features/f004 --timeout=300 | PASS | 项目 `.venv`：`14 passed, 1 skipped`（skip=`REAL_API_TEST` 真实 Chat）。夹具 `tmp_path` + `dependency_overrides[get_db]`，未触碰运行时库。 |
| 2 | Typecheck passes | PASS | 后端抽检相关模块 mypy 退出 0；前端 `npm run type-check` 退出 0。 |
| 3 | Lint passes | PASS | 后端抽检 ruff 退出 0；前端 eslint（ticketService / useTicketStore / EmployeePage）退出 0。 |
| 4 | VITE_USE_MOCK=false 时 tickets 不走 Mock | PASS | 见验收第 7 条；`isMockEnabled()` 仅当 `!== 'false'` 为真。 |
| 5 | DASHSCOPE / 外部服务口径 | PASS（受限） | `key_configured=True`。成功路径靠 monkeypatch；真实全路径 Chat/Embedding/Rerank **未**标为联调通过。 |
| 6 | 降级返回 DEGRADED_QA_MESSAGE | PASS | 配置默认「暂时无法自动答疑，请稍后再试，或转人工等待对接人。」；pytest 与 pipeline `except` 分支一致。 |
| 7 | config 自 .env；httpx trust_env=false；禁止 dashscope SDK | PASS | llm/rerank/embedding 均 `httpx.AsyncClient(trust_env=settings.http_client_trust_env)` 且默认 False；无 `import dashscope`。 |

## frontendIntegration / mockExitCriteria

| # | 项 | 结果 | 说明 |
|---|----|------|------|
| 1 | pages /employee | PASS | 发送 → store.send → 气泡刷新；首问后 `loadMine` 刷新列表。 |
| 2 | POST /api/tickets/messages | PASS | 8099 直连 + 5199 代理均 200，契约含 ticket / employee_message / system_message / qa_result_type。 |
| 3 | sendMessage 真实 API | PASS | `VITE_USE_MOCK=false` 时走 `api.post`，代理命中后端。 |
| 4 | qa_result_type 驱动气泡 | PASS | 后端返回类型决定 `system_message.content`；前端展示 system 气泡（直出/反问/生成/降级内容不同）。 |
| 5 | Vite 代理 / CORS | PASS | `vite.config.ts` `/api`→8099；`VITE_API_BASE_URL=/api`；CORS 含 5199/5175。 |

## 外部服务

| 项 | 状态 |
|----|------|
| key_configured | True |
| 真实百炼 Chat/Embedding/Rerank 全路径联调 | 未宣称通过（Mock/fallback + monkeypatch 为主；运行时偶发真实调用结果仅作连通旁证） |

## 测试隔离

- f004 夹具使用独立 `tmp_path` 库，禁止运行时 `drop_all`。
- pytest 后运行时库仍在：accounts/tickets/messages 表可查（验证中新增验收消息，未清库）。

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 运行时直连首问偶发 `degraded`（外部瞬时失败），代理另一次为 `clarification` | 百炼外部服务稳定性 | 不扩大 AC；用户门禁时可观察；Key 额度/模型可用性由运维确认 |
