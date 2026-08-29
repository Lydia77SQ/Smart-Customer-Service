# 数据模型

> 物理数据结构的唯一事实来源。每个实体和字段必须能追溯到 Feature 或通用基础设施需求。选型：SQLite + SQLAlchemy 2.0（`docs/tech-spec.md`）。

## 1. 数据设计原则

- 数据库类型：SQLite，文件 `backend/data/service_robot.db`（config `DATABASE_PATH`）
- ID 策略：整型主键自增
- 时间与时区：存储 UTC `DATETIME`，API 输出 ISO-8601（末尾 `Z`）
- 软删除 / 归档策略：MVP 不删除工单、消息、账号、知识文档；知识用 `status` 停用代替删除
- 审计策略：各业务表 `created_at`；工单与知识文档另有 `updated_at`。不单独做操作审计表

## 2. 实体总览

| 实体/表 | 业务对象 | Owner Feature | 读写 Feature | 生命周期 |
|---|---|---|---|---|
| accounts | 账号、长期画像 | F-002 | F-001、F-002、F-004、F-009 | 有效（MVP 不停用） |
| sessions | 登录状态 | F-001 | F-001、F-003 | 未登录 → 已登录 → 退出/过期 |
| tickets | 咨询工单、工单分类 | F-004 | F-004～F-011 | ai_assisting → pending → in_progress → closed |
| messages | 消息 | F-004 | F-004、F-005、F-006、F-007、F-008、F-009 | 随工单保存，不可改不可删 |
| suggestions | 建议答复 | F-009 | F-009、F-008（仅坐席选用发出） | 已生成；不进入员工消息 |
| knowledge_documents | 知识文档 | F-012 | F-012、F-013、F-004、F-009 | processing / enabled / disabled / failed |
| knowledge_chunks | 知识切片 | F-012 | F-012、F-004、F-009 | 随文档；检索仅 enabled |
| qa_pairs | 标准问答 | F-012 | F-012、F-004、F-009 | 随文档；匹配仅 enabled |
| knowledge_chunks_fts | 关键词检索虚表 | F-012 | F-004、F-009 | 与切片同步 |

短期记忆不落独立表：由 `messages` 按工单取最近 `SHORT_TERM_MEMORY_ROUNDS` 轮派生。

## 3. 实体定义

### accounts

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 账号主键 | platform | PK |
| account | VARCHAR(64) | 是 | — | 登录账号名 | F-002 / AC-F002-01 | UNIQUE；长度 ACCOUNT_MIN/MAX |
| password_hash | VARCHAR(255) | 是 | — | bcrypt 哈希 | F-001、F-002 | 禁止明文 |
| display_name | VARCHAR(64) | 是 | 与 account 相同 | 界面显示名 | F-001 / AC-F001-01 | |
| profile_json | TEXT | 是 | `{}` | 长期画像 JSON，只用于改写 | F-004 / BR-005 | 界面不展示 |
| created_at | DATETIME | 是 | utcnow | 创建时间 | platform | |

### sessions

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 会话主键 | platform | PK |
| account_id | INTEGER | 是 | — | 所属账号 | F-001 / AC-F001-01 | FK accounts.id |
| token_hash | VARCHAR(64) | 是 | — | Bearer token 的 SHA-256 | F-001 | UNIQUE |
| expires_at | DATETIME | 是 | now+SESSION_EXPIRE_HOURS | 过期时间 | F-001 | |
| created_at | DATETIME | 是 | utcnow | 签发时间 | platform | |

### tickets

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 工单主键 | F-004 / AC-F004-01 | PK |
| requester_id | INTEGER | 是 | — | 发起员工 | F-004、F-005 / BR-011 | FK accounts.id，不可改 |
| title | VARCHAR(80) | 是 | 首问截断 | 列表摘要 | F-004 / TICKET_TITLE_MAX_LENGTH | |
| status | VARCHAR(32) | 是 | `ai_assisting` | 工单状态 | F-004～F-011 | 枚举见下 |
| category | VARCHAR(32) | 否 | NULL | 坐席业务标签 | F-010 / AC-F010-01 | 枚举或 NULL |
| created_at | DATETIME | 是 | utcnow | 创建时间 | platform | |
| updated_at | DATETIME | 是 | utcnow | 最后变更 | platform | |

`status`：`ai_assisting` | `pending` | `in_progress` | `closed`。  
`category`：`IT-网络` | `IT-账号` | `行政-工牌` | `行政-场地`。

