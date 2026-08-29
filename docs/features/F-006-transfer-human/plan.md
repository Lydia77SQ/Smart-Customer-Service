# F-006 员工转人工实施计划

## 1. 追踪信息

- Feature：F-006
- Spec：docs/features/F-006-transfer-human/spec.md
- Spec 版本：1
- 依赖 Feature：F-004
- Data Model：docs/data-model.md（tickets、messages）
- API：API-F006-01；坐席不可见由 API-F007-01 覆盖 AC-F006-02
- 原型：docs/prototypes/employee.html（转人工）

## 2. 实现策略

- 前端实现路径：EmployeePage 转人工按钮；pending 后展示等待对接人文案
- 后端实现路径：tickets.py transfer；写系统消息 TRANSFER_SUCCESS_MESSAGE；status ai_assisting→pending
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：更新 tickets.status；追加 messages（system）
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | EmployeePage composer 转人工 | 状态与提示 | 不把按钮接到坐席页 |
| 后端 | tickets.py transfer | 状态机与系统消息 | 不自动接入坐席 |
| 测试 | backend/tests/features/f006 | 状态、队列过滤、完结拒绝 | 不测大模型 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 转人工 API | backend | POST transfer 与系统消息 | F-004 | AC-F006-01/03 |
| 员工转人工 UI | frontend | 按钮与等待文案 | 转人工 API | AC-F006-01 |
| Feature 测试 | test | pytest 状态与队列过滤（配合 F-007 队列） | 后端 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F006-01 | auto | API+E2E | backend/tests/features/f006/test_transfer.py；e2e/features/f006-transfer.spec.ts | pytest --timeout=120；playwright | required |
| AC-F006-02 | auto | API | backend/tests/features/f006/test_queue_hidden.py | pytest --timeout=120 | required |
| AC-F006-03 | auto | API | backend/tests/features/f006/test_transfer.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：夜间无坐席，工单停 pending（产品允许）。
- 数据迁移：无。
- 向后兼容：无。
- 回滚边界：状态可人工改回（仅运维，产品无入口）。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
