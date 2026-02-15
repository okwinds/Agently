# 08 / Utils 规格（基础设施）

本章描述复刻实现时必须具备的“基础能力”。这些能力是框架可靠性与可扩展性的根基。

## 1. RuntimeData（层级运行时数据）

实现：`agently/utils/RuntimeData.py`

关键特性：

- 支持 parent 继承
- `get(inherit=True)` 返回“合并视图”：
  - dict：递归合并（child 覆盖 parent）
  - list/set/tuple：合并去重（child 为主，同时补齐 parent 中缺失项）
- `set`/`__setitem__` 是“合并式写入”：
  - 对 dict：递归 merge
  - 对 list：append 去重
  - 对 set：add 去重
  - 对普通值：覆盖
- 支持 dot path 写入：`data["a.b.c"] = 1`
- 支持 `load(json/yaml/toml 或文件)` 读入 dict 并 update

复刻实现如果替换 RuntimeData 语义，会导致：

- Settings 继承/合并行为变化（影响插件配置、debug profile）
- Prompt 的 parent/child 合并变化（影响 always prompt）
- ExtensionHandlers（也是 RuntimeData）行为变化

## 2. SerializableRuntimeData

实现：`agently/utils/SerializableRuntimeData.py`

约束：

- 只允许 `SerializableValue`（由 `agently/types/data/serializable.py` 定义）
- 提供 Namespace 视图（SerializableRuntimeDataNamespace）

## 3. DataLocator（路径定位 + JSON 抽取）

实现：`agently/utils/DataLocator.py`

### 3.1 locate_path_in_dict

支持：

- dot path：`a.b[0].c` + wildcard：`a.b[*].c`
- slash path：`/a/b/0/c` + wildcard：`/a/b/*/c`

返回 default（默认 None）作为“未找到”标记。

### 3.2 locate_all_json / locate_output_json

用途：从模型输出文本中抽取 JSON 块用于解析。

- `locate_all_json(text)`：扫描字符串，提取所有 `{...}` 或 `[...]` 形式的 JSON-like block
  - 会处理 triple quotes、转义、避免把 `[OUTPUT]` 等标记误判
- `locate_output_json(text, output_schema_dict)`：
  - 若只有一个 JSON block：返回它
  - 若多个：遍历 block，尝试 json5.loads，并检查其 key 是否命中 output_schema 的 key
  - 否则返回最后一个 block

复刻建议：保持该抽取策略，以最大化结构化输出解析成功率。

## 4. DataFormatter（清洗/序列化/占位符）

实现：`agently/utils/DataFormatter.py`

关键能力：

- `sanitize(value, remain_type=False)`：
  - 将 RuntimeData/BaseModel/type/typing origin 等转换为可 JSON/YAML 序列化形式
- `to_str_key_dict(value, value_format, default_key, default_value)`：
  - 将非 dict 值包装为 `{default_key: value}`（用于 auth 等配置）
- `from_schema_to_kwargs_format(json_schema)`：
  - 将 JSON Schema 转成 Tool kwargs 格式：`{kw: (type, desc)}`，并支持 additionalProperties
- `substitute_placeholder(value, mappings, placeholder_pattern=...)`

## 5. LazyImport（可交互依赖安装）

实现：`agently/utils/LazyImport.py`

行为：

- `import_package(pkg, auto_install=True, version_constraint=None)`：
  - import 失败时会在 stdout 打印缺失提示，并询问用户是否 pip install（交互式 input）
  - 若 version_constraint 不满足，也会提示并询问安装指定版本
- `from_import(from_package, target_modules, ...)`：
  - 支持 `import from_package.module` 或 `getattr(base_module, module_attr)`

复刻注意：

- 这是一个“交互式”机制，不适合无交互环境；但当前框架设计就是如此。
- 若要在生产环境复刻，应提供非交互的替代方案（例如抛出明确错误并由部署系统安装依赖）。

## 6. StreamingJSONCompleter / StreamingJSONParser

实现：

- `agently/utils/StreamingJSONCompleter.py`
- `agently/utils/StreamingJSONParser.py`

用途：

- Completer：补全不完整 JSON（未闭合括号、字符串、注释），用于提升 json5.loads 成功率
- Parser：基于 output schema，从 delta 流中增量构建结构并产出 StreamingData

StreamingJSONParser 的关键点：

- 维护 `previous_data/current_data` 与 `field_completion_status`
- 通过 `DataPathBuilder.extract_parsing_key_orders(schema)` 决定字段完成顺序
- 对 string 字段产出“增量 delta”（suffix 或全量）
- 在判断字段完成时产出 is_complete=True 的 done 事件

复刻实现可简化内部细节，但必须保证：

- 输入 delta chunk（字符串）能产出 path/value/delta/is_complete 的事件序列
- 支持 list 下标路径与 wildcard_path/indexes（配合 ensure_keys）

## 7. FunctionShifter / GeneratorConsumer

用途：

- `FunctionShifter`：syncify/asyncify，把 sync/async 函数统一调用；并支持 syncify_async_generator
- `GeneratorConsumer`：消费 async generator 并缓存结果，同时提供 sync/async generator 视图

这些是框架“同步 API + 异步底层”的关键胶水。

