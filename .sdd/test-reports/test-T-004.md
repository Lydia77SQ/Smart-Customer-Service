# 测试报告：T-004 知识维护工作台 Mock（/knowledge）

**测试时间**：2026-08-29 17:33 (UTC+8)
**Tester Agent ID**：tester-T-004-20260829

## 结果：PASS

## 验收标准逐条验证

| # | 标准 | 结果 | 说明 |
|---|------|------|------|
| 1 | [AC-F012-01] 用户选择合法 .md 文件上传后，表格出现新行且状态标签为「启用」 | PASS | `KnowledgePage` 校验 `.md` 后调用 `knowledgeStore.upload` → `mockUploadKnowledgeDocument` 创建 `status=enabled` 并重载列表。抽检上传「新文档.md」：`upload_status=enabled`、`new_in_list=true`；页面 `statusLabel` 映射为「启用」/`tag-on`。 |
| 2 | [AC-F012-02] 用户选择非 Markdown 文件上传，页面提示「仅支持 Markdown」，列表不出现该文件为启用 | PASS | 页面层 `isMarkdownFile` 失败时 `setClientError('仅支持 Markdown，该文件未入库。')`（含 AC 要求短语且与原型全文一致）；Mock 层对非 `.md` 抛 `VALIDATION_ERROR` +「仅支持 Markdown」。抽检 `notes.txt`：`badMsg=仅支持 Markdown`、`badInList=false`。 |
| 3 | [AC-F013-03] 用户对已入库文档关闭启停开关，该行仍保留在列表并显示「已停用」标签 | PASS | `mockToggleKnowledgeDocument` 仅改 `status`（`enabled`→`disabled`），不删行；`useKnowledgeStore.toggle` 原地更新该项。抽检关闭 VPN 行：`vpn_still_in_list=true`、`vpn_status=disabled`；页面「已停用」/`tag-off`。 |
| 4 | [AC-F003-01] 用户在顶栏切换到其他工作台再返回，仍显示当前 Mock 用户身份 | PASS | `/knowledge` 使用共享 `AppHeader`，`displayName` 来自 `authStore.user.display_name`；token 存 `localStorage`，路由守卫不因工作台切换清会话。抽检 Mock 登录后 `display_name=王丽`；三端路由均挂载同一顶栏组件。 |
| 5 | 页面布局、配色与全部文案与 docs/prototypes/knowledge.html 一致（启停开关 52×32px） | PASS | 顶栏+工具栏+表格结构对齐原型。文案逐字对照：「上传 Markdown」「仅支持 .md」「仅支持 Markdown，该文件未入库。」「还没有知识文档。请上传 Markdown。」表头「文档名称/状态/更新时间/启用」；标签「启用/已停用」。默认三行文件名与原型一致（含空格）。`.switch` 为 `52×32px`、圆角 `8px`。 |

## 技术检查逐条验证

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | Typecheck passes | PASS | 独立执行 `npm run type-check`（vue-tsc）退出码 0 |
| 2 | Lint passes | PASS | Developer 已声明；抽检新增/修改 TS/Vue 文件 `eslint` 无 error（`styles.css` 仅有 ignore 配置 warning）。另 `npm run build` 退出码 0 |
| 3 | Mock 数据与 api-contracts.md 中 KnowledgeDocumentOut、status 枚举一致 | PASS | 列表/上传/启停响应字段均为 `id,filename,status,updated_at`（对应 tech-spec `KnowledgeDocumentOut`）；分页含 `items,page,page_size,total_items`。`status` 类型为 `enabled\|disabled\|failed\|processing`。内部 `storage_path`/`created_at` 未泄漏到 DTO（`hasStorage=false`）。handler 经显式 map。 |
| 4 | 样式取值与 docs/prototypes/design-tokens.md 逐项一致（色值/字号/圆角/间距） | PASS | `frontend/src/assets/styles.css` `:root` 色值、字体、字号、`--space-*`、`--radius: 8px`、`--shadow` 与取值表一致；知识开关尺寸与取值表「52×32px，圆角 8px」一致。 |

## 环境与命令证据

- `npm run type-check` 退出码 0
- 抽检 eslint 新增/修改文件：无 error
- `npm run build` 退出码 0
- Mock 行为：`vite-node` 加载 `mocks/auth.ts` + `mocks/knowledge.ts` + `utils/datetime.ts` 验证列表时间上海时区显示（与原型 `2026-08-28 18:20` 等一致）、上传启用、非 md 拒绝、启停保留行
- Mock 阶段：`type=frontend` 且 `frontendIntegration.required=false`；未启动真实后端；未使用 Playwright/Puppeteer/Cypress

## 规范对照摘要

- rules_files 全部解析存在：`harness-core/specification/default/frontend/{tech-stack,api-client,mock,style}.md`、`shared/{env-policy,naming,security}.md`、`docs/ui-design-spec.md`、`docs/prototypes/design-tokens.md`（`specification=default`）
- Mock 集中于 `frontend/src/mocks/knowledge.ts`；`knowledgeService` 在 `isMockEnabled()` 时走本地 handler，未发真实 HTTP
- 对照 F-012 / F-013 / F-003 `spec.md`：任务 AC 覆盖上传默认启用、拒非 md、停用保留、三端身份保持；未弱化所列 AC（答疑侧 AC-F013-01/02 不在本任务 AC）
- 未发现新增代码 TODO/FIXME/HACK；可读产物未见真实密钥泄露
- 开关五态伪类在实现样式中扩展（相对原型 CSS），符合 `style.md` 交互态要求，尺寸仍对齐取值表

## 超出范围发现（不影响当前任务判定）

| # | 问题 | 所属模块 | 建议处理方式 |
|---|------|---------|------------|
| 1 | `specification/default/frontend/mock.md` 要求界面 Mock 数据带 `[Mock]`，但本项目经验与原型均要求知识台不加 `[Mock]`（与 T-001～T-003 一致） | 规范 vs 原型 | 保持原型对齐；后续若统一策略再修订 harness mock 规范或项目约定 |
