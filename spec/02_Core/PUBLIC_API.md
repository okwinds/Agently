# 02 / 核心对外 API（Public API）

本章节以“用户如何使用这个框架”为主线，给出复刻实现必须兼容的类/方法/行为。

## 1. 顶层导出（agently/__init__.py）

```python
from agently import Agently, TriggerFlow, TriggerFlowBluePrint, TriggerFlowEventData, print_, async_print
```

### 1.1 `Agently`

- 类型：`AgentlyMain[Agent]`
- 语义：全局单例（全局 settings/plugin_manager/event_center/tool）

### 1.2 `TriggerFlow`

- 类型：`agently.core.TriggerFlow.TriggerFlow.TriggerFlow`（类）
- 语义：工作流编排 DSL 的入口

## 2. `AgentlyMain`

实现：`agently/base.py::AgentlyMain`

### 2.1 属性

- `Agently.settings: Settings`（全局）
- `Agently.plugin_manager: PluginManager`
- `Agently.event_center: EventCenter`
- `Agently.logger: logging.Logger`
- `Agently.tool: Tool`
- `Agently.AgentType: type[Agent]`（默认 Agent = BaseAgent + 扩展）

### 2.2 方法

- `Agently.set_settings(key, value, *, auto_load_env=False) -> self`
  - 关键语义见 `spec/01_Configuration/SETTINGS.md`
  - 特殊 key：`runtime.httpx_log_level` 或 `debug` 会刷新 httpx/httpcore logger level
- `Agently.set_debug_console("ON"|"OFF")`
  - ON：注册 `ConsoleHooker`（rich live dashboard + 替换 builtins.print）
  - OFF：卸载 `ConsoleHooker`
- `Agently.set_log_level(level)`：设置 logger level
- `Agently.create_prompt(name="agently_prompt") -> Prompt`
- `Agently.create_request(name=None) -> ModelRequest`
- `Agently.create_agent(name=None) -> Agent`

## 3. `Agent` / `BaseAgent`

实现：`agently/core/Agent.py::BaseAgent`，默认 `Agent` 为多继承组合（见 `agently/base.py`）。

### 3.1 BaseAgent 初始化语义

创建时会生成：

- `self.id`：uuid hex
- `self.name`：传入 name 或 `id[:7]`
- `self.settings: Settings(parent=global_settings)`
- `self.agent_prompt: Prompt(parent_prompt=None)`：长期生效（always=True 写入这里）
- `self.request: ModelRequest(parent_prompt=self.agent_prompt, parent_settings=self.settings, parent_extension_handlers=...)`
- `self.prompt`：`self.request.prompt` 的别名

并把 `ModelRequest` 的一组方法直接透传到 Agent：

- `get_response/get_result/get_meta/get_text/get_data/get_data_object/get_generator/get_async_generator`
- `start = get_data`，`async_start = async_get_data`

### 3.2 Prompt 快捷方法（写入 agent 或 request prompt）

所有方法都支持 `mappings: dict | None`（占位符替换）与 `always: bool`：

- `.system(prompt, always=False)`
- `.rule(prompt, always=False)`：会额外设置 `instruct` 包含 `{system.rule}`
- `.role(prompt, always=False)`：会设置 `instruct` 包含 `YOU MUST REACT...`
- `.user_info(prompt, always=False)`
- `.input(prompt, always=False)`
- `.info(prompt, always=False)`
- `.instruct(prompt, always=False)`
- `.examples(prompt, always=False)`
- `.output(prompt, always=False)`
- `.attachment(prompt, always=False)`
- `.options(options: dict, always=False)`

额外：

- `.get_prompt_text()`：返回 `Prompt.to_text()` 的裁剪子串（去掉角色前缀与末尾）
- `.get_json_prompt()`：导出 `{".agent": ..., ".request": ...}` 的 JSON
- `.get_yaml_prompt()`：同上，YAML

## 4. `ModelRequest`

实现：`agently/core/ModelRequest.py`

### 4.1 语义

`ModelRequest` 是可复用的“请求构建器”：

- 你可以设置 prompt，然后多次 `.get_response()`，每次都会创建新的 `ModelResponse`（新 response_id，settings/prompt/handlers 快照）。
- `get_response()` 调用后，会 `self.prompt.clear()` 清空 request prompt（注意 agent_prompt 不会清空）。

### 4.2 方法（核心）

- `.set_prompt(key, value, mappings=None)`：写入 `self.prompt`（等价 `prompt.set`）
- `.get_response() -> ModelResponse`
- `.get_result() -> ModelResponseResult`
- `.async_get_text()/async_get_data()/async_get_data_object()`
- `.get_generator(type=..., specific=...)`：同步 generator（内部创建 response）
- `.get_async_generator(type=..., specific=...)`：异步 generator

## 5. `Prompt`

实现：`agently/core/Prompt.py` + `AgentlyPromptGenerator`

Prompt 的规范与输出 schema 语法见：`spec/02_Core/PROMPT_SPEC.md`。

## 6. `ModelResponse` / `ModelResponseResult`

实现：`agently/core/ModelRequest.py`

### 6.1 统一响应事件流（标准化事件）

`ModelRequester.broadcast_response()` 必须产出如下事件（见 `agently/types/data/response.py`）：

- `error`
- `original_delta`
- `reasoning_delta`
- `delta`
- `tool_calls`
- `original_done`
- `reasoning_done`
- `done`
- `meta`
- `extra`

### 6.2 `get_generator` 的 type 语义（ResponseParser 决定）

常用 type：

- `delta`：只 yield `str` delta
- `specific`：yield `(event, data)`，event 过滤在 specific 列表中
- `all`：yield `(event, data)` 全部事件
- `original`：yield 原始事件（一般是原始 SSE JSON / 最终 JSON）
- `instant`/`streaming_parse`：yield `StreamingData`（结构化 path/value/delta/is_complete）

### 6.3 `ensure_keys` + 重试

`ModelResponseResult.async_get_data(type="parsed", ensure_keys=[...])`：

- 先调用 `ResponseParser.async_get_data(type="parsed")` 得到 parsed；
- 对每个 ensure_key 执行 `DataLocator.locate_path_in_dict(parsed, ensure_key, key_style)`；
- 若任一不存在：
  - 发系统消息（stage=No Target Data in Response, Preparing Retry）
  - 若 `_retry_count < max_retries`：重新创建 `ModelResponse(...).result.async_get_data(...)`（相当于重新请求模型）
  - 否则：raise ValueError 或返回最后一次 parsed（取决于 `raise_ensure_failure`）

结构化路径语法与 wildcard：见 `spec/02_Core/RESPONSE_STREAMING_SPEC.md`。

## 7. `Tool`

实现：`agently/core/Tool.py` + `AgentlyToolManager`

- `Agently.tool` 是全局 Tool，可直接注册工具并在 Agent 中使用。
- ToolManager 支持从 MCP server 动态导入工具（`use_mcp/async_use_mcp`）。

详见：`spec/03_Plugins/TOOL_MANAGER_AGENTLY.md` 与 `spec/06_Tools/BUILTIN_TOOLS.md`。

