# 08 / DataPathBuilder（路径构造与 schema 路径枚举）复刻规格

实现：`agently/utils/DataPathBuilder.py`  
测试来源：`tests/test_utils/test_data_locator.py`

DataPathBuilder 是三类能力的集合：

1. dot/slash path 的构造与互转；
2. 从 output schema（Agently 输出结构）提取“可能路径集合”（possible paths）；
3. 从 output schema 提取“解析顺序路径列表”（parsing key orders），用于 StreamingJSONParser 的字段完成判定。

## 1. 路径构造

### 1.1 `build_dot_path(keys)`

- keys=[] → `""`
- str key：
  - 第一个 key：`"a"`
  - 后续 key：追加 `".<key>"`
- int key：追加 `"[<i>]"`（不会插入点号）
- key 等于 `"*"`, `"[]"`, `"[*]"`：统一输出 `[*]`（以 bracket 形式表达 wildcard）

示例：

- `["a","b",0,"c"]` → `a.b[0].c`
- `["items","[*]","id"]` → `items[*].id`

### 1.2 `build_slash_path(keys)`

- keys=[] → `""`
- 结果以 `/` 开头，key 之间以 `/` 分隔：
  - `["a","b",0,"c"]` → `/a/b/0/c`

### 1.3 `convert_dot_to_slash(dot_path)`

规则：

- `""` → `"/"`
- 解析 dot_path：
  - `.` 分段
  - `[...]` 保留为一个 segment（如 `[*]`、`[0]`）
  - 结果为 `"/" + "/".join(segments)`

示例：

- `user.name` → `/user/name`
- `tasks[*].id` → `/tasks/[*]/id`

### 1.4 `convert_slash_to_dot(slash_path)`

规则：

- `""` 或 `"/"` → `""`
- segments = `slash_path.strip("/").split("/")`
- segment 如果形如 `[...]`：直接 append（不加点）
- 其它：
  - 第一个 segment：直接 append
  - 后续 segment：前缀 `.` 再 append

示例：

- `/user/name` → `user.name`
- `/tasks/[*]/id` → `tasks[*].id`

## 2. 从 output schema 提取路径

schema 输入要求：

- `agently_output_dict` 必须是 dict，否则 TypeError
- schema 节点可能是：
  - tuple：表示 `(type_or_schema, desc?, default?)`
  - dict：对象
  - list：数组 schema
  - typing list[T]（origin is list）
  - 其它类型/值（叶子）

### 2.1 `extract_possible_paths(schema, style="dot") -> set[str]`

遍历策略（递归）：

- 每到一个节点，先把当前路径加入集合（包括根路径 `""` 或 `"/"` 风格对应的 build 结果）
- tuple：递归到 tuple[0]（不改变 path_keys）
- dict：对每个 key 递归（path_keys + [key]）
- typing list[T]：递归到 T（path_keys + ["[*]"]）
- list：[item_schema...]：对每个 item 递归（path_keys + ["[*]"]）

输出包含所有“可能存在的路径”，用于：

- 结构化流式解析的路径集合参考
- UI 订阅路径（例如只关心某个字段 path）

### 2.2 `extract_parsing_key_orders(schema, style="dot") -> list[str]`

目的：返回一个按 schema 定义顺序遍历的“路径序列”，用于 StreamingJSONParser 判断“哪个字段更靠后”。

遍历策略与 possible_paths 类似，但使用 `OrderedDict` 去重并保持顺序：

- tuple：先 traverse tuple[0]，再把当前 path 记录一次（保证 leaf 与其祖先都在顺序里）
- dict：先遍历子字段，再记录当前 path
- typing list[T]：先遍历 T（追加 `[*]`），再记录当前 path
- list：对每个 item traverse（追加 `[*]`），再记录当前 path
- leaf：记录当前 path

关键点：**容器节点（对象/数组）也会出现在 parsing order 中**，这会影响 StreamingJSONParser 的 completion 判定（对象/数组也会被标记 done）。

## 3. get_value_by_path（从数据取值）

`get_value_by_path(data, path, style="dot")`：

- data 必须是 dict，否则 TypeError（尽管签名允许 Mapping|Sequence）
- 支持 dot 与 slash
- dot path 支持 `[...]` 语法：
  - `[*]` 会展开并收集所有匹配结果（flatten）
- slash path 支持数字段自动转 int

返回：

- 找不到路径 → `None`
- wildcard `[*]` → `list`（可能为空 list 或包含 nested flatten 后的结果）

