# 08 / LazyImport（延迟依赖与交互式安装）复刻规格

实现：`agently/utils/LazyImport.py`  
测试来源：`tests/test_utils/test_lazy_import.py`

LazyImport 提供两种入口：

- `import_package(package_name, auto_install=True, version_constraint=None, install_name=None)`
- `from_import(from_package, target_modules, auto_install=True, version_constraint=None, install_name=None)`

其核心特征是：当 import 失败或版本不满足时，会进行**交互式询问**（`input()`）并在用户同意后执行 pip install。

## 1. version_constraint 规范化

如果传入的 version_constraint 不带比较符（`==,>=,<=,!=,>,<`），会自动前缀 `==`。

## 2. import_package

算法：

1. `importlib.import_module(package_name)`
2. 若提供 version_constraint：
   - root_package_name = install_name 或 `package_name.split(".")[0]`
   - 读取 installed_version（importlib.metadata.version）
   - 用 `packaging.specifiers.SpecifierSet` 判断是否满足
   - 不满足：
     - print 警告
     - 如果 auto_install 且未 attempted_install：
       - input 询问是否安装指定版本
       - 同意则 subprocess.check_call pip install `<root_package_name><version_constraint>`
       - 递归重试一次（_attempted_install=True）
3. import 失败：
   - auto_install 且未 attempted_install：
     - print 缺失提示
     - input 询问是否安装
     - 同意则 pip install root_package_name，并递归重试一次
   - 否则 raise ImportError，提示手动安装

测试覆盖：

- `LazyImport.import_package("json5")` 能直接导入并使用；
- `auto_install=False` 时导入不存在包必须抛 ImportError。

## 3. from_import

输入 `target_modules` 可以是 str 或 list[str]：

- 尝试 import `from_package.<module_name>`
- 若 ModuleNotFoundError：
  - import base_package，再 getattr(base_module, module_name)（当模块其实是属性时）
  - 若仍不存在：抛 ModuleNotFoundError（带更明确错误）

版本检查与 auto_install 逻辑与 import_package 类似（同样是交互式）。

测试覆盖：

- `from_import("json5","loads")` 可获取函数；
- `unknown_method` 且 auto_install=False 必须抛 ModuleNotFoundError。

## 4. 复刻实现注意

这套机制对“无交互环境”不友好，但它是当前框架设计的一部分。复刻实现若要用于生产，建议提供：

- 非交互模式（遇到缺依赖直接抛可诊断错误）
- 或将依赖管理放到构建/部署流程中

