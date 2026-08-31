# 测试报告：T-022 F-010 工单分类闭环

**测试时间**：2026-08-30 23:32 (UTC+8)
**Tester Agent ID**：tester-T-022-20260830

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F010-01] 坐席在处理中工单选择业务分类，右栏与列表展示该分类标签 | PASS | 后端 `update_category` 写入 `tickets.category` 且不改状态。前端右栏 `tag tag-cat` + 左侧选中列表项展示 `selected.category`。pytest `test_in_progress_category_shown_on_detail_and_mine_list` 通过。真实联调：PUT category→200，`GET /mine` 与详情均返回所选分类（如 `IT-网络`→`行政-场地`）。 |
| 2 | [AC-F010-02] 坐席在已完结工单尝试更改分类，操作被拒绝，分类保持不变 | PASS | 服务层非 `pending`/`in_progress` 抛 `TicketConflictError("已完结不能改分类")`→409 CONFLICT。pytest `test_closed_ticket_category_rejected_unchanged` 通过。真实联调对既有 closed ticket#12：PUT→409，body=`{"code":"CONFLICT","message":"已完结不能改分类","data":null}`，详情 category 仍为 null。前端 `canClassify` 排除 closed，select `:disabled="!canClassify"`。 |
| 3 | 分类控件与 docs/prototypes/agent.html 右栏一致 | PASS | 右栏结构：label「分类」+ `.select`，选项 `IT-网络` / `IT-账号` / `行政-工牌` / `行政-场地` 与原型一致。AC 要求的分类标签用 `.tag.tag-cat` 展示（原型 HTML 未画标签，但 AC/列表展示要求覆盖）。closed 态禁用与原型 `state=closed` 行为一致。 |
| 4 | VITE_USE_MOCK=false 时分类请求命中真实后端 API，页面无 [Mock] 文案 | PASS | `ticketService.updateTicketCategory` 在 `isMockEnabled()===false` 时 `api.put('/tickets/{id}/category')`。前端 `VITE_USE_MOCK=false` 启于 5199，经代理 PUT 200。`/agent` HTML 无 `[Mock]`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | python -m pytest backend/tests/features/f010 --timeout=120 | PASS | 项目 `.venv`：`10 passed`（约 8.6s） |
| 2 | Typecheck passes | PASS | 后端 mypy（ticket 模型/服务/路由 + f010 tests）：Success；前端 `npm run type-check` 退出码 0 |
| 3 | Lint passes | PASS | `ruff check` 目标后端文件 + f010：All checks passed；前端 `npm run lint` 退出码 0 |
| 4 | VITE_USE_MOCK=false 时 category 更新不走 Mock 分支 | PASS | `updateTicketCategory` 仅 mock 开启时调 `mockUpdateCategory`；5199 代理实测走真实后端 |
| 5 | 样式取值与 docs/prototypes/design-tokens.md 一致 | PASS | `styles.css` `:root` 色值/字体/字号/圆角/间距与 design-tokens 一致；`.tag-cat` 使用 `--color-primary-soft` / `--color-primary`；`.select` 圆角 `--radius: 8px` |

## frontendIntegration

| 项 | 结果 | 说明 |
|---|------|------|
| pages `/agent` | PASS | 5199 返回页面；分类控件与标签在右栏/选中列表项 |
| services `frontend/src/services/ticketService.ts`（仓库实际文件名，非 tasks 中的 tickets.ts） | PASS | `updateTicketCategory` 真实路径 PUT `/tickets/{id}/category` |
| realApiEndpoints PUT category | PASS | 8099 直连与 5199 代理均 200（处理中）/ 409（已完结） |
| mockExitCriteria updateCategory→真实 API | PASS | 实现名为 `updateTicketCategory`；Mock 关闭时走真实 API |
| mockExitCriteria closed 分类控件 Disabled | PASS | `canClassify = selected && !isClosed && !classifying`；select `:disabled="!canClassify"`；store 对 closed 前置拦截 |

## 环境与命令证据

- 后端：`$env:PYTHONPATH=<project_root>` + `.venv` uvicorn `127.0.0.1:8099` 启动成功；`GET /health` 200
- 前端：`VITE_USE_MOCK=false` vite `127.0.0.1:5199`，`VITE_API_BASE_URL=/api`，proxy → `8099`
- CORS：允许 `http://localhost:5199` 等 tech-spec 四源
- 测试隔离：f010 用 `tmp_path` + `dependency_overrides[get_db]` + `trust_env=False`；无 `drop_all`；运行时库 `tickets`/`messages` 表仍在
- 结单 API（T-023）本轮未实现（POST close→404），AC-F010-02 用既有 closed 工单 + pytest 隔离库覆盖，未对运行时库做 SQL 强制改状态
- 未安装 Playwright / 未占用用户门禁端口 5175/8003
- 验证后已停止本轮 8099/5199 进程
- 报告未打印任何密钥；产出文件抽检无密钥泄露

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | POST `/api/tickets/{id}/close` 尚未实现（404） | F-011 / T-023 | 由 T-023 实现与验收 |
| 2 | 运行时库留有本轮联调产生的账号与分类工单 | 测试数据 | 不影响 AC；无需清库 |
| 3 | tasks.json `frontendIntegration.services` 写的是 `tickets.ts`，仓库实际为 `ticketService.ts` | 任务元数据 | 后续 Planner 校正路径即可 |
