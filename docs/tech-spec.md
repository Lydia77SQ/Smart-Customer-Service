# 技术方案：智能客服系统（service_robot）

specification: default

## 1 选型清单

> 逐项从 `harness-core/specification/default/backend/tech-stack.md`、`frontend/tech-stack.md` 与 `backend/layers.md` 依赖清单选取；外部 AI 能力统一走百炼（`shared/security.md` 红线：httpx 直调、禁 dashscope SDK）。

| 层 | 选型 | 版本 | 来源白名单 |
|---|---|---|---|
| 语言 | Python | 3.11+ | backend/tech-stack.md |
| Web 框架 | FastAPI + uvicorn | FastAPI 0.115.x / uvicorn 0.32.x | backend/tech-stack.md |
| 后端底座 | pycore（PYTHONPATH 引入，禁止 pip 安装） | 项目内副本 | backend/tech-stack.md |
| ORM | SQLAlchemy（asyncio） | 2.0.36 | backend/layers.md |
| 数据库 | SQLite（含向量 BLOB、FTS5 关键词索引、业务元数据） | — | backend/tech-stack.md |
| SQLite 驱动 | aiosqlite | 0.20.0 | backend/layers.md |
| HTTP 客户端（外部服务） | httpx | 0.28.1 | shared/security.md |
| 密码哈希 | bcrypt | 4.2.1 | backend/layers.md |
| 文件上传 | python-multipart | 0.0.20 | FastAPI 生态（multipart 上传） |
| 质量工具 | ruff + mypy + pytest + pytest-timeout | ruff 0.8.x / mypy 1.13.x / pytest 8.3.x / pytest-timeout 2.3.x | backend/tech-stack.md |
| 前端框架 | Vue 3 + TypeScript + Vite | Vue 3.5.13 / Vite 6.0.3 / TS 5.7.2 | frontend/tech-stack.md |
| 状态管理 | Pinia | 2.3.0 | frontend/tech-stack.md |
| 前端路由 | Vue Router | 4.5.0 | frontend/tech-stack.md |
| 请求库 | Axios | 1.7.9 | frontend/tech-stack.md |
| 对话大模型 | 百炼 OpenAI 兼容 Chat Completions | qwen-max | shared/security.md（百炼 HTTP） |
| 向量化 | 百炼 text-embedding | text-embedding-v3 | shared/security.md（百炼 HTTP） |
| 重排序 | 百炼 text-rerank | gte-rerank | shared/security.md（百炼 HTTP） |
| 关键词检索 | SQLite FTS5 | 内置于 SQLite | backend/tech-stack.md（SQLite） |
| 混合检索排序 | RRF（向量 Top-K + 关键词 Top-K 融合） | 自研 Service 层 | 业务方案（无额外库） |

认证方案：服务端签发 **opaque session token**（存 `sessions` 表），前端 `Authorization: Bearer <token>`；不引入 JWT 第三方库，符合白名单。

## 2 页面/功能矩阵

> 页面清单从 `docs/prototypes/` 继承，共 4 页；F-003 为顶栏切换，非独立页面。

| 页面 | 路由 | 原型 | Feature / AC | 内容 | 承载功能 | 调用接口 |
|---|---|---|---|---|---|---|
| 登录与注册 | `/login` | `login.html` | F-001 / AC-F001-01～03；F-002 / AC-F002-01～02 | Tab 切换登录/注册；账号密码表单；错误提示 | 登录、注册 | API-F002-01、API-F001-01、API-F001-03 |
| 员工咨询工作台 | `/employee` | `employee.html` | F-003 / AC-F003-01～02；F-004 / AC-F004-01～05；F-005 / AC-F005-01～03；F-006 / AC-F006-01、03 | 顶栏三端切换；我的咨询列表；对话气泡；新咨询；转人工；发送 | 三端切换、提问答疑、查看续聊、转人工 | API-F001-03、API-F005-01、API-F005-02、API-F004-01、API-F006-01、API-F001-02 |
| 坐席接待工作台 | `/agent` | `agent.html` | F-003 / AC-F003-01；F-006 / AC-F006-02；F-007 / AC-F007-01～03；F-008 / AC-F008-01～03；F-009 / AC-F009-01～03；F-010 / AC-F010-01～02；F-011 / AC-F011-01～03 | 顶栏；待处理/处理中列表；对话区；右栏接入/分类/智能回答/结单 | 三端切换、接入、回复、智能建议、分类、结单 | API-F001-03、API-F007-01、API-F005-02、API-F007-02、API-F008-01、API-F009-01、API-F010-01、API-F011-01 |
| 知识维护工作台 | `/knowledge` | `knowledge.html` | F-003 / AC-F003-01；F-012 / AC-F012-01～03；F-013 / AC-F013-01～03 | 顶栏；上传 Markdown；文档表；启停开关 | 三端切换、上传入库、启停知识 | API-F001-03、API-F012-01、API-F012-02、API-F013-01 |

