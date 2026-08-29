# 测试报告：T-014 F-012 上传 Markdown 入库闭环

**测试时间**：2026-08-29 23:28 (UTC+8)
**Tester Agent ID**：tester-T-014-20260829-r3

## 结果：PASS

本轮为第三次派出（前两轮无报告）。未安装 Playwright / Chromium；页面项以静态对照 + `VITE_USE_MOCK=false` 下 Vite 代理真实 API 判定。未清空运行时业务库，未复述密钥。

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F012-01] 上传合法 .md 且处理成功，列表出现且状态为启用 | PASS | 本轮运行时 `DASHSCOPE_API_KEY` **已配置**（非空、非 `.env.example` 占位）。直连 `POST http://127.0.0.1:8099/api/knowledge_documents` 上传合法 `.md`，HTTP 200，`data.status=enabled`，随后 `GET` 列表出现该文档且为启用。库内写入 `knowledge_chunks` / `qa_pairs`（embedding 非空）并同步 FTS。后端日志：Embedding HTTP 200 后标记启用。编排清单曾写 fallback/未提供，**以本轮独立复查为准**；不把「缺 Key」当作本轮事实。 |
| 2 | [AC-F012-02] 上传非 Markdown，页面提示仅支持 Markdown，列表不出现该文件为启用 | PASS | 页面 `KnowledgePage.vue` 在非 `.md` 时拦截，文案为原型全文「仅支持 Markdown，该文件未入库。」，不调用上传 API。后端契约路径：`POST` `notes.txt` → HTTP 400，`code=VALIDATION_ERROR`，`message=仅支持 Markdown`；随后列表无 `notes.txt`，更无为启用。 |
| 3 | [AC-F012-03] 入库失败时文档不得显示为启用 | PASS | pytest：`dashscope_api_key=""` 与 `EmbeddingError` 均 HTTP 200 且 `status=failed`，列表与库均非 enabled。运行时库既有失败行（id=1～7）列表字段为 `failed`。前端 `statusLabel`：`failed`/`processing` 显示「未生效」（非「启用」），开关 Disabled 且未勾选。 |
| 4 | 页面布局与 docs/prototypes/knowledge.html 一致 | PASS | 静态对照 `KnowledgePage.vue` + `AppHeader.vue` + `styles.css`：顶栏品牌/三端导航/退出 32px；工具条「上传 Markdown」+「仅支持 .md」；空态「还没有知识文档。请上传 Markdown。」；表头「文档名称 / 状态 / 更新时间 / 启用」；开关 52×32px、圆角 8px。失败提示与 ui-design-spec「入库未生效」一致。无原型外可见块、无 `[Mock]`。 |
| 5 | VITE_USE_MOCK=false 时上传与列表命中真实后端 API，页面无 [Mock] | PASS | 前端以 `VITE_USE_MOCK=false` 启动 5199。`GET/POST http://127.0.0.1:5199/api/knowledge_documents` 经 Vite 代理返回与 8099 相同契约信封（本轮代理上传亦 `status=enabled`）。`knowledgeService.ts` 在 `isMockEnabled()===false` 时走 `api.get/post('/knowledge_documents')`。`/knowledge` HTML 与源码无 `[Mock]`。 |

## technicalChecks

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | pytest backend/tests/features/f012 --timeout=300 | PASS | 项目 `.venv` Python 3.14：`12 passed, 1 skipped`（`test_real_embedding_optional` 因未设 `REAL_API_TEST` 跳过）。`pytest-timeout` 在位。夹具为 `tmp_path` 库 + 独立 `UPLOAD_DIR` + `dependency_overrides[get_db]`，未 `drop_all` 运行时库。 |
| 2 | Typecheck passes | PASS | 后端抽检 T-014 文件 `mypy` Success；前端 `npm run type-check` 退出码 0。 |
| 3 | Lint passes | PASS | 后端抽检 `ruff check` All checks passed；前端 `npm run lint` 退出码 0。 |
| 4 | VITE_USE_MOCK=false 时 knowledge 不走 Mock | PASS | 见验收第 5 条；`isMockEnabled()` 仅当 `VITE_USE_MOCK!=='false'` 才走 `mocks/knowledge`。 |
| 5 | Embedding Key 与失败文档 | PASS | **本轮 Key 已配置**，入库走真实 Embedding（HTTP 200），故 AC-F012-01 按成功启用验收，**不宣称「缺 Key 降级」**。失败路径仍由 pytest 与既有 `failed` 行覆盖。报告不写密钥原文。 |
| 6 | config 键从 backend/.env 读取，未硬编码密钥 | PASS | `AppSettings.dashscope_api_key` / `EMBEDDING_*` 由 `backend/.env` 加载；代码仅有 example 占位集合。`.sdd` / `docs` / experience 未见密钥泄露。`httpx.AsyncClient(trust_env=settings.http_client_trust_env)`，默认 `false`。无 dashscope SDK、无裸 `httpx.post`。 |
| 7 | 外部失败有清晰错误处理 | PASS | Key 空/占位或 HTTP/超时报 `EmbeddingError`，入库 `mark_status(failed)` 且打 error 日志；前端失败展示「入库未生效」。不静默标 enabled。 |

