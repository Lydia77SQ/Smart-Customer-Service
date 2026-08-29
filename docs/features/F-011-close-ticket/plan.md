# F-011 坐席结单实施计划

## 1. 追踪信息

- Feature：F-011
- Spec：docs/features/F-011-close-ticket/spec.md
- Spec 版本：1
- 依赖 Feature：F-007
- Data Model：docs/data-model.md（tickets）
- API：API-F011-01、API-F004-01、API-F008-01；AC-F011-02 无重开接口
- 原型：docs/prototypes/agent.html（结单 / 已完结）

## 2. 实现策略

- 前端实现路径：AgentPage 结单；双方 composer 禁用；无重开按钮
- 后端实现路径：tickets.py close；仅 in_progress→closed；pending CONFLICT；幂等 closed
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：更新 tickets.status=closed
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | AgentPage / EmployeePage | 结单与只读 | 不提供重开入口 |
| 后端 | POST close；发消息接口拒绝 closed | 状态机终态 | 不实现 reopen |
| 测试 | backend/tests/features/f011 | 双方拒发、待处理拒结、无 reopen | 无外部服务 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 结单 API | backend | POST close | F-007 | AC-F011-01/03 |
| 结单 UI | frontend | 结单与只读 | 结单 API | AC-F011-01 |
| Feature 测试 | test | pytest 终态；断言无 reopen 路由 | 前后端 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F011-01 | auto | API+E2E | backend/tests/features/f011/test_close.py；e2e/features/f011-close.spec.ts | pytest --timeout=120；playwright | required |
| AC-F011-02 | auto | API | backend/tests/features/f011/test_no_reopen.py | pytest --timeout=120（无 reopen 路由 + 状态不变） | required |
| AC-F011-03 | auto | API | backend/tests/features/f011/test_close.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：误结单（MVP 不分权，产品接受）。
- 数据迁移：无。
- 向后兼容：无 reopen（V2 F-016）。
- 回滚边界：产品无重开；运维改库不在 MVP。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