**前端路由守卫（F-003 / AC-F003-02）**：`/employee`、`/agent`、`/knowledge` 设置 `meta.requiresAuth: true`；`router.beforeEach` 无 token 时跳转 `/login` 并提示「请先登录后再进入工作台」。

**工单状态枚举（全局）**：`ai_assisting`（AI 接待中）→ `pending`（待处理）→ `in_progress`（处理中）→ `closed`（已完结）。

## 3 接口设计

> 响应统一经 `pycore.api.responses.success_response` / `error_response` 包装为信封 `{"code": ..., "message": ..., "data": ...}`。HTTP 状态码与信封 `code` 并用（错误码表见 `api-design.md`）。路由文件落位：`backend/src/api/routes/<资源复数>.py`，URL 前缀 `/api/<资源复数>`。

**资源词推导**：

| 名词实体 | 资源词 | 路由文件 |
|---|---|---|
| 账号 / 登录状态 | `auth` | `backend/src/api/routes/auth.py` |
| 咨询工单 | `tickets` | `backend/src/api/routes/tickets.py` |
| 知识文档 | `knowledge_documents` | `backend/src/api/routes/knowledge_documents.py` |

---

### 3.1 auth 资源

#### API-F002-01 本地账号注册：POST /api/auth/register

- 来源 Feature：F-002（覆盖 AC：AC-F002-01、AC-F002-02）
- 路由文件：`backend/src/api/routes/auth.py`
- 鉴权：公开
- 请求模型：`AuthRegisterRequest`
  - `account`: str（必填，`min_length=ACCOUNT_MIN_LENGTH`，`max_length=ACCOUNT_MAX_LENGTH`）
  - `password`: str（必填，`min_length=PASSWORD_MIN_LENGTH`，`max_length=PASSWORD_MAX_LENGTH`）
- 响应模型：`UserPublic`（经 `success_response` 包装）
  - `id`: int
  - `account`: str
  - `display_name`: str
- 错误码：`VALIDATION_ERROR` 参数不合法；`CONFLICT` 账号名已被占用（AC-F002-02）

#### API-F001-01 用户登录：POST /api/auth/login

- 来源 Feature：F-001（覆盖 AC：AC-F001-01、AC-F001-02）
- 路由文件：`backend/src/api/routes/auth.py`
- 鉴权：公开
- 请求模型：`AuthLoginRequest`
  - `account`: str（必填）
  - `password`: str（必填）
- 响应模型：`AuthSessionResponse`（经 `success_response` 包装）
  - `token`: str
  - `user`: `UserPublic`（`id: int`, `account: str`, `display_name: str`）
- 错误码：`VALIDATION_ERROR`；`UNAUTHORIZED` 账号或密码不正确（统一文案，不区分账号是否存在）

#### API-F001-02 退出登录：POST /api/auth/logout

- 来源 Feature：F-001
- 路由文件：`backend/src/api/routes/auth.py`
- 鉴权：`Depends(get_current_user)`
- 请求模型：无 body
- 响应模型：`null`（`success_response(data=None)`）
- 错误码：`UNAUTHORIZED`

#### API-F001-03 当前用户：GET /api/auth/me

- 来源 Feature：F-001、F-003（覆盖 AC：AC-F001-01、AC-F003-01）
- 路由文件：`backend/src/api/routes/auth.py`
- 鉴权：`Depends(get_current_user)`
- 请求模型：无
- 响应模型：`UserPublic`
- 错误码：`UNAUTHORIZED`

---

### 3.2 tickets 资源

