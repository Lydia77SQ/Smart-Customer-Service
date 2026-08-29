# F-012 上传 Markdown 并入库实施计划

## 1. 追踪信息

- Feature：F-012
- Spec：docs/features/F-012-upload-markdown/spec.md
- Spec 版本：1
- 依赖 Feature：F-001
- Data Model：docs/data-model.md（knowledge_documents、knowledge_chunks、qa_pairs、knowledge_chunks_fts）
- API：API-F012-01、API-F012-02
- 原型：docs/prototypes/knowledge.html

## 2. 实现策略

- 前端实现路径：KnowledgePage 上传与列表；processing 刷新
- 后端实现路径：knowledge_documents.py upload；切分、向量化、抽 QA；默认 enabled
- 状态管理：Pinia（auth / ticket / knowledge 按页读取）
- 数据持久化：插入文档/切片/问答；写 UPLOAD_DIR；同步 FTS
- 外部服务：百炼 Embedding
- 权限与安全：Bearer session；密钥只进 backend/.env；httpx trust_env=false

## 3. 影响范围

| 层级 | 预计模块/目录 | 变更目的 | 禁止影响 |
|---|---|---|---|
| 前端 | frontend/src/pages/KnowledgePage.vue | 上传与列表状态 | 不接受非 md 为启用 |
| 后端 | knowledge ingest 服务 | 切片+向量+QA | 失败不得 enabled |
| 测试 | backend/tests/features/f012 | 格式拒绝、失败不生效 | 可用检索标 agent |

## 4. 内部 Task 候选

| Task 候选 | 类型 | 产出 | 依赖 | 覆盖 AC |
|---|---|---|---|---|
| 入库流水线 | backend | 上传、切片、embedding、QA 抽取 | 基础设施 + 百炼 | AC-F012-01/03 |
| 知识列表 API 与页 | frontend/backend | GET 列表 + 上传 UI | 入库流水线 | AC-F012-01/02 |
| Feature 测试 | test | pytest 格式；agent 启用可用 | 前后端 | 全部 |

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
| AC-F012-01 | agent | API+E2E | backend/tests/features/f012/test_upload.py；e2e/features/f012-upload.spec.ts | pytest --timeout=300；playwright | agent 证据；缺 Embedding Key 不得宣称完整通过 |
| AC-F012-02 | auto | API | backend/tests/features/f012/test_upload.py | pytest --timeout=120 | required |
| AC-F012-03 | auto | API | backend/tests/features/f012/test_failed.py | pytest --timeout=120 | required |

## 7. 外部服务与测试权限

| 服务 | 配置字段 | Tester 权限 | 缺失时策略 | 可否宣称完整通过 |
|---|---|---|---|---|
| 百炼 Embedding | DASHSCOPE_API_KEY、EMBEDDING_* | 可向量化入库 | 可存原文，status=failed，不得宣称可供语义检索 | 否 |

## 8. 风险、迁移与回滚

- 风险：大文件超时；上限 KNOWLEDGE_MAX_SIZE_BYTES。
- 数据迁移：初始建知识四表。
- 向后兼容：无。
- 回滚边界：status=failed/disabled，不删文件亦可。

## 9. Definition of Done

- [ ] Spec 中全部 AC 有验证路径
- [ ] 物理数据与 API 契约已引用
- [ ] 内部 Task 候选覆盖完整纵向闭环
- [ ] 自动化测试路径和 CI 门禁明确
- [ ] 手工 / Agent / 外部服务验收没有伪装成自动通过
- [ ] 没有复制 harness-core 开发规范
