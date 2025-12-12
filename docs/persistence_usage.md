# MemoryPersistence 使用文档

## 概述

`MemoryPersistence` 提供记忆库的持久化存储功能，基于JSON文件实现自动保存/加载，支持版本兼容性、数据完整性验证、自动备份和恢复机制。

## 类定义

```python
class MemoryPersistence:
    """记忆持久化存储管理器"""

    # 当前存储格式版本
    FORMAT_VERSION = "1.0.0"
    # 支持的旧版本（用于向后兼容）
    SUPPORTED_VERSIONS = ["1.0.0", "0.9.0", "0.8.0"]

    def __init__(self, filepath: str = "./data/memory.json"):
        """
        初始化持久化管理器

        Args:
            filepath: 存储文件路径
        """
```

## 初始化

```python
from src.memory.persistence import MemoryPersistence

# 使用默认路径
persistence = MemoryPersistence()  # 保存到 ./data/memory.json

# 自定义路径
persistence = MemoryPersistence("/path/to/your/memory.json")

# 相对路径（自动创建目录）
persistence = MemoryPersistence("./data/memories/project_memory.json")
```

## 核心功能

### 1. 保存和加载

#### 保存记忆库

```python
from src.memory.bank import MemoryBank

# 创建或获取记忆库
bank = MemoryBank(max_entries=1000)

# 添加一些记忆条目...

# 保存到文件
success = persistence.save(bank)

if success:
    print(f"记忆库已保存到: {persistence.filepath}")
    print(f"共保存 {len(bank)} 条记忆")
else:
    print("保存失败，请检查错误日志")
```

#### 加载记忆库

```python
# 加载记忆库（创建新实例）
loaded_bank = persistence.load()
print(f"从 {persistence.filepath} 加载了 {len(loaded_bank)} 条记忆")

# 加载到现有记忆库（合并）
existing_bank = MemoryBank()
existing_bank.add(some_entry)  # 添加一些现有条目

merged_bank = persistence.load(existing_bank)
print(f"合并后共有 {len(merged_bank)} 条记忆")
```

#### 文件不存在的情况

```python
# 如果文件不存在，返回空记忆库
nonexistent_persistence = MemoryPersistence("./nonexistent.json")
bank = nonexistent_persistence.load()

print(f"加载结果: {len(bank)} 条记忆")  # 0
print(f"最大容量: {bank.max_entries}")  # 1000（默认值）
```

### 2. 导出和导入

#### 导出到文件

```python
# 导出到指定文件
export_path = "./exports/memory_export_20241211.json"
success = persistence.export_to_file(bank, export_path)

if success:
    print(f"记忆库已导出到: {export_path}")

    # 验证导出文件
    import json
    with open(export_path, "r") as f:
        export_data = json.load(f)

    print(f"导出版本: {export_data.get('version')}")
    print(f"导出条目数: {len(export_data.get('entries', []))}")
    print(f"导出时间: {export_data.get('export_timestamp')}")
```

#### 从文件导入

```python
# 从导出文件导入
import_path = "./exports/memory_export_20241211.json"
imported_bank = persistence.import_from_file(import_path)

print(f"从 {import_path} 导入了 {len(imported_bank)} 条记忆")

# 导入到现有记忆库（去重合并）
existing_bank = MemoryBank()
# ... 添加一些现有条目 ...

merged_bank = persistence.import_from_file(import_path, existing_bank)
print(f"合并后总数: {len(merged_bank)}")
```

### 3. 备份和恢复

#### 创建备份

```python
# 创建备份（默认目录：./backups/）
backup_path = persistence.backup(bank)

if backup_path:
    print(f"备份已创建: {backup_path}")
else:
    print("备份创建失败")

# 自定义备份目录
custom_backup_dir = "./custom_backups/"
backup_path = persistence.backup(bank, custom_backup_dir)
```

#### 自动备份机制

每次调用 `save()` 方法时，如果文件已存在，会自动创建备份：

```python
# 第一次保存 - 创建文件
persistence.save(bank)

# 第二次保存 - 自动创建备份
bank.add(new_entry)
persistence.save(bank)  # 自动备份旧版本

# 检查备份目录
import os
backup_dir = os.path.join(os.path.dirname(persistence.filepath), "backups")
if os.path.exists(backup_dir):
    backups = os.listdir(backup_dir)
    print(f"找到 {len(backups)} 个备份文件")
```

#### 从备份恢复

当主文件损坏时，`load()` 方法会自动尝试从备份恢复：

```python
# 模拟文件损坏
with open(persistence.filepath, "w") as f:
    f.write("corrupted content")

# 加载时会自动尝试从备份恢复
with self.assertLogs(level='WARNING') as log:
    recovered_bank = persistence.load()

print(f"恢复后条目数: {len(recovered_bank)}")
# 应该从最近的备份成功恢复
```

