# 01 / 初始化（Initialization）

## 1. 顶层入口

- 对外入口：`agently/__init__.py`
  - `Agently = AgentlyMain()`
  - 导出：`Agently, TriggerFlow, TriggerFlowBluePrint, TriggerFlowEventData, print_, async_print`

## 2. 全局初始化（agently/base.py）

初始化是“模块 import 时执行”的（即 import `agently` 即完成），关键对象为：

- `settings: Settings(name="global_settings")`
- `plugin_manager: PluginManager(settings, name="global_plugin_manager")`
- `event_center: EventCenter()`
- `tool: Tool(plugin_manager, settings)`
- `AgentlyMain`: 持有上述对象，并提供 `create_agent/create_prompt/create_request`

### 2.1 默认 settings（agently/_default_settings.yaml）

默认 YAML 主要包含：

- `storage.db_url`：默认 `sqlite+aiosqlite:///localstorage.db`
- `prompt.role_mapping`：系统/开发者/用户/助手角色映射
- `prompt.prompt_title_mapping`：to_text 模式下各 slot 标题映射
- `response.streaming_parse`、`response.streaming_parse_path_style`
- `runtime.*`：日志开关、raise 行为、httpx log level
- `plugins.ToolManager.activate`：默认激活 `AgentlyToolManager`

注意：其它插件的默认设置来自插件 `DEFAULT_SETTINGS`，注册时会注入到 Settings（详见下文）。

### 2.2 默认插件加载（agently/_default_init.py）

默认插件加载顺序：

1. PromptGenerator → `AgentlyPromptGenerator`
2. ModelRequester → `OpenAICompatible`（activate=True）
3. ResponseParser → `AgentlyResponseParser`
4. ToolManager → `AgentlyToolManager`

插件注册时的副作用（在 `PluginManager.register()` 内）：

- `settings["plugins.<Type>.activate"] = plugin_class.name`（若 activate=True）
- 合并 `plugin_class.DEFAULT_SETTINGS`：
  - 若包含 `$global`：会 `settings.update(DEFAULT_SETTINGS["$global"])`
  - 若包含 `$mappings`：会 `settings.update_mappings(DEFAULT_SETTINGS["$mappings"])`
  - 其余写入：`settings.set("plugins.<Type>.<PluginName>", default_settings)`

### 2.3 默认事件 hooker

`EventCenter` 默认注册：

- `SystemMessageHooker`（监听 `AGENTLY_SYS`）
- `PureLoggerHooker`（监听 `message`/`log`）

可通过 `Agently.set_debug_console("ON")` 注册 `ConsoleHooker`，提供 rich live dashboard，并劫持 `builtins.print`。

## 3. AgentlyMain 的外部 API（init 后可用）

- `Agently.settings`：全局 Settings
- `Agently.plugin_manager`：全局 PluginManager
- `Agently.event_center`：全局 EventCenter
- `Agently.tool`：全局 Tool（ToolManager 的 facade）
- `Agently.set_settings(key, value, auto_load_env=False)`：
  - 特殊 key：`runtime.httpx_log_level`、`debug` 会触发 httpx 日志级别刷新
- `Agently.set_debug_console("ON"|"OFF")`
- `Agently.create_agent(name=None)`
- `Agently.create_request(name=None)`
- `Agently.create_prompt(name="agently_prompt")`

