# 项目经验

> 当前项目长期有效的经验。  
> Developer / Tester / Bugfix 在任务完成后维护本文件。

---

## Harness 系统经验摘要

新项目开始时，Developer / Tester / Bugfix 需要同时参考：

- 当前项目经验：`.sdd/experience.md`
- 系统级经验：`<SDD_V6>/memory/harness-experience.md`

---

（项目经验将在开发过程中追加）

### T-001: 登录与注册页 Mock（/login）
- **陷阱**：本机 npm 11 默认 `allow-scripts` 会跳过 `esbuild` 的 postinstall，导致 `vite`/`npm run build` 找不到原生二进制。
- **经验**：Mock 登录成功凭证以 `docs/api-contracts.md` 示例为准（账号 `wang.li`，密码 `pass-word-6`，显示名「王丽」），不要把原型密码框里的 `••••••••` 当成真实密码。登录失败的 401 不能走全局拦截器跳转，否则错误密码也会被踢回登录页并冲掉「账号或密码不正确」。
- **避坑**：前端工程根目录加 `.npmrc`（`ignore-scripts=false`）。登录页文案必须逐字对照 `docs/prototypes/login.html`；`[Mock]` 标识只放在占位工作台，不要改登录卡片文案。Mock handler 必须按 endpoint 显式构造 `token`/`user` 或注册 `UserPublic`，禁止把带 `password` 的内部账号对象直接返回。
- **[SYSTEM] 建议回传系统级经验**：新脚手架在 npm 11+ 下必须允许 `esbuild` install 脚本，否则 Tester 的 `npm run build` 会红。

### T-002: 员工咨询工作台 Mock（/employee）
- **陷阱**：退出接口成功信封 `data` 为 `null`，不能走「code===200 且 data 非 null 才算成功」的 unwrap，否则 Mock 退出会误报失败。
- **经验**：员工列表必须按 `requester_id === 当前用户` 过滤；Mock 内可放他人工单（如 requester_id=99）用于证明隔离。新咨询 `ticket_id=null` 建 `ai_assisting` 单；`qa_result_type` 用关键词覆盖 clarification / direct_answer / generated_answer / degraded。转人工仅 `ai_assisting` 可点，成功后状态条用「待处理 · 已提交，等待对接人」。已完结输入框/发送/转人工均 Disabled。底栏 `flex-wrap: nowrap` + 按钮 `white-space: nowrap`。
- **避坑**：顶栏三端切换用共享 `AppHeader`，坐席/知识页可仍占位，但必须显示当前 `display_name`。员工页文案对齐 `docs/prototypes/employee.html`，不要在顶栏加 `[Mock]`。默认列表保持原型两条（VPN 处理中、工牌已完结）；AI 接待中与降级样例通过「新咨询」发送触发。

### T-003: 坐席接待工作台 Mock（/agent）
- **陷阱**：坐席中栏员工气泡不能复用员工台 `bubble-me`（右对齐主色），应对齐原型左对齐白底描边（`bubble-employee`）。建议文本只进右栏 `suggestions`，Mock handler 不得写入 `messages`。
- **经验**：`GET /tickets/agent-queue` 只接受 `pending` / `in_progress`，内部即使有 `ai_assisting`（如 requester_id=99）也不得出现在列表。接入成功后切到「处理中」并乐观更新当前项，避免待处理列表把当前单滤掉后中栏丢上下文。结单后保留详情以便验收输入框与发送禁用。`SuggestionOut` 显式 DTO 不含 `ticket_id`。
- **避坑**：推断建议时要把工单标题和最近员工消息一起做关键词，否则会议室/投影仪单会误出 VPN 建议。分类在右栏用 select 选中值 + `.tag-cat` 展示。顶栏继续用 `AppHeader`，不要加 `[Mock]`。不要删 `frontend/.npmrc`。

