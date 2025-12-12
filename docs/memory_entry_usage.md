# MemoryEntry 使用文档

## 概述

`MemoryEntry` 是记忆条目的核心数据结构，表示单个记忆单元。它遵循ReMem论文定义，包含任务输入、智能体输出、环境反馈等关键字段。

## 类定义

```python
class MemoryEntry:
    """记忆条目类，表示单个记忆单元"""

    def __init__(
        self,
        x: str,                    # 任务输入/触发情境
        y: str,                    # 智能体输出/存储知识
        feedback: str,             # 环境反馈
        tag: str = "",             # 记忆标签
        timestamp: Optional[datetime] = None,  # 时间戳
        id: Optional[str] = None   # 唯一标识符
    ):
```

## 字段说明

| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `id` | `str` | 唯一标识符，用于区分不同记忆条目 | 自动生成的UUID |
| `x` | `str` | 任务输入/触发情境，描述记忆的触发条件 | 必需 |
| `y` | `str` | 智能体输出/存储知识，记录智能体的响应或学到的知识 | 必需 |
| `feedback` | `str` | 环境反馈，记录执行结果或外部反馈 | 必需 |
| `tag` | `str` | 记忆标签，用于分类和检索 | 空字符串 |
| `timestamp` | `datetime` | 时间戳，记录记忆创建时间 | 当前UTC时间 |

## 属性访问器

所有字段都通过property装饰器提供getter和setter方法，支持类型验证：

```python
# 获取属性
entry_id = entry.id
task_input = entry.x
agent_output = entry.y
env_feedback = entry.feedback
memory_tag = entry.tag
create_time = entry.timestamp

# 设置属性（带类型验证）
entry.x = "新的任务输入"
entry.tag = "new-tag"
entry.timestamp = datetime.now()
```

## 核心方法

### `to_text()` - 生成文本表示

将记忆条目转换为标准化的文本格式，用于检索和显示。

```python
text = entry.to_text()
"""
输出格式：
[Task]: {x}
[Action]: {y}
[Feedback]: {feedback}
[Tag]: {tag}
[Timestamp]: {timestamp.isoformat()}
"""
```

### `to_dict()` - 序列化为字典

将记忆条目转换为字典格式，用于JSON序列化。

```python
data = entry.to_dict()
# 返回：{"id": "...", "x": "...", "y": "...", "feedback": "...", "tag": "...", "timestamp": "..."}
```

### `from_dict()` - 从字典反序列化

从字典创建MemoryEntry实例。

```python
data = {
    "id": "test-id",
    "x": "任务输入",
    "y": "智能体输出",
    "feedback": "环境反馈",
    "tag": "test",
    "timestamp": "2024-01-01T10:00:00"
}
entry = MemoryEntry.from_dict(data)
```

## 使用示例

### 基本使用

```python
from datetime import datetime
from src.memory.entry import MemoryEntry

# 创建记忆条目（自动生成ID和时间戳）
entry = MemoryEntry(
    x="用户询问如何配置Python环境",
    y="建议使用venv创建虚拟环境：python -m venv myenv",
    feedback="用户成功配置了环境",
    tag="python-config"
)

# 使用自定义ID和时间戳
entry_with_custom = MemoryEntry(
    x="调试Python代码",
    y="使用pdb调试器：import pdb; pdb.set_trace()",
    feedback="成功定位了bug",
    tag="debugging",
    timestamp=datetime(2024, 1, 1, 10, 0, 0),
    id="custom-id-123"
)
```

### 属性操作

```python
# 读取属性
print(f"任务输入: {entry.x}")
print(f"记忆标签: {entry.tag}")
print(f"创建时间: {entry.timestamp.isoformat()}")

# 更新属性
entry.tag = "updated-tag"
entry.feedback = "更新后的反馈信息"

# 类型验证
try:
    entry.x = 123  # 错误：必须是字符串
except TypeError as e:
    print(f"类型错误: {e}")

try:
    entry.id = ""  # 错误：不能为空
except ValueError as e:
    print(f"值错误: {e}")
```

### 序列化和反序列化

