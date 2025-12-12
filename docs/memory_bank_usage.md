# MemoryBank 使用文档

## 概述

`MemoryBank` 是记忆库管理类，负责管理`MemoryEntry`集合，提供添加、删除、检索、统计等功能。它支持基于LLM的智能检索和多种内存管理操作。

## 类定义

```python
class MemoryBank:
    """记忆库类，管理记忆条目集合"""

    def __init__(self, max_entries: int = 1000):
        """
        初始化记忆库

        Args:
            max_entries: 最大记忆容量，达到容量时会自动清理
        """
```

## 初始化

```python
from src.memory.bank import MemoryBank

# 使用默认容量（1000条）
bank = MemoryBank()

# 自定义容量
small_bank = MemoryBank(max_entries=100)  # 最多存储100条记忆
large_bank = MemoryBank(max_entries=10000)  # 最多存储10000条记忆
```

## 核心功能

### 1. 记忆条目管理

#### 添加记忆条目

```python
from src.memory.entry import MemoryEntry

# 创建记忆条目
entry = MemoryEntry(
    x="如何学习Python",
    y="从基础语法开始，然后学习常用库",
    feedback="学习进度良好",
    tag="learning"
)

# 添加条目
bank.add(entry)  # 或使用别名 bank.add_entry(entry)

# 验证添加
print(f"记忆库大小: {len(bank)}")  # 1
print(f"第一个条目: {bank[0].x}")  # "如何学习Python"
```

#### 获取记忆条目

```python
# 通过索引获取
entry = bank[0]  # 获取第一个条目

# 通过ID获取
entry = bank.get_entry("entry-id-123")

# 遍历所有条目
for i, entry in enumerate(bank.entries):
    print(f"条目{i}: {entry.x[:20]}...")
```

#### 更新记忆条目

```python
# 更新指定ID的条目
success = bank.update_entry(
    "entry-id-123",
    x="更新后的任务输入",
    tag="updated",
    feedback="新的反馈信息"
)

if success:
    print("更新成功")
else:
    print("条目不存在或更新失败")
```

#### 删除记忆条目

```python
# 通过索引删除
bank.delete([0, 2])  # 删除索引0和2的条目

# 通过ID删除
success = bank.delete_entry("entry-id-123")

# 清空记忆库
bank.clear()
print(f"清空后大小: {len(bank)}")  # 0
```

### 2. 检索功能

#### 简单文本搜索

```python
# 关键词搜索（大小写不敏感）
results = bank.search("Python", limit=5)
print(f"找到 {len(results)} 个相关条目")

for result in results:
    print(f"- {result.x[:30]}... (标签: {result.tag})")
```

#### 标签过滤

```python
# 获取特定标签的条目
python_entries = bank.filter_by_tag("python")
debug_entries = bank.filter_by_tag("debugging")

print(f"Python相关条目: {len(python_entries)}")
print(f"调试相关条目: {len(debug_entries)}")
```

#### 获取最近条目

```python
# 获取最近创建的10个条目
recent = bank.get_recent_entries(limit=10)

for i, entry in enumerate(recent):
    print(f"最近条目{i+1}: {entry.x[:30]}... ({entry.timestamp})")
```

#### LLM智能检索

```python
from src.llm.mock_llm import MockLLM

# 创建LLM实例（需要实现__call__方法）
llm = MockLLM()

# 执行检索
query = "如何调试Python代码中的内存泄漏"
results = bank.retrieve(llm, query, k=5, include_explanations=True)

print(f"查询: '{query}'")
print(f"返回 {len(results)} 个最相关结果")

for result in results:
    print(f"\n相关性评分: {result.relevance_score:.2f}")
    print(f"解释: {result.explanation}")
    print(f"记忆内容: {result.memory_entry.x[:50]}...")
```

### 3. 记忆操作

#### 合并记忆条目

```python
# 合并两个相关条目
bank.merge(0, 1)  # 合并索引0和1的条目

# 合并后的条目会包含两个原始条目的内容
merged_entry = bank[0]
print(f"合并后标签: {merged_entry.tag}")  # "merged(python,debugging)"
print(f"合并后内容: {merged_entry.x[:100]}...")
```

#### 重新标记

```python
# 修改条目标签
bank.relabel(0, "new-category")

# 验证修改
print(f"新标签: {bank[0].tag}")  # "new-category"
```

#### 批量操作