### T-004: 知识维护工作台 Mock（/knowledge）
- **陷阱**：契约示例文件名无空格（`VPN接入说明.md`），原型与 ui-design-spec 表格有空格（`VPN 接入说明.md`）。列表展示必须跟原型，不能照抄契约示例字符串。
- **经验**：上传 / 列表 / 启停三个 endpoint 字段虽同形，仍分别 map `KnowledgeUploadResponse` / `KnowledgeDocumentListItem` / `KnowledgeDocumentStatusResponse`，禁止把带 `storage_path` 的内部实体直接返回。非 `.md` 在页面拦截，提示用原型全文「仅支持 Markdown，该文件未入库。」；Mock 层仍按契约返回 `VALIDATION_ERROR` +「仅支持 Markdown」。默认三条含已停用的工牌行；关开关只改 `status=disabled`，行不消失。时间按 UTC ISO 存、上海时区显示成 `YYYY-MM-DD HH:mm`。
- **避坑**：顶栏继续用 `AppHeader`，不要加 `[Mock]`。开关 52×32px、圆角 8px 已在 `styles.css`，不要另造尺寸。不要改登录 / 员工 / 坐席页。不要删 `frontend/.npmrc`。

### T-005: 后端 pycore 接入与项目骨架
- **陷阱**：本机无 `python3.11`，一律用 `python`（3.14）。pycore `ConfigManager.load()` 目前只认 TOML，不能用来读 `backend/.env`。pycore 的 `integrations/db/session.py` 在 import 时调用 `get_config()`，配置未加载会直接失败。
- **经验**：`backend/src/main.py` 用 `pycore.api.APIServer` + `APIConfig.cors_origins` 注册 CORS（tech-spec §4 四个 origin）；从 `backend/` 启动必须 `PYTHONPATH` 指向项目根以引入 `pycore/`，禁止 pip 安装 pycore。SECRET_KEY 只写入 `backend/.env`。ruff B008 需把 `fastapi.Depends` 列入 `extend-immutable-calls`。mypy 用 `mypy_path=backend` 且 `pycore.*` `follow_imports=skip`，避免把框架源码纳入门禁。
- **避坑**：不要提前做 T-006 的 pytest-timeout、T-007 的全量 ConfigManager、T-008 的业务表/FTS5。质量门命令只覆盖 `backend/src` 与 `backend/tests`。PowerShell 下 `PYTHONPATH=.. python ...` 无效，短时启动用环境变量或绝对 `PYTHONPATH`。

### T-006: 工具链配置与 pytest-timeout
- **陷阱**：项目内 `pycore/` 没有 `pyproject.toml`，模板在框架源（Harness 根 `pyproject.toml`，`name = "pycore"`）。T-005 已有 ruff/mypy，但缺 `[tool.pytest.ini_options]`；空 `backend/tests` 无 `test_*.py` 时 pytest 退出码为 5。本机无 `python3.11`，门禁用 `python`（3.14）。
- **经验**：对照 pycore 模板补齐 pytest 段（`testpaths = ["backend/tests"]`、`pythonpath = ["backend"]`、`timeout = 120`），保留 T-005 的 ruff B008 与 mypy `pycore.* follow_imports=skip`。`requirements.txt` 补 `pytest` / `pytest-asyncio` / `pytest-timeout`，在项目根 `.venv` 安装。smoke test 只证明可发现，不 import `src.db.session`。
- **避坑**：质量门必须带 `--timeout=120`；`pip show pytest-timeout` 或 collect 可见 `plugins: timeout`。不要把 `pycore/` 纳入 ruff/mypy/pytest。不要提前做 T-007 全量 ConfigManager 或 T-008 全表建表。

### T-007: 配置加载与 backend/.env.example
- **陷阱**：pycore `ConfigManager.load()` 仍只内置 TOML 加载器，直接 `load(AppSettings, "backend/.env")` 会报无 loader；默认 `use_env=True` 还会把 `PYCORE_*` 进程环境合并进去，违反「禁止 os.environ 覆盖文件配置」。
- **经验**：在 `backend/src/core/config.py` 用 `ConfigLoader` 注册 dotenv 文件加载器（解析 `.env` 为 dict，不调用 `os.getenv` / `load_dotenv`），再 `ConfigManager.load(..., use_env=False)`。字段名用小写，`.env` 键按 tech-spec §4 大写，加载时转小写。`SECRET_KEY` 无默认且 `min_length=1`，缺失/空值抛中文 `ConfigurationError`。测试用临时 `.env` + `ConfigManager.reset()`，不要读真实 `backend/.env` 的密钥值。
- **避坑**：`.env.example` 只写占位（如 `change-me` / `your-dashscope-api-key`）。可向真实 `backend/.env` 补非密钥默认项，但不要改已有 `SECRET_KEY`、不要把真实 Key 写入任何 `.md`/`.json`。不要提前做 T-008 全表建表。PowerShell 下从 `backend/` 启动仍需把项目根设到 `PYTHONPATH`。

