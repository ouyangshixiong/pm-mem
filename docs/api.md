# pm-mem API 文档

## 概述

本文档描述 pm-mem 库的主要类和 API 接口。

## 核心类

### 1. ReMemAgent (`src.agent.remem_agent`)

ReMem Agent 的主类，实现完整的 Think/Refine/Act 状态机。

#### 初始化

```python
from src.agent.remem_agent import ReMemAgent
from src.llm.mock_llm import MockLLM

llm = MockLLM()
agent = ReMemAgent(
    llm=llm,
    memory_bank=None,  # 可选，MemoryBank实例
    persist_path="./data/memory.json",
    max_iterations=8,
    retrieval_k=5,
)
```

**参数**：
- `llm` (LLMInterface): LLM 接口实例
- `memory_bank` (MemoryBank, optional): 记忆库实例，如为 None 则创建新实例
- `persist_path` (str): 持久化文件路径
- `max_iterations` (int): 最大迭代次数
- `retrieval_k` (int): 检索返回的最相关记忆数量

#### 主要方法

##### `run_task(task_input: str) -> Dict[str, Any]`

运行单步任务。

```python
result = agent.run_task("如何配置nginx反向代理？")
```

**返回**：
- `action` (str): 最终动作/答案
- `traces` (List[str]): 执行轨迹
- `memory_size` (int): 任务后的记忆数量
- `iterations` (int): 实际迭代次数
- `retrieved_count` (int): 检索到的相关记忆数量
- `status` (str): 状态（completed/forced/max_iterations_exceeded）

##### `get_statistics() -> Dict[str, Any]`

获取 Agent 统计信息。

##### `save_memory() -> bool`

保存记忆库到文件。

##### `load_memory() -> bool`

从文件加载记忆库。

### 2. MemoryBank (`src.memory.bank`)

记忆库管理类。

#### 初始化

```python
from src.memory.bank import MemoryBank

bank = MemoryBank(max_entries=1000)
```

#### 主要方法

##### `add(entry: MemoryEntry) -> None`

添加记忆条目。

##### `delete(indices: List[int]) -> None`

删除指定索引的记忆条目。

##### `merge(idx1: int, idx2: int) -> None`

合并两个记忆条目。

##### `relabel(idx: int, new_tag: str) -> None`

重新标记记忆条目。

##### `retrieve(llm, query: str, k: int = 5) -> List[MemoryEntry]`

基于 LLM 的文本相关性检索。

##### `get_statistics() -> Dict[str, Any]`

获取记忆库统计信息。

### 3. MemoryEntry (`src.memory.entry`)

记忆条目数据结构。

#### 初始化

```python
from src.memory.entry import MemoryEntry

entry = MemoryEntry(
    x="任务输入",
    y="智能体输出",
    feedback="环境反馈",
    tag="标签",
    timestamp=None,  # 可选，datetime实例
    id=None,  # 可选，UUID字符串
)
```

#### 主要方法

##### `to_text() -> str`

生成标准化文本表示。

##### `to_dict() -> Dict[str, Any]`

转换为字典表示，用于序列化。

##### `@classmethod from_dict(data: Dict[str, Any]) -> MemoryEntry`

从字典创建 MemoryEntry 实例。

### 4. RefineEditor (`src.memory.editor`)

记忆编辑模块。

#### 静态方法

##### `parse_command(cmd: str) -> Dict[str, Any]`

解析 Refine 命令字符串。

```python
from src.memory.editor import RefineEditor

delta = RefineEditor.parse_command("DELETE 1,3; ADD{新内容}; MERGE 0&2")
# delta = {"delete": [1,3], "add": ["新内容"], "merge": [(0,2)], "relabel": []}
```

##### `validate_command(cmd: str) -> Tuple[bool, str]`

验证 Refine 命令语法是否合法。

##### `format_command(delete, add, merge, relabel) -> str`

格式化命令字典为 Refine 命令字符串。

### 5. LLM 接口 (`src.llm`)

#### LLMInterface (`src.llm.llm_interface`)

抽象接口，定义所有 LLM 实现必须提供的方法。

##### 主要方法

- `call(prompt: str, **kwargs) -> str`: 调用 LLM 生成文本
- `get_model_info() -> Dict[str, Any]`: 获取模型信息

#### DeepSeekClient (`src.llm.deepseek_client`)

DeepSeek API 客户端。

```python
from src.llm.deepseek_client import DeepSeekClient

# 从环境变量创建
client = DeepSeekClient.from_env()

# 或直接创建
client = DeepSeekClient(
    api_key="your_api_key",
    api_base="https://api.deepseek.com",
    model_name="deepseek-chat",
)
```

