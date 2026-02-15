# 01 / Settings 规格

## 1. Settings 的定位

`Settings` 是 Agently 的“配置总线”。它是 `SerializableRuntimeData` 的子类，具有：

- **层级继承**：每个 Settings 可指定 parent，读取默认 `inherit=True`；
- **路径设置**：支持 `a.b.c` 形式写入嵌套结构；
- **映射机制**：
  - path_mappings：把简写 key 映射到真实 settings path；
  - kv_mappings：把某个 key 的简写 value 映射到一组真实 settings 更新（类似 profile）。

核心实现文件：`agently/utils/Settings.py`。

## 2. 数据模型与操作语义

### 2.1 基础 API

- `Settings.get(key=None, default=None, inherit=True)`：
  - key 为 None 时返回“合并视图”（child 覆盖 parent；list/set 会合并去重；dict 递归合并）
- `Settings.set(key, value)` / `Settings.__setitem__`
- `Settings.update(dict)`
- `Settings.load(data_type, value)`：支持 json/yaml/toml（字符串或文件）
- `Settings.setdefault(key, value, inherit=True)`

注：`Settings` 继承了 `RuntimeData` 的“合并式 set”语义——对 dict/list/set 的写入是 merge，而不是覆盖（覆盖需要 `cover=True` 的内部路径写入，外部 API 默认不暴露）。

### 2.2 set_settings：面向用户的设置 API

`Settings.set_settings(key, value, auto_load_env=False)` 的额外语义：

1. 若 `auto_load_env=True`：
   - 尝试导入 `python-dotenv`，执行 `load_dotenv(find_dotenv())`
   - 使用占位符模式 `${ ENV.<NAME> }` 从 `os.environ` 替换 value 中的占位符
2. 若 `key` 在 path_mappings：
   - 实际执行 `update({actual_path: value})`
3. 若 `key` 在 kv_mappings：
   - 根据 `key.value` 找到 actual_settings dict 并 `update(actual_settings)`
4. 否则：`set(key, value)`

## 3. 映射机制

### 3.1 path_mappings

用途：给常用插件配置提供短路径。

示例（来自 `OpenAICompatible.DEFAULT_SETTINGS["$mappings"]["path_mappings"]`）：

- `"OpenAICompatible" -> "plugins.ModelRequester.OpenAICompatible"`
- `"OpenAI" -> "plugins.ModelRequester.OpenAICompatible"`
- `"OAIClient" -> "plugins.ModelRequester.OpenAICompatible"`

因此用户可写：

```python
Agently.set_settings("OpenAICompatible", {"base_url": "...", "model": "...", "auth": "..."})
```

### 3.2 kv_mappings

用途：把简单开关映射到一组 settings 更新（类似 debug profile）。

`agently/base.py` 注册的映射（debug 开关）：

- 当 `debug=True`：
  - `runtime.show_model_logs=True`
  - `runtime.show_tool_logs=True`
  - `runtime.show_trigger_flow_logs=True`
  - `runtime.httpx_log_level="INFO"`
- 当 `debug=False`：上述均为 False/Warning。

## 4. 必需/常用 Settings Key（复刻时需保持兼容）

### 4.1 prompt.*

- `prompt.role_mapping`：`system/developer/assistant/user/_` 角色映射（用于 to_text/to_messages）
- `prompt.prompt_title_mapping`：to_text 模式下分段标题（SYSTEM/INFO/INPUT/OUTPUT 等）

### 4.2 response.*

- `response.streaming_parse: bool`：是否启用 streaming_parse（由 ResponseParser/调用方决定如何使用）
- `response.streaming_parse_path_style: "dot"|"slash"`：StreamingData.path 输出格式

### 4.3 runtime.*

- `runtime.raise_error: bool`
- `runtime.raise_critical: bool`
- `runtime.show_model_logs: bool`
- `runtime.show_tool_logs: bool`
- `runtime.show_trigger_flow_logs: bool`
- `runtime.httpx_log_level: str`（用于设置 httpx/httpcore logger level）

### 4.4 plugins.*

- `plugins.<Type>.activate`：当前激活插件名（string）
- `plugins.<Type>.<PluginName>`：该插件的默认配置树（dict）

