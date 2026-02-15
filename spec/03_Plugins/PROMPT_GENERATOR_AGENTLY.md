# 03 / PromptGenerator: AgentlyPromptGenerator 复刻级规格

实现：`agently/builtins/plugins/PromptGenerator/AgentlyPromptGenerator.py`  
测试来源（可执行规格）：`tests/test_plugins/test_prompt_generator/test_agently_prompt_generator.py`

AgentlyPromptGenerator 的职责（对外接口是 `Prompt` 的方法）：

1. 将 `Prompt`（RuntimeData-like dict）规范化为 `PromptModel`（Pydantic）
2. 生成两种模型输入：
   - `to_text()`：单条文本 prompt（YAML 风格分块，首行 `user:`，末行 `assistant:`）
   - `to_messages()`：OpenAI-style chat messages（支持 rich content）
3. 根据 output schema 动态生成 Pydantic OutputModel（`to_output_model()`）
4. 将 prompt 导出为“可序列化数据”（`to_serializable_prompt_data/to_json_prompt/to_yaml_prompt`）

本文件以“**复刻实现 = 复现当前版本的行为（包括边界行为/潜在缺陷）**”为标准。

## 1. Prompt 空检查（_check_prompt_all_empty）

触发条件：

- `PromptModel.model_extra` 为空（即用户未自定义 extra keys）
- 且下列标准字段全部“空值”：
  - `input/info/instruct/output/attachment`
  - 空值判定：`None, "", [], {}`

触发结果：通过 messenger 抛 `KeyError`，错误文本固定为：

`Prompt requires at least one of 'input', 'info', 'instruct', 'output', 'attachment' or customize extra prompt keys to be provided.`

注意：

- `tools/action_results/examples/chat_history/system/developer/output_format` **不会参与**该空检查。
- 因此“只设置 tools”等仍会被认为是“空 prompt”并报错（复刻时必须保留）。

## 2. to_prompt_object（Prompt → PromptModel）

算法：

- `PromptModel(**self.prompt)`（直接用 Prompt 里的 dict 展开构造）
- `PromptModel` 的行为（例如：当设置 `output` 时自动把 `output_format` 变为 `"json"`）属于类型层面的约束，见测试 `test_to_prompt_object`。

## 3. to_text：YAML 分块文本 prompt（复刻级）

签名：`to_text(role_mapping: dict[str,str]|None=None) -> str`

### 3.1 role mapping 合并

- `merged_role_mapping = settings["prompt.role_mapping"]`（若非 dict 则视为 `{}`）
- 若传入 `role_mapping` 是 dict：`merged_role_mapping.update(role_mapping)`
- 生成首行 role：
  - `merged_role_mapping["user"]` 存在则用其值，否则字面量 `"user"`
- 生成末行 role：
  - `merged_role_mapping["assistant"]` 存在则用其值，否则字面量 `"assistant"`

### 3.2 分块顺序（严格）

输出始终由以下部分按顺序拼接（每部分使用 `\n` 连接；部分末尾通常会追加一个空行）：

1. 首行：`<user_role>:`（例如 `user:`）
2. `system`（如果存在）：`[SYSTEM]:` + YAML dump/str + 空行
3. `developer`（如果存在）：`[DEVELOPER DIRECTIONS]:` + YAML dump/str + 空行
4. `chat_history`（如果存在）：
   - 首行：`[CHAT HISTORY]:`（标题来自 `settings["prompt.prompt_title_mapping"].get("chat_history","CHAT HISTORY")`）
   - 对每条历史消息：
     - role：按 `merged_role_mapping` 映射
       - 优先 `merged_role_mapping[message.role]`
       - 否则若存在 `merged_role_mapping["_"]` 用它兜底
       - 否则用原 role
     - content：
       - 若 content 是 `{"type": ...}` dict：视为单元素 list
       - 若 content 是 list：逐个验证为 `ChatMessageContent`，仅当 `type=="text"` 才输出为一行：`[<role>]:<text>`
       - 非 text part：warning 并跳过
       - 否则：输出 `DataFormatter.sanitize(content)` 的字符串形态
   - chat_history 块末尾追加一个空行
5. `main prompt`：由 `_generate_main_prompt()` 生成的列表（见 4 节），逐行追加
6. 末行：`<assistant_role>:`（例如 `assistant:`）

### 3.3 tests 的“金标准”示例（必须逐字一致）

见 `tests/.../test_to_text` 与 `test_to_text_complex`：当给定 input/info/instruct/output 时，`to_text()` 输出必须与测试断言完全一致（包括空行、缩进、逗号与 `// desc` 注释位置）。

## 4. main prompt 生成（_generate_main_prompt）

该函数返回 `list[str]`，用于：

