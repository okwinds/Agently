# Agently 4（Python）复刻级规格文档索引

本规格文档基于当前代码仓库反向工程得到，目标是达到“仅凭此文档即可复刻实现（可用不同技术栈）”的粒度。

- 框架名称：`agently`
  - `pyproject.toml` 声明版本：`4.0.7.1`
- 反向工程基线：`git` commit `ab69851feb7f1eaf6f151019dc4de92fa76a7fef`
- 代码入口：`agently/__init__.py` 暴露 `Agently` 单例与 TriggerFlow 相关符号

## 阅读路径（推荐）

1. `spec/00_Overview/PROJECT.md`：是什么、解决什么问题、边界是什么  
2. `spec/00_Overview/ARCHITECTURE.md`：整体架构与执行链路（Prompt → Request → Stream → Parse）  
3. `spec/02_Core/PUBLIC_API.md`：外部开发者会直接调用的 API（Agently、Agent、ModelRequest、Prompt、Response、Tool、Session）  
4. `spec/03_Plugins/PLUGIN_SYSTEM.md`：插件系统（注册/激活/默认配置注入）  
5. `spec/05_TriggerFlow/TRIGGERFLOW_SPEC.md`：TriggerFlow（编排 DSL）  

## 文档目录

- 00 概览
  - `spec/00_Overview/PROJECT.md`
  - `spec/00_Overview/ARCHITECTURE.md`
  - `spec/00_Overview/GLOSSARY.md`
- 01 配置与初始化
  - `spec/01_Configuration/SETTINGS.md`
  - `spec/01_Configuration/INITIALIZATION.md`
- 02 核心抽象（Core）
  - `spec/02_Core/PUBLIC_API.md`
  - `spec/02_Core/PROMPT_SPEC.md`
  - `spec/02_Core/RESPONSE_STREAMING_SPEC.md`
  - `spec/02_Core/SESSION_SPEC.md`
- 03 插件（Plugins）
  - `spec/03_Plugins/PLUGIN_SYSTEM.md`
  - `spec/03_Plugins/PROMPT_GENERATOR_AGENTLY.md`
  - `spec/03_Plugins/MODEL_REQUESTER_OPENAI_COMPATIBLE.md`
  - `spec/03_Plugins/RESPONSE_PARSER_AGENTLY.md`
  - `spec/03_Plugins/TOOL_MANAGER_AGENTLY.md`
- 04 扩展（Extensions）
  - `spec/04_Extensions/EXTENSIONS.md`
- 05 工作流编排（TriggerFlow）
  - `spec/05_TriggerFlow/TRIGGERFLOW_SPEC.md`
- 06 内置工具（Built-in Tools）
  - `spec/06_Tools/BUILTIN_TOOLS.md`
- 07 集成（Integrations）
  - `spec/07_Integrations/CHROMADB.md`
- 08 工具箱（Utils）
  - `spec/08_Utils/UTILS.md`
  - `spec/08_Utils/RUNTIME_DATA.md`
  - `spec/08_Utils/DATA_PATH_BUILDER.md`
  - `spec/08_Utils/DATA_LOCATOR.md`
  - `spec/08_Utils/DATA_FORMATTER.md`
  - `spec/08_Utils/FUNCTION_SHIFTER.md`
  - `spec/08_Utils/GENERATOR_CONSUMER.md`
  - `spec/08_Utils/STREAMING_JSON_COMPLETER.md`
  - `spec/08_Utils/STREAMING_JSON_PARSER.md`
  - `spec/08_Utils/LAZY_IMPORT.md`
  - `spec/08_Utils/STORAGE.md`
  - `spec/08_Utils/PYTHON_SANDBOX.md`
  - `spec/08_Utils/LOGGER_AND_MESSENGER.md`
- 09 复刻验证与清单
  - `spec/09_Verification/ELEMENT_INVENTORY.md`
  - `spec/09_Verification/BEHAVIORAL_TEST_SPECS.md`
  - `spec/09_Verification/KNOWN_GAPS.md`
- 10 复刻指南
  - `spec/10_Replication/REPLICATION_GUIDE.md`
