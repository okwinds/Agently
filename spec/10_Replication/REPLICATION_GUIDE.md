# 10 / 复刻指南（Replication Guide）

本指南面向“要在新项目/新语言中复刻 Agently 4 的核心能力”的工程团队。

目标：复刻出一个兼容的最小实现（MVP），具备：

1. Prompt 标准槽位 + output schema
2. 插件系统（四类）
3. 模型请求链路（至少 OpenAICompatible）
4. ResponseParser（JSON5 抽取 + ensure_keys 重试 + streaming_parse）
5. ToolManager（注册/调用/MCP 导入）
6. TriggerFlow（when/to/batch/for_each/match + execution）

## A. 最小模块划分（建议保持）

1. `runtime_data`：层级数据结构（合并语义）
2. `settings`：在 runtime_data 之上增加 mappings + set_settings(env substitution)
3. `plugin_manager`：注册/激活/默认配置注入
4. `prompt`：
   - Prompt 容器（继承 runtime_data）
   - PromptModel（标准槽位 + default output_format）
   - PromptGenerator 插件：to_text/to_messages/to_output_model
5. `model_request`：
   - ModelRequest / ModelResponse / ModelResponseResult
   - ensure_keys 重试逻辑
6. `model_requester`（插件）：
   - OpenAICompatible：SSE + mapping
7. `response_parser`（插件）：
   - output_json 抽取（多 JSON block 选择）
   - JSON 补全（StreamingJSONCompleter）
   - JSON5 parse（支持注释）
   - streaming_parse（StreamingJSONParser）
8. `tool_manager`（插件）：
   - tool_func 装饰器从类型/注解生成 kwargs schema
   - MCP tool import（fastmcp）
9. `agent`：
   - BaseAgent 透传请求能力
   - 可选 Extensions（ToolExtension/KeyWaiter/ConfigurePrompt/AutoFunc）
10. `event_center`：
   - emit/system_message/hooker
11. `trigger_flow`：
   - blueprint + execution + DSL

## B. 复刻实现的关键不变量（必须保证）

1. **配置注入不变量**：`PluginManager.register()` 对 `$global/$mappings` 的处理与落盘路径必须一致。
2. **统一事件流不变量**：ModelRequester.broadcast_response 必须输出 AgentlyModelResponseEvent 枚举，且语义稳定。
3. **结构化解析不变量**：
   - JSON block 抽取策略（DataLocator.locate_output_json）要一致
   - JSON 补全 + JSON5 解析要一致
   - OutputModel 验证失败时不能阻断 parsed_result（result_object 可为 None）
4. **ensure_keys 重试不变量**：缺字段触发重新请求，直到 max_retries；错误策略可选 raise 或返回最后一次结果。
5. **工具调用不变量**：ToolManager.call_tool/async_call_tool 出错返回字符串而非 raise（防止模型链路崩溃）。
6. **TriggerFlow 事件命名与收集不变量**：When-/Batch-/ForEach-/Match-/Collect-/Chunk[...] 命名约定建议保持，以兼容示例与日志。

## C. 建议的“复刻验证协议”

1. 按 spec 实现 MVP
2. 把本仓库的 `examples/basic/*`、`examples/trigger_flow/*` 挑 5-8 个迁移到新实现，确保运行行为一致
3. 对齐以下验证点：
   - `to_messages` 的 role/strict_role_orders 行为
   - SSE streaming delta 的可持续输出
   - streaming_parse 的 path/value/delta/is_complete
   - ensure_keys 缺字段重试确实会发生
   - ToolExtension 的二次请求策略（tool_judgement_request）
   - TriggerFlow 的 batch/for_each/match 结果收集正确

## D. 语言/技术栈替换建议

- 若用 TypeScript 复刻：
  - RuntimeData/Settings 可用 immer + lodash merge 实现（但要复刻 list/set 合并去重语义）
  - OutputModel 可用 zod 生成（动态 schema）
  - JSON5 parse 用 `json5` 包
  - SSE 用 fetch EventSource 或自建 SSE parser
- 若用 Go 复刻：
  - OutputModel 用 mapstructure + 自定义校验；或用 JSON schema + validator
  - JSON5 可能需要引入第三方解析器，或限制输出为严格 JSON 并在 prompt 强约束

## E. 依赖策略（必须做的工程决策）

Agently 当前实现同时存在：

- “硬依赖”：在 `pyproject.toml` 的 `project.dependencies` 中声明（pydantic/httpx/json5/pyyaml 等）
- “软依赖”：通过 `LazyImport` 延迟加载（缺失时会 `input()` 询问并尝试 pip 安装，见 `spec/08_Utils/LAZY_IMPORT.md`）

复刻实现时必须明确以下策略之一：

1. **完全复刻当前行为**：在运行时尝试 import，缺失则交互式询问安装
   - 优点：对脚本/Notebook 友好
   - 缺点：CI/无交互环境会失败（例如 pytest 捕获 stdin）
2. **改为显式依赖管理**：将所有可选能力拆为 extra/feature flags，并在构建时安装
   - 优点：生产/CI 可靠
   - 缺点：对终端新手不如交互式提示友好

如果目标是“兼容当前生态”，建议至少保留“缺失依赖时的错误文案/诊断信息”，即使不再交互式安装。
