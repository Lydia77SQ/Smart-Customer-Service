# 测试报告：T-011 F-002 本地账号注册闭环

**测试时间**：2026-08-29 21:25
**Tester Agent ID**：tester（重新验证；上一轮未写出本报告）

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F002-01] 用户在登录页注册 Tab 提交未被占用的账号密码，页面提示注册成功，之后可用该账号登录 | PASS | Playwright（msedge）在 `VITE_USE_MOCK=false`、前端 5199 / 后端 8099 下：注册 Tab 提交新账号后出现「账号已创建，请使用该凭证登录」；业务库 `accounts` 写入 bcrypt 哈希（`$2b$…`）、明文不落库、`profile_json={}`。登录接口属 T-012，本轮按字面验到「账号已入库 + 成功提示」。 |
| 2 | [AC-F002-02] 用户使用已被占用的账号名注册，页面显示「该账号名已被占用」 | PASS | 同账号再次提交；页面 `.alert-error` 文案为「该账号名已被占用」；响应 HTTP 409、信封 `code=CONFLICT`、`message` 与 api-contracts 一致；原账号行未改写。 |
| 3 | 页面布局、配色与 docs/prototypes/login.html 注册视图一致 | PASS | 文案对齐原型：`智能客服系统`、`内部 IT / 行政支持`、Tab「登录/注册」、字段「账号/密码」、placeholder「请输入账号/请输入密码」、按钮「创建账号」、成功/冲突提示与原型一致。计算样式：`--color-page` rgb(244,244,245)、`--color-surface` 白、主按钮 rgb(37,99,235)、圆角 8px，对齐 design-tokens。 |
| 4 | VITE_USE_MOCK=false 时注册请求命中真实后端 POST /api/auth/register，页面无 [Mock] 文案 | PASS | `authService.register` 无 Mock 分支，直接 `api.post('/auth/register')`。浏览器请求 URL 为 `http://127.0.0.1:5199/api/auth/register`（Vite 代理至 8099）；页面无 `[Mock]`。 |

## 技术检查

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | pytest backend/tests/features/f002 --timeout=120 | PASS | 9 passed |
| 2 | Typecheck passes | PASS | `npm run type-check` 通过；ruff/mypy 抽检 T-011 相关后端文件通过 |
| 3 | Lint passes | PASS | `npm run lint` 通过；`ruff check` 抽检通过 |
| 4 | VITE_USE_MOCK=false 不走 mocks 注册 | PASS | `register()` 始终打真实 API，不调用 `frontend/src/mocks/*` |
| 5 | 浏览器证明命中 /api/auth/register | PASS | Playwright 捕获 2 次 POST `/api/auth/register`（200 成功 + 409 冲突） |
| 6 | 测试库隔离 / 业务库完好 | PASS | f002 测试用 tmp 库 + `dependency_overrides`；无对运行时 engine `drop_all`。pytest 与联调后 `service_robot.db` 核心表仍在 |
| 7 | CORS / 代理 | PASS | CORS 允许 `http://127.0.0.1:5199`；`VITE_API_BASE_URL=/api` 相对路径；vite `proxy['/api']` → 8099 |
| 8 | 密钥泄露 | PASS | 除 `backend/.env` 外，Developer 产出与 `.sdd/experience.md` 未见真实 Key/Token |

## 真实联调证据摘要

- 后端：`PYTHONPATH=<项目根>` + `python -m uvicorn src.main:app --host 127.0.0.1 --port 8099`
- 前端：`VITE_USE_MOCK=false` + `npm run dev -- --host 127.0.0.1 --port 5199`
- Playwright channel=`msedge`（cdn.playwright.dev 不可达，改用本机 Edge）
- 成功响应：`code=200, message=ok, data={id,account,display_name}`
- 冲突响应：`code=CONFLICT, message=该账号名已被占用, data=null`
- 验证后已关闭 8099/5199 短时进程

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `frontendIntegration.services` 写的是 `auth.ts`，实现文件为 `authService.ts` | 任务元数据 | Planner 后续可修正路径；实现可用，不判 FAIL |
| 2 | T-012 登录/登出/me 尚未实现，无法在本任务完成「真实登录会话」联调 | T-012 | 由 T-012 验收；本任务已确认账号可登录所需持久化 |
