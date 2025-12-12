# 配置管理使用文档

## 概述

本项目的配置管理系统提供统一的配置管理接口，支持环境变量、配置文件、命令行参数等多种配置源，并包含配置验证、类型转换、热重载等功能。

## 配置结构

### 配置文件位置

```
pm-mem/
├── configs/
│   ├── default.yaml          # 默认配置
│   ├── development.yaml      # 开发环境配置
│   ├── production.yaml       # 生产环境配置
│   └── test.yaml            # 测试环境配置
├── .env                     # 环境变量（开发）
├── .env.example            # 环境变量示例
└── .env.production        # 生产环境变量
```

### 配置层次结构

配置按以下优先级加载（从高到低）：
1. 命令行参数
2. 环境变量
3. 环境特定配置文件（如 `production.yaml`）
4. 默认配置文件（`default.yaml`）
5. 代码中的默认值

## 快速开始

### 基本使用

```python
from src.config.config_manager import ConfigManager

# 初始化配置管理器
config = ConfigManager()

# 获取配置值
log_level = config.get("logging.level", "INFO")
db_host = config.get("database.host", "localhost")
max_entries = config.get("memory.max_entries", 1000)

# 设置配置值
config.set("logging.level", "DEBUG")
config.set("memory.max_entries", 5000)

# 保存配置到文件
config.save_to_file("./configs/custom.yaml")
```

### 环境特定配置

```python
import os

# 设置环境变量
os.environ["APP_ENV"] = "production"

# 初始化时会自动加载对应环境的配置
config = ConfigManager()

# 获取生产环境配置
db_config = config.get_section("database")
print(f"数据库主机: {db_config['host']}")
print(f"数据库端口: {db_config['port']}")
```

## 配置管理器详解

### ConfigManager 类

```python
class ConfigManager:
    """配置管理器"""

    def __init__(
        self,
        config_dir: str = "./configs",
        env: Optional[str] = None,
        load_env_file: bool = True
    ):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录
            env: 环境名称（如 'development', 'production'）
            load_env_file: 是否加载.env文件
        """
```

### 初始化选项

```python
# 1. 默认初始化（自动检测环境）
config = ConfigManager()

# 2. 指定环境
config = ConfigManager(env="production")

# 3. 自定义配置目录
config = ConfigManager(config_dir="/etc/pm-mem/configs")

# 4. 禁用.env文件加载
config = ConfigManager(load_env_file=False)

# 5. 完全自定义
config = ConfigManager(
    config_dir="./my_configs",
    env="staging",
    load_env_file=True
)
```

## 配置访问方法

### 基本访问

```python
# 获取配置值（带默认值）
value = config.get("section.key", default_value)

# 示例
log_level = config.get("logging.level", "INFO")
timeout = config.get("api.timeout", 30)
enabled = config.get("feature.enabled", False)

# 获取整个配置节
logging_config = config.get_section("logging")
database_config = config.get_section("database")

# 获取所有配置
all_config = config.get_all()
```

### 类型安全访问

```python
# 获取整数
port = config.get_int("server.port", 8080)

# 获取浮点数
threshold = config.get_float("model.threshold", 0.5)

# 获取布尔值
debug = config.get_bool("debug.enabled", False)

# 获取列表
tags = config.get_list("memory.tags", ["default"])

# 获取字典
headers = config.get_dict("http.headers", {"User-Agent": "pm-mem"})
```

### 配置验证

```python
# 定义配置模式
config_schema = {
    "database": {
        "host": {"type": "string", "required": True},
        "port": {"type": "int", "min": 1, "max": 65535},
        "username": {"type": "string", "required": True},
        "password": {"type": "string", "required": True},
    },
    "logging": {
        "level": {"type": "string", "choices": ["DEBUG", "INFO", "WARNING", "ERROR"]},
        "format": {"type": "string", "default": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    }
}

# 验证配置
is_valid, errors = config.validate(config_schema)

if not is_valid:
    print("配置验证失败:")
    for error in errors:
        print(f"  - {error}")
else:
    print("配置验证通过")
```

