# F-008 坐席向员工发送回复实施计划

## 1. 追踪信息

- Feature：F-008
- Spec：docs/features/F-008-agent-reply/spec.md
- Spec 版本：1
- 依赖 Feature：F-007
- Data Model：docs/data-model.md（tickets、messages；AC-F008-03 读 suggestions）
- API：API-F008-01、API-F005-02；AC-F008-03 另读 API-F009-01 结果不入 messages
- 原型：docs/prototypes/agent.html（处理中）

## 2. 实现策略

- 前端实现路径：AgentPage composer 发送；员工页刷新可见 agent 消息
- 后端实现路径：tickets.py agent-replies；仅 in_progress；closed CONFLICT
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：追加 messages.sender_type=agent
- 外部服务：无
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | AgentPage / EmployeePage 对话 | 发出后两侧可见 | 不得把 suggestions.content 当 messages |
| 后端 | tickets.py agent-replies | 写入 agent 消息 | 不改 suggestions 表为员工可见 |
| 测试 | backend/tests/features/f008 | 同步、完结拒绝、建议不泄漏 | 不测大模型生成 |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 坐席回复 API | backend | POST agent-replies | F-007 | AC-F008-01/02 |
| 坐席发送 UI | frontend | composer 发送与禁用完结 | 回复 API | AC-F008-01/02 |
| Feature 测试 | test | pytest 消息可见性 | 前后端；建议泄漏依赖 F-009 夹具 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F008-01 | auto | API+E2E | backend/tests/features/f008/test_reply.py；e2e/features/f008-reply.spec.ts | pytest --timeout=120；playwright | required |
| AC-F008-02 | auto | API | backend/tests/features/f008/test_reply.py | pytest --timeout=120 | required |
| AC-F008-03 | auto | API | backend/tests/features/f008/test_no_leak.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

无外部服务。

## 8. 风险、迁移与回滚

- 风险：建议误入 messages。详情接口不得返回 suggestions 给员工。
- 数据迁移：无。
- 向后兼容：无。
- 回滚边界：消息不可删（产品规则），只能结单。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
