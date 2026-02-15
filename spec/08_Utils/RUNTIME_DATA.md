# 08 / RuntimeData（层级运行时数据）复刻规格

实现：`agently/utils/RuntimeData.py`  
测试来源（行为基准）：`tests/test_utils/test_runtime_data.py`、`tests/test_utils/test_runtime_data_2.py`

RuntimeData 是 Agently 里“所有可继承数据结构”的底座：Settings、Prompt、ExtensionHandlers、PluginManager.plugins 都建立在它的合并语义之上。复刻时，必须把**读取合并**与**写入合并**的规则做成完全一致，否则会出现隐蔽的不兼容。

## 1. 数据模型

- `RuntimeData(data: dict | None = None, name: str | None = None, parent: RuntimeData | None = None)`
- 内部存储：`self._data: dict`
- `parent` 参与默认的 `get(inherit=True)` 合并视图
- `name` 仅用于调试/日志

## 2. 读取语义（get/[]）

### 2.1 `get(inherit=True)` 的合并视图（关键不变量）

当 `inherit=True` 且存在 parent 时，返回视图满足：

- **dict**：递归合并
  - 子层不存在的 key 从 parent 补齐
  - 子层与 parent 同 key 且两者都是 dict → 递归合并
  - 子层与 parent 同 key 且子层不是 dict → 子层覆盖 parent
- **list**：合并去重（以子层为主）
  - 若 parent[key] 是 list/set/tuple：把 parent 里的每个 item 追加到子层 list（如果不在子层中）
  - 若 parent[key] 是单值：若不在子层 list 中则追加
- **set**：合并去重（以子层为主）
  - 若 parent[key] 是 list/set/tuple：逐个 add
  - 若 parent[key] 是单值：add
- **tuple**：不做可用的合并（测试里把 tuple 当作普通值/边界情况）
- **普通值**：子层优先

注意：返回的是深拷贝视图（copy），不是原始引用（测试 `test_copy_behavior` 覆盖）。

### 2.2 dot path 读取（`rd["a.b.c"]`）

- 支持 `.` 分隔的嵌套 dict 路径读取
- key 不存在时返回 `None`

### 2.3 非字符串 key

RuntimeData 支持非字符串 key（例如 `object()` 作为 key），且其值也可再次包装为 RuntimeData 用 dot path 读取（见测试 `RuntimeData(self.data[self.GLOBAL])["p.a"]`）。

## 3. 写入语义（set/[]）

### 3.1 `__setitem__`：合并式写入（关键不变量）

- 如果 key 是包含 `.` 的字符串：走 `_set_item_by_dot_path`
  - 自动创建缺失的中间 dict
  - 若中间路径处不是 dict，会抛 TypeError（“cannot set because not a dictionary”）
  - 默认是合并写入，不是覆盖写入
- 如果 key 是普通 key：
  - 若该 key 已存在：按 `_set_item` 的类型合并规则写入
  - 若不存在：直接 deep copy 写入

### 3.2 `_set_item` 合并规则（写入时的类型分派）

给定 `ref` 指向当前已有的容器（可能是 dict/list/set/普通值）：

- 若 `ref.get()` 是 dict 且新 value 是 Mapping：
  - 对每个 k：
    - 若不存在：copy 写入
    - 若存在：递归 `_set_item(ref.move_in(k), item_value)`
- 若 `ref.get()` 是 list：
  - 若新 value 是 Sequence 且非 str：逐个 append（若不在 list）
  - 否则：单值 append（若不在 list）
- 若 `ref.get()` 是 set：
  - 若新 value 是 Iterable 且非 (str/bytes)：逐个 add
  - 否则：add 单值
- 否则（普通值）：
  - 如果 existing 为 None：
    - 新 value 是 list：写入 list 的 copy
    - 否则：写入 value copy
  - 如果 existing 是 list：
    - 新 value 是 list：逐个 append（若不在 existing）
    - 否则：append 单值（若不在 existing）
  - 其它：直接覆盖 set

这些规则导致一个非常重要的工程事实：**同一个 path 在不同层（grandparent/parent/child）写入不同类型时，最终效果由“最子层类型”主导**，并且会发生“向 list/set 追加 parent 值”的行为（见 `tests/test_utils/test_runtime_data.py::test_setting_in_different_types`）。

## 4. 删除语义

- `del rd["a"]` 删除顶层 key
- `del rd["a.b.c"]` 删除嵌套 key（只删除叶子，不删除空父节点）
- `pop(key, default)` 支持 dot path

## 5. Namespace（RuntimeDataNamespace）

`rd.namespace("ns")` 返回一个视图对象，把所有操作限定在 `ns` 子树：

- `ns["a"]` 等价 `rd["ns.a"]`
- `ns.update({...})` 等价更新 `rd["ns...."]`

复刻时建议保持 namespace 的语义与原实现一致（它是很多模块“分区存储”的惯用写法）。

## 6. load/dump（序列化 I/O）

### 6.1 `load(type, value)`

支持：

- `json/yaml/toml`（字符串）
- `json_file/yaml_file/toml_file`（文件路径）

要求：

- 解析结果必须是 dict，否则抛 TypeError

### 6.2 `dump(type)`

把 RuntimeData 转成可序列化数据（内部 `_get_serializable_data`），规则：

- datetime/date → ISO string
- Path → str(path)
- set/tuple → list
- RuntimeData / Namespace → 递归提取其 `.data`

## 7. DictRef（内部辅助类）

`DictRef(container, key=None)` 用于在递归写入中定位“当前引用”，其规则在 `tests/test_utils/test_runtime_data_2.py::TestDictRef` 中覆盖（root set 只能 set dict，否则 TypeError）。

