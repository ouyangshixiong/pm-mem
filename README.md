# pm-mem: LLM长短记忆管理系统

基于ReMem（Self-Evolving Memory for LLM Agents）方法论实现的具备自演化记忆管理能力的LLM Agent系统。

## 项目概述

pm-mem实现了ReMem方法论的核心思想：让LLM Agent的记忆从静态的只追加结构升级为动态可编辑结构，支持记忆的动态编辑（删除、添加、合并、重标签）、运行时记忆库的主动优化、长短记忆的智能存储与检索。

## 核心特性

- **ReMem主循环**: 实现完整的Think/Refine/Act状态机，支持最大迭代次数限制和强制终止机制
- **动态记忆编辑**: 支持DELETE/ADD/MERGE/RELABEL四种原子操作，实现严格的Refine命令语法解析
- **多LLM支持**: 统一OpenAI兼容接口，支持DeepSeek、Kimi、Mimo三种LLM提供商
- **LLM驱动的检索**: 基于LLM API的文本相关性排序检索，不使用向量数据库和embedding技术
- **记忆库管理**: 实现MemoryEntry和MemoryBank类，支持序列化和持久化存储
- **异步与流式**: 支持同步、异步、流式三种调用模式，自动重试机制
- **配置化**: 支持环境变量配置，提供多提供商API密钥管理
- **完整测试**: 100%测试通过率，支持多模型验证

## 技术栈

- Python 3.10+
- LLM APIs: DeepSeek / Kimi / Mimo (OpenAI兼容接口)
- JSON文件存储
- pytest测试框架
- OpenAI Python SDK (v1.12+)

## 技术约束

- 禁止使用向量数据库、embedding、reranking技术
- 禁止使用PyTorch、PaddlePaddle等深度学习框架
- 统一使用OpenAI兼容接口，确保代码可移植性

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

2. 在`.env`文件中配置LLM API密钥（至少配置一个）：
```bash
# DeepSeek (必需/可选)
DEEPSEEK_API_KEY=your_deepseek_key_here

# Kimi (可选)
KIMI_API_KEY=your_kimi_key_here
KIMI_API_BASE=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2-0905-preview

# Mimo (可选)
MIMO_API_KEY=your_mimo_key_here
MIMO_API_BASE=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2-flash
```

3. 根据需要修改配置文件`configs/local.yaml`

### 基本用法

#### 方式1: 使用 CLI（推荐）

```bash
# 使用 DeepSeek
python src/cli.py --llm deepseek --task "如何配置nginx反向代理？"

# 使用 Kimi
python src/cli.py --llm kimi --task "给出一个标准的git提交流程命令"

# 使用 Mimo
python src/cli.py --llm mimo --task "检查当前项目的python运行环境"
```

#### 方式2: 使用 Python API

```python
from src.llm.deepseek_client import DeepSeekClient
from src.llm.kimi_client import KimiClient
from src.agent.remem_agent import ReMemAgent

# 选择 LLM 提供商
llm_client = DeepSeekClient(api_key="your_api_key")
# 或 llm_client = KimiClient(api_key="your_kimi_key")
# 或 llm_client = MimoClient(api_key="your_mimo_key")

# 创建 ReMem Agent
agent = ReMemAgent(llm_client)

# 运行任务
result = agent.run_task("如何配置nginx反向代理？")
print(result["action"])
```

#### 方式3: 使用 LLM 工厂

```python
from src.llm.llm_factory import LLMFactory

# 通过工厂创建客户端
factory = LLMFactory()
llm_client = factory.create("kimi", environment="production")

# 或从环境变量自动配置
from src.llm.kimi_client_enhanced import EnhancedKimiClient
llm_client = EnhancedKimiClient.from_env()
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

## 支持的 LLM 提供商

| 提供商 | 模型 | 上下文窗口 | 状态 | CLI 参数 |
|--------|------|------------|------|----------|
| DeepSeek | deepseek-reasoner | 64K | ✅ 已验证 | `--llm deepseek` |
| Kimi | kimi-k2-0905-preview | 128K | ✅ 已验证 | `--llm kimi` |
| Mimo | mimo-v2-flash | 32K | ✅ 已验证 | `--llm mimo` |
| Mock | mock-llm | N/A | ✅ 开发测试 | `--llm mock` |

### 测试验证

所有 LLM 提供商都通过了相同的测试套件：

- **Git 工作流测试**: 3/3 ✅
- **Nginx 健康检查测试**: 3/3 ✅
- **Python 环境测试**: 3/3 ✅

详细测试报告：
- [Kimi 测试报告](docs/pm-mem-self-evolving-memory-test-report-kimi.md)
- [Mimo 测试报告](docs/pm-mem-self-evolving-memory-test-report-mimo.md)

## 功能特性

### LLM 客户端功能

- ✅ **同步调用**: 基础 API 调用
- ✅ **异步调用**: `async_call()` 支持并发
- ✅ **流式响应**: `stream_call()` 实时输出
- ✅ **自动重试**: 指数退避策略（最大 3 次）
- ✅ **超时控制**: 可配置超时时间
- ✅ **错误处理**: 完善的异常分类
- ✅ **统计追踪**: Token 消耗和延迟统计

### 记忆系统功能

- ✅ **动态编辑**: DELETE/ADD/MERGE/RELABEL 操作
- ✅ **智能检索**: LLM 驱动的相关性排序
- ✅ **持久化**: JSON 文件存储
- ✅ **备份机制**: 自动备份和恢复
- ✅ **记忆去重**: 防止重复条目

## 需求实现状态

### 核心功能（P0）✅
- [x] REQ-001: ReMem主循环实现
- [x] REQ-002: 记忆检索模块
- [x] REQ-003: 记忆编辑模块

### 存储与持久化（P1）✅
- [x] REQ-004: 记忆条目数据结构
- [x] REQ-005: 记忆库管理
- [x] REQ-006: 持久化存储

### LLM集成（P1）✅
- [x] REQ-007: DeepSeek API集成
- [x] REQ-008: Kimi API集成
- [x] REQ-009: Mimo API集成
- [x] REQ-010: 提示词模板系统

### 系统控制（P2）✅
- [x] REQ-011: 配置管理系统
- [x] REQ-012: 日志与监控

### 测试与质量（P2）✅
- [x] REQ-013: 单元测试套件
- [x] REQ-014: 集成测试套件
- [x] REQ-015: 多模型验证

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