**共享模型**

```text
TicketStatus = Literal["ai_assisting", "pending", "in_progress", "closed"]
MessageSenderType = Literal["employee", "system", "agent"]
TicketCategory = Literal["IT-网络", "IT-账号", "行政-工牌", "行政-场地"]
QaResultType = Literal["direct_answer", "clarification", "generated_answer", "degraded", "none"]
```

- `TicketSummary`：`id: int`, `title: str`, `status: TicketStatus`, `category: TicketCategory | None`, `created_at: datetime`, `updated_at: datetime`
- `MessageOut`：`id: int`, `sender_type: MessageSenderType`, `content: str`, `created_at: datetime`
- `TicketDetail`：继承 `TicketSummary`，附加 `messages: list[MessageOut]`, `requester: UserPublic`

#### API-F005-01 我的咨询列表：GET /api/tickets/mine

- 来源 Feature：F-005（覆盖 AC：AC-F005-01）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 查询参数：
  - `page`: int = `TICKET_LIST_PAGE_DEFAULT`（`ge=1`）
  - `page_size`: int = `TICKET_LIST_PAGE_SIZE`（`ge=1`, `le=TICKET_LIST_PAGE_SIZE_MAX`）
- 响应模型：`PaginatedTicketSummary`（经 `paginated_response`）
  - `items`: list[`TicketSummary`]
  - `page`: int
  - `page_size`: int
  - `total_items`: int
- 业务规则：仅返回 `requester_id == current_user.id` 的工单（BR-011）
- 错误码：`UNAUTHORIZED`

#### API-F005-02 工单详情：GET /api/tickets/{ticket_id}

- 来源 Feature：F-005（覆盖 AC：AC-F005-01～03）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 响应模型：`TicketDetail`
- 业务规则：员工仅可读自己的工单；坐席可读 `pending` / `in_progress` 工单（BR-011）
- 错误码：`NOT_FOUND`；`FORBIDDEN`；`UNAUTHORIZED`

#### API-F004-01 发送员工消息并答疑：POST /api/tickets/messages

- 来源 Feature：F-004（覆盖 AC：AC-F004-01～05）；续聊发送亦走本接口（F-005 AC-F005-02）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 请求模型：`EmployeeMessageCreate`
  - `content`: str（必填，`min_length=1`, `max_length=EMPLOYEE_MESSAGE_MAX_LENGTH`）
  - `ticket_id`: int | None = None（`None` 表示「新咨询」，创建新工单）
- 响应模型：`EmployeeMessageResponse`
  - `ticket`: `TicketSummary`
  - `employee_message`: `MessageOut`
  - `system_message`: `MessageOut | None`
  - `qa_result_type`: `QaResultType`
- 业务规则（写死）：
  1. `ticket_id` 为空：创建工单，`status=ai_assisting`，`title` 取 `content` 前 `TICKET_TITLE_MAX_LENGTH` 字符。
  2. `status=ai_assisting`：写入员工消息后执行共用答疑链路（见 §5.1）；`system_message` 写入工单；`qa_result_type` 反映路径。
  3. `status=pending` 或 `in_progress`：仅写入员工消息，`system_message=null`，`qa_result_type=none`（BR-007）。
  4. `status=closed`：拒绝发送（BR-009、AC-F005-03）。
  5. 非本人工单：拒绝。
- 错误码：`VALIDATION_ERROR`；`NOT_FOUND`；`FORBIDDEN`；`CONFLICT`（已完结）；`UNAUTHORIZED`

#### API-F006-01 转人工：POST /api/tickets/{ticket_id}/transfer

- 来源 Feature：F-006（覆盖 AC：AC-F006-01、AC-F006-03）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 请求模型：无 body
- 响应模型：`TicketSummary`（`status` 变为 `pending`）
- 业务规则：仅 `ai_assisting` 且本人工单可转；转后写入系统提示消息「已提交，等待对接人」；`pending` / `in_progress` 返回 `CONFLICT` 提示已在人工流程；`closed` 拒绝
- 错误码：`CONFLICT`；`NOT_FOUND`；`FORBIDDEN`；`UNAUTHORIZED`

#### API-F007-01 坐席工单队列：GET /api/tickets/agent-queue

