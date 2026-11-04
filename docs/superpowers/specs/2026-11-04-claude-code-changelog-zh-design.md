# Claude Code 中文更新日志站设计

- 日期：2026-11-04
- 状态：设计已确认，待实现
- 仓库：`claude-code-changelog-zh`
- 站点：`https://frankarin.github.io/claude-code-changelog-zh/`（MVP 使用 GitHub Pages 默认域名）

## 1. 背景与目标

Claude Code 官方英文 changelog 位于 `https://code.claude.com/docs/en/changelog`，截至 2026-11-04 共 436 个版本、8,668 条条目、约 1.17 MB Markdown，平均每个版本 2,681 字符。官方中文文档站覆盖约 228 个页面，但 changelog 例外：`/docs/zh-CN/changelog` 返回 307，重定向到 GitHub 英文原文。

目标：为中文用户提供一个自动更新、零安装、可直接阅读的 Claude Code 更新日志站。读者不需要安装 Claude Code，也不区分使用 Claude CLI、Claude Desktop 还是手机浏览器。

核心定位：**摘要优先，全文兜底**。

- 日常读者在首页用 1 分钟看完当天更新。
- 排查问题的读者可以进入版本页查逐条中英对照。
- 搜索引擎可以索引每个版本的中文全文，覆盖长尾查询。

## 2. 先例与差异化

现有项目各自覆盖了一部分能力，但没有一个同时满足「中文摘要 + 中文全文 + 中英对照 + 搜索」：

| 项目 | 摘要 | 中文全文 | 站点/搜索 | 覆盖范围 |
| --- | --- | --- | --- | --- |
| 官方 whats-new | 有 | 无 | 官方站 | 滞后约 2 个月 |
| `Antony138/cc-digest` | 有 | 无（保留英文原文 bullets） | 有站点和 RSS | 每 2–3 天一期 |
| `MrJasonZhou/claude-code-changelog-i18n` | 无 | 有 | 无站点、无搜索 | 2026-08-08 起 |
| 本项目 | 有 | 有 | 有站点、搜索、RSS | 支持全量 436 个版本 |

差异化不靠「先发」，靠「完整、可读、可查」：

1. 逐条翻译，不遗漏；摘要由中文全文生成，两者一致。
2. 术语表约束译法，避免 plugin/插件、hook/钩子混用。
3. 中英对照可切换，命令、代码、路径保持英文。
4. 搜索覆盖全部条目，版本页可被搜索引擎收录。
5. 支持历史全量回填，不设起始日期。

## 3. 范围内与范围外

### MVP 范围

- 最新 20 个版本的抓取、解析、翻译、摘要和页面生成。
- 首页按天聚合的摘要卡。
- 版本页逐条中英对照。
- 归档页、全文搜索、按变更类型筛选。
- 术语表页、关于页。
- RSS、sitemap、robots.txt。
- GitHub Actions 每小时增量更新并部署 GitHub Pages。
- 本地可运行的命令行工具，便于贡献者复现。

### 非目标

- 不做账号、评论、点赞、访问统计。
- 不做 Claude Code 插件（站点数据可在后续复用）。
- 不做多语言，只做简体中文 `zh-CN`。
- 不做自定义域名，MVP 使用 GitHub Pages 默认域名。
- 不做实时通知（Telegram、飞书、邮件），只提供 RSS。
- 不做人工逐条校对，依靠术语表、结构校验和 overrides 修正。

## 4. 页面与交互

### 4.1 首页 `/`

- 顶部展示最新版本号、日期和「查看完整更新日志」入口。
- 主体按日期倒序排列，每天一张卡片。一天可能有 3–5 个版本，聚合后降低噪音。
- 每张日期卡包含：
  - 当天版本范围，例如 `2.1.316 – 2.1.318`，以及版本数量。
  - 一句话 TLDR（不超过 60 个汉字）。
  - 3–6 条关键变更，每条包含标题、分类、说明和需要行动项。
  - 破坏性变更、配置变更、安全修复必须有醒目标记。
  - 展开后列出当天每个版本的链接。
- 首屏最多渲染最近 7 天；更早内容进入归档页。