### 4. 文件验证和监控

#### 获取文件信息

```python
info = persistence.get_file_info()

if info["exists"]:
    print(f"文件大小: {info['file_size']} 字节")
    print(f"修改时间: {info['modified_time']}")
    print(f"存储版本: {info['version']}")
    print(f"条目数量: {info['entry_count']}")
    print(f"最大容量: {info['max_entries']}")
    print(f"完整性检查: {'通过' if info['integrity_check'] else '失败'}")
else:
    print(f"文件不存在: {info['error']}")
```

#### 验证文件完整性

```python
validation = persistence.validate_file()

if validation["valid"]:
    print("✅ 文件验证通过")
    print(f"  版本: {validation['version']} (支持: {validation['version_supported']})")
    print(f"  必要字段: {validation['has_required_fields']}")
    print(f"  条目列表: {validation['entries_is_list']}")
    print(f"  条目数量: {validation['entry_count']}")
    print(f"  校验和: {validation['checksum_valid']}")

    if validation["has_invalid_entries"]:
        print(f"⚠️  发现 {len(validation['invalid_entries'])} 个无效条目")
        for invalid in validation["invalid_entries"]:
            print(f"    索引 {invalid['index']}: {invalid['error']}")
else:
    print("❌ 文件验证失败")
    print(f"  错误: {validation['error']}")
```

## 高级功能

### 版本兼容性

`MemoryPersistence` 支持多个版本的存储格式：

```python
# 支持的版本
print(f"当前版本: {persistence.FORMAT_VERSION}")
print(f"支持版本: {persistence.SUPPORTED_VERSIONS}")

# 加载旧版本文件时会自动转换
old_version_data = {
    "version": "0.8.0",  # 旧版本
    "timestamp": "2024-01-01T10:00:00",
    "max_entries": 1000,
    "entries": [
        {
            "cue": "旧格式任务",  # 旧字段名
            "response": "旧格式输出",
            "feedback": "旧格式反馈",
            "tag": "old"
        }
    ]
}

# 保存旧格式文件
import json
with open("old_version.json", "w") as f:
    json.dump(old_version_data, f)

# 加载时会自动转换
old_persistence = MemoryPersistence("old_version.json")
bank = old_persistence.load()

print(f"加载条目数: {len(bank)}")  # 1
print(f"转换后x字段: {bank[0].x}")  # "旧格式任务"（从cue转换）
```

### 数据完整性保护

#### 校验和验证

每次保存时自动计算校验和，加载时验证：

```python
# 保存时计算校验和
persistence.save(bank)

# 查看文件内容
with open(persistence.filepath, "r") as f:
    data = json.load(f)

print(f"存储的校验和: {data['metadata']['checksum']}")

# 篡改文件内容
data["entries"][0]["x"] = "被篡改的内容"
with open(persistence.filepath, "w") as f:
    json.dump(data, f)

# 加载时会检测到篡改
validation = persistence.validate_file()
print(f"校验和验证: {validation['checksum_valid']}")  # False
```

#### 原子性保存

使用临时文件确保保存操作的原子性：

```python
# save() 方法的内部流程：
# 1. 写入临时文件 memory.json.tmp
# 2. 原子性地重命名为 memory.json
# 3. 如果中途失败，原始文件保持不变

# 这确保了即使在保存过程中崩溃，也不会损坏原始文件
```

### 错误处理和恢复

```python
try:
    # 尝试加载
    bank = persistence.load()

except Exception as e:
    print(f"加载失败: {e}")

    # 尝试手动恢复
    print("尝试手动恢复...")

    # 1. 检查文件是否存在
    if not os.path.exists(persistence.filepath):
        print("文件不存在，创建新记忆库")
        bank = MemoryBank()

    # 2. 尝试从备份恢复
    else:
        print("尝试从备份恢复...")
        backup_dir = os.path.join(os.path.dirname(persistence.filepath), "backups")
        if os.path.exists(backup_dir):
            # 查找最新备份
            backups = []
            for filename in os.listdir(backup_dir):
                if filename.startswith(os.path.basename(persistence.filepath) + ".backup_"):
                    filepath = os.path.join(backup_dir, filename)
                    backups.append((filepath, os.path.getmtime(filepath)))

            if backups:
                latest_backup = max(backups, key=lambda x: x[1])[0]
                print(f"使用备份: {latest_backup}")

                with open(latest_backup, "r") as f:
                    backup_data = json.load(f)

                # 手动恢复
                bank = MemoryBank(max_entries=backup_data.get("max_entries", 1000))
                for entry_data in backup_data.get("entries", []):
                    try:
                        entry = MemoryEntry.from_dict(entry_data)
                        bank.add(entry)
                    except:
                        pass  # 跳过无效条目

                print(f"从备份恢复了 {len(bank)} 条记忆")
            else:
                print("没有找到备份，创建新记忆库")
                bank = MemoryBank()
        else:
            print("备份目录不存在，创建新记忆库")
            bank = MemoryBank()

    # 3. 保存恢复后的记忆库
    persistence.save(bank)
    print("恢复完成并已保存")
```