### messages

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 消息主键 | F-004 | PK |
| ticket_id | INTEGER | 是 | — | 所属工单 | F-004 / BR-001 | FK tickets.id |
| sender_type | VARCHAR(16) | 是 | — | employee / system / agent | F-004、F-006、F-008 | |
| content | TEXT | 是 | — | 正文 | F-004、F-008 | 长度上限见 config |
| created_at | DATETIME | 是 | utcnow | 发送时间 | platform | 不可 UPDATE |

### suggestions

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 建议主键 | F-009 / AC-F009-01 | PK |
| ticket_id | INTEGER | 是 | — | 所属工单 | F-009 | FK tickets.id |
| content | TEXT | 是 | — | 建议正文（员工不可见） | F-009 / BR-008 | |
| result_type | VARCHAR(32) | 是 | — | 答疑路径类型 | F-009 | 不含 none |
| created_at | DATETIME | 是 | utcnow | 生成时间 | platform | |

### knowledge_documents

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 文档主键 | F-012 / AC-F012-01 | PK |
| filename | VARCHAR(255) | 是 | — | 原始文件名 | F-012 | |
| storage_path | VARCHAR(512) | 是 | — | UPLOAD_DIR 下相对路径 | F-012 | |
| status | VARCHAR(16) | 是 | `processing` | enabled / disabled / failed / processing | F-012、F-013 | |
| created_at | DATETIME | 是 | utcnow | 上传时间 | platform | |
| updated_at | DATETIME | 是 | utcnow | 状态变更时间 | F-013 | |

### knowledge_chunks

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 切片主键 | F-012 | PK |
| document_id | INTEGER | 是 | — | 所属文档 | F-012 | FK knowledge_documents.id |
| chunk_index | INTEGER | 是 | — | 文档内顺序 | F-012 | UNIQUE(document_id, chunk_index) |
| content | TEXT | 是 | — | 切片正文 | F-012 | CHUNK_SIZE |
| embedding | BLOB | 否 | NULL | 向量，维度 EMBEDDING_DIMENSIONS | F-004、F-012 | failed 可为空 |

### qa_pairs

| 字段 | 类型 | 必填 | 默认值 | 业务含义 | 来源 Feature/AC | 约束 |
|---|---|---|---|---|---|---|
| id | INTEGER | 是 | 自增 | 问答主键 | F-012、F-004 / AC-F004-02 | PK |
| document_id | INTEGER | 是 | — | 所属文档 | F-012 | FK knowledge_documents.id |
| question | TEXT | 是 | — | 标准问 | F-004 / BR-002 | |
| answer | TEXT | 是 | — | 标准答 | F-004 / BR-002 | |
| embedding | BLOB | 否 | NULL | 问句向量 | F-004 | |

### knowledge_chunks_fts

SQLite FTS5 虚表，内容列 `content`，外键列 `chunk_id` 对齐 `knowledge_chunks.id`。来源 F-012 / F-004 关键词召回。不单独作为 ORM 业务实体对外暴露。

## 4. 关系与约束

- `sessions.account_id` → `accounts.id`
- `tickets.requester_id` → `accounts.id`
- `messages.ticket_id` → `tickets.id`（无工单不得有消息）
- `suggestions.ticket_id` → `tickets.id`
- `knowledge_chunks.document_id` / `qa_pairs.document_id` → `knowledge_documents.id`
- `accounts.account` UNIQUE；`sessions.token_hash` UNIQUE
- 工单状态只允许 tech-spec 状态机迁移；`closed` 不得改 `category`、不得再插 `messages`（除历史已有）
- 答疑检索 JOIN 文档时必须 `knowledge_documents.status = 'enabled'`
- 并发：接入 `pending`→`in_progress` 用单行更新条件 `status='pending'`，0 行则按幂等或 CONFLICT 处理

## 5. 索引与查询依据

| 索引 | 服务查询 | 来源 Feature/AC | 原因 |
|---|---|---|---|
| ix_tickets_requester_updated | 我的咨询列表 | F-005 / AC-F005-01 | requester_id + updated_at DESC |
| ix_tickets_status_updated | 坐席队列 | F-007 / AC-F007-01 | status + updated_at |
| ix_messages_ticket_created | 详情与短期记忆 | F-005、F-004 | ticket_id + created_at |
| ix_suggestions_ticket_created | 最近建议 | F-009 | ticket_id + created_at DESC |
| ix_knowledge_documents_status | 列表与检索过滤 | F-012、F-013 | status |
| ix_knowledge_chunks_document | 切片加载 | F-012 | document_id |

## 6. 数据迁移与兼容性

- 初始建表：SQLAlchemy `create_all` + 创建 FTS5 虚表与切片同步触发器或应用层双写
- 变更策略：MVP 无历史库，允许重建
- 回滚边界：删除 `backend/data/service_robot.db` 与 `backend/data/uploads/` 即回到空库；不提供向下迁移脚本