#### MockLLM (`src.llm.mock_llm`)

模拟 LLM，用于测试和开发。

```python
from src.llm.mock_llm import MockLLM

llm = MockLLM(
    responses={"关键词": "响应"},
    default_response="默认响应",
)
```

### 6. 配置管理 (`src.config.config_manager`)

#### ConfigManager

```python
from src.config.config_manager import get_config_manager, get_config

# 获取配置管理器
config_manager = get_config_manager(config_path="./configs/local.yaml")

# 获取配置值
model_name = config_manager.get("llm.model_name")
# 或使用快捷函数
model_name = get_config("llm.model_name", "deepseek-chat")
```

### 7. 工具函数 (`src.utils`)

#### 日志设置 (`src.utils.logger`)

```python
from src.utils.logger import setup_logger

logger = setup_logger(
    name="pm-mem",
    level="INFO",
    log_file="./logs/pm-mem.log",
)
```

#### 验证器 (`src.utils.validators`)

```python
from src.utils.validators import validate_task_input, validate_refine_command

# 验证任务输入
valid, msg = validate_task_input("任务内容")

# 验证Refine命令
valid, msg = validate_refine_command("DELETE 1,3")
```

## 使用示例

### 基本使用

```python
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.llm.mock_llm import MockLLM
from src.agent.remem_agent import ReMemAgent
from src.memory.entry import MemoryEntry

# 1. 创建LLM
llm = MockLLM()

# 2. 创建Agent
agent = ReMemAgent(llm=llm)

# 3. 添加初始记忆
agent.M.add(MemoryEntry(
    x="如何学习Python？",
    y="从基础语法开始，然后学习常用库，最后做项目实践",
    feedback="学习路径有效",
    tag="learning",
))

# 4. 运行任务
result = agent.run_task("Python有哪些学习资源？")
print(result["action"])
```

### 使用真实 DeepSeek API

```python
import os
from src.llm.deepseek_client import DeepSeekClient
from src.agent.remem_agent import ReMemAgent

# 设置API密钥（建议通过环境变量）
os.environ["DEEPSEEK_API_KEY"] = "your_api_key"

# 创建DeepSeek客户端
llm = DeepSeekClient.from_env()

# 创建Agent
agent = ReMemAgent(llm=llm)

# 运行任务
result = agent.run_task("解释一下机器学习的基本概念")
```

### 自定义配置

```python
from src.config.config_manager import get_config_manager

# 创建配置管理器
config_manager = get_config_manager("./configs/my-config.yaml")

# 设置自定义配置
config_manager.set("llm.model_name", "deepseek-coder")
config_manager.set("agent.max_iterations", 10)

# 保存配置
config_manager.save()
```

## 错误处理

### 异常类型

1. **配置错误**：配置文件格式错误或缺少必需配置
2. **API 错误**：LLM API 调用失败
3. **验证错误**：输入或命令格式无效
4. **持久化错误**：文件读写失败

### 错误处理示例

```python
from src.llm.deepseek_client import DeepSeekClient
from src.agent.remem_agent import ReMemAgent
import logging

logging.basicConfig(level=logging.INFO)

try:
    llm = DeepSeekClient.from_env()
    agent = ReMemAgent(llm=llm)

    result = agent.run_task("测试任务")

    if result["status"] == "max_iterations_exceeded":
        print("警告: 达到最大迭代次数")

except ValueError as e:
    print(f"配置错误: {e}")
except Exception as e:
    print(f"运行时错误: {e}")
```

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest tests/ --cov=src
```

### 编写测试

```python
# tests/unit/test_example.py
import pytest
from src.memory.entry import MemoryEntry

def test_memory_entry():
    entry = MemoryEntry("任务", "输出", "反馈", "标签")
    assert entry.x == "任务"
    assert entry.y == "输出"
    assert entry.feedback == "反馈"
    assert entry.tag == "标签"
```

## 扩展开发

### 添加新的 LLM 提供商

1. 实现 `LLMInterface` 接口
2. 在 `src/llm/` 目录下创建新文件
3. 更新配置文件支持新提供商

### 添加新的记忆编辑操作

1. 在 `RefineEditor` 中添加解析逻辑
2. 在 `MemoryBank` 中实现操作逻辑
3. 更新验证器和测试

### 自定义提示词模板

```python
from src.agent.prompts import get_prompt_system

prompt_system = get_prompt_system()
prompt_system.register_template(
    name="custom_think",
    template="自定义Think模板: {task_input}\n{retrieved_memories}",
    version="1.0.0",
)
```