## 使用示例

### 完整工作流程

```python
import os
from datetime import datetime
from src.memory.bank import MemoryBank
from src.memory.entry import MemoryEntry
from src.memory.persistence import MemoryPersistence

class MemoryManager:
    def __init__(self, storage_path="./data/memory.json"):
        self.persistence = MemoryPersistence(storage_path)
        self.bank = self._initialize_bank()

    def _initialize_bank(self):
        """初始化记忆库"""
        print(f"存储文件: {self.persistence.filepath}")

        # 检查文件信息
        info = self.persistence.get_file_info()
        if info["exists"]:
            print(f"找到现有文件 ({info['file_size']} 字节)")

            # 验证文件
            validation = self.persistence.validate_file()
            if validation["valid"]:
                print("✅ 文件验证通过")
                bank = self.persistence.load()
                print(f"加载了 {len(bank)} 条现有记忆")
            else:
                print(f"⚠️ 文件验证失败: {validation['error']}")
                print("尝试从备份恢复...")
                bank = self.persistence.load()  # 会自动尝试恢复
                print(f"恢复后 {len(bank)} 条记忆")
        else:
            print("文件不存在，创建新记忆库")
            bank = MemoryBank(max_entries=1000)

        return bank

    def add_memory(self, x, y, feedback, tag=""):
        """添加新记忆"""
        entry = MemoryEntry(
            x=x,
            y=y,
            feedback=feedback,
            tag=tag,
            timestamp=datetime.now()
        )

        self.bank.add(entry)
        print(f"添加记忆: {x[:30]}... (标签: {tag})")

        # 定期保存（每10条保存一次）
        if len(self.bank) % 10 == 0:
            self.save()

    def save(self, backup=True):
        """保存记忆库"""
        print("保存记忆库...")

        # 创建备份
        if backup:
            backup_path = self.persistence.backup(self.bank)
            if backup_path:
                print(f"创建备份: {os.path.basename(backup_path)}")

        # 保存
        success = self.persistence.save(self.bank)
        if success:
            print(f"✅ 保存成功 ({len(self.bank)} 条记忆)")
        else:
            print("❌ 保存失败")

        return success

    def export(self, export_path):
        """导出记忆库"""
        print(f"导出到: {export_path}")
        success = self.persistence.export_to_file(self.bank, export_path)

        if success:
            # 验证导出文件
            validation = self.persistence.validate_file()
            print(f"导出验证: {'通过' if validation['valid'] else '失败'}")

        return success

    def get_stats(self):
        """获取统计信息"""
        file_info = self.persistence.get_file_info()
        bank_stats = self.bank.get_statistics()

        return {
            "file": file_info,
            "bank": bank_stats
        }

# 使用示例
if __name__ == "__main__":
    manager = MemoryManager("./data/project_memory.json")

    # 添加一些记忆
    manager.add_memory(
        x="如何配置开发环境",
        y="安装Python、VS Code、Git",
        feedback="配置成功",
        tag="setup"
    )

    manager.add_memory(
        x="遇到导入错误怎么办",
        y="检查PYTHONPATH，重新安装包",
        feedback="问题解决",
        tag="debugging"
    )

    # 保存
    manager.save()

    # 导出备份
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manager.export(f"./backups/memory_export_{timestamp}.json")

    # 查看统计
    stats = manager.get_stats()
    print(f"\n📊 统计信息:")
    print(f"  文件大小: {stats['file']['file_size']} 字节")
    print(f"  记忆条目: {stats['bank']['total_entries']}")
    print(f"  标签分布: {stats['bank']['tag_distribution']}")
```

### 生产环境配置

