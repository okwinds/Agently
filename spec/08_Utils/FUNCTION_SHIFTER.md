# 08 / FunctionShifter（sync/async 桥接）复刻规格

实现：`agently/utils/FunctionShifter.py`  
测试来源：`tests/test_utils/test_function_shifter.py`

FunctionShifter 是 Agently 中“同步 API + 异步内部实现”的关键胶水。

## 1. syncify

签名：

```python
syncify(func) -> sync_func
```

行为：

- 若 func 是 coroutine function：
  - wrapper 调用时：
    - 如果当前线程没有 running loop：`asyncio.run(func(*args, **kwargs))`
    - 如果存在 running loop：把 coroutine 移到新线程中执行（`run_async_func_in_thread`），内部也用 `asyncio.run`
- 若 func 是普通 function：原样返回

关键点：这是一种“强行同步化”的策略，确保在任何上下文都可调用（但在已存在 loop 的 async 环境会起线程）。

## 2. asyncify

签名：

```python
asyncify(func) -> async_func
```

行为：

- 若 func 已是 coroutine function：原样返回
- 否则：返回 wrapper，内部 `await asyncio.to_thread(func, *args, **kwargs)`

## 3. future

签名：

```python
future(func) -> func_returning_asyncio_Future
```

行为：

- 把 func asyncify 后，调度到某个 event loop：
  - 若存在 running loop：用该 loop
  - 否则：懒启动一个全局后台线程与 event loop（`_future_loop`），loop.run_forever
- 返回 `asyncio.ensure_future(async_func(...), loop=loop)`

实现里对异常回调的处理较粗糙（`exception = future.add_done_callback(lambda t: t.exception())`），复刻时建议保持行为一致（即异常仍会在 await/结果获取时暴露）。

## 4. syncify_async_generator

把 async generator 转成同步 generator：

- 在新线程里建 event loop，消费 async gen：
  - item → queue.put(("item", item))
  - error → queue.put(("error", e))
  - finally → queue.put(("end", SENTINEL))
- 主线程同步 yield item，遇到 error raise，遇到 end break
- finally join 线程

此能力被 ResponseParser 的同步 generator 模式使用。

## 5. auto_options_func（kwargs 过滤器）

用途：把一个“不接受多余 kwargs”的函数包装成“自动过滤多余 kwargs”的函数。

规则：

- inspect.signature
- 如果函数没有 `**kwargs` 参数：
  - wrapper 只保留 signature 中出现且 kind 是：
    - POSITIONAL_OR_KEYWORD
    - KEYWORD_ONLY
  的 kwargs
- 最终调用 func(*args, **filtered_kwargs*)

测试覆盖：原函数用多余参数会 raise；包装后会过滤掉多余 key 并正常返回。

