# 00 / 术语表（Glossary）

## 核心名词

- **Agently（单例）**：`from agently import Agently` 得到的 `AgentlyMain` 实例，持有全局 `settings/plugin_manager/event_center/tool`，并可创建 `Agent/Prompt/ModelRequest`。
- **Settings**：层级化配置容器（支持 parent 继承 + 映射机制），用于全局/agent/request/plugin 的配置传递。
- **Plugin / 插件**：实现某类协议（`PromptGenerator/ModelRequester/ResponseParser/ToolManager`）的组件；通过 `PluginManager.register()` 注册并可激活。
- **Prompt**：结构化提示容器（继承自 `RuntimeData`），可转换为 text/messages/pydantic prompt 对象/output model。
- **ModelRequest**：一次“向模型发起请求”的可复用构建器；内部会创建 `ModelResponse`（含 response_id）并通过插件链路执行。
- **ModelResponse / Result**：
  - `ModelResponse`：一次响应的快照（复制 prompt/settings/handlers），并创建 `ModelResponseResult`。
  - `ModelResponseResult`：封装 ResponseParser，并提供 `get_text/get_data/get_generator/...`。
- **Streaming**：
  - `delta`：模型输出的纯文本增量（`str`）。
  - `instant`/`streaming_parse`：结构化流（`StreamingData`），含 path/value/delta/is_complete。
- **ensure_keys**：对 `parsed` 结果执行路径存在性校验；缺失则触发重试（重新发起模型请求）。
- **Tool / ToolManager**：
  - `Tool`：面向用户的工具入口（内部持有 ToolManager 插件实例）。
  - `ToolManager`：注册/查询/调用工具函数，并支持从 MCP server 动态导入工具。
- **Extension / 扩展**：通过多继承 mixin 扩展 `BaseAgent` 能力（例如 ToolExtension/KeyWaiter/ChatSession/AutoFunc）。
- **EventCenter**：事件中心，支持 hook/hooker 插件；用于日志、系统消息、控制台面板等。
- **TriggerFlow**：事件驱动工作流编排 DSL；通过 BluePrint（图）+ Execution（执行）运行。

## 数据/结构术语

- **Prompt Slot（标准槽位）**：`PromptModel` 中约定的 key，例如 `system/developer/chat_history/info/instruct/examples/input/attachment/output/options`。
- **Output Schema（输出结构）**：`PromptModel.output` 的结构化描述（Mapping/Sequence/tuple/type 混合），用于：
  - 生成 output requirement prompt（JSON 结构说明）；
  - 动态生成 Pydantic 输出模型（用于解析/校验）。
- **Dot Path / Slash Path**：
  - dot：`a.b[0].c`
  - slash：`/a/b/0/c`