```python
# 定义批量操作
operations = [
    {
        "type": "add",
        "params": {
            "entry": {
                "x": "批量添加任务1",
                "y": "批量添加输出1",
                "feedback": "批量反馈1",
                "tag": "batch"
            }
        }
    },
    {
        "type": "relabel",
        "params": {
            "idx": 0,
            "new_tag": "batch-relabeled"
        }
    },
    {
        "type": "delete",
        "params": {
            "indices": [1, 2]
        }
    }
]

# 执行批量操作
results = bank.batch_operations(operations)

print(f"总操作数: {results['total_operations']}")
print(f"成功: {results['successful']}")
print(f"失败: {results['failed']}")

if results['errors']:
    print("错误详情:")
    for error in results['errors']:
        print(f"  操作{error['operation_index']}: {error['error']}")
```

### 4. 统计和监控

#### 获取统计信息

```python
stats = bank.get_statistics()

print(f"总条目数: {stats['total_entries']}")
print(f"最大容量: {stats['max_entries']}")
print(f"最旧条目: {stats['oldest_timestamp']}")
print(f"最新条目: {stats['newest_timestamp']}")

print("标签分布:")
for tag, count in stats['tag_distribution'].items():
    print(f"  {tag}: {count}")

print(f"操作历史记录数: {stats['operation_history_count']}")
```

#### 操作历史

```python
# 获取最近操作记录
history = bank.get_operation_history(limit=10)

for record in history:
    print(f"{record['timestamp']} - {record['operation_type']}: {record['details']}")

# 清空操作历史
bank.clear_operation_history()
```

## 高级功能

### 容量管理和自动清理

当记忆库达到最大容量时，会自动清理最旧的条目：

```python
# 创建小容量记忆库
small_bank = MemoryBank(max_entries=3)

# 添加4个条目（触发自动清理）
for i in range(4):
    entry = MemoryEntry(
        x=f"任务{i}",
        y=f"输出{i}",
        feedback=f"反馈{i}",
        timestamp=datetime(2024, 1, i+1, 10, 0, 0)
    )
    small_bank.add(entry)

print(f"实际存储条目: {len(small_bank)}")  # 3（清理了最旧的1个）
```

### 序列化和持久化

```python
# 导出为字典列表
data = bank.to_dict()
print(f"导出 {len(data)} 个条目")

# 保存到JSON文件
import json
with open("memory_bank.json", "w") as f:
    json.dump(data, f, indent=2)

# 从字典列表恢复
with open("memory_bank.json", "r") as f:
    loaded_data = json.load(f)

restored_bank = MemoryBank.from_dict(loaded_data, max_entries=1000)
print(f"恢复 {len(restored_bank)} 个条目")
```

### 与Persistence集成

```python
from src.memory.persistence import MemoryPersistence

# 创建持久化管理器
persistence = MemoryPersistence("./data/memory.json")

# 保存记忆库
persistence.save(bank)

# 加载记忆库
loaded_bank = persistence.load()

# 导出到其他文件
persistence.export_to_file(bank, "./backups/memory_backup.json")

# 从文件导入
imported_bank = persistence.import_from_file("./backups/memory_backup.json")
```

## 使用示例

### 完整工作流程

```python
from datetime import datetime
from src.memory.bank import MemoryBank
from src.memory.entry import MemoryEntry
from src.memory.persistence import MemoryPersistence

# 1. 初始化
bank = MemoryBank(max_entries=1000)
persistence = MemoryPersistence("./data/memory.json")

# 2. 加载现有记忆（如果存在）
if os.path.exists("./data/memory.json"):
    bank = persistence.load(bank)
    print(f"加载了 {len(bank)} 个现有记忆")

# 3. 添加新记忆
new_entry = MemoryEntry(
    x="用户询问如何优化数据库查询",
    y="建议添加索引、优化SQL语句、使用缓存",
    feedback="查询性能提升了50%",
    tag="database-optimization"
)
bank.add(new_entry)

# 4. 检索相关记忆
query = "数据库性能问题"
results = bank.search(query, limit=5)

if results:
    print(f"找到 {len(results)} 个相关记忆:")
    for entry in results:
        print(f"  - {entry.x[:40]}... (标签: {entry.tag})")
else:
    print("没有找到相关记忆")

# 5. 获取统计信息
stats = bank.get_statistics()
print(f"\n记忆库统计:")
print(f"  总条目: {stats['total_entries']}")
print(f"  标签分布: {stats['tag_distribution']}")

# 6. 定期保存
persistence.save(bank)
print("记忆库已保存")
```

### 智能助手集成