- 来源 Feature：F-007（覆盖 AC：AC-F007-01、AC-F006-02）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 查询参数：
  - `status`: Literal["pending", "in_progress"]（必填）
  - `page`: int = `TICKET_LIST_PAGE_DEFAULT`
  - `page_size`: int = `TICKET_LIST_PAGE_SIZE`
- 响应模型：`PaginatedAgentTicketSummary`（`paginated_response`）
  - `items`: list[`AgentTicketSummary`]
  - `AgentTicketSummary`：`id: int`, `title: str`, `status: TicketStatus`, `requester: UserPublic`, `waiting_minutes: int`, `updated_at: datetime`
- 业务规则：不得返回 `ai_assisting` 或 `closed` 工单（BR-006）
- 错误码：`VALIDATION_ERROR`；`UNAUTHORIZED`

#### API-F007-02 接入工单：POST /api/tickets/{ticket_id}/accept

- 来源 Feature：F-007（覆盖 AC：AC-F007-01～03）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 请求模型：无 body
- 响应模型：`TicketDetail`
- 业务规则：仅 `pending` → `in_progress`；`closed` / `ai_assisting` 拒绝；`in_progress` 幂等返回当前详情（不重复变更）
- 错误码：`CONFLICT`；`NOT_FOUND`；`UNAUTHORIZED`

#### API-F008-01 坐席回复：POST /api/tickets/{ticket_id}/agent-replies

- 来源 Feature：F-008（覆盖 AC：AC-F008-01～03）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 请求模型：`AgentReplyCreate`
  - `content`: str（必填，`min_length=1`, `max_length=AGENT_MESSAGE_MAX_LENGTH`）
- 响应模型：`MessageOut`（`sender_type=agent`）
- 业务规则：仅 `in_progress` 可发；`pending` 须先接入；`closed` 拒绝；空内容 `VALIDATION_ERROR`
- 错误码：`CONFLICT`；`VALIDATION_ERROR`；`NOT_FOUND`；`UNAUTHORIZED`

#### API-F009-01 智能回答建议：POST /api/tickets/{ticket_id}/suggestions

- 来源 Feature：F-009（覆盖 AC：AC-F009-01～03）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 请求模型：`SuggestionCreate`
  - `focus_message_id`: int | None = None（默认取工单最新员工消息作为答疑输入）
- 响应模型：`SuggestionOut`
  - `id`: int
  - `content`: str
  - `result_type`: Literal["direct_answer", "clarification", "generated_answer", "degraded"]
  - `created_at`: datetime
- 业务规则：仅 `in_progress`；走与 F-004 相同答疑链路（§5.1），结果写入 `suggestions` 表，**不**写入 `messages`（BR-008）；外部服务失败时 `result_type=degraded`，`content` 为失败说明
- 错误码：`CONFLICT`；`NOT_FOUND`；`UNAUTHORIZED`

#### API-F010-01 工单分类：PUT /api/tickets/{ticket_id}/category

- 来源 Feature：F-010（覆盖 AC：AC-F010-01～02）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 请求模型：`TicketCategoryUpdate`
  - `category`: `TicketCategory`（必填）
- 响应模型：`TicketSummary`
- 业务规则：`pending` / `in_progress` 可改；`closed` 拒绝（AC-F010-02）
- 错误码：`CONFLICT`；`VALIDATION_ERROR`；`NOT_FOUND`；`UNAUTHORIZED`

#### API-F011-01 结单：POST /api/tickets/{ticket_id}/close

