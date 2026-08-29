# API 契约

> 接口技术形态以 `docs/tech-spec.md` §3 为权威。本文补齐 Feature / AC 追踪、鉴权、幂等、数据影响与完整示例。编号沿用 tech-spec。Mock、前端类型、后端模型与测试均以本文为契约来源。

## 通用约定

### 信封

成功与失败均返回：

```json
{
  "code": 200,
  "message": "ok",
  "data": {}
}
```

- 成功：HTTP 200（或 201 仅当明确创建且 tech-spec 未另定时仍用 200，与 pycore `success_response` 一致），`code` 为 `200`，`data` 为业务对象或 `null`。
- 失败：HTTP 与信封 `code` 同时正确；`data` 为 `null`。

| 信封 code | HTTP | 含义 |
|---|---|---|
| 200 | 200 | 成功 |
| VALIDATION_ERROR | 400 | 参数验证失败 |
| UNAUTHORIZED | 401 | 未认证或凭证错误 |
| FORBIDDEN | 403 | 无权查看该资源 |
| NOT_FOUND | 404 | 资源不存在（含「员工看他人工单」对外视为不存在） |
| CONFLICT | 409 | 状态不允许该动作 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |

### 分页

列表成功时使用 `paginated_response`，`data` 形如：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0
}
```

页码从 1 起。工单列表默认 `TICKET_LIST_PAGE_SIZE`，知识列表默认 `KNOWLEDGE_LIST_PAGE_SIZE`。

### 鉴权

除注册、登录外，均需 `Authorization: Bearer <token>`。依赖 `get_current_user`。过期或无效 token → `UNAUTHORIZED`。

### 幂等

- 登录：每次成功签发新 session（旧 token 仍有效至过期，不强制踢下线）。
- 转人工：已是 `pending` / `in_progress` → `CONFLICT`，不创建第二张工单。
- 接入：已是 `in_progress` → 200 返回当前详情，不重复改状态。
- 结单：已是 `closed` → 200 返回当前摘要。
- 启停：对已是目标状态的文档再提交同一 `enabled` → 200 返回当前文档。

### 时间、枚举、空值

- 时间：UTC ISO-8601，例如 `2026-08-29T06:12:00Z`
- 工单状态：`ai_assisting` | `pending` | `in_progress` | `closed`
- 发送者：`employee` | `system` | `agent`
- 分类：`IT-网络` | `IT-账号` | `行政-工牌` | `行政-场地` 或 `null`
- 知识状态：`enabled` | `disabled` | `failed` | `processing`
- `qa_result_type`：`direct_answer` | `clarification` | `generated_answer` | `degraded` | `none`
- JSON `null` 表示无值；禁止省略必填键

### 无 API 说明

| AC | 说明 |
|---|---|
| AC-F001-03 | 工作台 `meta.requiresAuth` 路由守卫纯前端（无 token 跳转 `/login`）；无独立鉴权接口。与 AC-F003-02 同一守卫 |
| AC-F003-01 | 顶栏切换为前端路由；身份展示依赖 API-F001-03 |
| AC-F003-02 | 路由守卫纯前端（无 token 跳转 `/login`）；工作台数据接口仍返回 401 |
| AC-F011-02 | 不提供重开工单接口；已完结只能保持 `closed`（API-F011-01 幂等不回退） |

---

## API-F002-01 本地账号注册

- 来源 Feature：F-002
- 覆盖 AC：AC-F002-01、AC-F002-02
- 业务动作：尚未有账号的人创建可登录账号
- Method / Path：POST `/api/auth/register`
- 权限：公开
- 幂等性：同一 `account` 第二次调用返回 CONFLICT，不覆盖原账号

### 请求

- Body：`AuthRegisterRequest`

```json
{
  "account": "wang.li",
  "password": "pass-word-6"
}
```

约束：`account` 长度 3～64；`password` 长度 6～128。

### 成功响应

- HTTP 200

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "account": "wang.li",
    "display_name": "wang.li"
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 账号名已被占用 | 409 | CONFLICT | `{"code":"CONFLICT","message":"该账号名已被占用","data":null}` |
| 长度不合法 | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"参数验证失败","data":null}` |

### 数据影响

- 创建实体：accounts
- 状态变化：无

---

## API-F001-01 用户登录

