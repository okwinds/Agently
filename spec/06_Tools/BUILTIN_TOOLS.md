# 06 / 内置工具规格（Built-in Tools）

内置工具位于：`agently/builtins/tools/*`，其共同点是提供 `tool_info_list`：

- `[{name, desc, kwargs, func}]`

这些工具通常通过 ToolManager.register 注册到 agent 的 tool 列表中（示例见 `examples/builtin_tools/*`）。

## 1. Search

实现：`agently/builtins/tools/Search.py`

- 依赖：`ddgs>=9.10.0`（LazyImport）
- 初始化参数：
  - proxy/timeout
  - backend/search_backend/news_backend
  - region（默认 `us-en`）
  - options：透传给 ddgs
- 提供 4 个工具：
  - `search(query, timelimit=None, max_results=10)`
  - `search_news(query, timelimit=None, max_results=10)`
  - `search_wikipedia(query, ...)`
  - `search_arxiv(query, max_results=10)`：使用 httpx + feedparser 调 arXiv API

复刻注意：这些工具是 async 函数；ToolManager 会把它们当普通 callable 注册。

## 2. Browse

实现：`agently/builtins/tools/Browse.py`

- 依赖：`httpx`、`beautifulsoup4`（LazyImport）
- 工具：
  - `browse(url)`：抓取 HTML 并用 BeautifulSoup 提取可见文本（h1-h5/p/pre/td + div.content）
- 特性：
  - 若 301 且 url 是 http，会尝试替换成 https
  - 失败时返回字符串错误（不会 raise）

## 3. Cmd

实现：`agently/builtins/tools/Cmd.py`

定位：提供“受 allowlist 约束的 shell 执行器”，用于安全地让模型运行命令。

关键参数：

- `allowed_cmd_prefixes`：默认只允许 `ls/rg/cat/pwd/whoami/date/head/tail`
- `allowed_workdir_roots`：默认仅允许 `Path.cwd()` 下
- `timeout`：默认 20 秒
- `env`：可注入环境变量

工具：

- `cmd(cmd, workdir=None, allow_unsafe=False)`：
  - cmd 可为 str 或 list[str]；str 会通过 shlex.split
  - workdir 必须在 allow roots 下，否则返回 need_approval=True（不会执行）
  - cmd 前缀不在 allowlist 且 allow_unsafe=False：返回 need_approval=True
  - 允许执行时：subprocess.run(capture_output=True, text=True) 并返回 stdout/stderr/returncode

复刻重点：Cmd 工具通过“结构化返回值 + need_approval 标志”让上层 agent/应用可以做审批流。