### 4.2 版本页 `/v/<version>/`

- 标题：`Claude Code <version> 更新日志（中文翻译）`。
- 元信息：发布日期、英文原文链接、上一版/下一版导航。
- 按变更类型分组：新增、变更、改进、修复、其他。
- 每条默认显示中文；顶部提供三态切换：中文 / English / 对照。
- 对照模式每条显示英文原文和中文译文。
- 行内代码、命令、参数、路径、环境变量、产品名保持英文，并使用等宽样式。
- 每条有稳定锚点，由条目 id 中的点替换为连字符得到，例如 `2.1.318-fixes-3` 对应 `#item-2-1-318-fixes-3`，可复制链接。
- 页脚显示非官方声明和英文原文为准的提示。

### 4.3 归档页 `/archive/`

- 按月份分组列出全部版本，显示版本号、日期、变更数量和摘要首句。
- 支持按版本号或关键词即时过滤。
- 支持按变更类型筛选：新增、变更、改进、修复、破坏性变更。
- 数据量大时前端分页或懒加载，不一次性渲染 436 个版本。

### 4.4 搜索

- 独立搜索入口，也可在归档页顶部使用。
- 搜索索引覆盖中文译文、英文原文、版本号、日期。
- 输入即搜，结果按版本倒序，显示命中片段并高亮关键词。
- 搜索索引懒加载：首页不加载，用户首次聚焦搜索框时加载。
- 索引超过 2 MB 时按年份分片，避免移动端一次下载全部数据。

### 4.5 术语表 `/glossary/`

- 表格列出术语、推荐译法、说明和首次出现处理方式。
- 页面说明术语表版本号；译法变更会触发相关条目重译。

### 4.6 关于页 `/about/`

- 项目目的、数据来源、更新频率、翻译方法。
- 与先例的差异说明。
- 非官方声明、版权归属、纠错方式、下架联系方式。
- 成本与用量统计（可选展示最近 30 天 token 用量估算）。

### 4.7 通用要求

- 响应式布局，移动端单列。
- 支持浅色/深色主题，默认跟随系统，可手动切换并记忆。
- 语义化 HTML，键盘可操作，颜色对比度符合 WCAG AA。
- 页面无第三方脚本、无追踪、无 Cookie。
- 中文排版使用全角标点；英文与数字两侧按需留空格。

## 5. 数据模型

### 5.1 版本文件 `data/versions/<version>.json`

每个版本一个文件，提交进仓库，便于 diff、审阅和人工修正。

```json
{
  "schema_version": 1,
  "version": "2.1.318",
  "date": "2026-11-04",
  "source_url": "https://code.claude.com/docs/en/changelog.md",
  "source_hash": "sha256:...",
  "translation": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "prompt_version": "v1",
    "glossary_version": "v1",
    "translated_at": "2026-11-04T09:00:00Z"
  },
  "groups": [
    {
      "kind": "added",
      "heading_en": "Added",
      "heading_zh": "新增",
      "items": [
        {
          "id": "2.1.318-added-1",
          "en": "Added ...",
          "zh": "新增了……",
          "hash": "sha256:...",
          "status": "translated"
        }
      ]
    }
  ],
  "summary": {
    "tldr": "一句话概括本版最重要的变化。",
    "highlights": [
      {
        "title": "简短中文标题",
        "category": "新功能",
        "detail": "这是什么、为什么值得注意、对日常使用的影响。",
        "action": "需要用户主动做的事；无需行动则为 null",
        "example": {
          "lang": "bash",
          "code": "claude plugin install foo",
          "caption": "一行示例，可选"
        },
        "item_ids": ["2.1.318-added-1"]
      }
    ],
    "breaking": false
  }
}
```

字段约束：

