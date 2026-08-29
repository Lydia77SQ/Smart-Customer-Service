# F-010 坐席为工单分类实施计划

## 1. 追踪信息

- Feature：F-010
- Spec：docs/features/F-010-ticket-classify/spec.md
- Spec 版本：1
- 依赖 Feature：F-007
- Data Model：docs/data-model.md（tickets.category）
- API：API-F010-01
- 原型：docs/prototypes/agent.html（分类）

## 2. 实现策略

- 前端实现路径：AgentPage 分类选择；closed 禁用
- 后端实现路径：tickets.py category；pending/in_progress 可改；closed CONFLICT
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：更新 tickets.category、updated_at
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | AgentPage 右栏分类 | 写入展示 | 不在员工页改分类 |
| 后端 | PUT category | 枚举校验 | 不改状态机 |
| 测试 | backend/tests/features/f010 | 写入与完结拒绝 | 无外部服务 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 分类 API | backend | PUT category | F-007 | AC-F010-01/02 |
| 分类 UI | frontend | 选择与禁用 | 分类 API | AC-F010-01/02 |
| Feature 测试 | test | pytest | 前后端 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F010-01 | auto | API+E2E | backend/tests/features/f010/test_category.py；e2e/features/f010-category.spec.ts | pytest --timeout=120；playwright | required |
| AC-F010-02 | auto | API | backend/tests/features/f010/test_category.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：无。
- 数据迁移：category 可空。
- 向后兼容：无。
- 回滚边界：将 category 置 NULL。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
