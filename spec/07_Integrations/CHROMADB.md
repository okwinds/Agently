# 07 / 集成：ChromaDB 规格

实现：`agently/integrations/chromadb.py`

该模块提供对 `chromadb` 的轻量封装，目标是让 Agently Agent 可直接作为 embedding function。

## 1. LazyImport

模块 import 时会执行：

- `LazyImport.import_package("chromadb")`

因此在未安装 chromadb 时会触发交互式 pip 安装提示（见 `spec/08_Utils/UTILS.md` 的 LazyImport 章节）。

## 2. ChromaData

输入：

- `original_data: ChromaDataDict | list[ChromaDataDict]`
  - 必须包含 `document: str`
  - 可选：`metadata/id/embedding`
- embedding 来源：
  - 显式传入 `embedding_function(texts)->Embeddings`
  - 或传入 `agent`：embedding_function_by_agent = `agent.input(texts).start()`

输出：

- `get_kwargs()` 返回：
  - `documents/metadatas/ids`，以及可选 `embeddings`

## 3. ChromaResults

对 chromadb QueryResult 做规整：

- 输入 queries（str|list）与 results（QueryResult）
- 输出 `get()`：
  - 默认返回 dict：`{query: [{"id","document","metadata","distance"}...] }`
  - simplify_single_result=True 时：如果只有一个 query，返回 list[dict]
- 支持 distance 阈值过滤（dist < distance）

## 4. ChromaEmbeddingFunction

实现 chromadb 的 `EmbeddingFunction` 协议：

- `__call__(documents)`：转成 list[str]，调用 embedding_agent.input(texts).start()

## 5. ChromaCollection

构造：

- 默认 conn：`chromadb.Client(Settings(anonymized_telemetry=False))`
- metadata 注入 `hnsw:space`（cosine/l2/ip）
- 可选 embedding_agent：会构建 embedding_function
- `get_or_create` 支持

方法：

- `add(data, embedding_function=None)`：要求最终能得到 embedding_function，否则 NotImplementedError
- `query(query_or_queries, ..., top_n, where, where_document, distance)`：
  - 支持 str 与 list[str] 两种返回形态（重载）
  - 内部会把 chromadb 原始结果包装成 ChromaResults 并 `.get(...)`

复刻实现建议：保持“Agent 作为 embedding provider”的能力与结果规整结构不变，否则上层 RAG/知识库示例会失效。

