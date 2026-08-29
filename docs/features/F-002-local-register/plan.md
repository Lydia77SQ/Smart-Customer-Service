# F-002 本地账号注册实施计划

## 1. 追踪信息

- Feature：F-002
- Spec：docs/features/F-002-local-register/spec.md
- Spec 版本：1
- 依赖 Feature：无
- Data Model：docs/data-model.md（accounts）
- API：API-F002-01
- 原型：docs/prototypes/login.html（注册 Tab）

## 2. 实现策略

- 前端实现路径：LoginPage 注册 Tab；services/auth.ts register
- 后端实现路径：backend/src/api/routes/auth.py register；bcrypt 哈希
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：插入 accounts
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/pages/LoginPage.vue | 注册表单与冲突提示 | 不自动登录（Spec 未要求） |
| 后端 | backend/src/api/routes/auth.py | 创建账号 | 不签发 session |
| 测试 | backend/tests/features/f002 | 成功与 CONFLICT | 不写工单 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 后端注册 | backend | API 与单测 | 基础设施 | AC-F002-01/02 |
| 前端注册 Tab | frontend | 表单与错误文案 | 后端注册 | AC-F002-01/02 |
| Feature 测试 | test | pytest 冲突用例 | 后端完成 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F002-01 | auto | API | backend/tests/features/f002/test_register.py | pytest --timeout=120 | required |
| AC-F002-02 | auto | API | backend/tests/features/f002/test_register.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：账号枚举（冲突文案已产品确认）。
- 数据迁移：初始建 accounts。
- 向后兼容：无。
- 回滚边界：删除测试账号行。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