- 来源 Feature：F-001
- 覆盖 AC：AC-F001-01、AC-F001-02
- 业务动作：提交凭证获得登录状态
- Method / Path：POST `/api/auth/login`
- 权限：公开
- 幂等性：每次成功新建 sessions 行

### 请求

```json
{
  "account": "wang.li",
  "password": "pass-word-6"
}
```

### 成功响应

- HTTP 200

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "token": "8f3c1a2b9d0e4c6a7b8c9d0e1f2a3b4c",
    "user": {
      "id": 1,
      "account": "wang.li",
      "display_name": "王丽"
    }
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 账号或密码不正确 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"账号或密码不正确","data":null}` |

### 数据影响

- 读取实体：accounts
- 创建实体：sessions

---

## API-F001-02 退出登录

- 来源 Feature：F-001
- 覆盖 AC：无独立 AC（支持退出后需重新登录，配合 AC-F001-03）
- 业务动作：作废当前 token
- Method / Path：POST `/api/auth/logout`
- 权限：已登录
- 幂等性：重复退出已失效 token → UNAUTHORIZED

### 请求

- Header：`Authorization: Bearer <token>`
- Body：无

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": null
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 未登录或 token 无效 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 修改实体：删除对应 sessions 行

---

## API-F001-03 当前用户

- 来源 Feature：F-001、F-003
- 覆盖 AC：AC-F001-01、AC-F003-01
- 业务动作：读取当前登录身份供顶栏展示
- Method / Path：GET `/api/auth/me`
- 权限：已登录

### 请求

- Header：`Authorization: Bearer <token>`

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "account": "wang.li",
    "display_name": "王丽"
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 未登录 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 读取实体：accounts、sessions

---

## API-F005-01 我的咨询列表

- 来源 Feature：F-005
- 覆盖 AC：AC-F005-01
- 业务动作：列出当前用户自己的工单
- Method / Path：GET `/api/tickets/mine`
- 权限：已登录

### 请求

- Query：`page`（默认 1）、`page_size`（默认 20，最大 100）

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 12,
        "title": "VPN 连不上公司内网",
        "status": "in_progress",
        "category": "IT-网络",
        "created_at": "2026-08-29T06:00:00Z",
        "updated_at": "2026-08-29T06:12:00Z"
      },
      {
        "id": 8,
        "title": "工牌补办要找谁",
        "status": "closed",
        "category": "行政-工牌",
        "created_at": "2026-08-28T01:40:00Z",
        "updated_at": "2026-08-28T02:10:00Z"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total_items": 2
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 未登录 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 读取实体：tickets（仅 requester_id = 当前用户）

---

## API-F005-02 工单详情

- 来源 Feature：F-005、F-007、F-008
- 覆盖 AC：AC-F005-01、AC-F005-02、AC-F005-03、AC-F007-01、AC-F008-03
- 业务动作：打开一条咨询的全程消息
- Method / Path：GET `/api/tickets/{ticket_id}`
- 权限：已登录；员工仅本人工单；坐席可读 pending / in_progress（他人工单若为 ai_assisting 则 NOT_FOUND）

### 请求

- Path：`ticket_id` integer

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 12,
    "title": "VPN 连不上公司内网",
    "status": "in_progress",
    "category": "IT-网络",
    "created_at": "2026-08-29T06:00:00Z",
    "updated_at": "2026-08-29T06:12:00Z",
    "requester": {
      "id": 1,
      "account": "wang.li",
      "display_name": "王丽"
    },
    "messages": [
      {
        "id": 101,
        "sender_type": "employee",
        "content": "公司 VPN 连不上，提示认证失败。",
        "created_at": "2026-08-29T06:00:01Z"
      },
      {
        "id": 102,
        "sender_type": "system",
        "content": "请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。",
        "created_at": "2026-08-29T06:00:08Z"
      }
    ]
  }
}
```

`messages` 不含 suggestions。已完结工单仍返回全部历史消息，`status` 为 `closed`。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 不存在或不对员工展示 | 404 | NOT_FOUND | `{"code":"NOT_FOUND","message":"资源不存在","data":null}` |
| 未登录 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 读取实体：tickets、messages、accounts

---

## API-F004-01 发送员工消息并答疑