### T-008: SQLite 建表、FTS5 与 init_db
- **陷阱**：SQLAlchemy 2.0.36 在 Python 3.14 下解析 `Mapped[str | None]` / `Mapped[Optional[str]]` 会触发 `Union.__getitem__` TypeError，建表在 import 模型时失败。`cd backend && PYTHONPATH=.. python scripts/init_db.py` 时 `sys.path[0]` 是 `scripts/`，仅项目根无法导入 `src`。
- **经验**：可空列用 `Mapped[str]`/`Mapped[bytes]` + `nullable=True`，不要在 Mapped 里写 Union。`init_db.py` 把 `backend/` 与项目根插入 `sys.path`，导入一律 `src.*`。`DATABASE_PATH` 相对 `backend/`（`__file__`）解析为绝对路径并 `mkdir` 父目录。FTS5 虚表 `knowledge_chunks_fts(content, chunk_id UNINDEXED)` 加 INSERT/UPDATE/DELETE 触发器与切片同步。测试只用 `make_async_engine(tmp_path)` + `apply_schema`，禁止对运行时 `engine` `drop_all`。
- **避坑**：不要提前做 T-009 认证闭环或 T-011 注册 API。本机质量门用 `python`（3.14），不要 `python3.11`。PowerShell 下 `PYTHONPATH=..` 前缀无效，先 `$env:PYTHONPATH` 再跑脚本。pytest 后必须复查 `backend/data/service_robot.db` 表仍在。
- **[SYSTEM] 建议回传系统级经验**：SQLAlchemy 2.0.36 + Python 3.14 不能在 `Mapped[]` 中使用 `X | None` / `Optional[X]`，否则 `create_all` 前就会 TypeError。

### T-009: 路由级认证依赖 deps.py
- **陷阱**：pycore 模板 `get_current_user` 使用 `HTTPException`，FastAPI 默认响应是 `{"detail": ...}`，与契约信封 `{"code","message","data"}` 不一致。pycore `error_response` 的序列化字段是 `error`/`error_code`，也不能直接当 on-wire 信封。
- **经验**：opaque session 用 HMAC-SHA256(`SECRET_KEY`, raw token) 写入 `sessions.token_hash`（64 hex）。`get_current_user` 必须 `from src.db.session import get_db`。认证失败抛 `UnauthorizedError`，经 `register_auth_exception_handlers` 转 401 信封「未认证」，不注册 AuthMiddleware。受保护探测路由只放测试夹具，不要提前写 T-011/T-012 的 register/login/me。
- **避坑**：测试用 `tmp_path` 库 + `dependency_overrides[get_db]` 插入 session，禁止对运行时 `engine` `drop_all`。过期 session 按无效凭证 401。T-012 签发 session 必须复用 `hash_session_token`，否则登录后 `get_current_user` 对不上。
- **[SYSTEM] 建议回传系统级经验**：路由级 401 不要直接 `raise HTTPException`；pycore `error_response` 需映射为契约信封 `{code, message, data}`，否则 Tester 会按 api-contracts 判 FAIL。

### T-010: 健康检查与后端启动验证
- **陷阱**：本机 httpx 0.28 的 `ASGITransport` 没有 `lifespan` 参数，mypy 会报 `call-arg`；该版本只发 HTTP scope，本来就不会跑 FastAPI lifespan / `init_db`。
- **经验**：`GET /health` 由 pycore `APIServer._create_app` 注册，返回 `{"status":"healthy","version":...}`，不要改成契约信封。路由骨架只落 `auth` / `tickets` / `knowledge_documents` 三个空 `APIRouter`，不要提前写 register/login。
- **避坑**：短时启动用绝对 `PYTHONPATH` 指向项目根，PowerShell 下 `PYTHONPATH=..` 前缀无效。验证后必须关掉 8099。质量门不要扫 `pycore/`。测试用 `trust_env=False` 的 httpx，禁止对运行时 `engine` `drop_all`。

