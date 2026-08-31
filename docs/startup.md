# 启动文档：智能客服系统（service_robot）

规范集：`specification: default`。主路径对照 `docs/prototypes/index.html`（登录默认 → 员工咨询 → 坐席接待 → 知识维护）。本轮不含 F-014～F-019。

本文只记录字段名、端口、命令与配置状态，**不写入真实 Key / Token / Secret**。敏感值只允许出现在 `backend/.env`、`frontend/.env` 或 `frontend/.env.local`。

## 1. 环境要求

- Python 3.11+（本机可用 `python`；无 `python3` / `python3.11` 时一律用 `python`）
- Node.js + npm（前端在 `frontend/` 下安装与启动）
- 项目根目录与 `backend/`、`frontend/` 并列；`pycore/` 通过 `PYTHONPATH` 引入，禁止 pip 安装 pycore
- SQLite 业务库落点：`backend/data/service_robot.db`；上传目录：`backend/data/uploads/`

## 2. 端口（`shared/env-policy.md`）

| 用途 | 前端 | 后端 |
|---|---|---|
| Agent 自动开发 / Tester 自动验证 | **5199** | **8099** |
| 用户门禁验收 | **5175** | **8003** |

不得默认占用 `8000` / `5173`。前端代码只使用相对路径 `/api`、`/ws`；后端目标端口只出现在 Vite 代理或启动命令中。

后端 CORS 已允许：

- `http://localhost:5199`、`http://127.0.0.1:5199`
- `http://localhost:5175`、`http://127.0.0.1:5175`

## 3. 后端 `.env`（`backend/.env`）

复制 `backend/.env.example` 为 `backend/.env` 后填写。`.env` 已加入 `.gitignore`，**不得入库**。

| 字段名 | 配置状态写法 |
|---|---|
| `SECRET_KEY` | 必填，无默认；已配置于 `backend/.env` |
| `DASHSCOPE_API_KEY` | 百炼统一 Key；已配置于 `backend/.env`，或为占位/空（此时仅能降级） |
| `DATABASE_PATH` | 默认 `data/service_robot.db`（相对 `backend/`） |
| `UPLOAD_DIR` | 默认 `data/uploads` |
| `HOST` | 默认 `127.0.0.1` |
| `PORT` | Agent 默认 `8099`；用户门禁启动时改为 `8003` |
| `CORS_ORIGINS` | 含 5199 与 5175 的 localhost / 127.0.0.1 |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TIMEOUT_SECONDS` / `LLM_TEMPERATURE_*` | 对话；字段存在于 `.env.example` |
| `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` / `EMBEDDING_TIMEOUT_SECONDS` / `EMBEDDING_DIMENSIONS` | 向量化 |
| `RERANK_BASE_URL` / `RERANK_MODEL` / `RERANK_TIMEOUT_SECONDS` | 重排 |
| `HTTP_CLIENT_TRUST_ENV` | 必须为 `false` |
| `DEGRADED_QA_MESSAGE` | 答疑降级文案 |
| `DEGRADED_SUGGESTION_MESSAGE` | 建议降级文案 |
| `TRANSFER_SUCCESS_MESSAGE` | 转人工成功提示 |
| 其余长度/分页/检索阈值 | 与 `docs/tech-spec.md` §4 一致，可用 example 默认值 |

禁止把真实 Key 写进本文件、`.sdd/`、测试报告或经验。说明配置时写成「`DASHSCOPE_API_KEY`：已配置于 `backend/.env`」或「字段存在，未打印值」。

## 4. 前端 `.env`（`frontend/.env`）

复制 `frontend/.env.example`。开发环境禁止把 `VITE_API_BASE_URL` 写成完整后端 URL。

| 字段名 | 默认 / 要点 |
|---|---|
| `VITE_API_BASE_URL` | `/api`（相对路径，走 Vite 代理） |
| `VITE_BACKEND_PROXY_TARGET` | Agent 默认 `http://localhost:8099`；用户门禁改为 `http://localhost:8003` |
| `VITE_AXIOS_TIMEOUT_MS` | `30000` |
| `VITE_USE_MOCK` | 本地 Mock 开发可为 `true`；**全链路联调与用户门禁必须 `VITE_USE_MOCK=false`**，使 `/login` `/employee` `/agent` `/knowledge` 命中真实后端 API |

修改 `vite.config.ts` 或 `.env` 后必须重启 Vite。

