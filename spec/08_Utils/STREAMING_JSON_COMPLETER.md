# 08 / StreamingJSONCompleter（流式 JSON 补全器）复刻规格

实现：`agently/utils/StreamingJSONCompleter.py`  
测试来源：`tests/test_utils/test_streaming_json_completer.py`、`tests/test_utils/test_streaming_json_completer_comprehensive.py`

StreamingJSONCompleter 的目标是：给一个可能被截断的 JSON/JSON5 片段，在不引入太多“猜测语义”的前提下，**补齐括号、字符串、注释**，使其尽可能可被 `json5.loads()` 解析。

这是 Agently 能解析“模型输出里夹杂 markdown + 注释 + 截断 JSON”的关键组件。

## 1. 状态机（complete）

扫描 buffer（`self._buffer`）时维护：

- `stack`: list，记录未闭合的 `{` 与 `[`（只记录 opener）
- `in_string: bool`
- `string_char: "'" | '"' | None`
- `escape: bool`
- `comment: None | '//' | '/*'`

### 1.1 主循环规则

- 当 `comment is None`：
  - 如果 `in_string`：
    - `\\` 触发 escape
    - 遇到 `string_char` 结束 string
  - 如果不在 string：
    - `"` 或 `'` 开启 string（并记录 string_char）
    - `//` 开启单行 comment
    - `/*` 开启多行 comment
    - `{` / `[` 入栈
    - `}` / `]`：
      - 若 stack 为空：忽略该 unmatched closing
      - 若与栈顶 opener 匹配：pop
      - **如果 pop 后 stack 为空**，且不在 string/comment：认为已经找到了一个完整 JSON 结构，立即返回 `buf[:i+1]`
      - 若不匹配：忽略该 closing
- 当 `comment == '//'`：遇到 `\n` 或 `\r` 结束 comment
- 当 `comment == '/*'`：遇到 `*/` 结束 comment

这个“stack 归零时立即返回”导致一个重要不变量（测试覆盖 `multiple_root_objects`）：

> 如果 buffer 中出现多个根 JSON（例如 `{"a":1} {"b":2}`），Completer 只会返回第一个完整根对象。

## 2. 扫描结束后的补全规则

当扫描到 EOF 仍未返回完整结构时，会尝试“补齐”：

1. 若 in_string：追加 `string_char` 关闭字符串
2. 若 comment：
   - `//`：追加 `\n`
   - `/*`：追加 `*/`
3. 若 stack 非空：按相反顺序追加对应 closing（`{->}`、`[->]`）

最后返回补齐后的 buf。

## 3. reset/append

 - `reset(data="")`：直接替换内部 buffer
 - `append(data)`：拼接到 buffer 尾部

测试覆盖：

- reset 后旧数据不应残留；
- reset("") 后 complete() 返回空字符串。

## 4. 与 json5 的配合边界

Completer 只负责“结构补全”，不保证 json5 一定可解析：

- 非法 token 或极深嵌套可能触发 json5 解析失败（comprehensive test 里标注了一些可接受的极端情况）。