## 配置源管理

### 环境变量

环境变量使用 `PM_MEM_` 前缀，点号用下划线代替：

```bash
# .env 文件示例
PM_MEM_LOGGING_LEVEL=DEBUG
PM_MEM_DATABASE_HOST=localhost
PM_MEM_DATABASE_PORT=5432
PM_MEM_MEMORY_MAX_ENTRIES=5000
PM_MEM_API_TIMEOUT=30
```

```python
# 代码中访问
log_level = config.get("logging.level")  # 从 PM_MEM_LOGGING_LEVEL 读取
db_host = config.get("database.host")    # 从 PM_MEM_DATABASE_HOST 读取
```

### 配置文件

YAML 配置文件示例：

```yaml
# configs/default.yaml
app:
  name: "pm-mem"
  version: "1.0.0"
  env: "development"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/app.log"
  max_size: 10485760  # 10MB
  backup_count: 5

database:
  host: "localhost"
  port: 5432
  name: "pm_mem_db"
  username: "postgres"
  password: ""
  pool_size: 10
  timeout: 30

memory:
  max_entries: 1000
  persistence:
    file: "./data/memory.json"
    backup_dir: "./backups"
    auto_save: true
    save_interval: 300  # 5分钟

api:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  timeout: 30
  cors_origins:
    - "http://localhost:3000"
    - "http://127.0.0.1:3000"

llm:
  provider: "openai"
  model: "gpt-3.5-turbo"
  temperature: 0.7
  max_tokens: 1000
```

### 环境特定配置

```yaml
# configs/development.yaml
# 继承 default.yaml，覆盖开发环境特定配置
app:
  env: "development"

logging:
  level: "DEBUG"

database:
  host: "localhost"
  name: "pm_mem_dev"

api:
  debug: true
```

```yaml
# configs/production.yaml
# 继承 default.yaml，覆盖生产环境特定配置
app:
  env: "production"

logging:
  level: "WARNING"
  file: "/var/log/pm-mem/app.log"

database:
  host: "db.production.example.com"
  name: "pm_mem_prod"
  pool_size: 20

api:
  host: "0.0.0.0"
  port: 80
  workers: 8
  debug: false
```

### 命令行参数

```python
import argparse

# 创建命令行解析器
parser = argparse.ArgumentParser(description="PM-Mem 配置")
parser.add_argument("--config", help="配置文件路径")
parser.add_argument("--log-level", help="日志级别")
parser.add_argument("--db-host", help="数据库主机")
parser.add_argument("--max-entries", type=int, help="最大记忆条目数")

args = parser.parse_args()

# 更新配置
if args.config:
    config.load_from_file(args.config)

if args.log_level:
    config.set("logging.level", args.log_level)

if args.db_host:
    config.set("database.host", args.db_host)

if args.max_entries:
    config.set("memory.max_entries", args.max_entries)
```

## 高级功能

### 配置热重载

```python
import time
from threading import Thread

class ConfigWatcher:
    def __init__(self, config_manager, watch_interval=60):
        self.config = config_manager
        self.watch_interval = watch_interval
        self.running = False
        self.thread = None

    def start(self):
        """启动配置监视器"""
        self.running = True
        self.thread = Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        print("配置监视器已启动")

    def stop(self):
        """停止配置监视器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("配置监视器已停止")

    def _watch_loop(self):
        """监视循环"""
        last_mtime = self._get_config_mtime()

        while self.running:
            time.sleep(self.watch_interval)

            current_mtime = self._get_config_mtime()
            if current_mtime > last_mtime:
                print("检测到配置文件变化，重新加载...")
                self.config.reload()
                last_mtime = current_mtime

    def _get_config_mtime(self):
        """获取配置文件修改时间"""
        config_file = self.config.config_file
        if os.path.exists(config_file):
            return os.path.getmtime(config_file)
        return 0

# 使用示例
config = ConfigManager()
watcher = ConfigWatcher(config, watch_interval=30)
watcher.start()

# 主程序运行...
# 当配置文件被修改时，配置会自动重新加载

# 程序结束时
watcher.stop()
```

