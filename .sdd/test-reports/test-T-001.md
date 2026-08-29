# 测试报告：T-001 登录与注册页 Mock（/login）

**测试时间**：2026-08-29 16:30 (UTC+8)
**Tester Agent ID**：tester-T-001-reverify-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F001-01] 用户在登录页输入 Mock 测试账号密码并点击「登录」，页面跳转到员工咨询工作台（/employee） | PASS | `LoginPage.vue` 调 `login()` 成功后 `authStore.setSession` 并 `router.push('/employee')`。Mock 预置 `wang.li` / `pass-word-6`（与 `api-contracts.md` 示例一致）。`tsx` 执行 `mockLogin` 成功返回 `{code:200,message:'ok',data:{token,user}}`。 |
| 2 | [AC-F001-02] 用户在登录页输入错误密码并点击「登录」，页面显示「账号或密码不正确」，不进入工作台 | PASS | Mock 抛 401/`UNAUTHORIZED`/`账号或密码不正确`；`onLoginSubmit` catch 仅设 `alertKind='error'`，不写 session。登录失败走 Mock 直抛，不经 axios 401 全局跳转。文案与原型一致。 |
| 3 | [AC-F001-03] 用户未登录时直接访问 /employee、/agent 或 /knowledge，页面被拦回 /login 并提示「请先登录后再进入工作台」 | PASS | `router/index.ts`：三路由均 `meta.requiresAuth: true`；无 token 时 `next({ path:'/login', query:{ state:'need-login' } })`；`LoginPage` 将 `need-login` 映射为「请先登录后再进入工作台」。 |
| 4 | [AC-F002-01] 用户切换到注册 Tab 提交合法账号密码，页面提示账号已创建，可切回登录 Tab | PASS | 注册成功 `alertKind='ok'`，文案「账号已创建，请使用该凭证登录」；Tab 可切回登录。Mock 校验：新账号可再 `mockLogin` 成功。 |
| 5 | [AC-F002-02] 用户使用已占用账号名注册，页面显示「该账号名已被占用」，不创建新账号 | PASS | Mock 409/`CONFLICT`/`该账号名已被占用`；页面映射 `CONFLICT` → conflict 提示。`tsx` 确认冲突信封与文案正确。 |
| 6 | 页面布局、配色与全部文案与 docs/prototypes/login.html 一致 | PASS | 标题/副标题/Tab/字段/按钮/四类提示文案与原型逐字一致；结构含 `#tab-login`/`#tab-register`/`#form-login`/`#form-register`/`#btn-login`；auth 卡片布局对齐原型（含密码栏与主按钮 `margin-top: 16px`）。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | Typecheck passes | PASS | `npm run type-check`（vue-tsc）退出码 0（本轮独立重跑） |
| 2 | Lint passes | PASS | `npm run lint`（eslint .）退出码 0（本轮独立重跑） |
| 3 | Mock 响应信封与 api-contracts.md 中 API-F001-01、API-F002-01 一致 | PASS | 成功 `{code:200,message:'ok',data}`；登录 data=`token`+`user{id,account,display_name}`；注册 data=`{id,account,display_name}`；失败码/文案与契约表一致。字段均为契约子集，handler 显式构造 DTO，不回传含 password 的内部实体。 |
| 4 | 样式取值与 docs/prototypes/design-tokens.md 逐项一致 | PASS | `styles.css` `:root` 色值/字号/圆角/间距/阴影与取值表一致；登录密码栏与主按钮额外间距 16px（`.auth form .btn { margin-top: 16px }`）已落地。 |
| 5 | 响应式布局在 1440px 与 1280px 下无横向溢出 | PASS | `.card` 为 `width:400px; max-width:100%`，`.auth` 居中 padding；无固定超宽元素。静态 CSS 判定无横向溢出风险。 |

## 环境与命令证据

- 前端开发服：`npm run dev -- --host 127.0.0.1 --port 5199` → `http://127.0.0.1:5199/login` HTTP 200
- `npm run type-check` / `npm run lint` / `npm run build` 均退出码 0
- Mock 行为：`tsx` 加载 `frontend/src/mocks/auth.ts` 验证登录成功/失败、注册成功/冲突、注册后可登录
- Mock 阶段：`VITE_USE_MOCK=true`，未要求真实后端；`authService` 在 Mock 开启时走 `frontend/src/mocks/auth.ts`
- 验证结束后已关闭本 Tester 启动的 Vite 进程（5199 已停）

## 规范对照摘要

- rules_files（specification/default/... 与 docs/...）均存在，未静默降级
- Mock 数据集中于 `frontend/src/mocks/`；`VITE_API_BASE_URL=/api`；`vite.config.ts` 含 `/api` 与 `/ws` 代理
- 未发现可读产物中的真实密钥泄露

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `/employee`、`/agent`、`/knowledge` 仅为占位页 | T-002 及后续工作台任务 | 按任务依赖继续开发；守卫拦截已满足本任务 AC |
