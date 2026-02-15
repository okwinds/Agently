# 03 / 插件系统规格（Plugin System）

实现：`agently/core/PluginManager.py`

## 1. 插件类型（AgentlyPluginType）

定义：`agently/types/plugins/base.py`

允许的 plugin_type（字符串字面量）：

- `PromptGenerator`
- `ModelRequester`
- `ResponseParser`
- `ToolManager`

## 2. PluginManager 数据结构

- `self.settings: Settings`：插件配置写入的目标 Settings
- `self.plugins: RuntimeData`：按类型存储插件 class（可继承 parent PluginManager）

存储形态（逻辑）：

```python
plugins = {
  "ModelRequester": {
     "OpenAICompatible": <class OpenAICompatible>,
     ...
  },
  ...
}
```

## 3. 注册（register）规范（复刻级）

签名：

```python
register(plugin_type, plugin_class, activate=True) -> PluginManager
```

算法（必须保持一致）：

1. 若 `plugin_class` 有 `_on_register`：调用
2. 将其写入 `self.plugins[plugin_type][plugin_class.name] = plugin_class`
3. 若 `activate=True`：
   - `settings.set(f"plugins.{plugin_type}.activate", plugin_class.name)`
4. `default_settings = plugin_class.DEFAULT_SETTINGS.copy()`
5. 若 default_settings 包含 `$global`：
   - `settings.update(default_settings["$global"])`
   - 删除 `$global`
6. 若 default_settings 包含 `$mappings` 且为 dict：
   - `settings.update_mappings(default_settings["$mappings"])`
   - 删除 `$mappings`
7. `settings.set(f"plugins.{plugin_type}.{plugin_class.name}", default_settings)`

因此每个插件 class 必须至少提供：

- `name: str`
- `DEFAULT_SETTINGS: dict`

并且可选：

- `_on_register()/_on_unregister()`（静态方法）

## 4. 卸载（unregister）

支持传入 plugin_class 或 plugin_name 字符串。

行为：

1. 若不存在对应 plugin_type / plugin_name → 通过 messenger 抛错（EventCenter 日志）
2. 若 plugin_class 有 `_on_unregister`：调用
3. 从 `self.plugins[plugin_type]` 删除该插件条目

## 5. 激活（activate）机制

PluginManager 本身不提供 activate 方法，而是通过 settings key 指定激活插件：

- `settings["plugins.<Type>.activate"] = "<PluginName>"`

调用方（如 Prompt/Tool/ModelResponse）在运行时读取该 key，并实例化对应插件 class：

- Prompt：读取 `plugins.PromptGenerator.activate`
- Tool：读取 `plugins.ToolManager.activate`
- ModelResponse：读取 `plugins.ModelRequester.activate`
- ModelResponseResult：读取 `plugins.ResponseParser.activate`

## 6. 复刻实现建议

为了实现“换插件不改业务代码”，复刻时建议保持：

- 插件只通过 settings 获取自身配置（不要直接访问全局变量）
- 插件初始化参数保持与协议一致（Prompt/Settings/Generator 等）
- 插件输出数据结构严格遵守协议（尤其是 ModelRequester 的广播事件）

