# 00 / 项目概览（Project）

## 1. 项目标识

- 名称：Agently 4
- Python 包名：`agently`
- 版本：`4.0.7.1`（来自 `pyproject.toml`）
- Python 版本要求：`>= 3.10`（来自 `pyproject.toml`）
- License：Apache-2.0（见 `LICENSE`）

## 2. 目标与非目标

### 2.1 目标（Agently 要解决的问题）

Agently 的核心目标是把“调用大模型”变成可工程化的流水线，提供：

1. **标准化 Prompt 结构**：把系统/开发者/历史/输入/输出结构等槽位统一成 `PromptModel`；
2. **可插拔的模型请求层（ModelRequester 插件）**：把 Prompt 转成具体模型 API 请求；
3. **可控的流式响应**：支持 delta（纯文本增量）与 instant/streaming_parse（结构化字段增量）；
4. **结构化输出可靠性**：通过 `ensure_keys` + 重试，降低“缺字段导致业务崩溃”的概率；
5. **工具调用的工程化实现**：不依赖供应商 function-calling，也能进行“是否用工具/用哪个/参数是什么”的规划；
6. **工作流编排（TriggerFlow）**：把事件触发、分支、并发、循环、数据流做成可维护的 DSL。

### 2.2 非目标（当前代码不覆盖/不保证）

- 不提供完整的 Web UI 或统一的应用框架；框架是库（library）性质。
- 不保证所有模型服务商都能“开箱即用”；默认提供的是 `OpenAICompatible`，其余需自行配置或扩展插件。
- 不承诺结构化输出 100% 成功；`ensure_keys` 通过重试提高概率，但仍可能失败。

## 3. 面向的使用者与典型场景

- 使用者：GenAI 应用工程师（后端/全栈/数据/智能体开发）
- 典型场景：
  - 把自然语言输入转成**稳定的结构化 JSON**结果；
  - 将**工具使用决策**纳入可追踪的执行链路；
  - 在聊天场景中做**会话压缩/记忆 memo**；
  - 以 TriggerFlow 编排多步骤任务（并发、分支、循环）。

## 4. 高层模块分区（基于仓库结构）

- `agently/base.py`：全局初始化（Settings/PluginManager/EventCenter/Tool）+ `AgentlyMain` 单例
- `agently/core/*`：核心抽象（Agent、Prompt、ModelRequest、Tool、EventCenter、Session、TriggerFlow）
- `agently/builtins/*`：内置插件、工具、扩展、事件 hooker
- `agently/types/*`：协议、TypedDict、Pydantic 模型与类型别名
- `agently/utils/*`：运行时数据结构、路径定位、序列化、lazy import、流式 JSON 解析等基础设施

## 5. 依赖与可选能力（复刻必须理解）

### 5.1 “硬依赖”（pyproject.toml dependencies）

该项目的基础依赖在 `pyproject.toml` 的 `project.dependencies` 中声明，包含：

- `pydantic`（PromptModel / RequestData / Response types 等）
- `httpx` / `httpx-sse` / `stamina`（网络请求 + SSE + retry）
- `pyyaml`（YAML dump，用于 prompt 文本与 embeddings 输入转字符串）
- `json5`（结构化输出的 JSON5/注释容错解析）
- `toml` / `packaging` / `greenlet`（settings / version constraint / 依赖运行时）

### 5.2 “软依赖”（LazyImport：缺失时交互式安装）

部分模块通过 `LazyImport.import_package(...)` 延迟加载第三方包：缺失时会 `input()` 询问是否 pip 安装（见 `spec/08_Utils/LAZY_IMPORT.md`）。

关键软依赖与对应功能：

- `sqlmodel/sqlalchemy/aiosqlite`：`agently/utils/Storage.py`（SQLite 存储）
- `chromadb`：`agently/integrations/chromadb.py`（ChromaDB 集成）
- `dotenv`：`agently/utils/Settings.py`（读取 `.env`）
- `rich`：`agently/builtins/hookers/ConsoleHooker.py`（控制台渲染）
- `ddgs/feedparser/beautifulsoup4`：`agently/builtins/tools/Search.py`、`agently/builtins/tools/Browse.py`（搜索/抓取）
- `fastmcp`：`agently/builtins/plugins/ToolManager/AgentlyToolManager.py`（MCP tool import）

复刻实现时需要决定：

- 是保留这种“运行时交互式安装”语义（与现版本一致），还是改为“缺失依赖直接报错”（更适合生产/CI）。