### 配置加密

```python
from cryptography.fernet import Fernet

class SecureConfigManager(ConfigManager):
    """支持加密的配置管理器"""

    def __init__(self, encryption_key=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_key = encryption_key or self._generate_key()
        self.cipher = Fernet(self.encryption_key)

    def _generate_key(self):
        """生成加密密钥"""
        return Fernet.generate_key()

    def encrypt_value(self, value: str) -> str:
        """加密配置值"""
        if not value:
            return value
        encrypted = self.cipher.encrypt(value.encode())
        return encrypted.decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        """解密配置值"""
        if not encrypted_value:
            return encrypted_value
        decrypted = self.cipher.decrypt(encrypted_value.encode())
        return decrypted.decode()

    def save_secure(self, filepath: str, encrypt_fields=None):
        """保存加密配置"""
        encrypt_fields = encrypt_fields or ["database.password", "api.secret_key"]

        config_data = self.get_all()

        # 加密敏感字段
        for field in encrypt_fields:
            if self._get_nested(config_data, field):
                value = self._get_nested(config_data, field)
                encrypted = self.encrypt_value(value)
                self._set_nested(config_data, field, encrypted)

        # 保存到文件
        with open(filepath, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)

        print(f"加密配置已保存到: {filepath}")

# 使用示例
secure_config = SecureConfigManager(env="production")

# 设置敏感配置
secure_config.set("database.password", "my_secret_password")
secure_config.set("api.secret_key", "super_secret_key")

# 保存加密配置
secure_config.save_secure(
    "./configs/secure_production.yaml",
    encrypt_fields=["database.password", "api.secret_key", "llm.api_key"]
)

# 加载时自动解密
loaded_config = SecureConfigManager(
    encryption_key=secure_config.encryption_key,
    env="production"
)
password = loaded_config.get("database.password")  # 自动解密
```

### 配置模板

```python
class ConfigTemplate:
    """配置模板系统"""

    TEMPLATES = {
        "development": {
            "description": "开发环境配置",
            "settings": {
                "logging.level": "DEBUG",
                "database.host": "localhost",
                "api.debug": True,
                "memory.max_entries": 100
            }
        },
        "production": {
            "description": "生产环境配置",
            "settings": {
                "logging.level": "WARNING",
                "database.host": "db.cluster.example.com",
                "api.debug": False,
                "memory.max_entries": 10000
            }
        },
        "testing": {
            "description": "测试环境配置",
            "settings": {
                "logging.level": "INFO",
                "database.host": "localhost",
                "database.name": "test_db",
                "api.debug": False,
                "memory.max_entries": 1000
            }
        }
    }

    @classmethod
    def generate_config(cls, template_name, output_file=None):
        """生成配置模板"""
        if template_name not in cls.TEMPLATES:
            raise ValueError(f"未知模板: {template_name}")

        template = cls.TEMPLATES[template_name]
        config_data = {
            "app": {
                "name": "pm-mem",
                "env": template_name,
                "description": template["description"]
            }
        }

        # 应用模板设置
        for key, value in template["settings"].items():
            parts = key.split(".")
            current = config_data
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value

        # 输出到文件或返回数据
        if output_file:
            with open(output_file, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False)
            print(f"配置模板已生成: {output_file}")
            return output_file
        else:
            return config_data

# 使用示例
# 生成开发环境配置
ConfigTemplate.generate_config("development", "./configs/development.yaml")

# 生成生产环境配置
ConfigTemplate.generate_config("production", "./configs/production.yaml")

# 在代码中使用模板
config_data = ConfigTemplate.generate_config("testing")
config = ConfigManager()
config.update(config_data)
```

## 集成示例