### T-011: F-002 本地账号注册闭环
- **陷阱**：pycore `success_response` / `error_response` 序列化字段是 `success`/`error`/`error_code`，不是契约信封 `{code, message, data}`。FastAPI 默认校验失败是 422 `detail`。`get_db` 若不 `commit`，注册在请求结束后回滚，accounts 表写不进去。bcrypt 只接受 72 字节口令，契约密码上限是 128。
- **经验**：用 pycore 生成响应后再映射成契约信封；`RequestValidationError` 转 400 `VALIDATION_ERROR`「参数验证失败」；`AccountConflictError` 转 409「该账号名已被占用」。分层 models → repo → service → route；密码 bcrypt 哈希，超 72 字节先 SHA-256。注册不签发 session。前端 `register()` 不再走 Mock，登录仍可 `VITE_USE_MOCK`。
- **避坑**：不要提前写 login/logout/me。测试用 `tmp_path` 库 + `dependency_overrides[get_db]`，禁止对运行时 `engine` `drop_all`。本机质量门用 `python`（3.14），不要 `python3.11`。`requirements.txt` 需含 `bcrypt==4.2.1`。页面注册文案对齐 `login.html`，不要加 `[Mock]`。

### T-012: F-001 用户登录闭环
- **陷阱**：在 `env.d.ts` 里写 `declare module 'vue-router'` 会覆盖整个模块，导致 `createRouter` / `RouterLink` 全部报「无导出」。登录失败文案是「账号或密码不正确」，缺 token 是「未认证」，两套 401 不能混用。`/auth/me` 的 401 若走全局拦截器 `window.location`，会和 `router.beforeEach` 抢跳转。
- **经验**：在 T-011 注册上补 login/logout/me，opaque session 复用 `hash_session_token`（实现放到 `src.core.security`，`deps.py` 再导出）。每次登录新建 sessions 行，库内只存 HMAC，明文 token 只出现在登录响应。前端 `authService` 在 `VITE_USE_MOCK=false` 时 login/logout/me 已走真实 `/api/auth/*`；守卫用 `restoreSession()` 调 `GET /api/auth/me`，未登录进工作台带 `?state=need-login` 显示「请先登录后再进入工作台」。
- **避坑**：不要重写认证模块。登录请求不要套注册的账号/密码长度校验，否则短密码会变成 400 而不是契约 401。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止对运行时库 `drop_all`。本机质量门用 `.venv` 的 `python`（3.14）。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`（工单/知识仍靠 Mock）；Tester 用 `VITE_USE_MOCK=false` 验登录。`init_db` 必须幂等预置契约示例账号（与 Mock / api-contracts 示例同名），不能只靠用户先注册。登录页不得把所有异常都显示成「账号或密码不正确」。

### T-013: F-003 三端工作台切换闭环
- **陷阱**：AppHeader 写在三个页面内，切页会卸载重挂；若 onMounted 再调 `fetchMe` 失败就 `clearSession` 跳登录，三端切换会被误踢（AC-F003-01）。`VITE_USE_MOCK=false` 时工单/知识路由仍是空骨架，员工页 `loadMine` 不 catch 会变成未处理异常。
- **经验**：身份只由 `router.beforeEach` → `restoreSession()` → 真实 `GET /api/auth/me` 刷新；顶栏只展示 store 里的 `display_name`。导航用 Vue Router 的 `RouterLink`，`active-class`/`exact-active-class` 设为原型的 `is-active`。`/employee`、`/agent`、`/knowledge` 均 `meta.requiresAuth: true`，无 token 跳 `/login?state=need-login`。`restoreSession` 仅在 401 或本地没有 user 时清 session，避免切换时非认证错误误踢。
- **避坑**：不要另起一套认证。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。`RouteMeta` 在已 `import 'vue-router'` 的 `router/index.ts` 里做 augmentation，不要写进 `env.d.ts`。顶栏不要加 `[Mock]`。质量门：`npm run type-check`、`npm run lint`。

### Bugfix: 真实登录预置账号缺失
- **触发**：用户验收时两个契约示例账号均提示「账号或密码不正确」
- **根因**：T-012/T-013 门禁用 `VITE_USE_MOCK=false` 打真实 `/api/auth/login`，运行时 SQLite 未预置账号；登录页又把任意失败（含后端未启动）一律显示成「账号或密码不正确」。Plan.md 已写明 F-001 可用预置账号，但 `init_db` 只建表不种数据
- **已有经验回查**：有。T-012 Tester 超出范围已写「运行时库无契约示例账号」；T-001 写明 Mock 凭证以 api-contracts 示例为准
- **为什么仍然犯错**：Tester 把缺种账号标成可选/超出范围，未转成必须修复项；Developer 未把 Plan.md「可预置账号」落到 `init_db`；用户门禁说明强调关 Mock，未同步种库
- **修复**：`init_db` 幂等写入与 Mock 对齐的演示账号；登录页仅 401/`UNAUTHORIZED` 显示「账号或密码不正确」，连接失败改提示无法连接服务
- **避坑规则**：真实登录闭环交付时，`init_db` 必须能种出契约示例账号且不覆盖已有密码。登录失败文案必须按错误码分流。Tester 报告里的「超出范围 / 可选种账号」若会挡住用户门禁，必须当场修，不能留给用户先注册

### T-014: F-012 上传 Markdown 入库闭环
- **陷阱**：tech-spec §5.2 把 Embedding 写成 `input: string|string[]` + `parameters.dimensions`，但 `EMBEDDING_BASE_URL` 是百炼原生 URL，官方 HTTP 体是 `input.texts` + `parameters.dimension`，响应才是 `output.embeddings[].embedding`。页面拦截非 md 用原型全文「仅支持 Markdown，该文件未入库。」，后端契约文案是「仅支持 Markdown」。
- **经验**：入库同步完成：校验 → 落盘 UPLOAD_DIR → `processing` 行 → 切片/抽 QA → httpx Embedding（`trust_env` 取 config）→ 写 chunks/qa_pairs（FTS 靠 T-008 触发器）。Key 为空或 `.env.example` 占位、或调用失败时 HTTP 200 且 `status=failed`，不得 enabled。成功路径 pytest 用 monkeypatch `EmbeddingClient.embed_texts`，禁止打真实百炼。前端 `VITE_USE_MOCK=false` 时 `knowledgeService` 已走真实 `/knowledge_documents`；`processing` 时轮询列表；失败提示「入库未生效」。分页信封用 pycore `paginated_response` 再映射为契约 `items/page/page_size/total_items`。
- **避坑**：不要做 T-015 PATCH 启停或 T-016 答疑。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要把 `dashscope` SDK 或裸 `httpx.post` 带进代码。测试用 `tmp_path` 库 + 独立 `UPLOAD_DIR` + `dependency_overrides[get_db]`。multipart 需 `python-multipart`。本机质量门用 `.venv` 的 `python`（3.14），pytest 必须 `--timeout=300`（本任务目录）。缺 Key 不得宣称完整入库联调通过。

### T-015: F-013 启用停用知识文档闭环
- **陷阱**：AC-F013-01/02 的答疑语义依赖 T-016 员工提问流水线；本任务若去实现 Chat/Embedding/Rerank 会越界。停用若误删切片或列表过滤 `disabled`，会同时打掉 AC-F013-03。
- **经验**：PATCH `/api/knowledge_documents/{id}` 只改 `status`（enabled⇄disabled），幂等不再写 `updated_at`。`failed`/`processing` 返回 409「未生效文档不能启停」。检索约定落在 `list_enabled_ids` / `is_enabled_for_retrieval`，供 T-016 JOIN `status='enabled'`，本任务不跑答疑。前端 `toggle` 在 `VITE_USE_MOCK=false` 时走真实 PATCH 再 GET 列表刷新标签；开关 52×32px 已在 `styles.css`。
- **避坑**：不要实现 T-016 答疑，不要宣称百炼答疑联调通过。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。停用不得删除文档行、切片、qa_pairs 或 UPLOAD_DIR 原文。测试用 `tmp_path` + `dependency_overrides[get_db]`。本机质量门用 `.venv` 的 `python`（3.14），f013 pytest `--timeout=120`。

### T-016: F-004 员工提问答疑闭环
- **陷阱**：百炼 Chat Completions（`LLM_BASE_URL` + `/chat/completions`）真实响应是 OpenAI 兼容体（顶层 `choices[0].message.content`），不是原生 `output.text`。配置中的 Rerank 模型对当前账号可能返回业务失败（HTTP 非 200），生成路径必须降级为 `DEGRADED_QA_MESSAGE`，不能假装已重排成功。
- **经验**：答疑只 JOIN `knowledge_documents.status='enabled'`（复用 T-015 `list_enabled_ids` / `is_enabled_for_retrieval`）。标准问答余弦 ≥ `QA_SIMILARITY_THRESHOLD` 则直出且不调 LLM。pytest 成功路径 monkeypatch `EmbeddingClient.embed_texts` / `LlmClient.complete` / `RerankClient.rerank`；真实 Chat 结构已确认（`key_configured=True`），默认用例不得打真实百炼。`POST /api/tickets/messages` 响应已含工单与气泡；`GET /mine` 与 `GET /{id}` 仅本人工单最小接入，供列表刷新，不做 T-017 续聊扩张。前端 `ticketService.ts` 在 `VITE_USE_MOCK=false` 时走真实 POST；store 用 `qa_result_type` 对应的 `system_message` 展示气泡。
- **避坑**：禁止 dashscope SDK；httpx `trust_env=False`。不要把 Key、响应全文或 `sk-` 写入 `.sdd`。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要做转人工。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止 `drop_all` 运行时库。本机质量门用 `.venv` 的 `python`，f004 pytest `--timeout=300`。

### T-017: F-005 查看续聊闭环
- **陷阱**：`GET /mine` 列表 DTO 没有 `requester_id`，隔离只能在后端按 `requester_id == 当前用户` 过滤；测试必须先写入他人工单才能证明列表/详情/续发都看不到。已完结前端禁用输入后，仍要有后端 409「已完结，不能再发送」兜底。
- **经验**：T-016 已有 mine/detail/messages。本任务补齐双账号隔离、同一 `ticket_id` 续聊、closed 拒发。`pending`/`in_progress` 续发 `qa_result_type=none` 且不写系统气泡。员工页打开详情再核对 `requester.id`。`VITE_USE_MOCK=false` 时 `listMyTickets`/`getTicket`/`sendEmployeeMessage` 走真实 API。续聊若仍为 `ai_assisting` 会走 F-004 流水线，pytest monkeypatch `QaPipeline.run`，不测答疑语义。
- **避坑**：不要做转人工/坐席接入。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要宣称百炼答疑完整联调。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止 `drop_all` 运行时库。本机质量门用 `.venv` 的 `python`，f005 pytest `--timeout=120`。

### T-018: F-006 员工转人工闭环
- **陷阱**：`GET /api/tickets/agent-queue` 必须写在 `GET /{ticket_id}` 之前，否则 FastAPI 会把 `agent-queue` 当成 int 路径参数变成 400。坐席队列可见性看的是 `status=pending|in_progress`，不是 requester；从未转人工的 `ai_assisting` 即使属于当前登录人也不能进队列。
- **经验**：转人工只允许 requester 且 `ai_assisting`→`pending`，写入 `TRANSFER_SUCCESS_MESSAGE` 系统消息；`closed` 返回 409「已完结，不能转人工」且不插消息；`pending`/`in_progress` 返回 409「已在人工流程中」。详情对非发起人隐藏 `ai_assisting`（BR-006），已转人工单可供坐席点开上下文，但不做接入。`VITE_USE_MOCK=false` 时 `transferTicket` / `listAgentQueue` 已走真实 API；员工页仅 `ai_assisting` 可点转人工，状态条用「待处理 · 已提交，等待对接人」。
- **避坑**：不要实现坐席接入/回复/结单（T-019+）。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要宣称百炼答疑完整联调。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止 `drop_all` 运行时库。本机质量门用 `.venv` 的 `python`，f006 pytest `--timeout=120`。

### T-019: F-007 坐席接入工单闭环
- **陷阱**：接入冲突文案是「当前状态不可接入」，不要复用转人工的「已完结，不能转人工」或发消息的「已完结，不能再发送」。已 `in_progress` 再接入是 200 幂等，不能再 `touch` 改 `updated_at`。
- **经验**：复用 T-018 的 `GET /agent-queue`（仍须写在 `GET /{id}` 之前）。`POST /{id}/accept` 只把 `pending`→`in_progress`，不写系统消息。员工续发仍走 T-017 的 `pending`/`in_progress` 分支：`qa_result_type=none` 且 `system_message=null`。他人工单 `ai_assisting` 对外 404（BR-006）；发起人自己接入 AI 单才是 409。前端 `acceptTicket` 在 `VITE_USE_MOCK=false` 时已打真实 `/tickets/{id}/accept`；接入成功后切到「处理中」并保留当前详情，避免待处理列表把当前单滤掉。
- **避坑**：不要实现坐席回复/建议/分类/结单（T-020+）。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要宣称百炼答疑完整联调。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止 `drop_all` 运行时库。本机质量门用 `.venv` 的 `python`，f007 pytest `--timeout=120`。

### T-020: F-008 坐席回复闭环
- **陷阱**：完结拒发文案是「已完结，不能再发送」，与转人工「已完结，不能转人工」、接入「当前状态不可接入」不是同一句。待处理拒发是「请先接入后再回复」。T-008 建表测试在 `backend/tests/test_db_schema.py`，不要写进或覆盖 `features/f008/`。
- **经验**：`POST /{id}/agent-replies` 只允许 `in_progress`，写入 `sender_type=agent` 的 messages 并 `touch` 工单。详情只读 messages，不 JOIN suggestions；AC-F008-03 用夹具造 suggestions 行即可，不要实现获取建议 API。`GET /agent-queue` 仍须写在 `GET /{id}` 之前。`VITE_USE_MOCK=false` 时 `sendAgentReply` 已打真实 `/tickets/{id}/agent-replies`；员工刷新 `GET /{id}` 可见 agent 气泡。坐席页完结输入禁用，store 另做 409 文案兜底。
- **避坑**：不要实现智能建议生成/分类/结单（T-021+）。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要宣称百炼答疑完整联调。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止 `drop_all` 运行时库。本机质量门用 `.venv` 的 `python`，f008 pytest `--timeout=120`。

### T-021: F-009 坐席智能建议闭环
- **陷阱**：qa_pipeline 降级默认返回 `DEGRADED_QA_MESSAGE`（员工答疑口径）。坐席建议必须换成 `DEGRADED_SUGGESTION_MESSAGE`，否则右栏失败说明会对不上原型。画像要用工单发起人 `requester.profile_json`，不能用当前坐席账号。
- **经验**：复用 T-016 `QaPipeline.run`，结果只插入 `suggestions`，不写 `messages`、不 `touch` 工单、不改画像。成功路径 pytest monkeypatch `QaPipeline.run`；降级路径 monkeypatch `EmbeddingClient.embed_texts` 抛错，再断言 `result_type=degraded` 且员工详情消息条数不变。`GET /agent-queue` 仍须写在 `GET /{id}` 之前。前端 `createSuggestion` / `fetchSuggestion` 在 `VITE_USE_MOCK=false` 时已打真实 `POST /tickets/{id}/suggestions`；建议只渲染右栏，`填入输入框` 不自动发送。Key 已配置于 `backend/.env`，`key_configured=True`。
- **避坑**：不要实现分类/结单（T-022+），不要推倒重写答疑流水线。不要改 `frontend/.env` 默认 `VITE_USE_MOCK=true`。不要宣称 Chat/Embedding/Rerank 全路径完整联调通过。禁止 dashscope SDK；httpx `trust_env=False`。日志/报告只写 `key_configured=True`，禁止密钥片段。测试用 `tmp_path` + `dependency_overrides[get_db]`，禁止 `drop_all` 运行时库。本机质量门用 `.venv` 的 `python`，f009 pytest `--timeout=300`。

