# 08 / DataLocator（路径定位与 JSON 块抽取）复刻规格

实现：`agently/utils/DataLocator.py`  
测试来源：`tests/test_utils/test_data_locator.py`、`tests/test_plugins/test_response_parser/test_parse_response_with_comments.py`

DataLocator 的两大用途：

1. 从 dict/list 的复杂嵌套结构中定位某条路径（支持 wildcard）；
2. 从模型输出文本中抽取“最可能的输出 JSON block”（支持多 JSON 混杂、代码块、注释等）。

## 1. locate_path_in_dict（路径定位）

签名：

```python
locate_path_in_dict(original_dict: dict, path: str, style="dot"|"slash", default=None)
```

基础规则：

- `path==""` 或 path 非 str：返回 original_dict（整棵树）
- dot：
  - `a.b[2].c`：dict key 访问 + list index 访问
  - `[*]`：展开 list，对每个元素递归定位剩余路径；任何一个元素返回 default → 整体返回 default
- slash：
  - `/a/b/2/c`：按 `/` 分割；key 为 `*` 时展开 list；如果 segment 是数字字符串，会被当作 list index

返回值：

- 找不到 → default（默认 None）
- wildcard 展开 → list[values]

## 2. locate_all_json（抽取所有 JSON block）

目标：在一段任意文本中找出所有可能的 JSON-like 片段（`{...}` 或 `[...]`）。

算法要点（按实现）：

- 预处理：
  - triple quotes `"""..."""` 会被替换成 json5.dumps(内容)（避免内部括号干扰）
  - 把 `[OUTPUT]` 临时替换为 `$<<OUTPUT>>`，避免误判 block
- 单次线性扫描，维护：
  - stage（1=找起始 `{`/`[`，2=在 block 内）
  - layer（括号嵌套层）
  - in_quote、escape、skip_next
- 在 layer 回到 0 时收敛一个 block，存入列表
- 扫描结束返回 blocks list

复刻时要保留“字符串内转义与注释/换行处理”，否则在带注释/markdown 的模型输出中会显著降低抽取成功率。

## 3. locate_output_json（选择最可能的输出 JSON）

签名：

```python
locate_output_json(original_text: str, output_prompt_dict: dict) -> str | None
```

选择策略：

1. `all_json = locate_all_json(original_text)`
2. 若 `len(all_json)==0`：返回 None
3. 若 `len(all_json)==1`：返回该 block
4. 否则：
   - 遍历 `all_json[:-1]`：
     - 尝试 `json5.loads(json_string)`
     - 若解析结果是 dict，且其任意 key 命中 `output_prompt_dict` 的 key，则返回该 json_string
   - 若没有命中：返回 `all_json[-1]`

这一策略在测试里覆盖了：

- 文本中同时存在“解释 + incomplete JSON + 另一个 JSON object”的情况，应能根据 output_prompt_dict 选中更匹配的那个；
- JSON block 内可含 `//` 与 `/* */` 注释，并可被 `json5.loads` 成功解析（Completer 会负责补全）。