- `version` 为语义化版本字符串。
- `date` 为 ISO 日期 `YYYY-MM-DD`；日期源缺失时允许 `null`。
- `kind` 只能是 `added`、`changed`、`improvements`、`fixes`、`other`。
- `heading_en` 保留英文原文标题，例如 `15 improvements`。
- `heading_zh` 使用术语表统一译法，例如 `15 项改进`。
- `id` 在版本内唯一，由版本号、分组 kind、序号组成。
- `hash` 为规范化英文文本的 SHA-256，用于缓存和 overrides。
- `status` 只能是 `translated`、`fallback`、`needs_review`。
- `summary.highlights` 数量 1–6 条；正常版本 3–6 条。
- `summary.highlights[].category` 只能是 `新功能`、`改进`、`修复`、`破坏性变更`、`安全`。
- `summary.highlights[].item_ids` 必须引用本版本中存在的条目。
- `summary.highlights[].example` 可为 `null`；不为空时，`code` 必须是所引用条目原文中已出现的命令、参数或配置片段，不允许模型自行编写。
- `summary.breaking` 为真时，至少一条 highlight 的 category 为 `破坏性变更`。

### 5.2 日期摘要 `data/digests/<YYYY-MM-DD>.json`

```json
{
  "schema_version": 1,
  "date": "2026-11-04",
  "versions": ["2.1.318", "2.1.317"],
  "tldr": "当天更新的整体概括。",
  "highlights": [
    {
      "title": "简短中文标题",
      "category": "新功能",
      "detail": "面向日常使用的影响说明。",
      "action": null,
      "example": null,
      "version": "2.1.318",
      "item_ids": ["2.1.318-added-1"]
    }
  ],
  "breaking": false,
  "summary_hash": "sha256:..."
}
```

- 由当天的版本摘要聚合生成，不直接读英文原文。
- 当天仍有新版本发布时，每次运行重新生成并覆盖。
- `summary_hash` 由当天所有版本摘要的规范化 JSON 计算，未变化时不重复调用模型。
- 某天摘要生成失败时，首页回退为直接列出当天版本及其 TLDR，不让构建失败。
- 版本摘要输入优先使用中文译文；`status=fallback` 或 `needs_review` 的条目附带英文原文并标记 `[待校对]`，由模型在摘要中谨慎处理。

### 5.3 翻译缓存 `cache/translations/<hash>.json`

```json
{
  "schema_version": 1,
  "en": "Added ...",
  "zh": "新增了……",
  "provider": "deepseek",
  "model": "deepseek-chat",
  "prompt_version": "v1",
  "glossary_version": "v1",
  "created_at": "2026-11-04T09:00:00Z"
}
```

- 缓存 key 为 `sha256(normalized_en + prompt_version + glossary_version + provider + model)`。
- `cache/` 提交进仓库，避免每次运行重复付费；体积预计小于 20 MB。
- 上游修改某条英文时，只有该条缓存失效。

### 5.4 人工覆盖 `data/overrides/zh-CN.json`

```json
{
  "schema_version": 1,
  "items": {
    "sha256:...": "人工修正后的中文译文"
  },
  "summaries": {
    "2.1.318": {
      "tldr": "人工修正后的概括。"
    }
  }
}
```

- 构建时优先级：人工覆盖 > 翻译缓存 > 新翻译。
- 贡献者只需提交 overrides，不需要改流水线代码。

### 5.5 状态 `data/state.json`

```json
{
  "schema_version": 1,
  "last_fetch_at": "2026-11-04T09:00:00Z",
  "last_source_etag": "...",
  "last_version": "2.1.318",
  "translated_versions": 20,
  "usage": {
    "2026-11-04": {
      "input_tokens": 0,
      "output_tokens": 0,
      "estimated_cost_cny": 0.0
    }
  }
}
```

- 用于跳过无变化抓取、展示用量和预算保护。
- `usage` 只保留最近 90 天。

### 5.6 搜索索引

完整数组格式：

```json
[
  {
    "v": "2.1.318",
    "d": "2026-11-04",
    "g": "fixes",
    "id": "2.1.318-fixes-3",
    "zh": "修复了……",
    "en": "Fixed ..."
  }
]
```

分片 manifest 格式：

```json
{
  "shards": ["2026", "2025"],
  "latest": "2026"
}
```

- 字段名使用短名以控制体积。
- 只索引条目级数据，不重复索引摘要。
- 分片按版本发布日期所在年份划分，manifest 始终位于 `dist/search/index.json`。

## 6. 流水线架构

### 6.1 模块划分