- 来源 Feature：F-011（覆盖 AC：AC-F011-01～03）
- 路由文件：`backend/src/api/routes/tickets.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`ticket_id: int`
- 请求模型：无 body
- 响应模型：`TicketSummary`（`status=closed`）
- 业务规则：仅 `in_progress` → `closed`；`pending` 拒绝（AC-F011-03）；`closed` 幂等返回；结单后双方不可再发消息
- 错误码：`CONFLICT`；`NOT_FOUND`；`UNAUTHORIZED`

---

### 3.3 knowledge_documents 资源

**共享模型**

- `KnowledgeDocumentStatus = Literal["enabled", "disabled", "failed", "processing"]`
- `KnowledgeDocumentOut`：`id: int`, `filename: str`, `status: KnowledgeDocumentStatus`, `updated_at: datetime`

#### API-F012-01 上传 Markdown 入库：POST /api/knowledge_documents

- 来源 Feature：F-012（覆盖 AC：AC-F012-01～03）
- 路由文件：`backend/src/api/routes/knowledge_documents.py`
- 鉴权：`Depends(get_current_user)`
- 请求：`multipart/form-data`
  - `file`: UploadFile（必填；扩展名 `.md`；`max_size=KNOWLEDGE_MAX_SIZE_BYTES`）
- 响应模型：`KnowledgeDocumentOut`
- 业务规则：
  1. 非 `.md` → `VALIDATION_ERROR`，文案「仅支持 Markdown」。
  2. 入库成功：`status=enabled`（BR-015），切片入库并向量化，抽取标准问答对。
  3. 处理失败：`status=failed`，不参与答疑（AC-F012-03）。
  4. 处理中可先返回 `status=processing`，完成后前端刷新列表。
- 错误码：`VALIDATION_ERROR`；`INTERNAL_ERROR`（处理失败）；`UNAUTHORIZED`

#### API-F012-02 知识文档列表：GET /api/knowledge_documents

- 来源 Feature：F-012、F-013（覆盖 AC：AC-F013-03）
- 路由文件：`backend/src/api/routes/knowledge_documents.py`
- 鉴权：`Depends(get_current_user)`
- 查询参数：
  - `page`: int = `KNOWLEDGE_LIST_PAGE_DEFAULT`
  - `page_size`: int = `KNOWLEDGE_LIST_PAGE_SIZE`
- 响应模型：`PaginatedKnowledgeDocumentOut`（`paginated_response`）
- 业务规则：含启用、停用、失败、处理中全部条目（停用不删除，AC-F013-03）
- 错误码：`UNAUTHORIZED`

#### API-F013-01 启用/停用知识文档：PATCH /api/knowledge_documents/{document_id}

- 来源 Feature：F-013（覆盖 AC：AC-F013-01～02）
- 路由文件：`backend/src/api/routes/knowledge_documents.py`
- 鉴权：`Depends(get_current_user)`
- 路径参数：`document_id: int`
- 请求模型：`KnowledgeDocumentStatusUpdate`
  - `enabled`: bool（必填；`true`→`enabled`，`false`→`disabled`）
- 响应模型：`KnowledgeDocumentOut`
- 业务规则：仅 `enabled` / `disabled` 间切换；`failed` / `processing` 拒绝；停用立即生效（BR-016），不删切片
- 错误码：`CONFLICT`；`NOT_FOUND`；`UNAUTHORIZED`

---

## 4 config 键清单

> 默认值相对于 `backend/` 目录；存储落点见 `shared/env-policy.md`。密钥只写字段名，真实值写入 `backend/.env`（`shared/security.md`）。

| 键名 | 默认值 | 说明 | 使用处 |
|---|---|---|---|
| `DATABASE_PATH` | `data/service_robot.db` | SQLite 数据库文件 | DB 初始化 |
| `UPLOAD_DIR` | `data/uploads` | Markdown 原文件与持久化目录 | F-012 上传 |
| `HOST` | `127.0.0.1` | 后端监听地址 | 启动 |
| `PORT` | `8099` | Agent/Tester 后端端口 | 启动 |
| `DEBUG` | `false` | 调试开关 | 启动 |
| `SECRET_KEY` | （无默认，必填） | Session 签名与哈希盐 | 认证 |
| `CORS_ORIGINS` | `["http://localhost:5199","http://127.0.0.1:5199","http://localhost:5175","http://127.0.0.1:5175"]` | CORS 白名单 | APIServer |
| `SESSION_EXPIRE_HOURS` | `72` | 登录会话有效期（小时） | F-001 |
| `ACCOUNT_MIN_LENGTH` | `3` | 账号最小长度 | F-002 |
| `ACCOUNT_MAX_LENGTH` | `64` | 账号最大长度 | F-002 |
| `PASSWORD_MIN_LENGTH` | `6` | 密码最小长度 | F-002 |
| `PASSWORD_MAX_LENGTH` | `128` | 密码最大长度 | F-002 |
| `TICKET_TITLE_MAX_LENGTH` | `80` | 工单标题截取长度 | F-004 |
| `EMPLOYEE_MESSAGE_MAX_LENGTH` | `4000` | 员工单条消息上限 | F-004 |
| `AGENT_MESSAGE_MAX_LENGTH` | `4000` | 坐席单条消息上限 | F-008 |
| `TICKET_LIST_PAGE_DEFAULT` | `1` | 工单列表默认页码 | F-005、F-007 |
| `TICKET_LIST_PAGE_SIZE` | `20` | 工单列表每页条数 | F-005、F-007 |
| `TICKET_LIST_PAGE_SIZE_MAX` | `100` | 工单列表每页上限 | F-005 |
| `KNOWLEDGE_LIST_PAGE_DEFAULT` | `1` | 知识列表默认页码 | F-012 |
| `KNOWLEDGE_LIST_PAGE_SIZE` | `50` | 知识列表每页条数 | F-012 |
| `KNOWLEDGE_MAX_SIZE_BYTES` | `20971520` | 单 Markdown 上限（20MB） | F-012 |
| `QA_SIMILARITY_THRESHOLD` | `0.8` | 标准问答高置信直出阈值 | F-004、F-009 |
| `SHORT_TERM_MEMORY_ROUNDS` | `3` | 短期记忆轮数（最近 N 轮问答） | F-004、F-009 |
| `SEARCH_TOP_K` | `10` | 向量检索与关键词检索各取 Top-K | F-004、F-009 |
| `RRF_K` | `60` | RRF 融合常数 k | F-004、F-009 |
| `RERANK_TOP_N` | `5` | 重排后保留片段数 | F-004、F-009 |
| `CHUNK_SIZE` | `800` | 知识切片字符数 | F-012 |
| `CHUNK_OVERLAP` | `100` | 切片重叠字符数 | F-012 |
| `DASHSCOPE_API_KEY` | （无默认，必填） | 百炼统一 API Key | 外部服务 |
| `LLM_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 对话 API Base URL | F-004、F-009 |
| `LLM_MODEL` | `qwen-max` | 对话模型名 | F-004、F-009 |
| `LLM_TIMEOUT_SECONDS` | `60` | 对话 HTTP 超时 | F-004、F-009 |
| `LLM_TEMPERATURE_INTENT` | `0.1` | 意图识别温度 | F-004、F-009 |
| `LLM_TEMPERATURE_GENERATION` | `0.3` | 生成答复温度 | F-004、F-009 |
| `EMBEDDING_BASE_URL` | `https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding` | 向量化 API URL | F-004、F-009、F-012 |
| `EMBEDDING_MODEL` | `text-embedding-v3` | 向量化模型名 | F-004、F-009、F-012 |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | 向量化 HTTP 超时 | F-004、F-009、F-012 |
| `EMBEDDING_DIMENSIONS` | `1024` | 向量维度（与模型一致） | F-012 存储 |
| `RERANK_BASE_URL` | `https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank` | 重排 API URL | F-004、F-009 |
| `RERANK_MODEL` | `gte-rerank` | 重排模型名 | F-004、F-009 |
| `RERANK_TIMEOUT_SECONDS` | `30` | 重排 HTTP 超时 | F-004、F-009 |
| `HTTP_CLIENT_TRUST_ENV` | `false` | httpx 禁止继承环境变量 | 全部外部 HTTP |
| `DEGRADED_QA_MESSAGE` | `暂时无法自动答疑，请稍后再试，或转人工等待对接人。` | 外部能力不可用降级文案 | F-004 |
| `DEGRADED_SUGGESTION_MESSAGE` | `暂时无法生成建议。请手写回复，不要向员工发送自动消息。` | 建议失败文案 | F-009 |
| `TRANSFER_SUCCESS_MESSAGE` | `已提交，等待对接人` | 转人工成功提示 | F-006 |

