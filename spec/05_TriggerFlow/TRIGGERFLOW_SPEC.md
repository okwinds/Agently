# 05 / TriggerFlow 规格（工作流编排 DSL）

核心实现：

- `agently/core/TriggerFlow/TriggerFlow.py`
- `agently/core/TriggerFlow/BluePrint.py`
- `agently/core/TriggerFlow/Execution.py`
- `agently/core/TriggerFlow/Chunk.py`
- `agently/core/TriggerFlow/process/*`

TriggerFlow 是事件驱动的工作流系统。它的 DSL 实际是在 BluePrint 上注册 handler：

- 触发源（trigger_type）：
  - `event`：显式事件（包括 chunk trigger、START、用户 emit）
  - `runtime_data`：执行时的局部数据变更
  - `flow_data`：TriggerFlow 实例级全局数据变更（跨 execution）

## 1. TriggerFlow（顶层）

### 1.1 构造

```python
TriggerFlow(blue_print=None, name=None, skip_exceptions=False)
```

内部：

- `settings`：继承全局 settings
- `_flow_data: RuntimeData`：跨 execution 的共享数据
- `_blue_print`：handler 图
- `_executions: dict[id, TriggerFlowExecution]`
- `_start_process`：一个 TriggerFlowProcess，用于从 START 事件开始链式 DSL

### 1.2 chunk 定义

`TriggerFlow.chunk(handler_or_name)`：

- 传入函数：创建 `TriggerFlowChunk(handler, name=handler.__name__)` 并注册到 blueprint
- 传入字符串：返回装饰器 wrapper，用于给 chunk 自定义 name

Chunk 的行为：

- 调用 handler 得到 result
- `emit(chunk.trigger, result)`（trigger 名为 `Chunk[<handler_name>]-<uuid>`）

## 2. BluePrint（工作流图）

BluePrint 保存：

- `_handlers`：三类 handler 映射：event/flow_data/runtime_data
- `chunks`：name → TriggerFlowChunk

add_handler 会为每个 handler 分配唯一 handler_id（可指定 id）。

create_execution 会对 handlers/chunks 深拷贝快照，创建 TriggerFlowExecution。

## 3. Execution（一次运行）

Execution 保存：

- `_handlers`：来自 blueprint 的快照（避免运行时图变更影响已有 execution）
- `_runtime_data`：execution 局部数据
- `_system_runtime_data`：系统状态（result/result_ready/match_results/for_each_results 等）
- `_runtime_stream_queue`：runtime stream 队列
- `_concurrency_semaphore`：全局并发限制（可选）
- `_concurrency_depth`：ContextVar，用于避免嵌套 emit 反复获取 semaphore（depth>0 时不再占用 semaphore）

核心方法：

- `async_emit(trigger_event, value, trigger_type="event")`
  - 发系统消息 TRIGGER_FLOW（用于日志）
  - 找到对应 handlers 并并发执行（respect skip_exceptions）
  - 并发限制逻辑：
    - 外层 emit 获取 semaphore
    - 内层（depth>0）不再获取
- runtime_data/flow_data set/append/del：
  - 写入后会触发同名 key 的 handler（trigger_type=runtime_data/flow_data）
- `async_start(initial_value, wait_for_result=True, timeout=10)`
  - emit START
  - 等待 result_ready

## 4. DSL：BaseProcess.when/to/batch/collect/end/____

定义：`TriggerFlowBaseProcess`

### 4.1 when

支持输入：

1. str（事件名）或 TriggerFlowChunk：返回新的 process，触发源为 event
2. dict：可组合多个 trigger：
   - `{"event": [...], "runtime_data": [...], "flow_data": [...], "collect": ...}`

当组合多个 trigger 且数量>1 时：

- 创建 `when_trigger = "When-<uuid>"`
- 为每个 trigger 注册一个 wait_trigger handler
- mode：
  - `and`：收集所有触发值，全部到齐后 emit when_trigger（value=values dict）
  - `or`：任意触发即 emit when_trigger（value=(type,event,value)）
  - `simple_or`：任意触发即 emit when_trigger（value=value）

实现一致性注意（复刻必须保留的现版本边界行为）：

- 在 `mode="and"` 的实现里，源码中用于“写入 values”的判断条件存在一个变量引用问题：
  - 代码形如：`if data.trigger_type in values and data.trigger_event in values[trigger_type]: ...`
  - 其中 `trigger_type` 来自构建 `values` 时的外层循环变量，而不是 `data.trigger_type`
