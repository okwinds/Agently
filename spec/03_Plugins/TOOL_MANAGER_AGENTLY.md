# 03 / ToolManager: AgentlyToolManager 规格

实现：`agently/builtins/plugins/ToolManager/AgentlyToolManager.py`

ToolManager 负责：

- 注册工具函数（name/desc/kwargs/returns/tags）
- 查询工具（按 tag）
- 调用工具（sync/async）
- 从 MCP server 导入工具并生成代理函数

## 1. 数据结构

- `tool_funcs: dict[str, Callable]`：name → func
- `tool_info: dict[str, dict]`：name → {name, desc, kwargs, returns?}
- `tag_mappings: dict[str, set[str]]`：tag → set(tool_name)

## 2. register

签名：

```python
register(name, desc, kwargs, func, returns=None, tags=None)
```

行为：

- 写入 tool_funcs/tool_info
- 若 returns 非 None：tool_info[name]["returns"]=returns
- tags 可为 str/list/None；会更新 tag_mappings

## 3. tool_func 装饰器（自动从函数签名生成 schema）

规则：

- tool_name = func.__name__
- desc = func.__doc__ 或 func.__name__
- kwargs_signature：
  - 遍历 signature.parameters
  - 若参数注解为 `typing.Annotated[T, "..."]`：
    - base_type=T
    - annotations 追加描述文本
  - 若参数有 default：annotations 追加 `Default: <value>`
  - kwargs_signature[param] = (base_type, ";".join(annotations))
- returns：
  - 若 type_hints 包含 return：`DataFormatter.sanitize(type_hints["return"], remain_type=True)`

然后调用 register。

## 4. get_tool_info / get_tool_list

- 若不传 tags：返回全部
- 若传 tags（str|list）：
  - 合并所有 tag 对应的工具集合，去重

## 5. get_tool_func(name, shift)

- shift=None：返回原始函数
- shift="sync"：返回 `FunctionShifter.syncify(func)`
- shift="async"：返回 `FunctionShifter.asyncify(func)`

## 6. call_tool / async_call_tool

- 找不到工具：返回字符串 `"Can not find tool named '<name>'"`
- 执行异常：返回字符串 `"Error: <exception>"`

注意：这里没有 raise；错误以字符串返回。这是工具系统面向模型与业务的一个重要兼容语义。

## 7. MCP 支持（use_mcp/async_use_mcp）

### 7.1 导入流程

- 依赖：`fastmcp>=2.10`（LazyImport）
- 通过 `fastmcp.Client(transport)`：
  - `list_tools()` 获取工具列表
  - 每个工具注册到 ToolManager：
    - name/description
    - kwargs：`DataFormatter.from_schema_to_kwargs_format(tool.inputSchema)`
    - returns：`DataFormatter.from_schema_to_kwargs_format(tool.outputSchema)`
    - func：`_mcp_tool_func(tool.name, transport)`（返回 async function）
    - tags：工具自身的 `_meta._fastmcp.tags` + 外部 tags 参数

### 7.2 MCP 调用返回值规范

`_mcp_tool_func` 代理函数会：

- `client.call_tool(name, arguments, raise_on_error=False)`
- 若 `is_error`：返回 `{"error": <text>}`
- 若 `structured_content` 存在：直接返回 structured_content
- 否则尝试解析 content[0]：
  - TextContent：优先 json.loads(text)，失败则返回 text
  - Image/Audio/ResourceLink/EmbeddedResource：返回 `.model_dump()`
- 异常：返回 None

复刻时建议严格按上述语义，避免上层模型/工具规划逻辑因返回结构变化而失效。

### 7.3 无交互环境注意事项（与现实现一致）

由于 MCP 依赖通过 LazyImport 延迟加载：

- 在缺少 `fastmcp` 的环境中，首次调用 `use_mcp/async_use_mcp` 会触发 `input()` 询问是否 pip 安装
- 在 pytest 默认捕获 stdin 的场景下，这会导致测试用例在收集/执行阶段直接报错（`pytest: reading from stdin while output is captured`）

这是当前版本的行为；“完美复刻”需要保留这种交互式依赖安装语义，或在复刻实现中显式声明为不兼容差异（例如改为非交互报错）。