- 来源 Feature：F-004、F-005、F-007
- 覆盖 AC：AC-F004-01、AC-F004-02、AC-F004-03、AC-F004-04、AC-F004-05、AC-F005-02、AC-F005-03、AC-F007-02
- 业务动作：员工发送问题（新开或续聊）；AI 接待中走答疑链路
- Method / Path：POST `/api/tickets/messages`
- 权限：已登录员工（当前用户为 requester）
- 幂等性：每次调用追加新消息，不合并

### 请求

```json
{
  "content": "公司 VPN 连不上，提示认证失败。",
  "ticket_id": null
}
```

续聊时 `ticket_id` 为已有本人工单 ID。

### 成功响应（新开且反问）

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "ticket": {
      "id": 12,
      "title": "公司 VPN 连不上，提示认证失败。",
      "status": "ai_assisting",
      "category": null,
      "created_at": "2026-08-29T06:00:00Z",
      "updated_at": "2026-08-29T06:00:08Z"
    },
    "employee_message": {
      "id": 101,
      "sender_type": "employee",
      "content": "公司 VPN 连不上，提示认证失败。",
      "created_at": "2026-08-29T06:00:01Z"
    },
    "system_message": {
      "id": 102,
      "sender_type": "system",
      "content": "请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。",
      "created_at": "2026-08-29T06:00:08Z"
    },
    "qa_result_type": "clarification"
  }
}
```

`pending` / `in_progress` 时 `system_message` 为 `null`，`qa_result_type` 为 `none`。降级时 `qa_result_type` 为 `degraded`，`system_message.content` 为 `DEGRADED_QA_MESSAGE`。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 已完结再发 | 409 | CONFLICT | `{"code":"CONFLICT","message":"已完结，不能再发送","data":null}` |
| 非本人工单 | 404 | NOT_FOUND | `{"code":"NOT_FOUND","message":"资源不存在","data":null}` |
| 空内容 | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"参数验证失败","data":null}` |
| 未登录 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 创建实体：tickets（新开时）、messages（员工；AI 接待中另创系统消息）
- 修改实体：accounts.profile_json（每轮规则抽取）；tickets.updated_at
- 读取实体：qa_pairs、knowledge_chunks、knowledge_documents（仅 enabled）
- 状态变化：新开 → `ai_assisting`

---

## API-F006-01 转人工

- 来源 Feature：F-006
- 覆盖 AC：AC-F006-01、AC-F006-03
- 业务动作：AI 接待中工单转为待处理
- Method / Path：POST `/api/tickets/{ticket_id}/transfer`
- 权限：已登录且为 requester
- 幂等性：非 `ai_assisting` → CONFLICT

### 请求

- Path：`ticket_id`
- Body：无

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 12,
    "title": "VPN 连不上公司内网",
    "status": "pending",
    "category": null,
    "created_at": "2026-08-29T06:00:00Z",
    "updated_at": "2026-08-29T06:05:00Z"
  }
}
```

同时写入一条 `sender_type=system` 的消息，内容为 `TRANSFER_SUCCESS_MESSAGE`。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 已完结 | 409 | CONFLICT | `{"code":"CONFLICT","message":"已完结，不能转人工","data":null}` |
| 已在人工流程 | 409 | CONFLICT | `{"code":"CONFLICT","message":"已在人工流程中","data":null}` |
| 非本人工单 | 404 | NOT_FOUND | `{"code":"NOT_FOUND","message":"资源不存在","data":null}` |

### 数据影响

- 修改实体：tickets.status `ai_assisting` → `pending`
- 创建实体：messages（系统提示）

---

## API-F007-01 坐席工单队列

- 来源 Feature：F-007、F-006
- 覆盖 AC：AC-F007-01、AC-F006-02
- 业务动作：列出待处理或处理中工单（不含 AI 接待中）
- Method / Path：GET `/api/tickets/agent-queue`
- 权限：已登录

### 请求

- Query：`status` 必填，`pending` 或 `in_progress`；`page`；`page_size`

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 12,
        "title": "VPN 连不上公司内网",
        "status": "pending",
        "requester": {
          "id": 1,
          "account": "wang.li",
          "display_name": "王丽"
        },
        "waiting_minutes": 12,
        "updated_at": "2026-08-29T06:05:00Z"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total_items": 1
  }
}
```

