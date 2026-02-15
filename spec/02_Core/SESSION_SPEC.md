# 02 / Session（会话记忆）规格

实现：`agently/core/Session.py`

Session 是“聊天会话状态容器”，用于：

- 维护完整历史 `full_chat_history`
- 维护当前上下文 `current_chat_history`（可被压缩/裁剪）
- 维护 memo（结构化记忆）
- 在达到阈值时触发 resize（lite/deep/自定义）

## 1. 数据结构

- `id: str`（uuid hex）
- `full_chat_history: list[ChatMessage]`
- `current_chat_history: list[ChatMessage]`
- `memo: dict`
- `_turns: int`：累计轮数（按 append_message 次数递增）
- `_last_resize_turn: int`
- `_memo_cursor: int`：memo 更新游标（用于把新消息片段喂给 memo 更新器）

## 2. 关键 Settings（默认值）

Session 构造时会 setdefault：

- `session.resize.every_n_turns = 8`
- `session.resize.max_messages_text_length = 12000`（近似字符数）
- `session.resize.max_keep_messages_count = None`
- `session.memo.instruct`：用于更新 memo 的指令列表（默认 4 条）

兼容 legacy key：

- `session.resize.max_current_chars`（等价 max_messages_text_length）
- `session.resize.keep_last_messages`（等价 max_keep_messages_count）

## 3. Resize 策略（policy_handler）

`async_judge_resize()` 调用 policy_handler，返回：

- `None`：不 resize
- `"lite"|"deep"|str`：仅指定类型
- `{"type": ..., "reason": ..., "severity": ..., "meta": ...}`：带原因/严重度

默认 policy（`_default_policy_handler`）判定顺序：

1. 若 current_chat_history 近似字符数 ≥ `max_messages_text_length` → deep（reason=`max_messages_text_length`，severity=100）
2. 若消息数 > `max_keep_messages_count` → lite（reason=`max_keep_messages_count`，severity=50）
3. 若距离上次 resize 的轮数 ≥ `every_n_turns` → lite（reason=`every_n_turns`，severity=10）
4. 否则 None

（行为由 `tests/test_cores/test_session.py` 覆盖）

## 4. Resize handlers（lite/deep）

resize handler 的签名（见 `agently/types/plugins/Session.py`）：

```python
handler(full_chat_history, current_chat_history, memo, settings) -> (full, current, memo)
```

默认 handlers：

- lite：主要按“保留最后 N 条/按 max_chars 裁剪”策略压缩 current_chat_history，同时更新 memo
- deep：更强压缩：把历史分块，并通过模型生成 memo 与 summary（代码中包含 attachment summary 的收集）

复刻时必须保证：

- 同步与异步 handler 都可用（内部用 `FunctionShifter.asyncify` 统一成 async）
- handler 可以被用户覆盖（`set_resize_handlers`）
- policy 可以被用户覆盖（`set_policy_handler`）

## 5. Attachment summary

默认 attachment summary handler：

- 如果 message.content 是 list（rich content），对非 text part 生成摘要项：
  - `type`
  - `ref`：从 `file/url/path/id/name` 等字段中找一个
  - `meta`：提取 `name/mime_type/size/width/height/duration` 等

用于在 deep resize 时提供给模型，避免把二进制/大 payload 直接塞进 memo。