**前端 `.env` 键（`frontend/.env`）**

| 键名 | 默认值 | 说明 |
|---|---|---|
| `VITE_API_BASE_URL` | `/api` | API 相对路径 |
| `VITE_BACKEND_PROXY_TARGET` | `http://localhost:8099` | Vite 开发代理目标 |
| `VITE_AXIOS_TIMEOUT_MS` | `30000` | Axios 超时毫秒 |

`.env` 策略与端口约定见 `shared/env-policy.md`（Agent 前端 5199 / 后端 8099；用户门禁 5175 / 8003）。

## 5 外部服务规格（写死）

> 调用方式：`httpx.AsyncClient(trust_env=False)` 直调；禁止 `dashscope` SDK（`shared/security.md`）。请求头：`Authorization: Bearer {DASHSCOPE_API_KEY}`，`Content-Type: application/json`。

### 5.1 共用答疑链路（F-004 / F-009）

对输入问题文本 `query` 顺序执行：

1. **标准问答直出**：在启用中文档的标准问答中做向量相似度检索；`score >= QA_SIMILARITY_THRESHOLD`（0.8）→ 直接返回该答案，`result_type=direct_answer`。
2. **意图识别**（未达阈值）：调用 LLM，system prompt 判定 `intent: "clear" | "ambiguous"`；`ambiguous` → 生成反问，`result_type=clarification`。
3. **改写**（`clear`）：拼接账号长期画像 JSON + 最近 `SHORT_TERM_MEMORY_ROUNDS`（3）轮员工/系统消息，调用 LLM 输出 `rewritten_query`。
4. **混合检索**：对 `rewritten_query` 分别在启用中知识切片上做向量 Top-`SEARCH_TOP_K`（10）与 FTS5 关键词 Top-`SEARCH_TOP_K`（10），RRF 融合（`RRF_K=60`）得候选集。
5. **重排与生成**：调用 Rerank 取 Top-`RERANK_TOP_N`（5）；再调用 LLM 基于片段生成最终答复，`result_type=generated_answer`。
6. **降级**：任一步外部调用失败 → `result_type=degraded`，返回配置降级文案；F-004 写入 `system_message`；F-009 仅写 `suggestions` 表。