不得出现 `status=ai_assisting` 的工单。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| status 非法 | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"参数验证失败","data":null}` |
| 未登录 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 读取实体：tickets、accounts

---

## API-F007-02 接入工单

- 来源 Feature：F-007
- 覆盖 AC：AC-F007-01、AC-F007-03
- 业务动作：待处理 → 处理中
- Method / Path：POST `/api/tickets/{ticket_id}/accept`
- 权限：已登录
- 幂等性：已 `in_progress` 返回当前 TicketDetail

### 请求

- Path：`ticket_id`
- Body：无

### 成功响应

- HTTP 200，`data` 为 `TicketDetail`（结构同 API-F005-02），`status` 为 `in_progress`。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 已完结或仍为 AI 接待中 | 409 | CONFLICT | `{"code":"CONFLICT","message":"当前状态不可接入","data":null}` |
| 不存在 | 404 | NOT_FOUND | `{"code":"NOT_FOUND","message":"资源不存在","data":null}` |

### 数据影响

- 修改实体：tickets.status `pending` → `in_progress`

---

## API-F008-01 坐席回复

- 来源 Feature：F-008
- 覆盖 AC：AC-F008-01、AC-F008-02
- 业务动作：向处理中工单写入坐席消息
- Method / Path：POST `/api/tickets/{ticket_id}/agent-replies`
- 权限：已登录
- 幂等性：每次追加新消息

### 请求

```json
{
  "content": "已为你重置了 VPN 口令，请用邮件里的新密码再试。"
}
```

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 110,
    "sender_type": "agent",
    "content": "已为你重置了 VPN 口令，请用邮件里的新密码再试。",
    "created_at": "2026-08-29T06:20:00Z"
  }
}
```

员工再调 API-F005-02 可见该消息。建议未通过本接口发出前不会出现在 messages。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 已完结 | 409 | CONFLICT | `{"code":"CONFLICT","message":"已完结，不能再发送","data":null}` |
| 仍为待处理 | 409 | CONFLICT | `{"code":"CONFLICT","message":"请先接入后再回复","data":null}` |
| 空内容 | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"参数验证失败","data":null}` |

### 数据影响

- 创建实体：messages（agent）
- 修改实体：tickets.updated_at

---

## API-F009-01 智能回答建议

- 来源 Feature：F-009
- 覆盖 AC：AC-F009-01、AC-F009-02、AC-F009-03
- 业务动作：为处理中工单生成仅坐席可见的建议
- Method / Path：POST `/api/tickets/{ticket_id}/suggestions`
- 权限：已登录
- 幂等性：每次生成新 suggestions 行

### 请求

```json
{
  "focus_message_id": null
}
```

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 3,
    "content": "请确认是否使用公司门户的 VPN 客户端，并尝试忘记密码后用邮箱验证码重置。",
    "result_type": "generated_answer",
    "created_at": "2026-08-29T06:18:00Z"
  }
}
```

外部失败时 `result_type` 为 `degraded`，`content` 为 `DEGRADED_SUGGESTION_MESSAGE`。不创建 messages。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 非处理中 | 409 | CONFLICT | `{"code":"CONFLICT","message":"仅处理中可获取建议","data":null}` |
| 工单不存在 | 404 | NOT_FOUND | `{"code":"NOT_FOUND","message":"资源不存在","data":null}` |

### 数据影响

- 创建实体：suggestions
- 读取实体：messages、accounts、qa_pairs、knowledge_chunks、knowledge_documents

---

## API-F010-01 工单分类

- 来源 Feature：F-010
- 覆盖 AC：AC-F010-01、AC-F010-02
- 业务动作：为未完结工单写入分类
- Method / Path：PUT `/api/tickets/{ticket_id}/category`
- 权限：已登录
- 幂等性：重复写入同一分类返回当前摘要

### 请求