```
pipeline/
├─ __main__.py      # CLI 入口与命令编排
├─ fetch.py         # 下载英文 changelog，ETag/Last-Modified 条件请求
├─ parse.py         # 解析版本、日期、分组、条目，输出规范化结构
├─ cache.py         # 条目级翻译缓存与 overrides 读取
├─ translate.py     # OpenAI 兼容接口调用、批处理、重试
├─ summarize.py     # 版本摘要与日期摘要生成
├─ validate.py      # 结构、条目数、代码片段、摘要 schema 校验
├─ build.py         # 渲染静态站、搜索索引、RSS、sitemap
└─ render.py        # Jinja2 模板环境与通用过滤器
```

依赖：Python 3.10+、Jinja2 3.x、PyYAML 6.x。网络请求使用标准库 `urllib.request`，不引入 requests。测试使用标准库 `unittest`。

### 6.2 数据流

```
fetch
  → parse（按版本切块，规范化分组和条目）
  → 计算每条英文 hash
  → 命中 overrides/cache 则复用，否则进入待翻译队列
  → translate（分批、并发 2、失败重试）
  → validate（条目数、代码 token、长度比）
  → summarize（版本摘要；当天摘要）
  → build（版本页、首页、归档、搜索索引、RSS、sitemap）
  → 提交 data/ 与 cache/，部署 dist/
```

### 6.3 解析规则

主数据源：`https://code.claude.com/docs/en/changelog.md`。

页面结构：

```
**2.1.318**

November 4, 2026

**Added**

* 条目

**15 improvements**

* 条目

**47 bug fixes**

* 条目
```

解析规则：

- 版本行：`**<semver>**` 独占一行。
- 日期行：`Month D, YYYY` 独占一行，转换为 ISO 日期。使用内置英文月份映射，不依赖系统 locale，避免中文 Windows 环境下 `%B` 解析失败。
- 分组行：`**Added**`、`**Changed**`、`**N improvements**`、`**N bug fixes**`，以及可能的其他加粗标题。
- 条目行：以 `* ` 开头；续行并入上一条。
- 没有分组标题的版本，将条目放入 `other` 分组。
- 版本内条目顺序保持与原文一致。

兜底数据源：`https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md`。

- 版本行为 `## <version>`，条目为 `- `。
- 日期从 npm registry `https://registry.npmjs.org/@anthropic-ai/claude-code` 的 `time` 字段补齐。
- 合并规则：以主源为准；主源缺少的版本用兜底源补齐；主源缺少日期时用兜底源或 npm 补齐。合并后版本数仍少于兜底源时，本次运行以退出码 1 失败，避免格式变化导致静默丢版本。

### 6.4 翻译规则

接口：OpenAI 兼容 `POST {LLM_BASE_URL}/chat/completions`。

环境变量：

- `LLM_BASE_URL`：默认 `https://api.deepseek.com/v1`。
- `LLM_MODEL`：默认 `deepseek-chat`。
- `LLM_API_KEY`：必填，只从环境变量读取。
- `LLM_MAX_ITEMS_PER_RUN`：默认 600，预算保护。按平均每版 20 条估算，可覆盖首批 20 个版本。
- `LLM_CONCURRENCY`：默认 2。

批处理：

- 每批最多 30 条或 8,000 字符，以先到者为准。
- 同一版本尽量放在同一批，便于保持上下文。
- 请求体使用 JSON 输出模式；若服务商不支持，则要求返回 JSON 数组并做容错解析。
- 失败重试 2 次，指数退避 2s、8s；仍失败则将该批标记为 `fallback`，保留英文并记录日志。

提示词约束：

- 忠实翻译，不增删、不合并、不改顺序。
- 保留 Markdown 结构、条目数量和分组。
- 不翻译反引号内的代码、命令、参数、路径、环境变量、产品名和 URL。
- 使用开发者自然使用的中文技术表达，避免翻译腔和 AI 套话。
- `glossary.yml` 的 `keep_en` 词保持英文，`translate` 词按映射统一。
- 输出 JSON 数组，长度与输入一致，不要 Markdown 代码围栏。

精修（polish）pass：

