# 09 / 行为规格（从 tests 提炼）

本文件将 `tests/` 作为“可执行规格”的来源，抽取成可复刻实现的行为断言。

Source: `tests/test_main_package.py`
Source: `tests/test_cores/test_session.py`
Source: `tests/test_extensions/test_session_extension.py`
Source: `tests/test_extensions/test_tool_extension.py`
Source: `tests/test_cores/test_response.py`
Source: `tests/test_cores/test_request.py`
Source: `tests/test_plugins/test_prompt_generator/test_agently_prompt_generator.py`

## 1. AgentlyMain / Settings

- 断言：`Agently.set_settings("test", "test")` 后，`Agently.settings["test"] == "test"`  
  来源：`tests/test_main_package.py`

## 2. Session（上下文窗口裁剪）

来源：`tests/test_cores/test_session.py`

- `Session.session_settings["max_length"]` 为 `int` 时：
  - `add_chat_history(...)` 会在写入后触发 `resize()`（当 auto_resize=True）
  - 默认策略为 `simple_cut`：从末尾向前保留尽可能多的 message，使 `context_window` 的近似长度不超过 `max_length`
  - 若无法保留任何完整 message，但仍有历史 message：会截断最后一条 message 的 content，使其长度等于 `max_length`
- 若 `max_length` 为 `None`：不执行裁剪策略

补充断言：

- 支持 Session 的 JSON/YAML 导出与导入（含可选 `session_key_path`），并保留：
  - `id`
  - `full_context`
  - `context_window`
  - `session_settings`

## 3. SessionExtension（Agent 会话挂载）

来源：`tests/test_extensions/test_session_extension.py`

- `agent.activate_session(session_id=...)` 会创建/激活 `Session`，并将 `Session.context_window` 同步到 `agent.agent_prompt["chat_history"]`
- `agent.add_chat_history(...)` 会写入 `Session.full_context` 与 `Session.context_window`，并同步覆盖 `agent.agent_prompt["chat_history"]`
- `agent.clean_context_window()` 会清空 `Session.context_window` 并同步 `agent.agent_prompt["chat_history"]`
- `agent.deactivate_session()` 会清空 `agent.agent_prompt["chat_history"]` 并将 `activated_session` 置空
- `SessionExtension._session_request_prefix()` 在请求前会强制把 prompt 内的 `chat_history` 与 session 同步（覆盖 stale 值）
- `SessionExtension._session_finally()` 在请求结束后记录 user/assistant 两条消息到 session：
  - 默认行为：user 内容为 `str(result.prompt.to_text())`；assistant 内容为 parsed result 的 YAML dump 文本
  - 若配置 `session.input_keys` / `session.reply_keys`：按 key/path 提取并格式化为分段内容（支持 `.agent.*`、`.request.*` 与 `input.*` 路径）

## 4. ToolExtension（工具规划 + 执行）

来源：`tests/test_extensions/test_tool_extension.py`

- 在 agent 上注册 async tool 后，调用：
  - `.use_tool(add)`（alias）会使工具可被工具规划选择
  - 模型在输入中明确要求“Use tool to calculate”时，最终结构化输出 result 必须等于工具计算值

说明：该测试依赖本地模型服务（ollama）。当模型服务不可用时该测试会被 skip；但它仍定义了 ToolExtension 的“二次请求 + action_results 注入”的语义。

## 5. Response streaming_parse

来源：`tests/test_cores/test_response.py`

- 开启：
  - `response.streaming_parse=True`
  - `response.streaming_parse_path_style="slash"`
- 在 output 为结构化 schema 时，`response.get_generator(type="instant")` 必须 yield 至少一个 StreamingData，且首个 StreamingData.value 非 None。

说明：该测试依赖本地模型服务（ollama）。当模型服务不可用时该测试会被 skip。

## 6. 多 response 并发消费（独立性）

来源：`tests/test_cores/test_request.py::test_multiple_responses_independent_consumption`

- 同一个 `ModelRequest` 设置 prompt 并连续 `get_response()` 多次得到多个 response
- 多个 response 的 async generator 并发消费应互不干扰（每个 response 保持独立的 snapshot/consumer）

说明：该测试依赖本地模型服务（ollama）。当模型服务不可用时该测试会被 skip。

## 7. PromptGenerator（AgentlyPromptGenerator）

来源：`tests/test_plugins/test_prompt_generator/test_agently_prompt_generator.py`

- `to_prompt_object()`：
  - prompt 仅设置 input 时，`output_format` 默认是 `"markdown"`
  - 当设置 `output` 时，若用户未显式设置 `output_format`，应自动变为 `"json"`
  - 若用户已显式设置 `output_format`，后续设置 `output` 不应“感染”它（保持用户值）
- `to_text()`：
  - 对于 input/info/instruct/output 的组合，输出必须严格匹配测试中的多行字符串（包含空行与 `// desc` 注释）
  - `chat_history` 中非 text 类型 content 必须被跳过（warning）且不会出现在 to_text 输出中
- `to_messages(rich_content=False)`：
  - chat_history 中 list[part] 会被简化为纯文本（只保留 type=="text" 的 part，并以 `\\n\\n` 拼接）
  - main prompt（INFO/INSTRUCT/INPUT/OUTPUT REQUIREMENT/OUTPUT）会作为最后一条 user message 的 content（字符串）追加
- `to_messages(rich_content=True)`：
  - chat_history 必须保留原始 rich parts（包括非 text part）
  - assistant 的 string content 会被转换为 `[{type:"text", text: "..."}]`
- `strict_role_orders=True`：
  - 当 chat_history 第一条不是 user 时，必须在最前面插入一条 user message，内容为 `"[CHAT HISTORY]"`
  - 当 chat_history 最后一条不是 assistant 时，必须在末尾插入一条 assistant message，内容为 `"[User continue input]"`
- `to_output_model()`：
  - list schema 的输入允许单值并会被自动包装为 list
  - list 元素会被强制 cast（例如 `"456"` → `456`，`1` → `"1"`）