### 与记忆系统集成

```python
from src.config.config_manager import ConfigManager
from src.memory.bank import MemoryBank
from src.memory.persistence import MemoryPersistence

class ConfiguredMemorySystem:
    """基于配置的记忆系统"""

    def __init__(self, config_path=None):
        # 加载配置
        self.config = ConfigManager()

        if config_path:
            self.config.load_from_file(config_path)

        # 初始化记忆库
        max_entries = self.config.get_int("memory.max_entries", 1000)
        self.bank = MemoryBank(max_entries=max_entries)

        # 初始化持久化
        persistence_file = self.config.get("memory.persistence.file", "./data/memory.json")
        self.persistence = MemoryPersistence(persistence_file)

        # 加载现有记忆
        self.bank = self.persistence.load(self.bank)

        # 配置日志
        self._setup_logging()

    def _setup_logging(self):
        """配置日志系统"""
        import logging

        log_level = self.config.get("logging.level", "INFO")
        log_file = self.config.get("logging.file")

        logging.basicConfig(
            level=getattr(logging, log_level),
            format=self.config.get("logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            handlers=self._create_log_handlers(log_file)
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"记忆系统已初始化，最大容量: {self.bank.max_entries}")

    def _create_log_handlers(self, log_file):
        """创建日志处理器"""
        import logging.handlers

        handlers = [logging.StreamHandler()]

        if log_file:
            max_size = self.config.get_int("logging.max_size", 10485760)  # 10MB
            backup_count = self.config.get_int("logging.backup_count", 5)

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count
            )
            handlers.append(file_handler)

        return handlers

    def auto_save(self):
        """自动保存（如果启用）"""
        auto_save = self.config.get_bool("memory.persistence.auto_save", True)
        save_interval = self.config.get_int("memory.persistence.save_interval", 300)

        if auto_save:
            import time
            while True:
                time.sleep(save_interval)
                self.persistence.save(self.bank)
                self.logger.debug(f"自动保存完成，当前条目数: {len(self.bank)}")

    def get_stats(self):
        """获取系统统计信息"""
        bank_stats = self.bank.get_statistics()
        file_info = self.persistence.get_file_info()

        return {
            "memory_bank": bank_stats,
            "storage_file": file_info,
            "config": {
                "max_entries": self.bank.max_entries,
                "auto_save": self.config.get_bool("memory.persistence.auto_save"),
                "save_interval": self.config.get_int("memory.persistence.save_interval")
            }
        }

# 使用示例
memory_system = ConfiguredMemorySystem()

# 添加记忆
memory_system.bank.add(entry)

# 获取统计
stats = memory_system.get_stats()
print(f"当前条目: {stats['memory_bank']['total_entries']}")
print(f"文件大小: {stats['storage_file']['file_size']} 字节")

# 启动自动保存（在后台线程）
import threading
save_thread = threading.Thread(target=memory_system.auto_save, daemon=True)
save_thread.start()
```

### Docker 集成

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# 复制配置文件
COPY configs/ /app/configs/
COPY .env.production /app/.env

# 复制应用代码
COPY src/ /app/src/
COPY requirements.txt /app/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV APP_ENV=production
ENV PYTHONPATH=/app

