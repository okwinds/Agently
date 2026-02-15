# 08 / DataFormatter（清洗/类型保留/Schema 转换）复刻规格

实现：`agently/utils/DataFormatter.py`  
测试来源：`tests/test_utils/test_data_formatter.py`

## 1. sanitize(value, remain_type=False)

目标：把任意复杂对象转换成“可序列化、可打印、可用于 prompt”的形式。

核心规则（按实现）：

- 基础类型（str/int/float/bool/None）→ 原样
- datetime/date → `.isoformat()`
- RuntimeData / Namespace → 递归 sanitize `.data`
- `type`：
  - 若是 Pydantic `BaseModel` 子类：
    - 展开其 `model_fields`，生成 `{field_name: (annotation, desc?)}` 的 schema dict
    - annotation 会尝试 `field.rebuild_annotation()`，失败则用 field.annotation
  - 否则：
    - remain_type=False：返回 `value.__name__`（例如 `"str"`）
    - remain_type=True：返回 type 本身
- typing origin（`get_origin(value) != None`）：
  - remain_type=True：原样返回 typing 对象
  - remain_type=False：转成字符串表达：
    - list[T] → `"list[<T>]"`（T 会递归 sanitize）
    - dict[K,V] → `"dict[K, V]"`
    - tuple[...]、Union、Literal 等同理
- dict/list/set/tuple：递归 sanitize
- 兜底：`str(value)`

关键不变量（测试覆盖）：

- remain_type=True 时必须保留 Pydantic 泛型类型（例如 list[dict[str,str]] 不能退化成 string）
- remain_type=False 时允许退化成 `"list"`（在某些环境/版本下泛型字符串可能不稳定），测试允许两种结果

## 2. to_str_key_dict

用途：把“可能不是 dict 的值”规整为 dict，并把 key 强制转成 str。

规则：

- value 是 Mapping：
  - value_format=None：key sanitize→str；value 原样
  - value_format="serializable"：value 也 sanitize
  - value_format="str"：value sanitize 后再 str()
- value 非 Mapping：
  - 若提供 default_key：返回 `{default_key: value}` 再递归转换
  - 否则返回 default_value

## 3. from_schema_to_kwargs_format（JSON Schema → Tool kwargs）

输入：JSON Schema dict，要求：

- `schema["type"] == "object"`，否则 TypeError
- 不存在 "type" → KeyError

输出：`KwargsType`（dict[name] = (type, desc)）

规则：

- 遍历 `properties`：
  - kwarg_type = schema.pop("type", Any)
  - 删除 title
  - kwarg_desc = `";".join(f"{k}: {v}" ...)`
- 处理 additionalProperties：
  - False：不加 `<*>`
  - True/None：加 `<*>: (Any, "")`
  - dict：加 `<*>: (additional_type, additional_desc)`
  - 其它：加 `<*>: (Any, "")`

测试覆盖了 additionalProperties 的三种形态（false/true/schema）。

