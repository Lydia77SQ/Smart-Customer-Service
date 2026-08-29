# 测试报告：T-013 F-003 三端工作台切换闭环

**测试时间**：2026-08-29 22:20 (UTC+8)
**Tester Agent ID**：tester-T-013

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F003-01] 用户在员工咨询工作台顶栏依次进入坐席接待、知识维护再返回员工咨询，全程不要求重新登录且顶栏身份不变 | PASS | Playwright（channel=chrome，`VITE_USE_MOCK=false`，前端 5199 / 后端 8099）：登录后 `/employee` → 点顶栏「坐席接待」→「知识维护」→「员工咨询」，URL 分别为 `/agent`、`/knowledge`、`/employee`，全程未进 `/login`；顶栏 `display_name` 四次均为同一账号。切换过程中多次命中 `GET http://127.0.0.1:5199/api/auth/me` 且 HTTP 200。 |
| 2 | [AC-F003-02] 用户退出登录后未带 token 访问任一工作台，被拦回 /login | PASS | 点击顶栏「退出」后 `localStorage.token` 为 null 且进入 `/login`；再分别 `goto /employee`、`/agent`、`/knowledge`，均被拦回 `/login?state=need-login`。与 `router/index.ts` `beforeEach`（无 token → `/login`）一致。 |
| 3 | 三端顶栏布局与 docs/prototypes/employee.html 顶栏一致 | PASS | 静态对照 `AppHeader.vue` + 三页均引用该组件：品牌「智能客服系统」、导航「员工咨询 / 坐席接待 / 知识维护」、右侧 `display_name` +「退出」(height 32px)。E2E 确认三页顶栏文案与 `.nav a.is-active`（坐席页为「坐席接待」）与原型一致；无原型外元素、无 `[Mock]`。 |
| 4 | VITE_USE_MOCK=false 时 /api/auth/me 命中真实后端，页面无 [Mock] 文案 | PASS | 前端以 `VITE_USE_MOCK=false` 启动；浏览器侧 `/api/auth/me` 经 Vite 代理返回契约信封且 `code=200`；直连后端 `GET /api/auth/me` 同结果。员工/坐席/知识页 `body` 均无 `[Mock]`。`authService.fetchMe` 在 `isMockEnabled()===false` 时走 `api.get('/auth/me')`。 |

## technicalChecks

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | Typecheck passes | PASS | `frontend` 下 `npm run type-check` 退出码 0 |
| 2 | Lint passes | PASS | `frontend` 下 `npm run lint` 退出码 0 |
| 3 | VITE_USE_MOCK=false 时三端切换不走 Mock 身份分支 | PASS | `fetchMe`/`logout` 走真实 API；E2E 切换时 me 请求 URL 均为 `127.0.0.1:5199/api/auth/me`（非 Mock handler） |
| 4 | /employee、/agent、/knowledge 均设置 meta.requiresAuth: true | PASS | `frontend/src/router/index.ts` 三路由均 `meta: { requiresAuth: true }` |
| 5 | 样式取值与 docs/prototypes/design-tokens.md 一致 | PASS | `frontend/src/assets/styles.css` `:root` 与取值表一致；E2E 实测 `--color-primary=#2563EB`、`--radius=8px`、`--color-ink=#18181B`、`--color-page=#F4F4F5`、`--color-primary-soft=#EFF6FF`、`--color-muted=#71717A`、`--fs-caption=12px`、`--space-2=16px`；顶栏高度 56px、品牌字号 16px、退出按钮高度 32px，与原型 `styles.css` 顶栏一致 |

## frontendIntegration / mockExitCriteria

| # | 项 | 结果 | 说明 |
|---|----|------|------|
| 1 | 顶栏切换使用 Vue Router 导航，身份展示来自真实 /api/auth/me | PASS | `AppHeader` 使用 `RouterLink`；身份来自 `useAuthStore.user.display_name`，由 `restoreSession` → `fetchMe` 刷新 |
| 2 | 无 token 时 beforeEach 跳转 /login | PASS | 见 AC-F003-02 E2E |
| 3 | Vite 代理 | PASS | `vite.config.ts` 含 `/api` → `VITE_BACKEND_PROXY_TARGET`；`.env` 中 `VITE_API_BASE_URL=/api`（相对路径） |
| 4 | pages /employee /agent /knowledge | PASS | 三页均渲染 `AppHeader` 并可在真实联调路径下切换 |

## 验证证据摘要

- 后端：`uvicorn` `127.0.0.1:8099`（项目 `.venv` python）
- 前端：`npm run dev -- --host 127.0.0.1 --port 5199`，环境变量 `VITE_USE_MOCK=false`
- 测试账号：临时 `POST /api/auth/register` + login（未清空业务库）
- Playwright：`chromium.launch(channel='chrome')`（本机 Chrome；bundled chromium 下载失败故改用 channel）
- 验证后已停止本轮启动的前后端进程

## 代码核对（独立打开）

- `frontend/src/components/AppHeader.vue`：RouterLink 三端导航 + store 身份 + logout
- `frontend/src/router/index.ts`：requiresAuth + beforeEach + restoreSession
- `frontend/src/stores/useAuthStore.ts`：restoreSession → fetchMe；401 清会话
- `frontend/src/pages/{Employee,Agent,Knowledge}Page.vue`：均挂载 AppHeader
- `frontend/src/assets/styles.css`：顶栏与 design-tokens
- `frontend/src/services/authService.ts`：非 Mock 时真实 `/auth/me`、`/auth/logout`
- `.sdd/experience.md`：含 T-013 经验条目（无密钥泄露）