- `to_text()`：逐行写入文本 prompt
- `to_messages()`（rich_content=True 时）：作为 `{"type":"text"}` 的 `text` 字段内容（用 `\n`.join）
- `to_messages()`（rich_content=False 时）：作为最终 user message 的 string content（用 `\n`.join）

顺序与规则（严格）：

1. tools（仅当 `prompt_object.tools` 是 list）
   - 先输出 `[TOOLS]:`
   - 对每个 tool_info（dict）输出一个方括号块：
     - 输出 `[`、然后每个 key/value 一行、再输出 `]`
     - key 属于 `("kwargs","returns")` 时：用 `_generate_json_output_prompt()` 输出结构示例
2. action_results：用 `_generate_yaml_prompt_list(title, action_results)` 追加
3. info：
   - 输出 `[INFO]:`
   - Mapping：逐项输出 `- <title> : <sanitized>`
   - Sequence 且非 str：逐项输出 `- <sanitized>`
   - 其他：直接输出 `DataFormatter.sanitize(info)`
   - 最后追加一个空行
4. model_extra：对每个 extra key/value 调用 `_generate_yaml_prompt_list(title, content)`
5. instruct：`_generate_yaml_prompt_list("[INSTRUCT]", instruct)`
6. examples：`_generate_yaml_prompt_list("[EXAMPLES]", examples)`
7. input：`_generate_yaml_prompt_list("[INPUT]", input)`
8. output_requirement（仅当 output 存在）：
   - output_format == `"json"`：输出
     - `[OUTPUT REQUIREMENT]:`
     - `Data Format: JSON`
     - `Data Structure:`
     - `_generate_json_output_prompt(sanitized_output)`
     - 空行
   - output_format == `"markdown"`：输出 `[OUTPUT REQUIREMENT]:` + `Data Format: markdown text`
   - output_format == `"text"`：不输出 output_requirement
9. 最后总是追加 `[OUTPUT]:`

标题映射：均来自 `settings["prompt.prompt_title_mapping"]`（缺省则用大写默认标题）。

## 5. to_messages：Chat messages（复刻级 decision tree）

签名：

`to_messages(role_mapping=None, rich_content: bool|None=False, strict_role_orders: bool|None=True) -> list[dict]`

输出元素形态：

- `{"role": <str>, "content": <str>}`（当 `rich_content is False`）
- `{"role": <str>, "content": list[dict]}`（当 `rich_content` 为 True 或 chat_history 尚未被简化）

### 5.1 role mapping 合并

与 `to_text` 相同：`settings["prompt.role_mapping"]` + 传入 `role_mapping` 覆盖合并。

### 5.2 system/developer message

若存在 `system/developer`，各自追加一条 message：

- role 为 `"system"`/`"developer"`（或按 role_mapping 映射）
- content 为 `DataFormatter.sanitize(part)` 的 str 或 YAML dump（由 `_generate_yaml_prompt_message` 决定）

### 5.3 chat_history message（含 strict_role_orders）

将每条历史消息规范化为 `content: list[ChatMessageContent]` 的 `model_dump()` 结果（dict list）：

- origin_content 是 `{"type": ...}` dict → 包装成 list
- origin_content 不是 list → 转为 `[{ "type":"text", "text": str(origin_content)}]`

随后：

- 若 `strict_role_orders` 为真：
  - 连续同 role 的历史消息会被合并到同一条 message（content list extend）
  - 若合并后的 **第一条** role 不是 `"user"`：
    - 在最前面插入一条 user message，content 固定为 `[{type:"text", text:"[CHAT HISTORY]"}]`（标题可被 title_mapping 覆盖）
  - 若合并后的 **最后一条** role 不是 `"assistant"`：
    - 在末尾追加一条 assistant message，content 固定为 `[{type:"text", text:"[User continue input]"}]`
- 若 `strict_role_orders` 为假：
  - 不合并、也不会插入上述两条“纠错”消息

### 5.4 rich_content=False 时的 chat_history 简化

如果 `rich_content is False`，则对 chat_history 的每条 message：

- 如果 origin_content 是 str：直接加入 content 列表
- 如果 origin_content 是 Sequence（通常为 list[dict]）：
  - 仅保留 `type=="text"` 的 part，把其 `text` 追加到 content 列表
  - 其他 type：warning 并跳过
- 最终 `content = "\n\n".join(content_list)`（双换行拼接）
- 输出 message 为 `{"role": role, "content": content}`（string）

### 5.5 main prompt 与 attachment 的三种“特殊场景”

chat_history（若存在）处理完成后，进入主分支：

#### A) “仅 input”场景

条件（必须全部满足）：

- 有 `input`
- 且 `tools/action_results/info/instruct/output/model_extra/attachment` 全都为空

动作：追加 1 条 user message：`{"role": <user>, "content": sanitize(input)}`

#### B) “仅 attachment”场景

条件：

