# 07 / 集成：FastAPIHelper 规格

实现：`agently/integrations/fastapi.py`

Source: `agently/integrations/fastapi.py#FastAPIHelper`

该模块提供一个轻量的 FastAPI 集成层：把 `BaseAgent` / `ModelRequest` / `TriggerFlow` / `TriggerFlowExecution`（以及自定义 generator 函数）包装为 HTTP/SSE/WebSocket 接口，并提供统一的错误包装结构。

## 1. LazyImport

模块 import 时会执行：

- `LazyImport.import_package("fastapi", version_constraint=">=0.104")`

因此在未安装 fastapi 时会触发交互式 pip 安装提示（见 `spec/08_Utils/LAZY_IMPORT.md`）。

## 2. FastAPIHelperRequestData（请求 payload 协议）

实现：`FastAPIHelperRequestData(BaseModel)`

payload 语义固定为：

- `data: dict[str, Any]`：业务输入
- `options: dict[str, Any]`：传递给 provider 的可选参数（会被自动过滤）

解析规则（`FastAPIHelper._parse_request_payload`）：

- 当 payload 为 `str | bytes`：使用 `model_validate_json`
- 否则：使用 `model_validate`
- 解析失败统一抛 `ValueError`，错误信息包含“期望 JSON 对象包含 keys data/options”

注意：`options` 永远会被规整为 dict；如果请求侧未提供，则默认为 `{}`。

## 3. FastAPIHelper（应用容器）

`FastAPIHelper` 继承自 `fastapi.FastAPI`，构造参数：

```python
FastAPIHelper(
  response_provider=...,          # 必填
  response_warper=None,           # 可选：自定义响应包装器
  **fastapi_kwargs,
)
```

其中：

- `response_provider` 支持类型：
  - `BaseAgent`
  - `ModelRequest`
  - `TriggerFlow`
  - `TriggerFlowExecution`
  - `FastAPIHelperGeneratorFunction`（用户自定义函数，返回 Generator 或 AsyncGenerator）
- `response_warper`：`Callable[[SerializableValue | Exception], SerializableValue]`

### 3.1 默认响应包装（response_warper）

默认包装（`_default_response_warper`）：

- 正常返回值：
  - `{"status": 200, "data": <value>, "msg": None}`
- 异常：
  - `status` 映射：
    - `ValueError` → 422
    - `TimeoutError` → 504
    - 其它 `Exception` → 400
  - 返回结构：
    - `{"status": <status>, "data": None, "msg": <str(error)>, "error": <serialized>}`

异常序列化（`_serialize_exception`）包含：

- `type/module/message/args`
- 如果异常对象存在可调用 `errors()`：尝试附加 `validation_errors`（容错：errors() 若失败则忽略）
- 若存在 `__cause__`：附加 `cause`
- 若存在 `__context__` 且未 suppress：附加 `context`

## 4. Provider 适配（统一为 async generator / async result）

FastAPIHelper 的核心是把不同 provider 适配为统一执行路径：

- `_get_async_generator(request_data, options)`：用于 SSE/WebSocket 流式
- `_async_get_result(request_data, options)`：用于普通 GET/POST 一次性返回

### 4.1 BaseAgent

两种路径：

1) 若 agent 存在 `load_json_prompt` 方法（即混入 `ConfigurePromptExtension`）：
   - 通过 `load_json_prompt(json.dumps(request_data))` 将 request_data 视为 prompt DSL 批量配置
   - 然后调用 `agent.get_async_generator(**options)` 或 `agent.async_start(**options)`
2) 否则：
   - 遍历 `request_data` 的每个 key/value：
     - 如果 agent 上存在同名可调用方法（例如 `.system/.input/.output` 等），则调用该方法写入 prompt
     - 否则把该 key/value 汇入 `input_data`，最终执行 `agent.input(input_data)`
   - 然后调用 `agent.get_async_generator(**options)` 或 `agent.async_start(**options)`

### 4.2 ModelRequest

行为与 BaseAgent 类似：

- 对存在同名方法的 key/value 直接调用（例如 `.input/.output/.options` 等）
- 剩余字段聚合为 `input_data` 并调用 `request.input(input_data)`
- 然后调用 `request.get_async_generator(**options)` 或 `request.async_start(**options)`

### 4.3 TriggerFlow / TriggerFlowExecution

- 流式：调用 `get_async_runtime_stream(request_data, **options)`
- 一次性结果：调用 `async_start(request_data, **options)`
- 并发选项联动：
  - 当 provider 是 `TriggerFlowExecution` 且 `options["concurrency"]` 为 int 时，FastAPIHelper 会先调用 `execution.set_concurrency(concurrency)`

### 4.4 Callable（GeneratorFunction / AsyncGeneratorFunction）

当 `response_provider` 是可调用对象：

- 调用 `response_provider(request_data, **options)` 得到 generator
- 若为同步 `Generator`：使用 `FunctionShifter.asyncify_sync_generator(generator)` 桥接为 async generator
- 若为 `AsyncGenerator`：直接返回
- 否则抛 `TypeError`（报错信息会包含 provider 与返回值类型）

注意：FastAPIHelper 在调用 provider 前会使用 `FunctionShifter.auto_options_func` 自动过滤多余 `options` key（避免 provider 不接受多余 kwargs 时抛错）。

## 5. Handler 与对外路由

FastAPIHelper 提供四类 handler（均基于 `_parse_request_payload`）：

- `post_handler(body=Body(default=None))`：解析 body → `_async_get_result` → `response_warper`
- `get_handler(payload: str)`：解析 payload(str) → `_async_get_result` → `response_warper`
- `sse_handler(payload: str)`：解析 payload(str) → `_get_async_generator` → `StreamingResponse(text/event-stream)`
  - 正常 event：`data: <json>\n\n`
  - 异常 event：`event: error\ndata: <json>\n\n`
- `websocket_handler(websocket)`：`accept()` 后持续接收消息并逐条发送 JSON 文本；异常同样通过包装后发送

并提供便捷注册方法：

- `use_post(path, ...)` / `use_get(path, ...)` / `use_sse(path, ...)` / `use_websocket(path, ...)`

复刻实现建议：保持 payload 结构（data/options）、错误包装字段（status/data/msg/error）与 generator 桥接语义一致，否则示例与调用方会出现不可预期差异。