- 第一遍翻译完成后，默认再跑一遍精修，输入英文原文和中文初稿。
- 精修只做四件事：纠正误译、消除翻译腔、统一术语、确保代码片段未被改动。
- 不做扩写、不补充原文没有的信息、不改变条目顺序。
- 精修结果与初稿条目数、ID 必须一致；校验不通过则保留初稿。
- 通过 `LLM_POLISH=0` 可关闭，用于节省成本或排查问题。
- 精修后的译文才写入缓存，避免每次运行重复精修。

### 6.5 校验规则

翻译结果写入前必须通过：

1. 数组长度等于输入条目数。
2. 每条中文非空，且不是纯英文原样返回（允许专有名词占多数）。
3. 英文中的每个行内代码 token（反引号内容）必须原样出现在中文中。
4. 中文长度与英文长度比在 0.25–2.5 之间。
5. 摘要 schema 合法，`item_ids` 全部存在，category 在枚举内。
6. `example.code` 必须是所引用条目原文的子串；不是则丢弃该示例，不影响构建。
7. 版本条目总数与英文解析结果一致。

校验失败：

- 第一次失败：带失败原因重试一次。
- 第二次失败：该条 `status=needs_review`，保留英文，构建时显示「待校对」标记。
- 运行结束时输出失败清单，GitHub Actions 中作为摘要展示。

### 6.6 摘要规则

版本摘要输入为中文条目及 `item_ids`，输出严格 JSON。

- `tldr` 不超过 60 个汉字。
- `highlights` 正常版本 3–6 条；条目少于 3 条的版本允许 1–2 条。
- 必须覆盖破坏性变更、需要用户修改配置的变更、安全修复。
- `detail` 不超过 120 个汉字，说明影响而不是复述原文。
- `action` 只在用户需要主动操作时填写。
- 不得编造条目；`item_ids` 必须来自输入。
- 摘要模型可与翻译模型相同，也可通过 `SUMMARY_MODEL` 单独指定。

日期摘要输入为当天所有版本摘要，输出日期级 TLDR 和 3–6 条 highlights，并保留 `version` 与 `item_ids`。当天摘要未变化时（`summary_hash` 相同）跳过调用。

### 6.7 构建

- 使用 Jinja2，开启自动转义。
- 输出目录 `dist/`，不提交进仓库。
- 生成页面：
  - `dist/index.html`
  - `dist/v/<version>/index.html`
  - `dist/archive/index.html`
  - `dist/glossary/index.html`
  - `dist/about/index.html`
  - `dist/404.html`
- 生成资源：
  - `dist/assets/style.css`
  - `dist/assets/app.js`
  - `dist/search/index.json`：索引小于 2 MB 时为完整条目数组；超过 2 MB 时改为 manifest，格式为 `{"shards":["2026","2025"],"latest":"2026"}`，各年份数据位于 `dist/search/<year>.json`
  - `dist/rss.xml`
  - `dist/sitemap.xml`
  - `dist/robots.txt`
- 每个版本页包含：标题、meta description、canonical、Open Graph 标签。
- `sitemap.xml` 包含首页、归档、术语表、关于和全部版本页。
- RSS 包含最近 30 天的日期摘要。

### 6.8 CLI

```bash
# 增量更新：抓取、翻译新增/变更、生成摘要、构建
python -m pipeline update

# 只处理指定数量，用于首次运行或预算控制
python -m pipeline update --max-new 20

# 从指定日期回填
python -m pipeline update --since 2026-08-08 --max-new 50

# 全量回填（分批执行，每批最多 50 个版本）
python -m pipeline update --all --max-new 50

# 只重建站点，不抓取不翻译
python -m pipeline build

# 校验数据完整性，不写文件
python -m pipeline verify
```

`--max-new` 限制本次处理的版本数，不是条目数；条目级的预算保护由 `LLM_MAX_ITEMS_PER_RUN` 负责。`--all` 表示处理所有尚未翻译的版本，仍受 `--max-new` 限制。

退出码：

- `0`：成功，包含「无新版本」。
- `1`：抓取失败或解析失败。
- `2`：部分翻译失败但已生成 fallback，站点仍可构建。
- `3`：配置错误，例如缺少 `LLM_API_KEY`。

