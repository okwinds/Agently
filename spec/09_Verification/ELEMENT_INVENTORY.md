# 09 / 元素清单（Element Inventory）

本清单用于“规格覆盖校验”：确保代码中存在的主要元素，在 spec 中都有对应章节。

## 1. 包入口与全局初始化

- `agently/__init__.py`
- `agently/base.py`
- `agently/_default_init.py`
- `agently/_default_settings.yaml`

## 2. Core

- Agent & Request & Response
  - `agently/core/Agent.py`
  - `agently/core/ModelRequest.py`
  - `agently/core/Prompt.py`
  - `agently/core/Tool.py`
  - `agently/core/Session.py`
- PluginManager & Events
  - `agently/core/PluginManager.py`
  - `agently/core/EventCenter.py`
  - `agently/core/ExtensionHandlers.py`

## 3. TriggerFlow

- `agently/core/TriggerFlow/TriggerFlow.py`
- `agently/core/TriggerFlow/BluePrint.py`
- `agently/core/TriggerFlow/Execution.py`
- `agently/core/TriggerFlow/Chunk.py`
- `agently/core/TriggerFlow/Process.py`
- `agently/core/TriggerFlow/process/BaseProcess.py`
- `agently/core/TriggerFlow/process/ForEachProcess.py`
- `agently/core/TriggerFlow/process/MatchCaseProcess.py`

## 4. Builtins（Plugins / Extensions / Tools / Hookers）

- Plugins
  - `agently/builtins/plugins/PromptGenerator/AgentlyPromptGenerator.py`
  - `agently/builtins/plugins/ModelRequester/OpenAICompatible.py`
  - `agently/builtins/plugins/ResponseParser/AgentlyResponseParser.py`
  - `agently/builtins/plugins/ToolManager/AgentlyToolManager.py`
- Agent Extensions
  - `agently/builtins/agent_extensions/ToolExtension.py`
  - `agently/builtins/agent_extensions/KeyWaiterExtension.py`
  - `agently/builtins/agent_extensions/AutoFuncExtension.py`
  - `agently/builtins/agent_extensions/ConfigurePromptExtension.py`
  - `agently/builtins/agent_extensions/ChatSessionExtension.py`
- Built-in Tools
  - `agently/builtins/tools/Search.py`
  - `agently/builtins/tools/Browse.py`
  - `agently/builtins/tools/Cmd.py`
- Hookers
  - `agently/builtins/hookers/SystemMessageHooker.py`
  - `agently/builtins/hookers/PureLoggerHooker.py`
  - `agently/builtins/hookers/ConsoleHooker.py`

## 5. Types

- `agently/types/data/*`（prompt/request/response/event/tool/serializable）
- `agently/types/plugins/*`（protocols）
- `agently/types/trigger_flow/*`

## 6. Utils

- `agently/utils/RuntimeData.py`
- `agently/utils/SerializableRuntimeData.py`
- `agently/utils/Settings.py`
- `agently/utils/DataLocator.py`
- `agently/utils/DataFormatter.py`
- `agently/utils/DataPathBuilder.py`
- `agently/utils/FunctionShifter.py`
- `agently/utils/GeneratorConsumer.py`
- `agently/utils/LazyImport.py`
- `agently/utils/Storage.py`
- `agently/utils/StreamingJSONCompleter.py`
- `agently/utils/StreamingJSONParser.py`
- `agently/utils/Messenger.py`
- `agently/utils/Logger.py`
- `agently/utils/PythonSandbox.py`

## 7. 集成

- `agently/integrations/chromadb.py`

## 8. 测试覆盖（用作行为规格来源）

主要测试入口（不一定可在无模型环境中执行，但可作为语义来源）：

- core：`tests/test_cores/*`
- plugins：`tests/test_plugins/*`
- utils：`tests/test_utils/*`
- extensions：`tests/test_extensions/*`