```python
# 序列化为字典
entry_data = entry.to_dict()
print(f"序列化数据: {entry_data}")

# 保存到JSON文件
import json
with open("memory.json", "w") as f:
    json.dump(entry_data, f, indent=2)

# 从JSON文件加载
with open("memory.json", "r") as f:
    loaded_data = json.load(f)

restored_entry = MemoryEntry.from_dict(loaded_data)
print(f"恢复的条目ID: {restored_entry.id}")
```

### 比较和哈希

```python
# 创建两个条目
entry1 = MemoryEntry(x="任务1", y="输出1", feedback="反馈1", id="same-id")
entry2 = MemoryEntry(x="任务2", y="输出2", feedback="反馈2", id="same-id")
entry3 = MemoryEntry(x="任务1", y="输出1", feedback="反馈1", id="different-id")

# 比较（基于ID）
print(entry1 == entry2)  # True - ID相同
print(entry1 == entry3)  # False - ID不同

# 哈希（基于ID）
print(hash(entry1) == hash(entry2))  # True

# 作为字典键
memory_dict = {entry1: "存储的值"}
print(memory_dict[entry2])  # "存储的值" - 因为ID相同
```

### 文本表示

```python
# 生成标准化文本
text = entry.to_text()
print(text)
"""
[Task]: 用户询问如何配置Python环境
[Action]: 建议使用venv创建虚拟环境：python -m venv myenv
[Feedback]: 用户成功配置了环境
[Tag]: python-config
[Timestamp]: 2024-01-01T10:00:00
"""

# 字符串表示（用于调试）
print(repr(entry))
# MemoryEntry(id=..., x=用户询问如何配置Python环境..., tag=python-config)
```

## 兼容性说明

### 旧格式支持

`from_dict()` 方法支持旧格式数据，自动处理字段名映射：

```python
# 旧格式数据（使用cue和response字段）
old_format = {
    "cue": "旧格式任务输入",
    "response": "旧格式输出",
    "feedback": "旧格式反馈",
    "tag": "old",
    "id": "old-id"
}

# 自动转换为新格式
entry = MemoryEntry.from_dict(old_format)
print(entry.x)  # "旧格式任务输入"（从cue转换）
print(entry.y)  # "旧格式输出"（从response转换）
```

### 缺失字段处理

当字典中缺少必要字段时，`from_dict()` 方法会提供默认值：

```python
# 缺少某些字段的数据
partial_data = {
    "x": "任务",
    "y": "输出"
    # 缺少feedback和tag
}

entry = MemoryEntry.from_dict(partial_data)
print(entry.feedback)  # ""（空字符串）
print(entry.tag)       # ""（空字符串）
```

## 最佳实践

1. **ID管理**：除非有特殊需求，否则让系统自动生成UUID作为ID
2. **时间戳**：使用UTC时间确保跨时区一致性
3. **标签使用**：使用有意义的标签便于后续检索和过滤
4. **字段内容**：保持x、y、feedback字段内容简洁明了
5. **序列化**：使用`to_dict()`和`from_dict()`进行持久化存储

## 错误处理

所有setter方法都包含类型验证，确保数据一致性：

```python
try:
    # 有效操作
    entry.x = "新的任务输入"
    entry.timestamp = datetime.now()

    # 无效操作（会抛出异常）
    entry.id = 123           # TypeError: id必须是字符串
    entry.id = ""            # ValueError: id不能为空
    entry.timestamp = "now"  # TypeError: timestamp必须是datetime对象

except (TypeError, ValueError) as e:
    print(f"错误: {e}")
    # 处理错误或使用默认值
```

## 相关类

- `MemoryBank`：管理MemoryEntry集合
- `MemoryPersistence`：提供持久化存储功能
- `RetrievalResult`：检索结果包装类

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2024-01-01 | 初始版本，包含基本字段和方法 |
| 1.1.0 | 2024-01-15 | 添加property getter/setter，增强类型验证 |
| 1.2.0 | 2024-02-01 | 改进兼容性，支持旧格式数据 |

---

*文档最后更新：2024-12-11*