```python
class SmartAssistant:
    def __init__(self, llm):
        self.bank = MemoryBank()
        self.llm = llm
        self.persistence = MemoryPersistence("./data/assistant_memory.json")

        # 加载历史记忆
        self.bank = self.persistence.load(self.bank)

    def process_query(self, user_query: str) -> str:
        # 1. 检索相关历史记忆
        relevant_memories = self.bank.retrieve(
            self.llm,
            user_query,
            k=3,
            include_explanations=True
        )

        # 2. 基于记忆生成响应
        context = self._build_context(relevant_memories)
        response = self._generate_response(user_query, context)

        # 3. 记录本次交互
        self._record_interaction(user_query, response)

        # 4. 定期保存
        self.persistence.save(self.bank)

        return response

    def _build_context(self, memories):
        context = "相关历史经验:\n"
        for memory in memories:
            context += f"- {memory.memory_entry.x}: {memory.memory_entry.y}\n"
            context += f"  反馈: {memory.memory_entry.feedback}\n"
            context += f"  相关性: {memory.relevance_score:.2f} ({memory.explanation})\n"
        return context

    def _generate_response(self, query, context):
        # 使用LLM生成响应（简化示例）
        prompt = f"""
        用户查询: {query}

        {context}

        请基于以上历史经验，给出最佳建议:
        """
        return self.llm(prompt)

    def _record_interaction(self, query, response):
        # 等待用户反馈（简化示例）
        feedback = input("这个回答有帮助吗？ (yes/no): ")

        entry = MemoryEntry(
            x=query,
            y=response,
            feedback=feedback,
            tag="assistant-interaction"
        )
        self.bank.add(entry)
```

## 性能考虑

1. **检索性能**：
   - `search()` 使用线性搜索，适合小型记忆库
   - 对于大型记忆库，考虑使用倒排索引或向量数据库

2. **内存使用**：
   - 设置合理的 `max_entries` 避免内存溢出
   - 定期清理不需要的记忆条目

3. **持久化频率**：
   - 高频保存可能影响性能
   - 考虑增量保存或定时保存策略

## 错误处理

```python
try:
    # 正常操作
    bank.add(entry)
    results = bank.search("query")

    # 边界情况处理
    if len(bank) == 0:
        print("记忆库为空")
        return []

    # 索引验证
    if index >= len(bank):
        raise IndexError(f"索引 {index} 超出范围 (0-{len(bank)-1})")

    entry = bank[index]

except ValueError as e:
    print(f"值错误: {e}")
    # 处理无效参数
except IndexError as e:
    print(f"索引错误: {e}")
    # 处理越界访问
except Exception as e:
    print(f"未知错误: {e}")
    # 记录日志并恢复
```

## 最佳实践

1. **标签设计**：使用一致的标签命名规范
2. **容量规划**：根据应用需求设置合适的 `max_entries`
3. **定期维护**：清理无效条目，合并相似记忆
4. **版本控制**：对记忆库进行版本管理和备份
5. **监控告警**：监控记忆库大小和操作频率

## 相关类

- `MemoryEntry`：记忆条目数据结构
- `MemoryPersistence`：持久化存储管理
- `RetrievalResult`：检索结果包装类
- `MockLLM`：LLM接口模拟实现

## API参考

### 主要方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `add(entry)` | 添加记忆条目 | `None` |
| `add_entry(entry)` | 添加记忆条目（别名） | `None` |
| `get_entry(id)` | 根据ID获取条目 | `MemoryEntry` 或 `None` |
| `update_entry(id, **kwargs)` | 更新条目 | `bool` |
| `delete(indices)` | 删除指定索引条目 | `None` |
| `delete_entry(id)` | 根据ID删除条目 | `bool` |
| `search(query, limit=10)` | 文本搜索 | `List[MemoryEntry]` |
| `filter_by_tag(tag)` | 标签过滤 | `List[MemoryEntry]` |
| `get_recent_entries(limit=10)` | 获取最近条目 | `List[MemoryEntry]` |
| `retrieve(llm, query, k=5, include_explanations=True)` | LLM智能检索 | `List[Union[MemoryEntry, RetrievalResult]]` |
| `merge(idx1, idx2)` | 合并两个条目 | `None` |
| `relabel(idx, new_tag)` | 重新标记 | `None` |
| `clear()` | 清空记忆库 | `None` |
| `get_statistics()` | 获取统计信息 | `Dict[str, Any]` |
| `batch_operations(operations)` | 批量操作 | `Dict[str, Any]` |
| `to_dict()` | 序列化 | `List[Dict[str, Any]]` |
| `from_dict(data, max_entries=1000)` | 反序列化 | `MemoryBank` |

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `entries` | `List[MemoryEntry]` | 记忆条目列表 |
| `max_entries` | `int` | 最大容量 |
| `operation_history` | `List[Dict[str, Any]]` | 操作历史记录 |

---

*文档最后更新：2024-12-11*