## 7. 自动化与部署

### 7.1 GitHub Actions

文件：`.github/workflows/update.yml`。

- 触发：
  - `schedule: 0 * * * *`（每小时）。
  - `workflow_dispatch`，支持 `mode=update|backfill` 和 `max_new` 输入；`backfill` 模式使用 `--since` 或 `--all`。
- 权限：`contents: write`、`pages: write`、`id-token: write`。
- 并发：`group: changelog-update`，`cancel-in-progress: false`。
- 步骤：
  1. checkout。
  2. 安装 Python 3.11 和依赖。
  3. 运行 `python -m pipeline update --max-new 50`。
  4. 若 `data/` 或 `cache/` 有变化，提交并推送。
  5. 上传 `dist/` 为 Pages artifact。
  6. 部署 GitHub Pages。
- 无新版本时跳过提交和部署，避免空提交。
- 回填通过手动触发，`max_new` 默认 50，避免单次运行过长。

### 7.2 密钥

- `LLM_API_KEY` 存放在仓库 Secrets。
- `LLM_BASE_URL`、`LLM_MODEL` 存放在仓库 Variables，便于切换服务商。
- 仓库只提交 `.env.example`，不提交 `.env`。
- 日志中不得输出密钥；错误信息统一打码。
- Fork 的用户需要自行添加 Secrets；公开站点由主仓库维护。

### 7.3 成本与限流

- 日常每天新增约 1 个版本（发版密集时一天多版），单版本平均 2,681 字符；按 DeepSeek 价格估算，日常成本为几分钱到几毛钱。
- 全量 436 个版本回填预计几元到十几元，以实际 token 计费为准。
- `LLM_MAX_ITEMS_PER_RUN` 默认 600，防止异常情况下单次费用失控。
- 记录最近 90 天 token 用量；关于页可选择展示估算成本。
- 遇到 429 或 5xx 使用指数退避；连续失败 3 次停止本次运行，保留已有缓存。

## 8. 质量与可维护性

### 8.1 术语表

文件：`glossary.yml`，带 `version` 字段。初始条目：

**原则：只保留 Claude Code 生态的专有名词和缩写，不保留普通技术词。** 判断标准是：这个词在中文语境里是否有稳定、无歧义的译法。有译法就翻译；只有产品名、功能名、协议名和缩写才保留英文。

保留英文的术语（keep_en）分三类：

1. **产品与协议名**：`Claude Code`、`Claude Desktop`、`Claude Tag`、`MCP`、`VS Code`、`GitHub`、`GitLab`、`AWS`、`Bedrock`、`Vertex`、`Foundry`、`CLI`、`SDK`、`API`。
2. **Claude Code 的功能/组件名**：`skill`、`plugin`、`hook`、`subagent`、`agent`、`session`、`prompt`、`token`、`worktree`、`marketplace`、`mod`、`artifact`、`connector`。
3. **没有合适中文译法或中文语境已通用英文的词**：`token`。

以下词**不再保留英文**，必须翻译：

| 英文 | 中文 |
| --- | --- |
| gateway | 网关 |
| runner | 运行器 |
| checkpoint | 检查点 |
| compaction | 上下文压缩 |
| context window | 上下文窗口 |
| auto mode | 自动模式 |
| permission mode | 权限模式 |
| remote control | 远程控制 |
| output style | 输出样式 |
| status line | 状态栏 |
| slash command | 斜杠命令 |
| workflow | 工作流 |
| teammate | 队友 |
| channel | 频道 |
| routine | 例程 |
| goal | 目标 |
| design | 设计 |
| editor | 编辑器 |
| terminal | 终端 |
| desktop app | 桌面应用 |
| web app | 网页版 |
| mobile app | 移动端应用 |
| network file system | 网络文件系统 |
| shared home directory | 共享主目录 |
| retry | 重试 |
| fallback | 回退 |

结构性标题和普通技术词继续翻译：

| 英文 | 中文 | 说明 |
| --- | --- | --- |
| Added | 新增 | 分组标题 |
| Changed | 变更 | 分组标题 |
| Improvements | 改进 | 分组标题 |
| Bug fixes | 修复 | 分组标题 |
| breaking change | 破坏性变更 |  |
| deprecation | 弃用 |  |
| security fix | 安全修复 |  |
| usage limit | 用量限制 |  |
| authentication | 认证 |  |
| organization | 组织 |  |