```python
class ProductionMemoryPersistence(MemoryPersistence):
    """生产环境持久化管理器"""

    def __init__(self, filepath, backup_retention_days=30, enable_compression=False):
        super().__init__(filepath)
        self.backup_retention_days = backup_retention_days
        self.enable_compression = enable_compression

    def save(self, memory_bank):
        """增强的保存方法"""
        # 1. 验证记忆库
        if len(memory_bank) == 0:
            print("警告: 尝试保存空记忆库")

        # 2. 创建备份
        backup_path = self.backup(memory_bank)
        if backup_path:
            print(f"生产备份: {backup_path}")

            # 清理旧备份
            self._cleanup_old_backups(
                os.path.dirname(backup_path),
                days_to_keep=self.backup_retention_days
            )

        # 3. 保存（调用父类方法）
        success = super().save(memory_bank)

        if success:
            # 4. 记录审计日志
            self._log_audit("save", {
                "entry_count": len(memory_bank),
                "backup_created": backup_path is not None,
                "timestamp": datetime.now().isoformat()
            })

        return success

    def _log_audit(self, action, details):
        """记录审计日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "file": self.filepath,
            **details
        }

        # 这里可以写入文件、数据库或发送到监控系统
        print(f"[AUDIT] {json.dumps(log_entry)}")

# 生产环境使用
production_persistence = ProductionMemoryPersistence(
    filepath="/var/data/memory/production_memory.json",
    backup_retention_days=90,  # 保留90天备份
    enable_compression=False
)
```

## 最佳实践

### 1. 文件管理
- 使用有意义的文件命名：`project_memory.json`、`user_123_memory.json`
- 定期清理旧备份文件
- 监控文件大小，避免过大影响性能

### 2. 错误处理
- 始终检查 `save()` 和 `load()` 的返回值
- 实现适当的重试机制
- 记录详细的错误日志

### 3. 性能优化
- 避免频繁保存，考虑批量操作
- 对于大型记忆库，考虑分片存储
- 定期验证文件完整性

### 4. 安全考虑
- 敏感信息不要存储在记忆库中
- 设置适当的文件权限
- 考虑加密存储选项

## 故障排除

### 常见问题

#### 1. 文件损坏
```
症状：加载失败，JSON解析错误
解决：
  1. 检查 validate_file() 结果
  2. 尝试从备份恢复
  3. 手动修复或重建文件
```

#### 2. 版本不兼容
```
症状：加载旧版本文件失败
解决：
  1. 检查 SUPPORTED_VERSIONS
  2. 使用兼容模式加载
  3. 升级文件格式
```

#### 3. 磁盘空间不足
```
症状：保存失败，IO错误
解决：
  1. 清理旧备份
  2. 减少记忆库容量
  3. 压缩存储数据
```

#### 4. 权限问题
```
症状：保存失败，权限被拒绝
解决：
  1. 检查文件权限
  2. 使用合适的存储目录
  3. 以正确用户身份运行
```

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 逐步调试
persistence = MemoryPersistence("./debug_memory.json")

# 1. 检查文件状态
info = persistence.get_file_info()
print(f"文件状态: {info}")

# 2. 验证文件
validation = persistence.validate_file()
print(f"验证结果: {validation}")

# 3. 尝试加载
try:
    bank = persistence.load()
    print(f"加载成功: {len(bank)} 条记忆")
except Exception as e:
    print(f"加载失败: {e}")
    import traceback
    traceback.print_exc()
```

## API参考

### 主要方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `save(memory_bank)` | 保存记忆库到文件 | `bool` |
| `load(memory_bank=None)` | 从文件加载记忆库 | `MemoryBank` |
| `export_to_file(memory_bank, export_path)` | 导出到指定文件 | `bool` |
| `import_from_file(import_path, memory_bank=None)` | 从文件导入 | `MemoryBank` |
| `backup(memory_bank, backup_dir="./backups")` | 创建备份 | `str` 或 `None` |
| `get_file_info()` | 获取文件信息 | `Dict[str, Any]` |
| `validate_file()` | 验证文件完整性 | `Dict[str, Any]` |

### 内部方法（高级使用）

| 方法 | 说明 |
|------|------|
| `_ensure_directory()` | 确保存储目录存在 |
| `_load_entry_with_compatibility(entry_data)` | 兼容性加载条目 |
| `_load_with_compatibility(data, memory_bank)` | 兼容模式加载 |
| `_validate_data_integrity(data)` | 验证数据完整性 |
| `_calculate_checksum(data)` | 计算校验和 |
| `_create_backup(filepath)` | 创建文件备份 |
| `_cleanup_old_backups(backup_dir, days_to_keep=7)` | 清理旧备份 |
| `_recover_from_backup(memory_bank)` | 从备份恢复 |

### 类属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `FORMAT_VERSION` | `str` | 当前存储格式版本 |
| `SUPPORTED_VERSIONS` | `List[str]` | 支持的旧版本 |
| `filepath` | `str` | 存储文件路径 |

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2024-01-01 | 初始版本，基本保存/加载功能 |
| 1.1.0 | 2024-02-01 | 添加版本兼容性支持 |
| 1.2.0 | 2024-03-01 | 添加数据完整性验证和校验和 |
| 1.3.0 | 2024-04-01 | 添加自动备份和恢复机制 |
| 1.4.0 | 2024-05-01 | 添加文件验证和监控功能 |

---

*文档最后更新：2024-12-11*