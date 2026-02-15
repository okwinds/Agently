# 08 / Logger & Messenger 复刻规格

实现：

- Logger：`agently/utils/Logger.py`
- Messenger：`agently/utils/Messenger.py`

## 1. create_logger（AgentlyLogger）

### 1.1 Logger 类

- `AgentlyLogger(logging.Logger)`：
  - `raise_error(error)`：
    - 若 error 为 str：包装成 RuntimeError
    - `self.error(error)`
    - 如果 `Agently.settings["runtime.raise_error"]` 为真：raise

框架中部分模块通过 logger.raise_error 来决定是否抛异常或仅记录。

### 1.2 Formatter

- 若环境中存在 `uvicorn`：
  - 使用 `uvicorn.logging.DefaultFormatter`
- 否则：
  - 使用自定义 `AgentlyFormatter`，为 record 注入 `levelprefix`

默认 fmt：

- `%(levelprefix)s %(asctime)s | %(message)s`

### 1.3 dictConfig

会配置 root logger 与 uvicorn.error / uvicorn.access 的 handler/level。

## 2. create_messenger

`create_messenger(module_name)` 实际上是对全局 `event_center.create_messenger(module_name)` 的薄封装。

因此 messenger 的行为由 `EventCenterMessenger` 决定：

- message/debug/info/warning/error/critical 会被转成 EventCenter 的 emit（log/message/console 等事件）
- hooker（PureLoggerHooker/SystemMessageHooker/ConsoleHooker）决定最终输出形态

