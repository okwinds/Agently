# 02 / Session（会话上下文窗口）规格

实现：`agently/core/Session.py`

Source: `agently/core/Session.py#Session`
Source: `tests/test_cores/test_session.py`

Session 是一个“会话上下文窗口容器”，用于在 Agent 侧维护：

- 完整上下文：`full_context`
- 当前可用于 prompt 的窗口：`context_window`
- 可选 memo：`memo`（当前实现不内置自动生成/更新逻辑，但允许由自定义策略写入）

它的内置目标非常明确：当启用 `session.max_length` 且 `auto_resize=True` 时，保证 `context_window` 在近似长度意义上不超过阈值。

## 1. 构造与设置

构造：

```python
Session(id=None, auto_resize=True, settings={})
```

关键点：

- `id`：uuid hex（可由调用方指定）
- `auto_resize`：
  - True：每次 `set/add/reset/clean` chat history 后自动触发 `resize()`
  - False：调用方需要显式调用 `resize()`
- `settings`：
  - 传入 dict：会创建 `Settings(settings, parent=agently.base.settings)`
  - 传入 Settings：会创建 `Settings(parent=settings)`
- `session_settings`：`SettingsNamespace(self.settings, "session")`
  - 默认包含 `session.max_length`（默认值为 null）

## 2. 数据结构（对外可观察）

Session 内部主要维护三块状态：

- `_full_context: list[ChatMessage]`：会话完整历史
- `_context_window: list[ChatMessage]`：用于 prompt 的上下文窗口
- `_memo: SerializableValue | None`

对外以属性形式暴露（均返回 copy，避免外部直接修改内部 list）：

- `full_context`：返回 `_full_context.copy()`
- `context_window`：返回 `_context_window.copy()`
- `memo`：返回 `_memo`

注意：`ChatMessage` 为 pydantic 模型（见 `agently/types/data`），dict 形式的 `{role, content}` 会被规范化为 `ChatMessage`。

## 3. 上下文长度口径与默认裁剪策略（simple_cut）

长度计算口径（近似）：

- 对窗口中每条 message 取 `len(str(message.model_dump()))` 并累加

默认分析策略（`_default_analysis_handler`）：

- 当 `session.max_length` 为 int 且 `context_window_length > max_length` 时，返回策略名 `"simple_cut"`
- 否则返回 None（不裁剪）

默认执行策略（`_simple_cut_execution_handler`）：

1. 从 `context_window` 尾部向前遍历，尽可能保留更多 message，使累积长度不超过 `max_length`
2. 若最终 `new_context_window` 为空但原窗口非空：
   - 将最后一条 message 的 `content` 转为 str，并截断为最后 `max_length` 个字符
   - 返回仅包含这一条被截断 message 的新窗口
3. 返回三元组 `(new_full_context, new_context_window, new_memo)`：
   - 当前默认策略不会重写 full_context 与 memo（返回 None 表示不更新）

## 4. API（同步/异步）

Session 的公开方法以 async 为主，sync 版本通过 `FunctionShifter.syncify` 提供包装（同名字段直接绑定到实例上）。

### 4.1 历史写入

- `reset_chat_history()` / `async_reset_chat_history()`：
  - 清空 full_context 与 context_window
  - 若 auto_resize=True：会调用 `async_resize()`
- `clean_context_window()` / `async_clean_context_window()`：
  - 清空 context_window（full_context 不变）
  - 若 auto_resize=True：会调用 `async_resize()`
- `set_chat_history(chat_history)` / `async_set_chat_history(...)`：
  - 支持 `Sequence[ChatMessage|dict]` 或单条 message
  - 会同时写入 full_context 与 context_window
  - 若 auto_resize=True：会调用 `async_resize()`
- `add_chat_history(chat_history)` / `async_add_chat_history(...)`：
  - 支持批量或单条追加到 full_context/context_window
  - 若 auto_resize=True：会调用 `async_resize()`

### 4.2 策略注册与执行

- `register_analysis_handler(handler)`：
  - handler 输入：`(full_context, context_window, memo, session_settings)`
  - 返回：`str | None`（策略名；None 表示不执行）
- `register_execution_handlers(strategy_name, handler)`：
  - handler 输入：`(full_context, context_window, memo, session_settings)`
  - 返回三元组：`(new_full_context|None, new_context_window|None, new_memo|None)`
- `analyze_context()` / `async_analyze_context()`：运行 analysis_handler
- `execute_strategy(strategy_name)` / `async_execute_strategy(strategy_name)`：运行 execution_handler
- `resize()` / `async_resize()`：
  - 先 analyze_context 得到 strategy_name
  - 若不为 None：执行该策略

错误与边界：

- 若 strategy_name 不存在于 execution_handlers 字典：会 warning 并不更新上下文

## 5. 序列化与加载（JSON/YAML）

Source: `agently/core/Session.py#load_json_session`
Source: `agently/core/Session.py#load_yaml_session`

Session 支持导出为“可序列化 session_data”并 JSON/YAML dump：

- `to_serializable_session_data()`：
  - `id/auto_resize/full_context/context_window/memo/session_settings`
- `get_json_session()` / `get_yaml_session()`

并支持从“文件路径或内容字符串”加载（容错能力较强）：

- `load_json_session(path_or_content, session_key_path=None, encoding="utf-8")`
  - 使用 `json5` 解析（允许注释等宽松语法）
- `load_yaml_session(path_or_content, session_key_path=None, encoding="utf-8")`
  - 使用 `yaml.safe_load`
- 两者均支持：
  - 传入路径且存在则读文件，否则视为内容字符串
  - 可选 `session_key_path`：用 `DataLocator.locate_path_in_dict` 从大 payload 中抽取 session_data
  - `context_window` 缺失时会回退：
    - 优先读取 `window_context`
    - 再回退到 `full_context`

## 6. 与 SessionExtension 的联动（Agent 侧）

实现：`agently/builtins/agent_extensions/SessionExtension.py`

Source: `agently/builtins/agent_extensions/SessionExtension.py#SessionExtension`
Source: `tests/test_extensions/test_session_extension.py`

SessionExtension 提供“把 Session 挂到 Agent”并自动同步 `chat_history` 的机制：

- `activate_session()` 后：
  - `agent.activated_session` 指向某个 Session
  - `agent.agent_prompt["chat_history"]` 会被同步为 `Session.context_window`
- 请求前（request_prefixes handler）：
  - prompt 内 `chat_history` 会被强制覆盖为 `Session.context_window`
  - 若 `Session.memo` 非空，则写入 `CHAT SESSION MEMO`
- 请求后（finally handler）：
  - 默认把用户 prompt（`result.prompt.to_text()`）与 assistant parsed result 记录为两条 chat_history
  - 若配置 `session.input_keys` / `session.reply_keys`，则按 key/path 提取并格式化后记录
