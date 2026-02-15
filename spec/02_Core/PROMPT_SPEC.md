# 02 / Prompt 规格（Prompt Spec）

## 1. 标准槽位（PromptModel）

定义位置：`agently/types/data/prompt.py::PromptModel`

标准 key（PromptStandardSlot）：

- `system`
- `developer`
- `chat_history`
- `info`
- `tools`
- `action_results`
- `instruct`
- `examples`
- `input`
- `attachment`
- `output`
- `output_format`
- `options`

PromptModel 的关键行为：

- `output_format` 默认规则：
  1. 若 `output` 是 Mapping/Sequence 且非 str：`output_format="json"`
  2. 若 `output` 是 `type`：
     - `str`：视为无结构输出，`output=None`，`output_format="markdown"`
     - 其它 type：转换成 JSON schema（`{"value": (type,), "reply": (str, ... )}`）
  3. 其它情况：`output_format="markdown"`
- `attachment` 被规范化为 `list[ChatMessageContent]`（支持 rich content）
- `chat_history` 被规范化为 `list[ChatMessage]`

## 2. Prompt 容器（Prompt / RuntimeData）

`Prompt` 继承 `RuntimeData`，因此：

- 支持 parent_prompt 继承（Agent 层 prompt 作为 Request 层 prompt 的 parent）
- `set/append/update` 支持占位符替换：
  - 占位符模式：`${ ... }`
  - 使用 `DataFormatter.substitute_placeholder`（详见 utils 文档）

## 3. 输出结构（Output Schema）语法（复刻级）

输出结构用于两件事：

1) PromptGenerator 生成“输出要求提示”（给模型看的 JSON 结构示例）；  
2) PromptGenerator 动态生成 Pydantic 输出模型（ResponseParser 解析 JSON 用）。

Agently 的输出 schema 允许混合如下构件：

### 3.1 Mapping（dict）

形式：`{ field_name: field_schema, ... }`

field_schema 可以是：

- tuple：`(type_or_schema, desc?, ...)`
- type：如 `str/int/bool/...` 或 typing origin（list/dict/Union 等）
- Mapping/Sequence：嵌套结构
- 其它任意值（会被视为 Any 或 string 描述，取决于生成器）

### 3.2 Sequence（list / set / tuple-of-schemas）

形式：`[ item_schema ]` 或 `{ item_schema }`（内部统一按 Sequence 处理）

语义：

- 表示数组（list）
- item_schema 为上述任意 schema
- 生成 output requirement 时会输出：
  - `[` 换行
  - item_schema 的结构
  - `...`（表示省略更多项）
  - `]`

### 3.3 Tuple（类型+描述）

最常用形式：

- `(str,)`
- `(str, "说明")`
- `([str], "说明")` 或 `([("str","desc")], "说明")`（用于 list item 的描述）

规则（来自 `AgentlyPromptGenerator`）：

- 若 tuple[0] 是 dict/list/set：递归生成该结构
- 否则输出 `<tuple[0]>`

### 3.4 `type`

如果某个字段直接写 `str`/`int`/`MyPydanticModel`：

- 生成 output model 时：
  - 如果是 Pydantic BaseModel 子类，会展开字段为 schema
  - 否则作为字段类型

## 4. Prompt → text / messages 的生成规范

Agently 支持两种“把 prompt 给模型”的方式：

- `to_text()`：单条 user prompt，按块拼接 YAML 风格内容
- `to_messages()`：OpenAI-style chat messages 列表（role + content list）

关键配置：

- `prompt.role_mapping`：把 slot 角色映射成模型 API 的 role
- `prompt.prompt_title_mapping`：to_text 中各块标题

严格角色顺序（`strict_role_orders=True`）：

- chat_history 中如果连续出现同角色，会合并到同一条 message（content 列表 extend）
- 若 chat_history 第一条不是 `user`，会自动插入一个空 user message 以符合一些模型端约束
- 若最后一条不是 `user`，也会插入 user message（见 PromptGenerator 实现）

详见：`spec/03_Plugins/PROMPT_GENERATOR_AGENTLY.md`。

