# Claude Code 中文更新日志

把 [Claude Code 官方 changelog](https://code.claude.com/docs/en/changelog) 自动翻译成简体中文的静态站。

**在线地址**：https://frankarin.github.io/claude-code-changelog-zh/

非官方社区项目，不隶属 Anthropic，也未获其背书。英文原文为准。

## 为什么做这个

Claude Code 几乎每个工作日都在发版，官方 changelog 是英文，而且很长。官方中文文档站覆盖了大部分文档，但 changelog 仍然跳转到英文原文。现有社区项目要么只做摘要，要么只有裸 Markdown 全文，没有同时提供「摘要入口 + 逐条全文 + 中英对照 + 搜索」。

本站的定位是 **摘要优先，全文兜底**：

- 首页按天聚合，用一分钟看完当天更新。
- 点进版本页可以逐条查中英对照。
- 搜索覆盖全部条目，能定位到具体版本和句子。

## 特性

- 摘要卡：TLDR、3–6 条关键变更、需要行动项、破坏性变更标记、命令示例。
- 版本页：逐条中英对照，中文 / English / 对照三态切换。
- 归档与搜索：按月份浏览，支持版本号、日期、关键词搜索。
- 术语表：Claude Code 生态专有名词保留英文，普通技术词统一译法。
- 增量翻译：条目级 hash 缓存，上游改一条只重译一条。
- 精修 pass：翻译后再做一遍纠错、去翻译腔、统一术语、保护代码片段。
- 无追踪、无 Cookie、无第三方脚本。

## 工作方式

```
抓取官方 changelog.md
  → 解析版本、日期、分组、条目
  → 条目级 hash 缓存命中则复用
  → 只翻译新增/变更条目（OpenAI 兼容接口）
  → 精修译文
  → 生成版本摘要与日期摘要
  → 校验条目数、代码 token、摘要 schema
  → 渲染静态站、搜索索引、RSS、sitemap
```

主数据源是 `code.claude.com/docs/en/changelog.md`，兜底用 GitHub 上的 `CHANGELOG.md`，日期用 npm registry 补齐。

## 本地运行

要求 Python 3.10+。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

# 翻译最新 20 个版本并构建
python -m pipeline update --max-new 20

# 本地预览
python -m http.server 8000 -d dist
```

打开 http://localhost:8000/。

Windows Git Bash 下临时设置 `SITE_BASE` 时，命令前加 `MSYS_NO_PATHCONV=1`，否则 `/claude-code-changelog-zh` 会被转换成 `D:/Git/...`。写进 `.env` 不受影响。

`.env` 会被自动读取；已存在的环境变量优先，不会被覆盖。

### 常用命令

```bash
# 增量更新（只处理新版本和上游变更过的版本）
python -m pipeline update

# 只处理最新 20 个版本
python -m pipeline update --max-new 20

# 从指定日期开始回填
python -m pipeline update --since 2026-08-08 --max-new 50

# 全量回填，每次最多 50 个版本
python -m pipeline update --all --max-new 50

# 强制重译选中的版本（术语表升版后使用）
python -m pipeline update --all --max-new 20 --force

# 只重新构建站点
python -m pipeline build

# 校验数据完整性
python -m pipeline verify
```

`--max-new` 限制版本数，不是条目数。单次条目预算由 `LLM_MAX_ITEMS_PER_RUN` 控制，默认 600。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 无 | 必填。OpenAI 兼容接口的密钥。 |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | 接口地址。 |
| `LLM_MODEL` | `deepseek-chat` | 翻译模型。 |
| `SUMMARY_MODEL` | 同 `LLM_MODEL` | 摘要模型，可单独指定。 |
| `LLM_POLISH` | `1` | 是否启用精修 pass。 |
| `LLM_MAX_ITEMS_PER_RUN` | `600` | 单次运行的条目预算。 |
| `SITE_BASE` | 空 | 站点子路径。GitHub Pages 项目站设为 `/claude-code-changelog-zh`。 |
| `SITE_URL` | `http://localhost:8000` | 站点根地址，用于 canonical、RSS、sitemap。 |

仓库中不包含任何密钥。Fork 后请自行在仓库 Secrets 中添加 `LLM_API_KEY`。

## 部署到 GitHub Pages

1. 推送仓库到 GitHub。
2. 打开 **Settings → Pages**，把 **Source** 设为 **GitHub Actions**。
3. 打开 **Settings → Secrets and variables → Actions**：
   - Secrets：添加 `LLM_API_KEY`。
   - Variables：可选添加 `LLM_BASE_URL`、`LLM_MODEL`、`SUMMARY_MODEL`。
4. 打开 **Actions → Update changelog → Run workflow**，选择 `mode=update`、`max_new=20`。
5. 首次运行如果没有配置 `LLM_API_KEY`，会直接用仓库里已有的 `data/` 构建并部署；配置密钥后，后续运行才会拉取新版本并翻译。
6. 有密钥时，运行会提交 `data/` 和 `cache/`，然后部署 Pages。

定时任务每小时检查一次。没有新版本时不会产生翻译费用。

回填历史版本：手动触发工作流，`mode=backfill`，`max_new` 设为 50，重复执行直到覆盖所需范围。

## 成本

日常每天新增约 4 个版本，按 DeepSeek 价格估算，成本为几分钱到几毛钱。全量 436 个版本回填预计几元到十几元，以实际 token 计费为准。

`data/state.json` 记录最近 90 天的 token 用量，`LLM_MAX_ITEMS_PER_RUN` 防止单次运行失控。

## 人工修正

### 修正某条译文

1. 在版本 JSON 里找到条目的 `hash`。
2. 编辑 `data/overrides/zh-CN.json`，在 `items` 下添加 `hash -> 中文`。
3. 运行 `python -m pipeline build`。

构建时优先级：人工覆盖 > 翻译缓存 > 新翻译。

### 修正术语

编辑 `glossary.yml`，递增 `version`。术语表版本变化会让相关缓存失效，下次更新自动重译。

## 目录结构

```
pipeline/          抓取、解析、翻译、摘要、校验、构建
templates/         Jinja2 页面模板
assets/            CSS 与前端脚本
data/versions/     每个版本一个 JSON
data/digests/      按天的摘要
data/overrides/    人工修正
cache/translations 条目级翻译缓存
tests/             解析、校验、构建测试
dist/              构建产物（git 忽略）
```

## 测试

```bash
python -m unittest discover -s tests -t .
```

测试不依赖网络和真实模型。

## 声明

- 本项目是非官方社区项目，不隶属 Anthropic，也未获其背书。
- 英文原文版权归 Anthropic PBC 所有；翻译仅供学习参考，英文原文为准。
- Clawd 形象版权归 Anthropic 所有，不在本站代码的 MIT 许可范围内；本项目为非官方、非商业使用。
- 机器翻译可能存在错误，欢迎通过 issue 或 PR 纠错。
- 收到权利方的下架要求时，会及时移除相关内容。

## License

代码使用 MIT 许可证。翻译内容不单独主张版权。