## frontendIntegration / mockExitCriteria

| # | 项 | 结果 | 说明 |
|---|----|------|------|
| 1 | pages /knowledge | PASS | 路由 `meta.requiresAuth: true`；页面绑定 store 上传与列表。 |
| 2 | POST/GET /api/knowledge_documents 真实命中 | PASS | 8099 直连 + 5199 代理均 200 契约信封。 |
| 3 | processing 可轮询 | PASS | `useKnowledgeStore.pollUntilSettled` 在 `status==='processing'` 时按秒刷新列表。本轮同步返回 enabled，未长时间停留 processing。 |
| 4 | Vite 代理 | PASS | `vite.config.ts`：`/api` → `VITE_BACKEND_PROXY_TARGET`（默认 8099）；`frontend/.env` 中 `VITE_API_BASE_URL=/api`。 |
| 5 | CORS 四 origin | PASS | `backend/src/core/config.py` 含 5199/5175 的 localhost 与 127.0.0.1。 |

## 外部服务

| 服务 | 配置状态 | 本轮调用 | 可否宣称完整联调 |
|---|---|---|---|
| 百炼 Text Embedding | **Key 已配置**（非占位） | 运行时入库日志 Embedding HTTP 200；文档 id=8/9 `status=enabled`，切片/问答 embedding 已落盘 | 本轮上传成功路径已打到真实 Embedding HTTP 200。编排 `external_services.status=fallback` 与运行时不符；**以独立证据为准**。未打印 Key。 |

缺 Key 降级路径（pytest + 历史 failed 行）已验证，不替代本轮成功启用证据。

## 验证证据摘要

- 后端：本轮启动 `uvicorn` `127.0.0.1:8099`（项目 `.venv`；`PYTHONPATH` 指向项目根）。8099 曾被旧进程占用后已释放，本轮进程与当前代码一致。
- 前端：`VITE_USE_MOCK=false`，`npm run dev -- --host 127.0.0.1 --port 5199`。
- 登录：预置账号 `wang.li`（未清空业务库；token 已脱敏）。
- pytest 后复查运行时库：表仍在，`accounts` 仍有记录，知识表未被测试夹具清空。
- 浏览器：未安装 Chromium；未跑 Playwright。可判定项已由静态 + httpx 完成。
- 验证后已停止本轮启动的前后端进程。

## 代码核对（独立打开）

- `backend/src/models/knowledge.py`：契约 DTO，无 `storage_path`
- `backend/src/repositories/knowledge.py`：文档/切片/QA 写入
- `backend/src/services/embedding.py`：httpx 直调，缺 Key/失败抛 `EmbeddingError`
- `backend/src/services/knowledge.py`：非 md 拒绝；失败 `failed`；成功 `enabled`
- `backend/src/api/routes/knowledge_documents.py`：POST/GET 需 `get_current_user`
- `backend/src/api/deps.py`：`get_db` 来自 `src.db.session`；校验错误转信封
- `backend/tests/features/f012/{conftest,test_upload,test_failed}.py`：隔离库
- `frontend/src/services/knowledgeService.ts`、`frontend/src/stores/useKnowledgeStore.ts`、`frontend/src/pages/KnowledgePage.vue`
- `.sdd/experience.md`：T-014 条目无密钥泄露

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `frontend/.env` 默认仍为 `VITE_USE_MOCK=true`；本轮用启动环境变量覆盖 | frontend env | 用户门禁须显式 `VITE_USE_MOCK=false` 并重启 Vite |
| 2 | `tasks.json` 写 `frontend/src/services/knowledge.ts` / `stores/knowledge.ts`，仓库实际为 `knowledgeService.ts` / `useKnowledgeStore.ts` | Planner 路径 | 不挡验收 |
| 3 | 编排 `external_services` 仍标 Embedding `fallback`，与本轮运行时 Key 已配置不一致 | 任务清单 | 以 `.env` 实际状态为准，勿用过期 fallback 覆盖成功证据 |
