# 08 / GeneratorConsumer（多订阅消费器）复刻规格

实现：`agently/utils/GeneratorConsumer.py`  
测试来源：`tests/test_utils/test_generator_consumer.py`

GeneratorConsumer 用于把一个（async）generator 变成“可被多个订阅者重复消费”的事件源，并支持：

- 历史回放（late subscriber 可以 replay）
- 异常广播（异常会被所有订阅者感知并 raise）
- 同步订阅（通过线程桥接）
- close 后禁止再次订阅

这是 ResponseParser/TriggerFlow 等模块支持“一个 response 被多个消费者同时读”的关键组件。

## 1. 初始化

输入必须是：

- `types.GeneratorType` 或 `types.AsyncGeneratorType`

否则 TypeError。

内部状态：

- `_history: list`：存储所有非异常、非 sentinel 的 msg
- `_listeners: list[asyncio.Queue]`：每个订阅者一个 queue
- `_consume_task: asyncio.Task | None`：第一次订阅时启动
- `_done: asyncio.Event`：源 generator 结束时 set
- `_exception: Exception | None`：源异常
- `_closed: bool`：close 后 True
- `_sentinel: object`：结束标记

## 2. 消费与广播

`_consume()`：

- 逐条读取源 generator：
  - item → `_broadcast(item)`
- 捕获异常：
  - `_exception = e`
  - `_broadcast(e)`（异常也作为消息发给 listeners）
- finally：
  - `_done.set()`
  - 若尚未 broadcast sentinel：`_broadcast(_sentinel)`

`_broadcast(msg)`：

- msg 不是 sentinel 且不是 Exception → append 到 history
- 对每个 listener queue：`await queue.put(msg)`

## 3. get_async_generator（异步订阅）

行为：

1. 若 `_closed=True`：raise RuntimeError
2. 确保 started（启动 `_consume_task`）
3. 创建 queue，加入 listeners
4. 将 history replay 到 queue
5. 若 `_exception` 已存在：把异常放入 queue（订阅者会马上 raise）
6. 若 `_done` 已 set：把 sentinel 放入 queue
7. 循环读取 queue：
   - sentinel → break
   - Exception → raise
   - 否则 yield msg
8. finally：从 listeners 移除 queue

测试覆盖了：

- 多次订阅会 replay 同样的历史；
- 源抛异常时，订阅方会 raise，并且能收到异常前的消息；
- 源结束后仍可重复订阅（replay after done）。

## 4. get_generator（同步订阅）

实现策略：起一个 daemon thread，在 thread 内 `asyncio.run(bridge())`：

- bridge 内部与 get_async_generator 类似，但把每条 msg 放入一个同步 `queue.Queue`（sync_q）
- 主线程同步 generator 从 sync_q 拉取：
  - sentinel → break
  - Exception → raise
  - 否则 yield msg

注意：同步订阅始终新起线程；这在高频调用时有成本，但复刻需保持语义一致。

## 5. get_result

等待源结束并返回 history：

- 若源抛异常：raise
- 否则返回 `_history`

## 6. close

`close()`：

- `_closed=True`
- cancel consume_task（若存在）
- `_done.set()`
- broadcast sentinel（如果还没 broadcast）

测试覆盖：close 后再次 get_async_generator/get_generator 必须 raise RuntimeError。

