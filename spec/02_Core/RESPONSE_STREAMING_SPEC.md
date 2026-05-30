# 02 / 响应与流式解析规格（Response & Streaming）

## 1. 统一响应事件（AgentlyModelResponseEvent）

定义：`agently/types/data/response.py`

事件枚举（顺序非强制，但典型顺序为：delta 多次 → done → meta）：

- `error`: `Exception | str | Any`
- `original_delta`: `dict | str`（供应商原始片段，通常为 SSE JSON 文本）
- `reasoning_delta`: `str`
- `delta`: `str`（用户最常消费的增量）
- `tool_calls`: `Any`（供应商工具调用结构，或框架扩展产物）
- `original_done`: `dict`（供应商最终 JSON 或重构后的 done message；注意：并非所有 ModelRequester 都会产出，缺省可为 `{}`）
- `reasoning_done`: `str`
- `done`: `Any`（通常为最终文本；embeddings 时可能为 embedding 列表）
- `meta`: `dict`（id/role/finish_reason/usage 等）
- `extra`: `dict`（额外字段，如 function_call 等）

补充（实现细节，复刻必须包含）：

- 某些 ModelRequester（例如 OpenAICompatible）在 `yield_extra_content_separately=True` 时，除了 `extra` 事件，还会额外 yield `(extra_key, extra_value)` 形式的“非标准 event name”（如 `function_call`）。消费方需要容忍并按需过滤。

## 2. ResponseParser 的职责边界

`ResponseParser` 必须提供：

- `get_text()/get_data()/get_meta()/get_data_object()`
- `get_generator(type=...)`（同步）
- `get_async_generator(type=...)`（异步）

并维护 `full_result_data`（见 `AgentlyModelResult`）。

## 3. `AgentlyResponseParser` 的解析算法（复刻级）

定义：`agently/builtins/plugins/ResponseParser/AgentlyResponseParser.py`

### 3.1 Buffer 与 text_result

- 在 `_extract()` 中，遇到 `delta` 事件会把 data 拼进 `buffer`
- 遇到 `done` 事件：
  - `full_result_data["text_result"] = str(data)`
  - 对于 `output_format != "json"`：
    - embeddings 特判：如果 `data` 是 list 且 item.object == "embedding" → 转成 embedding 列表
    - `parsed_result = data`
  - 对于 `output_format == "json"`：
    1. `cleaned_json = DataLocator.locate_output_json(str(data), output_schema)`
    2. 若有 cleaned_json：
       - `completed = StreamingJSONCompleter().complete(cleaned_json)`
       - `parsed = json5.loads(completed)`（支持 JSON5 与注释）
       - 尝试 `OutputModel.model_validate(parsed)` 得到 `result_object`（失败则 None）
       - 写入 `cleaned_result/parsed_result/result_object`
    3. 若无 cleaned_json：
       - `cleaned_result=None; parsed_result=None`

### 3.2 generator(type="instant"/"streaming_parse")

instant/streaming_parse 的输出是 `StreamingData`：

- 输入：事件流中的 `delta` chunk
- 组件：`StreamingJSONParser(output_schema)`
  - `.parse_chunk(delta)`：产生多个 StreamingData（字段增量/完成）
  - `.finalize()`：在 done 时补全并生成最终 completion 事件

路径格式：

- 默认 dot path：`a.b[0].c`
- 若 settings `response.streaming_parse_path_style="slash"`：会把 dot 转成 slash（`DataPathBuilder.convert_dot_to_slash`）

### 3.3 `StreamingData` 的 wildcard/indexes 语义

定义：`agently/types/data/response.py::StreamingData`

- `path`：带具体下标的路径（如 `todos[3]`）
- `wildcard_path`：把具体下标替换成 `[*]` 的路径（如 `todos[*]`）
- `indexes`：提取的下标序列（tuple[int,...]）

这使得 `ensure_keys=["todos[*]"]` 可以表达“列表每项必须存在”的校验（注意：`ensure_keys` 校验是用 `DataLocator` 的 `[*]` 语法完成）。

## 4. `ensure_keys`（重试机制）规范

实现：`agently/core/ModelRequest.py::ModelResponseResult.async_get_data`

参数：

- `ensure_keys: list[str] | None`
- `key_style: "dot"|"slash"`：用于 `DataLocator.locate_path_in_dict`
- `max_retries: int`
- `raise_ensure_failure: bool`

算法：

1. 仅当 `type == "parsed" 且 ensure_keys 非空` 时启用
2. 获取 parsed
3. 对每个 ensure_key：
   - `DataLocator.locate_path_in_dict(parsed, ensure_key, key_style, default=EMPTY)`
   - 若返回 EMPTY：判定失败
4. 失败：
   - 发系统消息（stage=No Target Data...）
   - `_retry_count < max_retries` 时：重新创建 ModelResponse 并递归调用（相当于重新向模型发起请求）
   - 否则：
     - `raise_ensure_failure=True`：raise ValueError
     - 否则返回最后一次 parsed

## 5. 同步/异步一致性

- `get_generator`（同步）通过 `asyncio.run(self._ensure_consumer())` 初始化 consumer
- `get_async_generator`（异步）await `_ensure_consumer()`

复刻时需要保证：

- 同一 `ModelResponse` 的多个消费方可以独立消费（见 tests：多个 response 并发消费）
- 在 `cancel_logs()` 后日志输出停止，但解析仍然继续。
