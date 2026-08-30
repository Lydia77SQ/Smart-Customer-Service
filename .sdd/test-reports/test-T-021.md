# 测试报告：T-021 F-009 坐席智能建议闭环

**测试时间**：2026-08-30 11:45 (UTC+8)
**Tester Agent ID**：tester-T-021-20260830

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F009-01] 坐席在处理中工单点击「获取建议」，右栏出现建议文本，中栏员工消息流不出现该文本 | PASS | 后端 `create_suggestion` 仅写 `suggestions` 表；详情只读 `messages`。前端 `AgentPage` 右栏 `class="suggest"` 渲染，`thread` 仅 `v-for="message in selected.messages"`。pytest `test_in_progress_suggestion_visible_only_in_payload` 通过。真实联调 ticket#10：POST suggestions 200（`result_type=clarification`），员工 GET 详情 messages 不含建议且条数不变。 |
| 2 | [AC-F009-02] 坐席不点击发送，工单消息列表不增加建议内容 | PASS | 建议路径不调用 `MessageRepository.add`；`onFill` 只写 `draft`，不调用 `send`。pytest `test_suggestion_does_not_add_message_row` 通过。真实库：suggestions 有新行，`suggestion_in_messages=0`，messages 计数不变。 |
| 3 | [AC-F009-03] 外部能力不可用时，右栏显示失败说明，员工侧无新的系统消息 | PASS | 降级时 `content=settings.degraded_suggestion_message` 且 `result_type=degraded`；前端 `suggestionFailed` 时右栏 `hint` 展示。pytest `test_external_unavailable_returns_degraded_suggestion` 通过（monkeypatch Embedding 失败）。员工 messages 无降级文案、无新系统消息。 |
| 4 | 右栏建议区布局与 docs/prototypes/agent.html 一致 | PASS | 文案「智能回答 / 获取建议 / 填入输入框」与失败 hint 文案对齐原型；结构为 label→secondary 按钮→`.suggest` / `.hint`→填入→结单。`.suggest` CSS 与原型 `styles.css` 一致（`primary-soft` / `radius` / `12px` / `fs-caption` / `1.55`），取值符合 `design-tokens.md`。 |
| 5 | VITE_USE_MOCK=false 时建议请求命中真实后端 API，页面无 [Mock] 文案 | PASS | `createSuggestion` 在 `isMockEnabled()===false` 时 `POST /tickets/{id}/suggestions`。前端以 `VITE_USE_MOCK=false` 启于 5199；经代理 POST 200。`/agent`、`/employee` HTML 无 `[Mock]`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m pytest backend/tests/features/f009 --timeout=300 | PASS | 项目 `.venv`：`11 passed, 1 skipped`（约 9.6s）；跳过项为 `REAL_API_TEST` 门控的真实 Chat 用例 |
| 2 | Typecheck passes | PASS | 后端 mypy（目标 4 文件，`--follow-imports=silent`）：Success；前端 `npm run type-check` 退出码 0 |
| 3 | Lint passes | PASS | `ruff check` 目标后端文件 + f009 tests：All checks passed；前端 eslint 抽检 AgentPage/store/ticketService 退出码 0 |
| 4 | VITE_USE_MOCK=false 时 suggestions 不走 Mock 分支 | PASS | `ticketService.createSuggestion` 仅 mock 开启时调 `mockCreateSuggestion`；5199 代理实测走真实后端 |
| 5 | DASHSCOPE_API_KEY / 外部服务 | PASS（有边界） | `key_configured=true`（来自 `.env` 非空配置检测，未打印密钥）。真实 POST 返回 `clarification`，说明管线可跑通部分路径；**未宣称** Chat/Embedding/Rerank 全路径完整联调通过。降级由 pytest monkeypatch 覆盖。 |
| 6 | 降级路径返回 DEGRADED_SUGGESTION_MESSAGE | PASS | pytest 断言 content 等于配置项且为「暂时无法生成建议。请手写回复，不要向员工发送自动消息。」，且 ≠ QA 降级文案 |
| 7 | 建议不写入 messages 表 | PASS | 服务层只 `suggestions.add`；pytest + 真实库核对通过 |

## frontendIntegration

| 项 | 结果 | 说明 |
|---|------|------|
| pages `/agent` `/employee` | PASS | 5199 返回页面；建议仅右栏；员工详情不泄漏 |
| services `ticketService.ts` / `useAgentStore.ts` | PASS | `createSuggestion` 真实路径；store `fetchSuggestion` 写入 `suggestion`/`suggestionFailed`，不改 `detail.messages` |
| realApiEndpoints POST suggestions | PASS | 8099 直连与 5199 代理均 200 |
| mockExitCriteria fetchSuggestion→真实 API | PASS | Mock 关闭且代理命中后端 |
| mockExitCriteria 建议仅右栏、可填入不自动发送 | PASS | `onFill` 只填 draft；无自动 `send` |

## 环境与命令证据

- 后端：`$env:PYTHONPATH=<project_root>` + `.venv` uvicorn `127.0.0.1:8099` 启动成功
- 前端：`VITE_USE_MOCK=false` vite `127.0.0.1:5199`，`VITE_API_BASE_URL=/api`，proxy → `8099`
- CORS：允许 `http://localhost:5199`
- 测试隔离：f009 用 `tmp_path` + `dependency_overrides[get_db]` + `trust_env=False`；运行时库表仍在（未 drop_all）
- 未安装 Playwright / 未下载浏览器
- 验证后已停止本轮启动的前后端进程
- 报告未打印任何密钥或 `sk-` 片段；`experience.md` 无密钥泄露

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | 分类 / 结单完整交互属 T-022 / T-023 | F-010 / F-011 | 后续任务验证 |
| 2 | 运行时库留有本轮联调 suggestions 行 | 测试数据 | 不影响 AC；无需清库 |
