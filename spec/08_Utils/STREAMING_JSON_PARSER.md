# 08 / StreamingJSONParser（结构化流式解析器）复刻规格

实现：`agently/utils/StreamingJSONParser.py`  
测试来源：`tests/test_utils/test_streaming_json_parser.py`

StreamingJSONParser 的目标是：在模型输出以 `delta` 字符串分片到达时，尽早解析出符合 output schema 的 JSON 结构，并产出 `StreamingData` 事件：

- `event_type="delta"`：某个 path 的值发生增量变化（尤其是字符串字段）
- `event_type="done"`：某个 path 被判定为“已完成”（不会再变化）

它与 `AgentlyResponseParser.get_generator(type="instant")` 配合，实现 UI 的“字段级流式渲染”。

## 1. 初始化与依赖

- 输入：`schema: dict`（Agently output schema）
- 依赖：
  - `StreamingJSONCompleter`（补全 JSON）
  - `DataLocator.locate_output_json`（从 buffer 抽取目标 JSON block）
  - `DataPathBuilder.extract_parsing_key_orders`（字段顺序）
  - `DataPathBuilder.extract_possible_paths`（可能路径集合）
  - `json5`（解析 JSON5）

内部状态（必须存在）：

- `previous_data/current_data: dict`
- `field_completion_status: set[str]`：已完成的 path
- `string_values: dict[str, str]`：用于字符串 delta 计算（path → 当前值）
- `expected_field_order: list[str]`：来自 `DataPathBuilder.extract_parsing_key_orders(schema, style="dot")`
- `all_possible_paths: set[str]`：来自 `DataPathBuilder.extract_possible_paths(schema, style="dot")`

## 2. parse_chunk（单片段解析）

输入：`chunk: str`（来自模型的增量 delta）

步骤（复刻级）：

1. `self.completer.append(chunk)`
2. `completed_json = self.completer.complete()`
3. `located_json = DataLocator.locate_output_json(completed_json, self.schema)`
4. 若 `located_json` 存在：
   - 尝试 `parsed_data = json5.loads(located_json)`
   - `self.previous_data = deepcopy(self.current_data)`
   - `self.current_data = parsed_data`
   - `yield` `_compare_and_generate_events()` 的所有事件
5. 若解析失败（`json.JSONDecodeError` 或 `ValueError`）：吞掉异常，不 yield（等待更多 chunk）

重要语义：`parse_chunk()` 允许“无输出”，且不会因为暂时无法解析而报错。

## 3. 事件生成（_compare_and_generate_events）

核心思想：递归对比 `current_data` 与 `previous_data`，按路径产出 delta 与 done。

### 3.1 路径表示

- 使用 `DataPathBuilder.build_dot_path(path_keys)` 得到 dot path：
  - 对 list index 输出 `a.b[0].c`

### 3.2 字符串字段（增量 delta）

当某个路径上的 `current_value` 为 `str`：

1. `previous_str = previous_value if isinstance(previous_value, str) else ""`
2. 若 `current_value != previous_str`：
   - 若 `previous_str` 非空且 `current_value.startswith(previous_str)`：
     - `delta = current_value[len(previous_str):]`（后缀增量）
   - 否则：
     - `delta = current_value`（全量作为增量；用于 previous 为空或结构跳变）
   - 若 delta 非空：
     - yield `StreamingData(path, value=current_value, delta=delta, is_complete=False, event_type="delta", full_data=current_data)`
     - 同时 `self.string_values[path] = current_value`
3. 然后执行完成判定（见第 4 节）：
   - 若完成：yield done（delta=None，is_complete=True）

测试不变量：

- username 分三段输入（"A" + "l" + "ice"）应产生至少 3 个 delta；将 delta 拼接得到最终值 `"Alice"`。

### 3.3 primitive（非 str 的叶子）

当 `current_value` 既不是 dict/list，也不是 None：

- 若 `current_value != previous_value`：
  - yield delta（`StreamingData.delta = current_value`）
- 若完成判定为真：
  - yield done

测试不变量：

- 某些字段允许没有 delta（例如 age），但如果存在 delta，则其 done 必须发生在 delta 之后。

### 3.4 dict/object

当 `current_value` 为 dict：

1. `previous_dict = previous_value if isinstance(previous_value, dict) else {}`
2. 遍历 `current_value.items()`：
   - 对每个 key 递归（child_path_keys = path_keys + [key]）
   - `previous_child = previous_dict.get(key)`
3. 子字段处理完后，对对象 path 本身执行完成判定：
   - 若完成：yield done（value 为整个 dict）

### 3.5 list/array

当 `current_value` 为 list：

1. `previous_list = previous_value if isinstance(previous_value, list) else []`
2. 遍历 `enumerate(current_value)`：
   - previous_child = `previous_list[i]`（若越界则 None）
   - 递归处理 child_path_keys = path_keys + [i]
3. 元素处理完后，对数组 path 本身执行完成判定：
   - 若完成：yield done（value 为整个 list）

测试不变量：

- `emails`、`languages` 等数组字段：最终 done 的 value 必须是完整 list，即使中间 chunk “缺一段”（因为最终 JSON 仍会被 completer+json5 完整解析）。

## 4. 完成判定（_should_mark_field_complete）

输入：

- `path: str`
- `current_value`
- `previous_value`

规则（复刻级，按源码顺序）：

1. 若 `path in field_completion_status`：返回 False
2. `current_parsing_paths = _get_current_parsing_paths()`：
   - 遍历 `current_data` 的 dict/list 结构
   - 收集所有“当前存在”的 dot path（对象/数组/叶子都在集合里；根路径空字符串不会加入）
3. `furthest_parsing_path = _get_furthest_parsing_path(current_parsing_paths)`：
   - 遍历 `current_parsing_paths`：
     - 若 path 在 `expected_field_order` 中：取其 index
     - 选择 index 最大者作为 furthest
   - 不在 expected_field_order 的 path 会被忽略
4. 主规则：
   - 如果 furthest 存在，且 `_is_path_before(path, furthest)` 为 True：
     - 且 `current_value == previous_value` 且 current_value 非 None → complete
5. 叶子字段额外规则：
   - 若 current_value 不是 dict/list 且非 None：
     - 遍历 `current_parsing_paths`：
       - 若 `_is_path_before(path, parsing_path)`：
         - 若 `current_value == previous_value` → complete
         - break
6. 否则 False

`_is_path_before(path1, path2)`：

- 若两者都可在 expected_field_order 找到 index：返回 `index1 < index2`
- 否则 fallback `_is_array_path_before(path1, path2)`：
  - 返回 `len(path1) < len(path2) or path1 < path2`

工程解释（必须理解但不必改变）：

- “如果解析已经推进到更靠后的字段，并且当前字段值稳定”，则认为该字段完成；
- 这是启发式完成判定，不是严格的 JSON 语法完成判定。

## 5. finalize（流结束时强制补齐 done）

`finalize()` 的目标是：为所有尚未 done 的路径补齐 done 事件，避免 UI “永远等不到完成信号”。

算法：

- 递归遍历 `current_data`：
  - dict：先递归子字段，再对对象 path 产出 done（如果没 done 过）
  - list：先递归元素，再对数组 path 产出 done
  - primitive：对 path 产出 done

测试不变量：

- 最后一个完成事件可能是根对象字段（例如 `"response"`），因为 schema 顶层 key 会在 current_data 中存在。

## 6. parse_stream

输入：`chunk_stream: AsyncGenerator[str]`

- 对每个 chunk：调用 `parse_chunk` 并 yield
- stream 结束：调用 `finalize` 并 yield

