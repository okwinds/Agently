# 08 / PythonSandbox（受限执行环境）复刻规格

实现：`agently/utils/PythonSandbox.py`

PythonSandbox 用于在受限环境中执行代码片段（`exec`），并限制：

- 可用 builtins
- 可访问对象的私有属性
- 返回值类型

## 1. SAFE_BUILTINS

默认允许的 builtins（MappingProxyType 保护）：

- 数学/集合：abs/min/max/sum/len/range/enumerate/sorted
- 容器：list/dict/set/tuple
- 基础类型：str/int/float/bool/type(None)
- print

不包含 import/open/eval/exec 等高风险能力。

## 2. SAFE_TYPES（默认允许返回类型）

默认允许：

`[int, float, str, list, dict, set, tuple, bool, type(None)]`

可通过构造参数 `allowed_return_types` 扩展。

## 3. 对象包装（_wrap_obj）

对 preset_objects 中的对象会被包装成 ObjectWrapper：

- 禁止访问以下划线开头的属性（`_private`）：raise AttributeError
- 可调用方法：调用后检查返回值类型是否安全
- 普通属性：读取后检查类型是否安全

## 4. run(code)

执行步骤：

1. 把 preset_objects 包装
2. 构造 globals：
   - `__builtins__` = SAFE_BUILTINS
   - + preset_objects + base_vars
3. `exec(code, globals_dict, local_vars)`
4. 对 local_vars 中所有变量执行 `_check_safe_value`（不安全则 raise ValueError）
5. 返回 local_vars

复刻实现必须保留“结果类型校验”，否则 sandbox 失去意义。