## 5. 启动命令

以下在**项目根** `Projects_Repo/service_robot` 下执行。PowerShell 不能使用 `PYTHONPATH=.. cmd` 这种 Unix 前缀，需先赋值环境变量。

### 5.1 依赖

```powershell
python -m pip install -r backend/requirements.txt
cd frontend
npm install
```

### 5.2 初始化数据库（可选；uvicorn 启动也会经 lifespan 幂等执行）

```powershell
cd backend
$env:PYTHONPATH = (Resolve-Path ..).Path
python scripts/init_db.py
```

`init_db` 会建表并幂等预置契约示例账号（与 `docs/api-contracts.md` / Mock 同名），不覆盖已有密码。

### 5.3 Agent / Tester 端口（前端 5199 / 后端 8099）

后端：

```powershell
cd backend
$env:PYTHONPATH = (Resolve-Path ..).Path
python -m uvicorn src.main:app --host 127.0.0.1 --port 8099
```

前端（真实联调）：

```powershell
cd frontend
$env:VITE_USE_MOCK = "false"
npm run dev -- --host 127.0.0.1 --port 5199
```

Vite 默认把 `/api` 代理到 `http://localhost:8099`。

### 5.4 用户门禁端口（前端 5175 / 后端 8003）

后端：

```powershell
cd backend
$env:PYTHONPATH = (Resolve-Path ..).Path
python -m uvicorn src.main:app --host 127.0.0.1 --port 8003
```

前端：

```powershell
cd frontend
$env:VITE_USE_MOCK = "false"
$env:VITE_BACKEND_PROXY_TARGET = "http://localhost:8003"
npm run dev -- --host 127.0.0.1 --port 5175
```

POSIX 等价：

```bash
# Agent 后端
cd backend && PYTHONPATH=.. python -m uvicorn src.main:app --host 127.0.0.1 --port 8099
# Agent 前端
cd frontend && VITE_USE_MOCK=false npm run dev -- --host 127.0.0.1 --port 5199
# 用户门禁后端
cd backend && PYTHONPATH=.. python -m uvicorn src.main:app --host 127.0.0.1 --port 8003
# 用户门禁前端
cd frontend && VITE_USE_MOCK=false VITE_BACKEND_PROXY_TARGET=http://localhost:8003 npm run dev -- --host 127.0.0.1 --port 5175
```

## 6. 主路径联调要点（`VITE_USE_MOCK=false`）

对照 `docs/prototypes/index.html` 主路径，按 Plan.md §7：

1. 注册 / 登录（`/login`）
2. 顶栏切换员工 / 坐席 / 知识维护（同一登录，不重新登录）
3. 上传 Markdown 知识（`/knowledge`），默认启用
4. 启停开关：停用后列表仍在，文档与切片不删除
5. 员工提问（`/employee`）
6. 转人工
7. 坐席接入（`/agent`）
8. 获取智能建议：只出现在坐席右栏，**员工消息列表不得出现该建议文本**
9. 坐席回复
10. 分类
11. 结单
12. 双方无法再发；无「重新打开」入口，无 reopen API

各步骤须命中真实后端 `/api/*`，不是 `frontend/src/mocks/`。

## 7. 百炼外部服务（fallback）

完整联调需要 `DASHSCOPE_API_KEY` 可调用 Chat Completions / Embedding / Rerank。`fallback_allowed=true`：

- Key 缺失或为 `.env.example` 占位：入库 `status=failed`；答疑返回 `DEGRADED_QA_MESSAGE`；建议返回 `DEGRADED_SUGGESTION_MESSAGE`
- 调用失败同样走上述降级，不得假装已重排或已生成成功
- **不得宣称百炼 Chat / Embedding / Rerank 完整联调通过**，除非 Tester 在真实 Key 下单独验证对应 Feature（T-014 / T-016 / T-021 等首次联调，本任务不替代）

E2E 套件 `backend/tests/e2e` 对外部 HTTP 使用 monkeypatch，只回归业务主链路与不泄漏约定。

## 8. 部署前检查

- `backend/.env`、`frontend/.env` 不入库（`.gitignore` 已排除）
- `specification: default`
- 无 reopen API、前端无「重新打开」
- 停用知识不删除文档行、切片、问答对或 `UPLOAD_DIR` 原文
- 禁止 `dashscope` SDK；HTTP 客户端 `trust_env=false`
- F-014～F-019 不在本轮范围