- 有 `attachment`
- 且 `input/tools/action_results/info/instruct/output/model_extra` 全都为空

动作：

- 若 `rich_content` 为真：追加 1 条 user message，content 为 `attachment` 的 `model_dump()` 列表
- 若 `rich_content` 为假：对每个 attachment：
  - 仅当 `type=="text"` 且为 `TextMessageContent`：各自追加一条 user message（content 为 text）
  - 其他类型：warning 并跳过

测试“金标准”：`test_rich_prompt`

#### C) 一般场景（包含 main prompt）

否则进入一般场景：

- role 固定为 user（或 role_mapping 后的 user）
- 若 `rich_content` 为真：
  - 追加 1 条 user message
  - content 为 list，首元素是 `{"type":"text","text":"<main prompt text>"}`（`<main prompt text> = "\n".join(_generate_main_prompt())`）
  - 若存在 attachment：将每个 `attachment.model_dump()` 追加到 content 列表末尾
- 若 `rich_content` 为假：
  - 先处理 attachment：对每个 attachment，若是 text 类型则**先**追加一条 user message（content 为 text），否则 warning 跳过
  - 最后追加 1 条 user message，content 为 `"\n".join(_generate_main_prompt())`

测试“金标准”：`test_message_prompt` 与 `test_strict_role_orders`

注意：本实现 **不会**自动追加空的 assistant message；最后一条通常是 user message。

## 6. 输出模型：to_output_model/_generate_output_model（复刻级）

目标：把 `prompt.output`（schema）转为 Pydantic model，用于 ResponseParser 在 done 时校验/生成 `result_object`。

### 6.1 输入约束

- `output_prompt` 必须是 `Mapping` 或 `Sequence` 且不能是 str；否则抛 TypeError。
- Mapping → 生成名为 `AgentlyOutput` 的 model
- Sequence → 生成 `AgentlyOutput`，其唯一字段名为 `"list"`，类型由该 Sequence 推导

### 6.2 Schema → 类型推导规则

对 Mapping 的每个字段 `field_name: field_type_schema`：

- `str`：字段类型为 `Any`，description 为该字符串
- `Mapping`：递归生成子 model（字段类型为该 model）
- `tuple`：
  - `value_type = schema[0]`（缺省 Any）
  - `desc = schema[1]`（缺省空字符串）
  - `default_value = schema[2]`（缺省 None）
  - 若 `value_type` 是类型或 typing origin：字段类型为 `value_type`，description 为 desc
  - 否则：字段类型保持 `Any`，description 变为 `type: <value_type>; desc: <desc>`
- `Sequence`：递归生成 list schema（详见 6.3）
- `type` 或 typing origin：字段类型为 `T | None`
- 其他：字段类型 `Any`，description 为 `str(schema)`

最终通过：

- `create_model(name, __config__={'extra': 'allow'}, **fields, **validators)`

确保模型允许 extra 字段（模型多输出不会被拒绝）。

### 6.3 list 字段的 ensure/cast（ensure_list_and_cast）

当字段类型是 list（`get_origin(field_type) in (list, List)`）时，会包装成：

- `Annotated[field_type, PlainValidator(lambda value: ensure_list_and_cast(value, elem_type))]`

`ensure_list_and_cast(v, elem_type)` 的行为（测试 `test_output_model` 覆盖）：

- 若 `v` 不是 list：先变为 `[v]`
- 对每个 item：
  - 若 elem_type 不是具体 `type`（或 elem_type is Any）：原样保留
  - 若 item 已是 elem_type：原样保留
  - 若 item 是 Mapping 且 elem_type 有 `model_validate`/`parse_obj`：优先用其构造（支持嵌套 BaseModel）
  - 否则：调用 `elem_type(item)` 强制转换

示例（tests 断言）：

- schema：`{"thinking": [(str, ...)]}`，数据：`{"thinking": 1}` → 输出：`thinking == ["1"]`
- schema：`[(int,)]`，数据：`{"list": ["456"]}` → 输出：`list == [456]`

## 7. Prompt 导出：to_serializable_prompt_data/to_json_prompt/to_yaml_prompt

目的：把 prompt 转成可 JSON/YAML 序列化的结构，供日志/存档/调试使用。

规则：

- `to_serializable_prompt_data(inherit=False)`：
  - 从 `self.prompt.get(default={}, inherit=inherit)` 获取 dict
  - 若包含 `"output"`：
    - 递归把 tuple schema 转成形如 `{"$type": ..., "$desc": ...}` 的 dict（见 `_to_serializable_output_prompt`）
  - 最后 `DataFormatter.sanitize(prompt_data)` 统一清理不可序列化值
- `to_json_prompt()`：`json.dumps(..., indent=2, ensure_ascii=False)`
- `to_yaml_prompt()`：`yaml.safe_dump(..., indent=2, allow_unicode=True, sort_keys=False)`
