# F-007 坐席接入待处理工单实施计划

## 1. 追踪信息

- Feature：F-007
- Spec：docs/features/F-007-agent-accept/spec.md
- Spec 版本：1
- 依赖 Feature：F-001、F-006
- Data Model：docs/data-model.md（tickets、messages、accounts）
- API：API-F007-01、API-F007-02、API-F005-02；接入后停自动答复由 API-F004-01 覆盖 AC-F007-02
- 原型：docs/prototypes/agent.html

## 2. 实现策略

- 前端实现路径：AgentPage 待处理/处理中列表；接入按钮；对话区加载详情
- 后端实现路径：tickets.py agent-queue / accept；accept 仅 pending→in_progress
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：更新 tickets.status
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/pages/AgentPage.vue | 队列与接入 | 列表不得出现 ai_assisting |
| 后端 | tickets.py queue/accept | 状态机 | 不在接入时自动发言 |
| 测试 | backend/tests/features/f007 | 接入与拒绝 | 不测建议内容 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 坐席队列与接入 API | backend | GET agent-queue、POST accept | F-006 | AC-F007-01/03 |
| 坐席工作台列表 UI | frontend | 待处理/处理中与接入 | 队列 API | AC-F007-01 |
| Feature 测试 | test | pytest 状态；员工续聊无 system 答复 | 前后端 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F007-01 | auto | API+E2E | backend/tests/features/f007/test_accept.py；e2e/features/f007-accept.spec.ts | pytest --timeout=120；playwright | required |
| AC-F007-02 | auto | API | backend/tests/features/f007/test_no_auto_reply.py | pytest --timeout=120 | required |
| AC-F007-03 | auto | API | backend/tests/features/f007/test_accept.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：无坐席认领锁（MVP 接受同一账号多端）。
- 数据迁移：无。
- 向后兼容：无。
- 回滚边界：in_progress 不自动退回 pending。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