实现上，`glossary.yml` 分为 `keep_en` 和 `translate` 两组，提示词和校验都读取同一份文件。`keep_en` 中的词在译文中保持原样；`translate` 中的词按映射统一。提示词明确要求：**不在 `keep_en` 列表里的词，按中文技术文档习惯翻译，不得整词保留英文。**

术语表变更时递增 `glossary_version`，相关缓存自动失效并重译。

### 8.2 测试

- `tests/fixtures/changelog_sample.md`：包含 3 个版本、4 种分组、无分组版本、续行、行内代码、issue 链接。
- `tests/test_parse.py`：解析结果与期望 JSON 完全一致。
- `tests/test_validate.py`：条目数不一致、代码 token 缺失、长度比异常必须报错。
- `tests/test_build.py`：构建后版本页数量、首页摘要卡、RSS 条目、搜索索引条目符合预期。
- 网络和模型调用在测试中全部 mock，CI 不依赖真实 API。
- 新增解析规则必须先加 fixture 再改实现。

### 8.3 人工修正流程

1. 读者发现问题，提交 PR 修改 `data/overrides/zh-CN.json`。
2. CI 运行 `python -m pipeline verify` 和构建测试。
3. 合并后下一次构建生效，不触发重新翻译。
4. 若问题来自术语表，修改 `glossary.yml` 并递增版本，触发相关条目重译。

## 9. 目录结构

```
claude-code-changelog-zh/
├─ .github/workflows/update.yml
├─ .gitignore
├─ .env.example
├─ LICENSE
├─ README.md
├─ requirements.txt
├─ glossary.yml
├─ pipeline/
│  ├─ __init__.py
│  ├─ __main__.py
│  ├─ fetch.py
│  ├─ parse.py
│  ├─ cache.py
│  ├─ translate.py
│  ├─ summarize.py
│  ├─ validate.py
│  ├─ build.py
│  └─ render.py
├─ templates/
│  ├─ base.html
│  ├─ index.html
│  ├─ version.html
│  ├─ archive.html
│  ├─ glossary.html
│  ├─ about.html
│  └─ 404.html
├─ assets/
│  ├─ style.css
│  └─ app.js
├─ data/
│  ├─ versions/<version>.json
│  ├─ digests/<YYYY-MM-DD>.json
│  ├─ overrides/zh-CN.json
│  └─ state.json
├─ cache/translations/<hash>.json
├─ tests/
│  ├─ fixtures/changelog_sample.md
│  ├─ test_parse.py
│  ├─ test_validate.py
│  └─ test_build.py
├─ dist/                  # 构建产物，git 忽略
└─ docs/superpowers/specs/2026-11-04-claude-code-changelog-zh-design.md
```

## 10. 法务与署名

- 全站页脚和关于页声明：本项目为非官方社区项目，不隶属 Anthropic，也未获其背书。
- 英文原文版权归 Anthropic PBC；翻译仅供学习参考，英文原文为准。
- 机器翻译可能存在错误，欢迎通过 issue 或 PR 纠错。
- 收到权利方的下架要求时，及时移除相关内容。
- 代码使用 MIT 许可证；翻译内容不单独主张版权。
- 不复制官方页面样式和素材；站点视觉自行设计。

## 11. 验收标准

### 流水线

- `python -m pipeline update --max-new 20` 能在无缓存环境下生成 20 个版本文件和对应页面。
- 解析条目数与英文原文逐版本一致，误差为 0。
- 行内代码 token 保留率 100%；无法保留的条目标记 `needs_review` 并在运行摘要中列出。
- 重复运行不产生新的模型调用；上游改一条只重译一条。
- `python -m pipeline verify` 在数据完整时退出码为 0。

### 站点

