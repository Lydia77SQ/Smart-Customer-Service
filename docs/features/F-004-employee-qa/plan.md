# F-004 员工提问并获得系统答复实施计划

## 1. 追踪信息

- Feature：F-004
- Spec：docs/features/F-004-employee-qa/spec.md
- Spec 版本：1
- 依赖 Feature：F-001（知识可空；F-012/F-013 虚线依赖）
- Data Model：docs/data-model.md（tickets、messages、accounts、qa_pairs、knowledge_chunks、knowledge_documents）
- API：API-F004-01
- 原型：docs/prototypes/employee.html

## 2. 实现策略

- 前端实现路径：EmployeePage 对话发送；stores/ticket.ts；services/tickets.ts
- 后端实现路径：backend/src/api/routes/tickets.py；services/qa_pipeline.py、ticket_service.py；画像更新 accounts.profile_json
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：创建/更新 tickets、messages；更新 accounts.profile_json
- 外部服务：百炼 Chat / Embedding / Rerank
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/pages/EmployeePage.vue、services/tickets.ts | 发送与气泡 | 不把 suggestions 接到员工页 |
| 后端 | backend/src/services/qa_pipeline.py、ticket_service.py | 建单与答疑链路 | in_progress/pending 不得自动对外发言 |
| 测试 | backend/tests/features/f004 | 状态机与降级 | 语义质量不得标纯 auto |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 答疑链路服务 | backend | QA pipeline + config 键 | 知识表可空 | AC-F004-01～05 |
| 发消息 API | backend | POST /api/tickets/messages | 答疑链路 | AC-F004-01～05 |
| 员工对话 UI | frontend | 发送与结果展示 | 发消息 API | AC-F004-01 |
| Feature 测试 | test | pytest 状态；agent/external 语义 | 前后端 | 全部 |

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
| AC-F004-01 | agent | API+E2E | backend/tests/features/f004/test_ask.py；e2e/features/f004-ask.spec.ts | pytest --timeout=300；playwright | agent 证据，不可标纯 auto 通过 |
| AC-F004-02 | agent | API | backend/tests/features/f004/test_direct_qa.py | pytest --timeout=300（可夹具向量） | agent |
| AC-F004-03 | agent | API | backend/tests/features/f004/test_clarify.py | pytest --timeout=300 | agent |
| AC-F004-04 | agent | API | backend/tests/features/f004/test_disabled_kb.py | pytest --timeout=300 | agent |
| AC-F004-05 | external | API | backend/tests/features/f004/test_degraded.py | pytest --timeout=300（断网或假 Key） | external；缺 Key 不得宣称完整通过 |

## 7. 外部服务与测试权限

| 服务 | 配置字段 | Tester 权限 | 缺失时策略 | 可否宣称完整通过 |
|---|---|---|---|---|
| 百炼 Chat | DASHSCOPE_API_KEY、LLM_BASE_URL、LLM_MODEL、LLM_TIMEOUT_SECONDS、LLM_TEMPERATURE_* | 可调用 qwen-max | 降级文案 + 允许转人工 | 否 |
| 百炼 Embedding | DASHSCOPE_API_KEY、EMBEDDING_* | 可向量化 | 降级 | 否 |
| 百炼 Rerank | DASHSCOPE_API_KEY、RERANK_* | 可重排 | 降级 | 否 |

## 8. 风险、迁移与回滚

- 风险：外部超时用 LLM_TIMEOUT_SECONDS；空知识走反问/降级。
- 数据迁移：初始建 tickets/messages。
- 向后兼容：无。
- 回滚边界：工单保留；停止调用百炼即停自动答疑。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
