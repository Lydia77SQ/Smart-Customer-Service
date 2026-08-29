# F-003 三端工作台切换实施计划

## 1. 追踪信息

- Feature：F-003
- Spec：docs/features/F-003-workbench-switch/spec.md
- Spec 版本：1
- 依赖 Feature：F-001
- Data Model：docs/data-model.md（accounts、sessions）
- API：API-F001-03；AC-F003-02 无（纯前端）
- 原型：docs/prototypes/employee.html（顶栏）；agent.html、knowledge.html 同源顶栏

## 2. 实现策略

- 前端实现路径：AppHeader.vue；router：/employee /agent /knowledge，meta.requiresAuth
- 后端实现路径：无新路由；复用 GET /api/auth/me
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：无新表
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/components/AppHeader.vue、router | 三端切换与未登录跳转 | 不引入角色隐藏（BR-014） |
| 后端 | 无新增 | 身份仍走 me | 不改工单状态机 |
| 测试 | e2e/features/f003 | 切换保持登录 | 不测答疑内容 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 前端顶栏与路由 | frontend | 三工作台入口与守卫 | F-001 | AC-F003-01/02 |
| Feature 测试 | test | Playwright 切换；Agent 判断身份不变 | 前端完成 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F003-01 | agent | E2E | e2e/features/f003-switch.spec.ts | playwright（Agent 判断身份不变、无需重登） | agent 证据，不可标纯 auto 通过 |
| AC-F003-02 | auto | E2E | e2e/features/f003-switch.spec.ts | playwright | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：无。
- 数据迁移：无。
- 向后兼容：无。
- 回滚边界：还原路由与顶栏。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