# 运行应用
CMD ["python", "-m", "src.main"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - PM_MEM_DATABASE_HOST=db
      - PM_MEM_DATABASE_PORT=5432
      - PM_MEM_DATABASE_NAME=pm_mem_prod
      - PM_MEM_DATABASE_USERNAME=postgres
      - PM_MEM_DATABASE_PASSWORD=${DB_PASSWORD}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - db

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=pm_mem_prod
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 最佳实践

### 1. 配置组织
- 按功能模块组织配置节
- 使用有意义的命名
- 保持配置层次清晰

### 2. 安全考虑
- 敏感信息使用环境变量
- 生产环境禁用调试模式
- 定期轮换加密密钥

### 3. 性能优化
- 避免频繁的配置重载
- 缓存常用配置值
- 使用配置默认值减少文件读取

### 4. 维护建议
- 提供配置示例文件
- 记录配置变更历史
- 定期验证配置有效性

## 故障排除

### 常见问题

#### 1. 配置未加载
```
症状：配置值为None或默认值
解决：
  1. 检查配置文件路径
  2. 验证文件权限
  3. 检查环境变量前缀
```

#### 2. 类型转换错误
```
症状：get_int() 返回字符串
解决：
  1. 检查配置文件中的值类型
  2. 使用正确的获取方法
  3. 添加配置验证
```

#### 3. 环境变量未生效
```
症状：环境变量值未被读取
解决：
  1. 检查变量名格式（PM_MEM_前缀）
  2. 确认环境变量已导出
  3. 重启应用进程
```

#### 4. 配置覆盖问题
```
症状：配置值被意外覆盖
解决：
  1. 检查配置加载顺序
  2. 避免重复设置
  3. 使用配置锁机制
```

### 调试工具

```python
# 配置调试工具
def debug_config(config_manager):
    """调试配置管理器"""
    print("=== 配置调试信息 ===")

    # 1. 显示所有配置源
    print("\n1. 配置源:")
    print(f"   配置文件: {config_manager.config_file}")
    print(f"   环境: {config_manager.env}")
    print(f"   已加载.env: {config_manager.env_loaded}")

    # 2. 显示配置层次
    print("\n2. 配置层次:")
    all_config = config_manager.get_all()
    for key, value in all_config.items():
        if isinstance(value, dict):
            print(f"   {key}:")
            for subkey, subvalue in value.items():
                print(f"     {subkey}: {subvalue}")
        else:
            print(f"   {key}: {value}")

    # 3. 显示环境变量映射
    print("\n3. 环境变量映射:")
    env_vars = {k: v for k, v in os.environ.items() if k.startswith("PM_MEM_")}
    for key, value in env_vars.items():
        config_key = key[8:].lower().replace("_", ".")
        print(f"   {key} -> {config_key}: {value}")

    # 4. 验证配置
    print("\n4. 配置验证:")
    is_valid, errors = config_manager.validate()
    if is_valid:
        print("   ✅ 配置验证通过")
    else:
        print("   ❌ 配置验证失败:")
        for error in errors:
            print(f"     - {error}")

# 使用示例
config = ConfigManager()
debug_config(config)
```

## API参考

### ConfigManager 方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `get(key, default=None)` | 获取配置值 | `Any` |
| `get_section(section)` | 获取配置节 | `Dict[str, Any]` |
| `get_all()` | 获取所有配置 | `Dict[str, Any]` |
| `get_int(key, default=0)` | 获取整数配置 | `int` |
| `get_float(key, default=0.0)` | 获取浮点数配置 | `float` |
| `get_bool(key, default=False)` | 获取布尔值配置 | `bool` |
| `get_list(key, default=None)` | 获取列表配置 | `List[Any]` |
| `get_dict(key, default=None)` | 获取字典配置 | `Dict[str, Any]` |
| `set(key, value)` | 设置配置值 | `None` |
| `update(config_dict)` | 批量更新配置 | `None` |
| `validate(schema=None)` | 验证配置 | `(bool, List[str])` |
| `save_to_file(filepath)` | 保存配置到文件 | `bool` |
| `load_from_file(filepath)` | 从文件加载配置 | `bool` |
| `reload()` | 重新加载配置 | `None` |

### 环境变量映射

环境变量到配置键的映射规则：
- 前缀：`PM_MEM_`
- 转换：`PM_MEM_LOGGING_LEVEL` → `logging.level`
- 示例：
  - `PM_MEM_DATABASE_HOST` → `database.host`
  - `PM_MEM_API_TIMEOUT` → `api.timeout`
  - `PM_MEM_MEMORY_MAX_ENTRIES` → `memory.max_entries`

---

*文档最后更新：2024-12-11*