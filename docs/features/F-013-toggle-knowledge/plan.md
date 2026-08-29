# F-013 启用或停用知识文档实施计划

## 1. 追踪信息

- Feature：F-013
- Spec：docs/features/F-013-toggle-knowledge/spec.md
- Spec 版本：1
- 依赖 Feature：F-012
- Data Model：docs/data-model.md（knowledge_documents；答疑读 tickets/messages）
- API：API-F013-01、API-F012-02；答疑影响走 API-F004-01
- 原型：docs/prototypes/knowledge.html（开关）

## 2. 实现策略

- 前端实现路径：KnowledgePage 启停开关（52×32）；列表不因停用消失
- 后端实现路径：PATCH knowledge_documents；enabled⇄disabled；failed/processing CONFLICT
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：更新 knowledge_documents.status；不删切片
- 外部服务：无（启停本身）；答疑影响依赖 F-004 外部链路
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | KnowledgePage 开关 | 立即反映 status | 停用不得从列表移除 |
| 后端 | PATCH status | 立即排除检索 | 不物理删除 |
| 测试 | backend/tests/features/f013 | 列表仍在；答疑变化标 agent | 启停 API 可 auto |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 启停 API | backend | PATCH enabled | F-012 | AC-F013-03 |
| 知识开关 UI | frontend | 开关与列表 | 启停 API | AC-F013-03 |
| Feature 测试 | test | pytest 不删除；agent 答疑变化 | 与 F-004 联测 | 全部 |

> 此表供 Planner 生成 `.sdd/tasks.json`。任务运行状态统一记录在 `.sdd/tasks.json`。

## 5. 开发规范引用

- 规范集：harness-core/specification/default/（集名=Plan.md 头部 specification: default）
- 前端任务：specification/default/frontend/（tech-stack / api-client / mock / style）+ shared/（env-policy / naming / security）
- 后端任务：specification/default/backend/（tech-stack / layers / api-design / error-handling / workflow）+ shared/（env-policy / naming / security）

只引用路径，不复制内容。

## 6. AC → 测试映射

| AC | 验证类型 | 测试层级 | 计划测试路径 | 确定性命令 | CI 门禁 |
|---|---|---|---|---|---|
| AC-F013-01 | agent | API | backend/tests/features/f013/test_toggle_qa.py | pytest --timeout=300 | agent；依赖答疑语义 |
| AC-F013-02 | agent | API | backend/tests/features/f013/test_toggle_qa.py | pytest --timeout=300 | agent |
| AC-F013-03 | auto | API+E2E | backend/tests/features/f013/test_toggle.py；e2e/features/f013-toggle.spec.ts | pytest --timeout=120；playwright | required |

## 7. 外部服务与测试权限

无外部服务。 AC-F013-01/02 的答疑侧验证若走真实链路，受百炼 Key 约束，不得伪装成 auto 通过。

## 8. 风险、迁移与回滚

- 风险：停用延迟（必须同步过滤 enabled）。
- 数据迁移：无。
- 向后兼容：无。
- 回滚边界：再次 PATCH enabled=true。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
