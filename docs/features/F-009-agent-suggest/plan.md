# F-009 坐席获取智能回答建议实施计划

## 1. 追踪信息

- Feature：F-009
- Spec：docs/features/F-009-agent-suggest/spec.md
- Spec 版本：1
- 依赖 Feature：F-007
- Data Model：docs/data-model.md（suggestions、tickets、messages）
- API：API-F009-01、API-F005-02（证明不入员工消息）
- 原型：docs/prototypes/agent.html（智能回答）

## 2. 实现策略

- 前端实现路径：AgentPage 右栏请求建议、展示 SuggestionOut；选用后走 F-008 发送
- 后端实现路径：tickets.py suggestions；复用 qa_pipeline；结果只写 suggestions
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：插入 suggestions；不写 messages
- 外部服务：百炼 Chat / Embedding / Rerank
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | AgentPage 建议区 | 展示与选用 | 员工页零绑定 suggestions |
| 后端 | qa_pipeline + suggestions 表 | 仅坐席可见 | 失败不写员工 system 消息 |
| 测试 | backend/tests/features/f009 | 不泄漏、降级 | 语义质量标 agent/external |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 建议 API | backend | POST suggestions | F-007 + qa_pipeline | AC-F009-01～03 |
| 坐席建议 UI | frontend | 请求、展示、不自动发送 | 建议 API | AC-F009-01/02 |
| Feature 测试 | test | pytest 隔离；agent/external | 前后端 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）
- 另加 specification/default/backend/plugin.md 中与外部 HTTP 不冲突的部分；实际调用以 shared/security.md 的 httpx 直调为准（`trust_env=false`，禁止 dashscope SDK）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F009-01 | agent | API+E2E | backend/tests/features/f009/test_suggest.py；e2e/features/f009-suggest.spec.ts | pytest --timeout=300；playwright | agent 证据，不可标纯 auto 通过 |
| AC-F009-02 | auto | API | backend/tests/features/f009/test_no_message.py | pytest --timeout=120 | required |
| AC-F009-03 | external | API | backend/tests/features/f009/test_degraded.py | pytest --timeout=300（假 Key） | external；缺 Key 不得宣称完整通过 |

## 7. 外部服务与测试权限

| 服务 | 配置字段 | Tester 权限 | 缺失时策略 | 可否宣称完整通过 |
|---|---|---|---|---|
| 百炼 Chat | DASHSCOPE_API_KEY、LLM_BASE_URL、LLM_MODEL、LLM_TIMEOUT_SECONDS、LLM_TEMPERATURE_* | 可调用 qwen-max | 降级文案 + 允许转人工 | 否 |
| 百炼 Embedding | DASHSCOPE_API_KEY、EMBEDDING_* | 可向量化 | 降级 | 否 |
| 百炼 Rerank | DASHSCOPE_API_KEY、RERANK_* | 可重排 | 降级 | 否 |

## 8. 风险、迁移与回滚

- 风险：失败路径误写 messages。必须走 DEGRADED_SUGGESTION_MESSAGE。
- 数据迁移：初始建 suggestions。
- 向后兼容：无。
- 回滚边界：停用建议按钮即可。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
