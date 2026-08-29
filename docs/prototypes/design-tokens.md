# 设计取值表

> B2 已确认原型的权威取值。前端实现必须逐项照抄，禁止近似。来源：`docs/prototypes/index.html` 设计取值表与 `styles.css` `:root`。

## 色值

| Token | 取值 | 用途 |
|---|---|---|
| `--color-ink` | `#18181B` | 正文 |
| `--color-primary` | `#2563EB` | 主色 |
| `--color-primary-soft` | `#EFF6FF` | 主色浅底 |
| `--color-page` | `#F4F4F5` | 页面底 |
| `--color-surface` | `#FFFFFF` | 面板 |
| `--color-line` | `#E4E4E7` | 分割线 |
| `--color-muted` | `#71717A` | 次要文字 |
| `--color-success` | `#059669` | 成功 / 启用 |
| `--color-warning` | `#D97706` | 警告 / 待处理 |
| `--color-danger` | `#DC2626` | 危险 / 停用 / 错误 |
| `--color-done` | `#A1A1AA` | 已完结 |
| `--color-focus-bar` | `#1D4ED8` | 状态条底（白字） |

## 字体

| Token | 取值 |
|---|---|
| `--font-title` | Outfit, Inter, sans-serif（字距 `-0.04em`） |
| `--font-body` | Inter, Geist, sans-serif |
| `--fs-title` | `24px` |
| `--fs-section` | `16px` |
| `--fs-body` | `14px` |
| `--fs-caption` | `12px` |

界面文案一律中文。

## 间距与圆角

| Token | 取值 |
|---|---|
| `--space-1` | `8px` |
| `--space-2` | `16px` |
| `--space-3` | `24px` |
| `--space-4` | `32px` |
| `--radius` | `8px`（不超过 `12px`） |
| 登录密码栏与主按钮额外间距 | `16px` |
| 知识启停开关 | `52×32px`，圆角 `8px` |

## 阴影

| Token | 取值 |
|---|---|
| `--shadow` | `0 1px 2px rgba(24, 24, 27, 0.06)` |
