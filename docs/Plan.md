# 全局开发计划

specification: default

## 1. Feature 交付总览

| Feature | 用户结果 | 依赖 | Spec | Plan | 优先级 | 状态 |
|---|---|---|---|---|---|---|
| F-002 本地账号注册 | 尚未有账号的人获得可登录账号 | 无 | features/F-002-local-register/spec.md | features/F-002-local-register/plan.md | MVP | Ready |
| F-001 用户登录 | 提交有效凭证后进入系统，身份可识别 | 无 | features/F-001-user-login/spec.md | features/F-001-user-login/plan.md | MVP | Ready |
| F-003 三端工作台切换 | 同一登录下在员工 / 坐席 / 知识维护之间切换 | F-001 | features/F-003-workbench-switch/spec.md | features/F-003-workbench-switch/plan.md | MVP | Ready |
| F-012 上传 Markdown 并入库 | 文档入库且默认启用 | F-001 | features/F-012-upload-markdown/spec.md | features/F-012-upload-markdown/plan.md | MVP | Ready |
| F-013 启用或停用知识文档 | 启停立即影响后续答疑，文档不删除 | F-012 | features/F-013-toggle-knowledge/spec.md | features/F-013-toggle-knowledge/plan.md | MVP | Ready |
| F-004 员工提问并获得系统答复 | 形成工单并得到直出 / 反问 / 生成答复 | F-001 | features/F-004-employee-qa/spec.md | features/F-004-employee-qa/plan.md | MVP | Ready |
| F-005 查看并继续自己的咨询 | 看到自己的历史；未完结可续、已完结只读 | F-004 | features/F-005-view-continue/spec.md | features/F-005-view-continue/plan.md | MVP | Ready |
| F-006 员工转人工 | 工单进入待处理，坐席可见，上下文保留 | F-004 | features/F-006-transfer-human/spec.md | features/F-006-transfer-human/plan.md | MVP | Ready |
| F-007 坐席接入待处理工单 | 工单变为处理中，系统停止自动对外发言 | F-001、F-006 | features/F-007-agent-accept/spec.md | features/F-007-agent-accept/plan.md | MVP | Ready |
| F-008 坐席向员工发送回复 | 员工在同一咨询中看到人工消息 | F-007 | features/F-008-agent-reply/spec.md | features/F-008-agent-reply/plan.md | MVP | Ready |
| F-009 坐席获取智能回答建议 | 坐席看到建议；员工侧看不到未发出内容 | F-007 | features/F-009-agent-suggest/spec.md | features/F-009-agent-suggest/plan.md | MVP | Ready |
| F-010 坐席为工单分类 | 工单带有业务标签 | F-007 | features/F-010-ticket-classify/spec.md | features/F-010-ticket-classify/plan.md | MVP | Ready |
| F-011 坐席结单 | 工单已完结，双方不能再发 | F-007 | features/F-011-close-ticket/spec.md | features/F-011-close-ticket/plan.md | MVP | Ready |

F-014～F-019 仅在 Feature Map 登记，本轮不进入本表。运行进度由 `.sdd/tasks.json` 同步，开发入口生成后回写本表状态。

## 2. 交付依赖图

```text
F-002 ─┐
       ├→ F-001 → F-003
       │         ↘ F-012 → F-013
       │         ↘ F-004 → F-005
       │                 → F-006 → F-007 → F-008
       │                                 → F-009
       │                                 → F-010
       │                                 → F-011
F-012 / F-013 虚线供给 F-004、F-009（无知识仍可降级运行）
```

无循环依赖。F-002 不是 F-001 的唯一账号来源（可预置账号）。

建议开发顺序（Mock → 基础设施 → 纵向闭环）：

1. F-002 → F-001 → F-003
2. F-012 → F-013
3. F-004 → F-005 → F-006
4. F-007 → F-008 → F-009 → F-010 → F-011

## 3. 前端 Mock 验收阶段

- 页面映射：`/login`（F-001、F-002）、`/employee`（F-003～F-006）、`/agent`（F-003、F-007～F-011）、`/knowledge`（F-003、F-012、F-013）。原型：`docs/prototypes/*.html`。
- Mock 数据必须符合 `docs/api-contracts.md` 信封、枚举与错误码；不得发明契约外字段。
- 原型验收门禁：四页布局与文案对齐 `docs/ui-design-spec.md` 与已确认原型（含知识开关尺寸、登录按钮间距、composer 转人工/发送不换行）。
- Mock 阶段不调用百炼；答疑气泡可用契约内 `qa_result_type` 样例。

