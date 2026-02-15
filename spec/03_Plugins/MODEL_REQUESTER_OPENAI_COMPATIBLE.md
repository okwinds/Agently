# 03 / ModelRequester: OpenAICompatible 规格

实现：`agently/builtins/plugins/ModelRequester/OpenAICompatible.py`

OpenAICompatible 是一个“OpenAI API 兼容层”的 ModelRequester 插件，支持：

- chat/completions/embeddings 三类 endpoint
- SSE streaming（chat/completions）
- non-stream（含 embeddings）
- 通过 `content_mapping` 将供应商响应映射为 Agently 统一事件流

## 1. 配置（DEFAULT_SETTINGS）

插件 settings namespace：`plugins.ModelRequester.OpenAICompatible`

### 1.1 常用 key

- `model_type`: `"chat"|"completions"|"embeddings"`（默认 chat）
- `model`: `str | None`（若 None 用 default_model[model_type]）
- `default_model`: dict，默认：
  - chat: `gpt-4.1`
  - completions: `gpt-3.5-turbo-instruct`
  - embeddings: `text-embedding-ada-002`
- `base_url`: 默认 `https://api.openai.com/v1`
- `full_url`: 可直接指定完整 endpoint URL（优先于 base_url + path_mapping）
- `path_mapping`: 默认：
  - chat: `/chat/completions`
  - completions: `/completions`
  - embeddings: `/embeddings`
- `auth`: 支持多形态（见下文）
- `headers/client_options/request_options/proxy/timeout`
- `stream: bool`（默认 True；注意：embeddings 也会携带 stream 字段，但请求走“非 SSE”分支，见 4 节）
- `rich_content: bool`（当 prompt 有 attachment 时会被置 True）
- `strict_role_orders: bool`（messages 构建时用）
- `content_mapping`: 内容路径映射（id/role/delta/done/usage 等）
- `content_mapping_style`: `"dot"|"slash"`
- `yield_extra_content_separately: bool`

### 1.2 path_mappings（Settings 简写）

`$mappings.path_mappings` 注册：

- `OpenAICompatible`/`OpenAI`/`OAIClient` → `plugins.ModelRequester.OpenAICompatible`

因此用户可通过 `Agently.set_settings("OpenAICompatible", {...})` 写入该插件配置。

## 2. generate_request_data（复刻级）

输出类型：`AgentlyRequestData`（Pydantic 模型，见 `agently/types/data/request.py`）

生成步骤（复刻级，按源码逐步描述）：

### 2.1 初始化副作用：attachment → rich_content

在 `__init__` 中，如果 `prompt["attachment"]` 为 truthy：

- 直接写入 `plugin_settings["rich_content"] = True`

这意味着：只要 prompt 有 attachment，OpenAICompatible 将强制启用 rich content（对 chat messages 形态有决定性影响）。

### 2.2 data（按 model_type 分支）

`AgentlyRequestDataDict` 初始结构固定为：

- `client_options: {}`
- `headers: {}`
- `data: {}`
- `request_options: {}`
- `request_url: ""`

随后按 `model_type` 生成 `data`：

1. `model_type == "chat"`
   - `data = {"messages": prompt.to_messages(...)}`
   - 参数：
     - `rich_content = bool(plugin_settings.get("rich_content", False))`
     - `strict_role_orders = bool(plugin_settings.get("strict_role_orders", False))`
   - 注意：该 strict_role_orders 的 fallback default 是 `False`，但 DEFAULT_SETTINGS 为 True；因此若用户未覆盖，最终仍为 True。
2. `model_type == "completions"`
   - `data = {"prompt": prompt.to_text()}`
3. `model_type == "embeddings"`
   - `sanitized_input = DataFormatter.sanitize(prompt["input"])`
   - 若 `sanitized_input` 是 list：
     - `data["input"]` 是 list[str]，每个 item：
       - `str|int|float|bool|None` → `str(item)`（None 会变为 `"None"`）
       - 其他 → `yaml.safe_dump(item)`
   - 否则（非 list）：
     - `data["input"]` 是单个 str，规则同上
4. 其他 model_type：
   - messenger error(TypeError(...), status="FAILED") 并将 `data = {}`

### 2.3 headers

- `headers = DataFormatter.to_str_key_dict(plugin_settings["headers"], value_format="str", default_value={})`
- 然后强制 `headers.update({"Connection": "close"})`

注意：`AgentlyRequestData` 类型本身也会在 validator 中再次确保 Connection: close，重复添加是当前行为的一部分。

### 2.4 client_options（proxy + timeout）

- `client_options = DataFormatter.to_str_key_dict(plugin_settings["client_options"], default_value={})`
- 若 `proxy` 存在：`client_options.update({"proxy": proxy})`
- timeout：
  - `timeout_configs = DataFormatter.to_str_key_dict(plugin_settings["timeout"], default_value={})`
  - `timeout = httpx.Timeout(**timeout_configs)`
  - `client_options.update({"timeout": timeout})`

### 2.5 request_options（合并顺序、model/stream 强制）

1. 初始：从 settings 读入并规范化
   - `request_options = DataFormatter.to_str_key_dict(plugin_settings["request_options"], value_format="serializable", default_value={})`
2. 合并 prompt options（若存在）
   - `request_options_in_prompt = prompt.get("options", {})`
   - `request_options.update(request_options_in_prompt)`
   - 然后再次 `DataFormatter.to_str_key_dict(..., value_format="serializable")` 以保证可序列化
3. 强制 model（覆盖前面同名 key）
   - `model = plugin_settings.get("model", default_model[model_type])`
