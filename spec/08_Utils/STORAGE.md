# 08 / Storage（SQLite/SQLModel 存储）复刻规格

实现：`agently/utils/Storage.py`  
测试来源：`tests/test_utils/test_storage.py`

Storage 提供同步与异步两个实现：

- `Storage`：基于 `sqlmodel.Session`（同步）
- `AsyncStorage`：基于 `sqlalchemy.ext.asyncio.AsyncSession`（异步）

两者的 API 设计保持一致（table_exists/create_tables/set/get），以便上层逻辑可选择同步或异步运行时。

## 0. 依赖与 LazyImport（复刻必须保留的语义）

`agently/utils/Storage.py` 在 import 时会通过 `LazyImport.import_package(...)` 软依赖加载：

- `sqlmodel`
- `sqlalchemy`
- `aiosqlite`

如果缺失依赖，LazyImport 会触发交互式 `input()` 询问是否 pip 安装（见 `spec/08_Utils/LAZY_IMPORT.md`）。这会导致在无交互环境（例如 pytest 默认捕获 stdin）下出现收集错误，这是现版本行为的一部分。

## 1. 初始化与 db_url 校验

共同规则：

- 构造参数：
  - `parent_settings: RuntimeData | None`（内部会 `namespace("storage")`）
  - `db_url: str | None`（可通过 settings `storage.db_url` 覆盖）
- 若最终 `db_url` 为空：NotImplementedError（提示缺失 db_url）
- 若 db_url 不包含 `"://"`：ValueError（提示 SQLAlchemy URL 格式）
- 若 db_url 以 `sqlite` 开头：
  - 会创建本地文件目录（`os.makedirs(os.path.dirname(...), exist_ok=True)`）

测试覆盖：使用 `sqlite:///localstorage.db` 与 `sqlite+aiosqlite:///localstorage.db`。

## 2. table_exists

- Storage：`inspect(self.engine).has_table(table_name)`
- AsyncStorage：通过 `conn.run_sync(inspect)` 查询 table_names

## 3. create_tables

- Storage：`SQLModel.metadata.create_all(self.engine)`
- AsyncStorage：`await conn.run_sync(SQLModel.metadata.create_all)`

## 4. set（upsert/merge）

语义：对传入对象执行 merge 并 commit（类似 upsert），并在异常时 rollback。

- 输入可以是单个 SQLModel 或 list[SQLModel]
- 对同一个 primary key 的对象：
  - 后写入的会覆盖之前的（测试覆盖 “不同对象但同 primary key”）

## 5. get（query）

参数：

- `model: Type[T]`
- `where: ColumnElement | list[ColumnElement] | None`
- `first: bool`：
  - True：返回 scalars().first()
  - False：返回 scalars().all()
- `limit/offset/order_by`

测试覆盖：

- first=True/False
- order_by=Column("key").asc()