## 4. 后端基础设施阶段

- 项目结构：`backend/` FastAPI + pycore（PYTHONPATH 副本，禁止 pip 安装 pycore）；`frontend/` Vue 3 + Vite。规范集 `specification: default`。
- 配置：`docs/tech-spec.md` §4 config 键；密钥只进 `backend/.env`（`DASHSCOPE_API_KEY`、`SECRET_KEY` 无默认）。
- 数据库：SQLite `DATABASE_PATH`；按 `docs/data-model.md` 初始建表（含 FTS5）。
- 健康检查：pycore 既有 health；监听 `HOST`/`PORT`（Agent 8099）。
- 跨 Feature 认证：opaque session + `get_current_user`；路由文件 `auth.py` / `tickets.py` / `knowledge_documents.py`。
- 外部 HTTP：`httpx.AsyncClient(trust_env=False)`；禁止 dashscope SDK。

## 5. 逐 Feature 纵向闭环阶段

| 顺序 | Feature | 完整闭环 | 用户门禁 |
|---|---|---|---|
| 1 | F-002 | 注册成功 / 账号冲突 | 每 Feature Tester 通过后确认是否继续 |
| 2 | F-001 | 登录成功 / 拒错密 / 未登录拦截 | 同上 |
| 3 | F-003 | 三端切换保持登录；未登录不可入 | AC-F003-01 需 Agent 证据 |
| 4 | F-012 | 上传 md 默认启用；拒非 md；失败不生效 | AC-F012-01 需 Agent；Embedding Key |
| 5 | F-013 | 启停不删除；答疑立即受影响 | AC-F013-01/02 需 Agent |
| 6 | F-004 | 建单答疑四路径 + 降级 | AC-F004-01～04 Agent；AC-F004-05 external |
| 7 | F-005 | 只看自己的单；续聊；完结只读 | 确认后继续 |
| 8 | F-006 | 转人工待处理；未转不可见；完结拒转 | 确认后继续 |
| 9 | F-007 | 接入处理中；停自动答复；非待处理拒接 | 确认后继续 |
| 10 | F-008 | 人工消息同步；完结拒回；建议不泄漏 | 确认后继续 |
| 11 | F-009 | 建议仅坐席；不发送则不入消息；失败不骚扰员工 | AC-F009-01 Agent；AC-F009-03 external |
| 12 | F-010 | 分类写入；完结拒改 | 确认后继续 |
| 13 | F-011 | 结单双方拒发；无重开；待处理拒结 | 确认后继续 |

## 6. 外部服务与测试权限清单

| 服务 | 用途 | 配置字段 | Tester 权限 | 缺失策略 | 状态 |
|---|---|---|---|---|---|
| 百炼 Chat Completions | 意图、反问、改写、生成（F-004、F-009） | DASHSCOPE_API_KEY、LLM_* | 可调用 qwen-max | DEGRADED_* 文案 + 转人工 | 进入开发前向用户索取 Key |
| 百炼 Text Embedding | 标准问答/切片向量（F-004、F-009、F-012） | DASHSCOPE_API_KEY、EMBEDDING_* | 可向量化 | 入库 failed；答疑降级 | 同上 |
| 百炼 Text Rerank | 混合检索后重排（F-004、F-009） | DASHSCOPE_API_KEY、RERANK_* | 可重排 | 答疑降级 | 同上 |

SQLite 为本机文件，不算外部服务。缺 Key 时 Tester 不得宣称 F-004 / F-009 / F-012 完整联调通过。

## 7. 最终回归与交付

- 跨 Feature E2E：注册/登录 → 上传知识 → 员工提问 → 转人工 → 坐席接入 → 建议（不泄漏）→ 回复 → 分类 → 结单 → 双方无法再发。
- 启动文档：按 `shared/env-policy.md` 记录 Agent 端口 5199/8099 与用户门禁端口 5175/8003。
- 部署前检查：`.env` 不入库；`specification: default`；无 reopen API；停用知识不删除。
