# pm-mem: LLM长短记忆管理系统

基于ReMem（Self-Evolving Memory for LLM Agents）方法论实现的具备自演化记忆管理能力的LLM Agent系统。

## 项目概述

pm-mem实现了ReMem方法论的核心思想：让LLM Agent的记忆从静态的只追加结构升级为动态可编辑结构，支持记忆的动态编辑（删除、添加、合并、重标签）、运行时记忆库的主动优化、长短记忆的智能存储与检索。

## 核心特性

- **ReMem主循环**: 实现完整的Think/Refine/Act状态机，支持最大迭代次数限制和强制终止机制
- **动态记忆编辑**: 支持DELETE/ADD/MERGE/RELABEL四种原子操作，实现严格的Refine命令语法解析
- **LLM驱动的检索**: 基于DeepSeek API的文本相关性排序检索，不使用向量数据库和embedding技术
- **记忆库管理**: 实现MemoryEntry和MemoryBank类，支持序列化和持久化存储
- **配置化**: 支持YAML/JSON配置文件，提供默认配置和用户配置合并
- **完整测试**: 单元测试覆盖率 > 85%，集成测试覆盖所有用户场景

## 技术栈

- Python 3.10+
- DeepSeek API
- JSON文件存储
- pytest测试框架

## 技术约束

- 禁止使用向量数据库、embedding、reranking技术
- 禁止使用PyTorch、PaddlePaddle等深度学习框架
- 仅使用DeepSeek API，不引入其他LLM服务

## 项目结构

```
pm-mem/
├── src/                    # 源代码
│   ├── agent/             # ReMem Agent核心
│   ├── memory/            # 记忆管理
│   ├── llm/               # LLM集成
│   ├── config/            # 配置管理
│   └── utils/             # 工具函数
├── tests/                 # 测试
├── examples/              # 示例
├── configs/               # 配置文件
├── docs/                  # 文档
└── scripts/               # 脚本
```

## 快速开始

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd pm-mem

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置

1. 复制环境变量示例文件：
```bash
cp .env.example .env
```

2. 在`.env`文件中配置DeepSeek API密钥：
```
DEEPSEEK_API_KEY=your_api_key_here
```

3. 根据需要修改配置文件`configs/local.yaml`

### 基本用法

```python
from src.llm.deepseek_client import DeepSeekClient
from src.agent.remem_agent import ReMemAgent

# 初始化LLM客户端
llm_client = DeepSeekClient(api_key="your_api_key")

# 创建ReMem Agent
agent = ReMemAgent(llm_client)

# 运行任务
result = agent.run_task("如何配置nginx反向代理？")
print(result["action"])
```

## 开发指南

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成测试覆盖率报告
pytest --cov=src tests/
```

### 代码规范

项目遵循PEP 8规范，使用black进行代码格式化：

```bash
# 格式化代码
black src/ tests/

# 检查代码风格
flake8 src/ tests/
```

## 需求实现状态

### 核心功能（P0）
- [ ] REQ-001: ReMem主循环实现
- [ ] REQ-002: 记忆检索模块
- [ ] REQ-003: 记忆编辑模块

### 存储与持久化（P1）
- [ ] REQ-004: 记忆条目数据结构
- [ ] REQ-005: 记忆库管理
- [ ] REQ-006: 持久化存储

### LLM集成（P1）
- [ ] REQ-007: DeepSeek API集成
- [ ] REQ-008: 提示词模板系统

### 系统控制（P2）
- [ ] REQ-009: 配置管理系统
- [ ] REQ-010: 日志与监控

### 测试与质量（P2）
- [ ] REQ-011: 单元测试套件
- [ ] REQ-012: 集成测试套件

## 文档

- [API文档](docs/api.md)
- [使用指南](docs/usage.md)
- [架构设计](docs/architecture.md)

## 许可证

本项目基于MIT许可证发布，详见[LICENSE](LICENSE)文件。

## 贡献

欢迎提交Issue和Pull Request。请确保代码符合项目规范并通过所有测试。

## 致谢

本项目基于ReMem（Self-Evolving Memory for LLM Agents）方法论实现，感谢相关研究者的工作。