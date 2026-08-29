# 测试报告：T-012 F-001 用户登录闭环

**测试时间**：2026-08-29 22:10
**Tester Agent ID**：tester-t012-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F001-01] 用户在登录页输入正确账号密码并登录，进入员工咨询工作台且顶栏显示当前用户身份；刷新页面后仍保持登录 | PASS | Playwright（系统 Chrome）在 `VITE_USE_MOCK=false`、前端 5199、后端 8099：先注册测试账号，登录后跳转 `/employee`，顶栏展示 `display_name`；`reload` 后仍停留 `/employee` 且身份仍在。 |
| 2 | [AC-F001-02] 用户输入错误密码，页面显示「账号或密码不正确」，不进入工作台 | PASS | 同环境浏览器：错误密码后 URL 仍为 `/login`，页面出现「账号或密码不正确」；网络见 `POST /api/auth/login` → 401。 |
| 3 | [AC-F001-03] 用户未登录直接访问 /employee、/agent 或 /knowledge，被跳转 /login 并提示请先登录 | PASS | 无 token 访问三路径均落 ` /login?state=need-login`，文案「请先登录后再进入工作台」（对齐原型）。 |
| 4 | VITE_USE_MOCK=false 时登录请求命中真实后端 API，页面无 [Mock] 文案 | PASS | 浏览器 Network：`POST http://127.0.0.1:5199/api/auth/login`、`GET .../api/auth/me` 真实命中；登录页/工作台 HTML 无 `[Mock]`。 |
| 5 | python -m pytest backend/tests/features/f001 --timeout=120 通过 | PASS | 项目 `.venv`：`15 passed`（带 `--timeout=120`）。测试使用独立 tmp DB + `dependency_overrides[get_db]`，未 drop 运行时库。 |
| 6 | Typecheck passes | PASS | 后端抽检相关模块 `mypy` Success；前端 `npm run type-check`（vue-tsc）通过。 |
| 7 | Lint passes | PASS | 后端相关文件 `ruff check` All checks passed；前端 `npm run lint` 通过。 |
| 8 | VITE_USE_MOCK=false 时 auth 服务不走 Mock 分支 | PASS | 静态：`authService.ts` 在 `isMockEnabled()` 为 false 时走 `api.post/get`；运行时以 `VITE_USE_MOCK=false` 启动 Vite，login/me/logout 均打到 `/api/auth/*`。 |
| 9 | 浏览器证明 login/me 命中 /api/auth/* 真实端点 | PASS | Playwright 捕获：`POST /api/auth/login` 401/200、`GET /api/auth/me` 200（经 Vite 代理至 8099）。另验证 `POST /api/auth/logout` 200，之后 me → 401。 |

## 前端集成 / Mock 退出

| 检查项 | 结果 | 说明 |
|---|---|---|
| vite `server.proxy['/api']` | PASS | `frontend/vite.config.ts` 代理到 `VITE_BACKEND_PROXY_TARGET`（默认 8099） |
| `VITE_API_BASE_URL` 相对路径 | PASS | `/api` |
| CORS 四 origin | PASS | `backend/src/core/config.py` 含 5199/5175 localhost 与 127.0.0.1 |
| router.beforeEach + 真实 me | PASS | `frontend/src/router/index.ts`：`requiresAuth` 无 token → need-login；有 token → `restoreSession()` → `fetchMe()` |
| 高保真原型文案（login.html #form-login） | PASS | 「智能客服系统」「内部 IT / 行政支持」「登录/注册」「账号」「密码」「登录」「账号或密码不正确」「请先登录后再进入工作台」一致 |
| design-tokens | PASS | `frontend/src/assets/styles.css` `:root` 色值/字体/圆角/间距与 `docs/prototypes/design-tokens.md` 一致 |

## 代码存在性抽检

已独立打开并核对：`security.py`、`session` repo、`models/auth.py`、`services/auth.py`、`deps.py`、`routes/auth.py`、`test_login.py`、`useAuthStore.ts`、`router/index.ts`、`api.ts`、`authService.ts`、`LoginPage.vue`、`AppHeader.vue`、`.sdd/experience.md`（无密钥泄露）。

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `frontend/.env` 默认仍为 `VITE_USE_MOCK=true`；本轮验收以启动环境变量覆盖为 `false` | frontend env | 用户门禁验收时显式 `VITE_USE_MOCK=false` 并重启 Vite |
| 2 | 运行时库无契约示例账号 `wang.li`（仅有历史联调注册账号）；可通过注册后再登录完成 AC | seed / F-002 | 可选：门禁前预置 `wang.li` 或沿用注册路径 |
