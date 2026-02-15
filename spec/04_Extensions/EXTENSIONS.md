# 04 / Agent 扩展（Extensions）规格

默认 Agent 类型在 `agently/base.py` 中通过多继承组合：

- `ToolExtension`
- `KeyWaiterExtension`
- `AutoFuncExtension`
- `ConfigurePromptExtension`
- `BaseAgent`

另有可选扩展：`ChatSessionExtension`（未混入默认 Agent，但可自行组合）。

## 1. ToolExtension

实现：`agently/builtins/agent_extensions/ToolExtension.py`

### 1.1 对外方法

- `register_tool(name, desc, kwargs, func, returns=None)`：注册到全局 ToolManager，并打 tag `agent-<name>`
- `@agent.tool_func`：装饰器注册工具并打 agent tag
- `use_tools(tools)` / `use_tool`：
  - tools 可为 str/callable/list
  - callable 若尚未注册，会自动 tool_func 注册
  - 最终为这些工具打 tag `agent-<name>`
- `use_mcp/async_use_mcp(transport)`：
  - 调用全局 tool 的 `async_use_mcp(transport, tags=[agent-tag])`

### 1.2 扩展点：request_prefix + broadcast_prefix

ToolExtension 在初始化时注册两个 extension handler：

- request_prefix：在真正请求模型前运行，用来做“是否用工具”的规划
- broadcast_prefix：在响应广播前运行，用来把工具日志注入结果流与 extra

#### request_prefix（工具规划算法）

1. 获取该 agent tag 下的 tool_list（Tool.get_tool_list(tags=[agent-tag])）
2. 若工具不为空：
   - 创建一个新的 `ModelRequest`（tool_judgement_request）
   - prompt：
     - input = 原 prompt.input
     - extra instruction = 原 prompt.instruct（现实现用 key `"extra instruction"`，包含空格；该字段会作为 PromptModel.extra 存在，但当前不影响后续主请求）
     - tools = tool_list
     - instruct = 固定句式：Judge if you need to use tool...
     - output schema = `{use_tool: bool, tool_command:{purpose, tool_name, tool_kwargs}}`
   - 获取 response，并用 `type="instant"` 流式解析：
     - 如果 `use_tool` 完成且为 False：cancel_logs + return（不使用工具）
     - 如果 `tool_command` 完成：执行工具，写入：
       - prompt.action_results = {purpose: tool_result}
       - prompt.extra_instruction = 固定 NOTICE（要求引用来源；现实现用 key `"extra_instruction"`，下划线形式，会作为 extra key 出现在 PromptGenerator main prompt 中）
       - 保存 tool_log（name/kwargs/purpose/result）

注意：该算法意味着 ToolExtension 会进行 **两次模型请求**：

- 第一次：工具规划（是否用工具 + 生成 tool kwargs）
- 第二次：带着 action_results 重新让模型回答

这是一种“function calling 外置化”的实现策略，复刻时应保持一致。

#### broadcast_prefix（工具日志注入）

如果存在 tool_log：

- yield `("tool", tool_log)` 作为广播前缀事件（event 名不是 AgentlyModelResponseEvent 枚举的一部分，但会被上游消费为 extra）
- 确保 `full_result_data["extra"]["tool_logs"]` 是 list，并 append tool_log
- 若 `runtime.show_tool_logs=True`：发系统消息 TOOL

## 2. KeyWaiterExtension

实现：`agently/builtins/agent_extensions/KeyWaiterExtension.py`

用途：在结构化 streaming_parse 中等待某些 key 完成，并在到达时触发 handler。

关键 API：

- `get_key_result(key)`：等待某 key 完成并返回 value
- `wait_keys(keys)`：同步 generator，yield (path, value)
- `async_wait_keys(keys)`：异步 generator
- `when_key(key, handler)`：注册 handler
- `start_waiter()` / `async_start_waiter()`：消费 instant stream，并在 key complete 时执行 handler（支持 async）

校验：必须先定义 output prompt，否则报错；`must_in_prompt=True` 时还要求 key 出现在 output schema 中。

## 3. AutoFuncExtension

实现：`agently/builtins/agent_extensions/AutoFuncExtension.py`

用途：把普通函数包装成“由模型实现”的函数（自动生成 input/instruct/output）。

规则：

- 读取 func signature，把实参绑定成 dict 作为 `.input()`
- instruction = func.__doc__
- output_dict = func.__annotations__["return"]（要求 return 注解是输出 schema）
- 同步函数：调用 `.start()`；异步函数：调用 `.async_start()`
- 不允许 generator/async generator（直接抛 TypeError）

## 4. ConfigurePromptExtension

实现：`agently/builtins/agent_extensions/ConfigurePromptExtension.py`

用途：从 YAML/JSON 的“prompt 配置 DSL”批量设置 agent/request prompt，并支持 alias 调用。

支持：

- `.load_yaml_prompt(path_or_content, mappings=None, prompt_key_path=None)`
- `.load_json_prompt(...)`

配置 DSL（核心规则）：

- key:
  - `.agent`：写入 agent_prompt（always 语义）
  - `.request`：写入 request.prompt
  - `.alias`：调用 agent 上同名方法（如果存在且可调用）
  - `$<key>`：写入 agent_prompt 的 `<key>`（去掉 `$` 前缀）
  - 其它 key：写入 request.prompt
- 对 output 字段会执行 `_generate_output_value`：
  - 支持 `$type/$desc` 或 `.type/.desc` 语法转为 `(type, desc)`
  - 支持 dict/list 递归

## 5. ChatSessionExtension（可选）

实现：`agently/builtins/agent_extensions/ChatSessionExtension.py`

用途：自动把每轮对话写回 chat_history，并支持记录输入/输出的特定路径（dot/slash）。

关键点：

- 通过 `extension_handlers.append("finally", __finally)` 在每次请求结束后记录
- `activate_chat_session(chat_session_id=None)`：
  - 激活某个 session_id，并把历史 chat_history 加载到 agent_prompt
- `record_input_paths`/`record_output_paths`：
  - 支持记录整个 prompt slot 或 slot 内某个 path
  - mode 支持 `first|all`