```json
{
  "category": "IT-网络"
}
```

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 12,
    "title": "VPN 连不上公司内网",
    "status": "in_progress",
    "category": "IT-网络",
    "created_at": "2026-08-29T06:00:00Z",
    "updated_at": "2026-08-29T06:21:00Z"
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 已完结 | 409 | CONFLICT | `{"code":"CONFLICT","message":"已完结不能改分类","data":null}` |
| 非法分类 | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"参数验证失败","data":null}` |

### 数据影响

- 修改实体：tickets.category

---

## API-F011-01 结单

- 来源 Feature：F-011
- 覆盖 AC：AC-F011-01、AC-F011-02、AC-F011-03
- 业务动作：处理中 → 已完结
- Method / Path：POST `/api/tickets/{ticket_id}/close`
- 权限：已登录
- 幂等性：已 closed 返回当前摘要；无重开接口（AC-F011-02 无 API）

### 请求

- Path：`ticket_id`
- Body：无

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 12,
    "title": "VPN 连不上公司内网",
    "status": "closed",
    "category": "IT-网络",
    "created_at": "2026-08-29T06:00:00Z",
    "updated_at": "2026-08-29T06:30:00Z"
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 待处理未接入 | 409 | CONFLICT | `{"code":"CONFLICT","message":"未接入不能结单","data":null}` |
| 仍为 AI 接待中 | 409 | CONFLICT | `{"code":"CONFLICT","message":"当前状态不可结单","data":null}` |

### 数据影响

- 修改实体：tickets.status → `closed`

无 API：不提供重开工单接口（AC-F011-02）。

---

## API-F012-01 上传 Markdown 入库

- 来源 Feature：F-012
- 覆盖 AC：AC-F012-01、AC-F012-02、AC-F012-03
- 业务动作：上传 .md 并切块、向量化、抽标准问答
- Method / Path：POST `/api/knowledge_documents`
- 权限：已登录
- 请求：`multipart/form-data` 字段 `file`

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 3,
    "filename": "VPN接入说明.md",
    "status": "enabled",
    "updated_at": "2026-08-28T10:20:00Z"
  }
}
```

处理失败时 `status` 为 `failed`，HTTP 仍可为 200（文档已记录）或 500 INTERNAL_ERROR（未落盘）；实现必须与「失败文档不得 enabled」一致：若已插入行则返回 200 且 `status=failed`。

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 非 Markdown | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"仅支持 Markdown","data":null}` |
| 超过大小 | 400 | VALIDATION_ERROR | `{"code":"VALIDATION_ERROR","message":"参数验证失败","data":null}` |

### 数据影响

- 创建实体：knowledge_documents、knowledge_chunks、qa_pairs、FTS 行；磁盘 UPLOAD_DIR 文件

---

## API-F012-02 知识文档列表

- 来源 Feature：F-012、F-013
- 覆盖 AC：AC-F012-01、AC-F013-03
- 业务动作：列出全部文档含停用与失败
- Method / Path：GET `/api/knowledge_documents`
- 权限：已登录

### 请求

- Query：`page`、`page_size`

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "filename": "VPN接入说明.md",
        "status": "enabled",
        "updated_at": "2026-08-28T10:20:00Z"
      },
      {
        "id": 2,
        "filename": "工牌补办流程.md",
        "status": "disabled",
        "updated_at": "2026-08-27T03:05:00Z"
      }
    ],
    "page": 1,
    "page_size": 50,
    "total_items": 2
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| 未登录 | 401 | UNAUTHORIZED | `{"code":"UNAUTHORIZED","message":"未认证","data":null}` |

### 数据影响

- 读取实体：knowledge_documents

---

## API-F013-01 启用或停用知识文档

- 来源 Feature：F-013
- 覆盖 AC：AC-F013-01、AC-F013-02
- 业务动作：整篇启用或停用
- Method / Path：PATCH `/api/knowledge_documents/{document_id}`
- 权限：已登录
- 幂等性：已是目标状态则返回当前文档

### 请求

```json
{
  "enabled": false
}
```

### 成功响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 2,
    "filename": "工牌补办流程.md",
    "status": "disabled",
    "updated_at": "2026-08-29T07:00:00Z"
  }
}
```

### 失败响应

| 场景 | HTTP | 业务错误码 | 返回内容 |
|---|---|---|---|
| failed / processing | 409 | CONFLICT | `{"code":"CONFLICT","message":"未生效文档不能启停","data":null}` |
| 不存在 | 404 | NOT_FOUND | `{"code":"NOT_FOUND","message":"资源不存在","data":null}` |

### 数据影响

- 修改实体：knowledge_documents.status（enabled ⇄ disabled）；不删切片与 qa_pairs

答疑侧 AC-F013-01 / AC-F013-02 的检索效果由 API-F004-01、API-F009-01 在后续提问中体现。