4. 强制 stream（覆盖前面同名 key）
   - `is_stream = plugin_settings.get("stream")`
   - 若 `is_stream is None`：
     - embeddings → False
     - 其他 → True
   - `request_options["stream"] = is_stream`

注意：

- 这里的“embeddings → False”仅在 `stream is None` 时生效；若 DEFAULT_SETTINGS 里的 stream=True 未被用户显式覆盖，embeddings 仍会携带 stream=True。
- embeddings 的网络请求实际走“非 SSE”分支（由 4 节的 `model_type` 决定），stream 值并不影响分支选择。

### 2.6 request_url（full_url 优先）

- `full_url = plugin_settings.get("full_url")`
- `base_url = str(plugin_settings.get("base_url"))`，若尾字符为 `/` 则删去一个 `/`
- `path_mapping = DataFormatter.to_str_key_dict(plugin_settings["path_mapping"], value_format="str", default_value={})`
  - 并强制每个 path 以 `/` 开头
- 若 `isinstance(full_url, str)`：直接使用 `request_url = full_url`
- 否则：`request_url = f"{base_url}{path_mapping[model_type]}"`

## 3. 认证（auth）规则

auth 从 settings `auth` 读取，支持：

- 直接给 `"DEEPSEEK_API_KEY"` 这种字符串（会被 `DataFormatter.to_str_key_dict(..., default_key="api_key")` 结构化成 `{api_key: ...}`）
- dict：
  - `{api_key: "..."}`
  - `{headers: {...}}`：将自定义 headers 合并入请求 headers
  - `{body: {...}}`：将字段写入 request body（`request_data.data.update(**body)`）

如果同时存在 `api_key` 且不为 `"None"`：

- header 使用 `Authorization: Bearer <api_key>`

此外还兼容 settings 的 `api_key` 字段（当 auth.api_key == "None" 时会用它兜底）。

## 4. request_model（网络请求与流式）

### 4.1 chat/completions 且 stream=True：SSE

- 使用 `httpx.AsyncClient(**client_options)`
- 使用 `httpx_sse.aconnect_sse` 建立 SSE 连接
- 内部 `_aiter_sse_with_retry` 对 `ReadError` 做 stamina retry
- 产出：`yield sse.event, sse.data`
- DONE 判定：实现中存在 `has_done` 标记，但当前代码在收到 `"[DONE]"` 时把它置为 False，导致循环结束后仍会补发一条 `("message","[DONE]")`（这是现版本行为，复刻实现必须保留）

异常处理：

- SSEError：fallback 到普通 POST 获取错误细节
- HTTPStatusError/RequestError/Exception：yield ("error", e)

### 4.2 非流式：POST 一次性返回

（用于 embeddings 或显式 stream=False）

- `yield "message", response.content.decode()`
- `yield "message", "[DONE]"`

## 5. broadcast_response（统一事件流映射，复刻级）

输入：`response_generator`（来自 request_model，event+message）

输出：`AgentlyResponseGenerator`（yield `(AgentlyModelResponseEvent, data)`）

内部维护：

- `meta: dict`
- `message_record: dict`（最后一条 loaded_message）
- `reasoning_buffer: str`
- `content_buffer: str`

映射算法：

1. 若 event == error：yield `("error", message)`
2. 若 message != "[DONE]"：
   - yield `("original_delta", message)`
   - `loaded_message = json.loads(message)`，并更新 `message_record`
   - 按 content_mapping 定位并 yield：
     - id → meta["id"]
     - role → meta["role"]
     - reasoning → yield reasoning_delta（累加 reasoning_buffer）
     - delta → yield delta（累加 content_buffer）
     - tool_calls → yield tool_calls
     - extra_delta：yield ("extra", {k:v})；如 `yield_extra_content_separately` 则再 yield `(k, v)`
3. 当 message == "[DONE]"：
   - 计算 done_content：
     - embeddings 且 done_mapping None：done_mapping="data"
     - 若 done_mapping：从 message_record 提取
     - 否则：done_content = content_buffer
   - yield ("done", done_content or content_buffer)
   - yield ("reasoning_done", reasoning_content or reasoning_buffer)
   - yield ("original_done", ...)（见注意事项：chat/completions 在现版本中可能不会产出该事件）
   - meta 补齐 finish_reason/usage
   - yield ("meta", meta)
   - extra_done：yield ("extra", {k:v})

## 6. 复刻实现注意事项

1. `content_mapping` 必须可配置，否则无法兼容不同供应商的响应字段路径。
2. broadcast_response 必须保证：
   - `delta/done/meta` 等事件语义稳定
   - embeddings 的 done 映射行为一致（done=data）
3. 对 JSON5 / 注释的容错在 ResponseParser 中实现，不应放在 ModelRequester 中。

4. “按当前实现复刻”的两个边界/缺陷（必须保留）

- **request_model 的 has_done 逻辑**：SSE 收到 `"[DONE]"` 时未将 has_done 置 True，导致会额外补发一次 `("message","[DONE]")`。
- **broadcast_response 的 match-case 分支**：done 分支里写成了 `case "_"`（字面量字符串），因此当 `model_type` 为 `"chat"`/`"completions"` 时不会进入该分支，通常不会 yield `original_done`。这会使 `AgentlyResponseParser.full_result_data["original_done"]` 对 chat/completions 保持初始 `{}`。

5. yield_extra_content_separately 会产生“非标准事件名”

当 `yield_extra_content_separately=True` 且 extra_delta 命中时，会额外 yield `(extra_key, extra_value)`（例如 `(function_call, {...})`），该 event name 不属于 `AgentlyModelResponseEvent` 固定枚举；复刻实现需保留此行为以兼容现有消费方。
