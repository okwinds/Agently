# 03 / ResponseParser: AgentlyResponseParser 规格

实现：`agently/builtins/plugins/ResponseParser/AgentlyResponseParser.py`

AgentlyResponseParser 的职责是：

- 消费 ModelRequester 的统一事件流；
- 维护 `full_result_data`；
- 在 done 时对结构化输出进行抽取/补全/解析；
- 提供多种 generator 视图（delta/specific/all/original/instant）。

## 1. full_result_data（AgentlyModelResult）

字段（初始值）：

- `result_consumer: GeneratorConsumer | None`
- `meta: dict`
- `original_delta: list[dict|str]`
- `original_done: dict`
- `text_result: str`
- `cleaned_result: str | None`
- `parsed_result: SerializableValue`
- `result_object: BaseModel | None`
- `errors: list[Exception]`
- `extra: dict | None`

## 2. 解析（_extract）规范

按事件处理（核心分支）：

- `original_delta`：append 到 original_delta
- `delta`：
  - 拼接 buffer
  - 若 `$log.cancel_logs != True`：发 system_message stage=Streaming（delta=True）
  - 若 cancel_logs：只会发一次“logging canceled...”提示，然后停止 streaming 日志
- `done`：
  - `text_result = str(data)`
  - 若 output_format == json：
    - `DataLocator.locate_output_json(text_result, output_schema)`
    - `StreamingJSONCompleter.complete()`
    - `json5.loads()`
    - `OutputModel.model_validate(parsed)`（失败 => None）
  - 否则：
    - embeddings 特判：把 `[{object:"embedding", embedding:[...]}]` 变成 `[[...], ...]`
    - `parsed_result = data`
  - 发 system_message stage=Done（或无法解析时输出 ❌）
- `meta`：若 data 是 Mapping，则 update 到 meta
- `error`：若 data 是 Exception，则 append 到 errors

finally：如果 response_generator 有 aclose，则尝试关闭（suppress RuntimeError）。

## 3. get_(async)_data/get_text/get_meta

调用前会 `_ensure_consumer()`，确保 GeneratorConsumer 已启动并消费完毕。

- parsed：`parsed_result`（若有 copy 方法则返回 copy）
- original：`original_done.copy()`
- all：`full_result_data.copy()`

## 4. get_(async)_generator(type=...)

支持 type：

- `all`：yield (event, data)
- `delta`：yield str（仅 delta 事件）
- `specific`：yield (event, data)（event ∈ specific）
- `original`：yield data（event.startswith("original")）
- `instant`/`streaming_parse`：
  - 当 output_format == json 且 StreamingJSONParser 存在：
    - `delta`：`parse_chunk(delta)` 得到 StreamingData 序列并 yield
    - `tool_calls`：yield StreamingData(path="$tool_calls", value=data)
    - `done`：`finalize()` 并 yield completion events
  - path_style == slash 时：转换 path

兼容性说明：`instant` 在协议中被认为是 `streaming_parse` 的 v3 兼容别名。