- 首页、版本页、归档页、术语表页、关于页、404 页均可访问。
- 版本页三态切换正常，刷新后保持偏好。
- 搜索能命中中文译文、英文原文、版本号和日期。
- 移动端 375px 宽度无横向滚动。
- 浅色/深色主题均通过对比度检查。
- 每个版本页有独立 title、description、canonical 和 OG 标签。
- RSS 和 sitemap 可被标准校验器解析。

### 自动化

- GitHub Actions 每小时运行；无新版本时不提交、不部署。
- 有新版本时自动提交数据并部署 Pages。
- 仓库中不存在任何明文密钥；`git grep` 检查 `sk-`、`ghp_`、`AKIA` 等模式无命中。
- Fork 后不配置 Secrets 时，工作流给出明确错误并以退出码 3 结束。

## 12. 里程碑

### M1：解析与数据

- 完成 fetch、parse、cache、validate。
- 用最新 20 个版本生成 `data/versions/`。
- 单元测试覆盖正常版本、无分组版本、续行、代码 token。

### M2：翻译与摘要

- 接入 OpenAI 兼容接口。
- 完成条目级缓存、重试、fallback、用量记录。
- 生成 20 个版本的翻译和摘要。
- 人工抽查 3 个版本，确认术语和可读性。

### M3：站点

- 完成模板、样式、搜索、RSS、sitemap。
- 本地构建并逐页验收。
- 移动端和深色模式检查。

### M4：自动化与发布

- 配置 GitHub Actions 和 Pages。
- 首次部署，验证线上抓取、翻译、部署链路。
- 补充 README、关于页、贡献指南。

### M5：历史回填

- 分批回填 436 个版本。
- 抽样检查早期版本格式兼容性。
- 观察 7 天增量更新稳定性。

## 13. 风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 上游 Markdown 格式变化 | 解析失败或漏版本 | fixture 测试；版本数比对；失败时 Actions 报错并保留上次数据 |
| 翻译质量不稳定 | 读者不信任 | 术语表、代码 token 校验、overrides、人工抽查 |
| API 费用失控 | 维护成本上升 | 单次条目上限、预算日志、回填手动触发 |
| 429/5xx | 更新中断 | 指数退避、断点续跑、缓存不丢 |
| 版权或下架要求 | 站点不可用 | 显著声明、及时响应、内容可快速移除 |
| GitHub Actions 定时任务被停用 | 不再自动更新 | 工作流每次提交保持仓库活跃；README 说明手动触发方式 |
| Fork 用户无 Secrets | 工作流失败 | 明确文档与退出码 3 提示 |
| 搜索索引过大 | 移动端卡顿 | 超过 2 MB 按年份分片，懒加载 |

## 14. 后续可选项

以下不在 MVP 内，验证需求后再做：

- Claude Code 插件：复用站点数据，提供 `/changelog-zh` 本地阅读。
- 每日/每周邮件或 Telegram/飞书推送。
- PWA 离线阅读。
- 版本对比视图：选择两个版本查看差异。
- 英文原文变更监测：上游修改已发布版本时单独提示。
- 自定义域名与访问统计。

## 15. 决策记录

- 2026-11-04：选择公共静态站而非 Claude Code 插件，因为目标读者包含 Claude Desktop 用户，插件无法覆盖。
- 2026-11-04：选择「摘要优先 + 全文兜底」，因为纯全文日常可读性低，纯摘要与 cc-digest 同质。
- 2026-11-04：选择条目级缓存而非版本级缓存，降低上游修改和术语表升级的重译成本。
- 2026-11-04：默认 DeepSeek，接口保持 OpenAI 兼容，便于切换服务商。
- 2026-11-04：翻译数据提交进仓库，构建产物不进仓库，兼顾审阅、纠错和仓库体积。
- 2026-11-04：MVP 只做最新 20 个版本，全量回填放到 M5，避免首次上线被长任务阻塞。
- 2026-11-04：Claude Code 生态专有名词（skill、MCP、hook、plugin、session 等）保留英文，只翻译普通技术叙述，降低目标读者的理解成本。
- 2026-11-04：翻译增加精修 pass，默认开启；精修只纠错、去翻译腔、统一术语、保护代码片段，不扩写。
- 2026-11-04：摘要卡支持一行示例，但示例必须来自原文已有命令或配置，校验时做子串核对，防止模型编造。