仅 `status=enabled` 的文档参与步骤 1、4（BR-016）。

### 5.2 服务清单

| 服务 | URL | 模型/关键字段 | 用途 | 额度来源 |
|---|---|---|---|---|
| 百炼 Chat Completions | `POST {LLM_BASE_URL}/chat/completions` | 模型 `qwen-max`；请求体 `model`, `messages: [{role, content}]`, `temperature`；响应取 `choices[0].message.content` | 意图识别、反问、改写、生成答复 | 进入开发前向用户确认 |
| 百炼 Text Embedding | `POST {EMBEDDING_BASE_URL}` | 模型 `text-embedding-v3`；请求体 `model`, `input: string \| string[]`, `parameters.dimensions={EMBEDDING_DIMENSIONS}`；响应取 `output.embeddings[].embedding` | 问答/切片向量化、相似度 | 进入开发前向用户确认 |
| 百炼 Text Rerank | `POST {RERANK_BASE_URL}` | 模型 `gte-rerank`；请求体 `model`, `input.query`, `input.documents[]`, `parameters.top_n={RERANK_TOP_N}`；响应取 `output.results[].index` / `relevance_score` | 混合检索后重排 | 进入开发前向用户确认 |

密钥配置键：`DASHSCOPE_API_KEY`（写入 `backend/.env`，`.env.example` 占位，禁止写入本文档）。

## 6 风险清单

| 风险 | 影响 | 应对 |
|---|---|---|
| 百炼 API 不可用或额度不足 | 夜间 AI 答疑中断（PRD 风险） | 降级文案 + 保留转人工；Tester 标记 external 用例；进入开发前确认 Key 与额度 |
| SQLite 向量规模增长 | 检索变慢 | MVP 单组织可接受；切片数监控；V2 可迁移 PG，本轮不扩 scope |
| 同一账号可进坐席台与知识库 | 误结单、误传制度（PRD 已接受） | MVP 不分权；操作日志留痕；V2 F-014 分权 |
| 高置信阈值不准 | 该直出却生成，或该反问却直出 | 阈值写死 config `QA_SIMILARITY_THRESHOLD`，可调需改文档+config |
| 知识为空 | 无法有依据作答 | 上线前导入首批 Markdown；空库时走反问/降级，不编造制度 |
| 待处理无坐席在线 | 员工等待体验差 | 转人工后展示 `TRANSFER_SUCCESS_MESSAGE`；产品允许（PRD） |