- 该问题会导致 `and` 模式下对 `values[...]` 的更新在某些输入顺序/组合下失效，从而表现为：
  - `When-<uuid>` 可能永远不会被 emit（一直等待 values 中的 EMPTY 变为真实值）
- 因此，“完美复刻”需要按现实现重现该行为；如果你希望在复刻实现中修复它，应明确记录为与 Agently 4.0.7.1 的不兼容差异。

### 4.2 to

`to(chunk|handler|name|("name", handler), side_branch=False)`

- 会把 handler 转成 chunk（若不是已有 chunk）
- 在当前 trigger 上注册 handler：`blue_print.add_handler(trigger_type, trigger_event, chunk.async_call)`
- 返回新的 process：
  - 若 side_branch=False：下一段链路的 trigger_event 为该 chunk.trigger
  - side_branch=True：保持当前 trigger_event（分支不改变主链路）

### 4.3 batch

`batch(*chunks, side_branch=False, concurrency=None)`

语义：在同一 trigger 下并发执行多个 chunk，等待全部完成后 emit batch_trigger。

- 为每个 chunk 注册 handler（可选 semaphore 做 batch 内并发限制）
- 同时注册一个 wait_all_chunks 监听各 chunk.trigger，收集 result
- 全部 done 后 emit `Batch-<uuid>`，value 为 `{chunk_name: result}`

### 4.4 collect

`collect(collection_name, branch_id=None, mode="filled_and_update"|"filled_then_empty")`

语义：用于多个分支结果汇聚。

- 在 block_data.global_data.collections 下为 branch_id 初始化 EMPTY
- 每个分支结束时写入自身结果；当所有 branch 都非 EMPTY：
  - emit `Collect-<collection_name>`，value 为该 collection dict
- mode=filled_then_empty 时会清空 collection（一次性）

实现一致性注意：

- 源码使用 `with Lock(): ...` 来保护初始化写入，但该 Lock 是在调用处临时创建的实例（不是共享锁），因此它在多线程下并不提供真实的互斥保护；复刻实现若要严格一致，应视为“无有效锁”。

### 4.5 end

语义：设置 execution result（如果尚未设置）。

- 若 `_system_runtime_data.result` 仍为 EMPTY：设置为当前 value
- 触发 result_ready Event

### 4.6 ____

链式表达式分隔符。可选打印/日志当前 value 与 annotations，不影响数据流。

## 5. DSL：ForEachProcess

`for_each(concurrency=None)`：

- 创建 for_each_id 与 block_data（嵌套层）
- send_items 会：
  - 对输入 data.value：
    - 如果是 Sequence 且非 str：遍历 items
    - 否则视为单个 item
  - 为每个 item 分配 layer mark（item_id），并在 system_runtime_data.for_each_results 下写 EMPTY
  - emit `ForEach-<id>-Send`（每个 item 一次，可并发）

`end_for_each()`：

- 收集每个 item 的结果；当某个 for_each_instance 的所有 item 都完成：
  - emit `ForEach-<id>-End`，value 为按 item_id 顺序的结果 list
  - 清理 for_each_results

## 6. DSL：MatchCaseProcess

`match(mode="hit_first"|"hit_all")`：

- 为每个 case 分配 case_id，并在命中时 emit `Match-<id>-Case-<case_id>`
- hit_first：命中第一个就 return
- hit_all：
  - 为每个命中 case 分配 layer mark（用于收集结果）
  - 最终在 end_match 汇聚为 list

`case(condition)`：

- condition 可为 callable(data)->bool 或 SerializableValue（与 data.value 比较）

`case_else()`：

- else 分支（若没有命中任何 case 时执行）

`end_match()`：

- 汇聚所有分支结果，emit `Match-<id>-Result`

别名：

- `if_condition/elif_condition/else_condition/end_condition`

## 7. 复刻实现建议

TriggerFlow 的复刻难点在于：

- layer mark 的嵌套与 result 收集（match/for_each）
- 并发限制（全局 execution concurrency + batch/for_each 局部 concurrency）
- handler 图的“构建期 vs 运行期”分离（blueprint 快照）

建议复刻时保持相同的事件命名约定（When-/Batch-/ForEach-/Match-/Collect-/Chunk[...]），以便示例代码与日志行为一致。
