# F-001 用户登录实施计划

## 1. 追踪信息

- Feature：F-001
- Spec：docs/features/F-001-user-login/spec.md
- Spec 版本：1
- 依赖 Feature：无（账号可由 F-002 或预置产生）
- Data Model：docs/data-model.md（accounts、sessions）
- API：API-F001-01、API-F001-02、API-F001-03；AC-F001-03 无独立接口（纯前端守卫）
- 原型：docs/prototypes/login.html

## 2. 实现策略

- 前端实现路径：frontend/src/pages/LoginPage.vue；stores/auth.ts；services/auth.ts；router 守卫（meta.requiresAuth）
- 后端实现路径：backend/src/api/routes/auth.py；services/auth_service.py；repositories/account_repo.py、session_repo.py；deps.get_current_user
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：校验 accounts.password_hash；写入 sessions.token_hash
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/pages、stores、services、router | 登录表单、会话保持、未登录拦截 | 不改注册校验规则 |
| 后端 | backend/src/api/routes/auth.py | login / logout / me | 不改工单与知识表 |
| 测试 | backend/tests/features/f001；e2e/features | 凭证对错与工作台拦截 | 不调用百炼 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 后端认证与 session | backend | login/logout/me 与 API 单测 | 基础设施 | AC-F001-01/02 |
| 前端登录页与守卫 | frontend | LoginPage、auth store、requiresAuth | 后端认证 | AC-F001-01/02/03 |
| Feature 测试 | test | pytest + Playwright 登录流 | 前后端完成 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F001-01 | auto | API+E2E | backend/tests/features/f001/test_login.py；e2e/features/f001-login.spec.ts | pytest --timeout=120；playwright | required |
| AC-F001-02 | auto | API | backend/tests/features/f001/test_login.py | pytest --timeout=120 | required |
| AC-F001-03 | auto | E2E | e2e/features/f001-login.spec.ts | playwright | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：明文 token 只在响应中出现一次，库内仅存 hash。
- 数据迁移：初始建 sessions。
- 向后兼容：无既有数据。
- 回滚边界：清空 sessions，用户重新登录。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
