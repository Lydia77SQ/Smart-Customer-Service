# F-005 查看并继续自己的咨询实施计划

## 1. 追踪信息

- Feature：F-005
- Spec：docs/features/F-005-view-continue/spec.md
- Spec 版本：1
- 依赖 Feature：F-004
- Data Model：docs/data-model.md（tickets、messages）
- API：API-F005-01、API-F005-02；续聊发送复用 API-F004-01
- 原型：docs/prototypes/employee.html

## 2. 实现策略

- 前端实现路径：EmployeePage 列表 + 对话只读/续聊；composer 在 closed 禁用
- 后端实现路径：backend/src/api/routes/tickets.py mine / detail；messages 在 closed 返回 CONFLICT
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：只读列表与详情；续聊写 messages（经 F-004）
- 外部服务：无（续聊若仍为 ai_assisting 则触发 F-004 外部链路）
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/pages/EmployeePage.vue | 我的列表、详情、完结只读 | 不展示他人工单 |
| 后端 | tickets.py mine/detail | BR-011 隔离 | 坐席队列不走 mine |
| 测试 | backend/tests/features/f005 | 隔离与完结拒绝 | 不测答疑语义 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 我的列表与详情 API | backend | GET mine / GET detail | F-004 工单存在 | AC-F005-01/03 |
| 员工列表与只读 UI | frontend | 列表、打开、完结禁用发送 | 列表 API | AC-F005-01～03 |
| Feature 测试 | test | pytest 隔离与 CONFLICT | 前后端 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F005-01 | auto | API+E2E | backend/tests/features/f005/test_mine.py；e2e/features/f005-history.spec.ts | pytest --timeout=120；playwright | required |
| AC-F005-02 | auto | API+E2E | backend/tests/features/f005/test_continue.py | pytest --timeout=120 | required |
| AC-F005-03 | auto | API | backend/tests/features/f005/test_closed.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：IDOR（他人工单）。对外 NOT_FOUND。
- 数据迁移：无新表。
- 向后兼容：无。
- 回滚边界：还原查询过滤。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
