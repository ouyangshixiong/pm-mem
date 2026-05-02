# pm-mem

pm-mem 是一个面向长内容创作和智能体工作流的自演化记忆系统。它以 ReMem（Self-Evolving Memory for LLM Agents）方法论为核心，将 LLM 的记忆从“只追加的上下文记录”扩展为可检索、可编辑、可持久化、可审阅的长期记忆层。

项目当前提供两类能力：

- 通用 ReMem Agent：围绕 Think / Refine / Act 循环执行任务，并在运行中检索、更新和沉淀记忆。
- 短剧创作记忆管理：以六层 Markdown 文件维护作品元数据、核心设定、人物档案、情节脉络、剧本档案和分镜档案，并提供 Web 管理页、外部作品导入和 LLM 检索接口。

## Quick Start

首次使用请从 [quick-start.md](quick-start.md) 开始。该文档包含安装依赖、配置模型、启动 Web 管理页和运行 CLI 的最短路径。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

启动后访问：

```text
http://127.0.0.1:8000
```

## 技术背景

传统 LLM 应用通常依赖会话上下文、外部 RAG 或简单日志来保存历史信息。这类方案很容易遇到三个问题：

- 上下文窗口有限，旧信息会被截断或遗忘。
- 只追加的记忆会不断膨胀，重复、冲突和低价值信息难以及时处理。
- 业务知识与模型推理过程脱节，长期一致性依赖人工反复校对。

pm-mem 的设计目标是让记忆成为可维护的系统资产。Agent 在执行任务时会先检索相关记忆，再判断是否需要 Think（继续推理）、Refine（编辑记忆）或 Act（输出结果）。记忆编辑通过 DELETE、ADD、MERGE、RELABEL 等原子操作完成，使长期记忆可以随着任务反馈持续演化。

在短剧创作场景中，项目进一步把通用记忆机制映射为人类可读的 Markdown 分层记忆。创作者可以直接审阅、修改和锁定关键层，LLM 也可以在生成剧本、分镜或导入外部作品时读取这些稳定记忆。

## 核心架构

```text
用户任务 / 外部作品 / Web 操作
        |
        v
ReMem Agent
  - Think: 结合任务与记忆进行内部推理
  - Refine: 对记忆执行结构化编辑
  - Act: 输出结果并沉淀新记忆
        |
        +-- Memory Store
        |     - JSON 记忆库
        |     - Markdown 六层作品记忆
        |
        +-- LLM Client
        |     - DeepSeek
        |     - Kimi
        |     - Mimo
        |     - 本地 OpenAI Responses 兼容服务
        |
        +-- Role Prompts
              - 编剧
              - 制片人
              - 分镜师
              - 一致性校验员
```

### 主要模块

- `app.py`：FastAPI Web 管理页与 HTTP API。
- `workflow.py`：短剧创作工作流，负责按角色读取分层记忆并写回结果。
- `import_coordinator.py`：外部作品导入协调器，将故事、剧本和分镜素材整理为六层记忆。
- `memory_manager.py`：Markdown 作品目录、分层文件和锁定状态管理。
- `src/agent/`：ReMem Agent、角色和状态机。
- `src/memory/`：记忆条目、记忆库、编辑器、检索、持久化与存储后端。
- `src/llm/`：统一 LLM 接口及 DeepSeek、Kimi、Mimo、本地兼容客户端。
- `src/config/`：配置加载、环境变量覆盖和 API Key 管理。
- `roles/`：短剧工作流使用的角色提示词。

## 主要功能

### 自演化记忆 Agent

- Think / Refine / Act 状态循环。
- 基于 LLM 的文本相关性检索，不依赖向量数据库、embedding 或 reranking 服务。
- 支持记忆新增、删除、合并和重标签。
- 支持 JSON 文件持久化，适合轻量部署和版本审阅。
- 支持执行轨迹记录，便于回看一次任务如何读取、判断和更新记忆。

### 短剧分层记忆

每个作品独立保存在 `works/{WORK_UUID}/` 下，包含固定的六层 Markdown：

- `01_作品元数据层.md`
- `02_核心设定层.md`
- `03_人物档案层.md`
- `04_情节脉络层.md`
- `05_剧本档案层.md`
- `06_分镜档案层.md`

这些文件既是系统记忆，也是可人工审核的作品档案。Web 管理页支持创建作品、编辑分层内容、预览 Markdown、锁定关键层和删除作品。

### 外部作品导入

pm-mem 可接收外部系统整理出的故事、剧本和分镜文本，通过角色提示词和 LLM 生成六层 Markdown 记忆。导入接口会保留来源系统、外部作品 ID、来源 URL 和原始 payload，便于后续追溯。

### LLM 记忆检索

系统提供只读检索 API。它会把作品的 Markdown 记忆切成可追溯片段，交给 LLM 逐批判断相关性，并返回 top-k 证据；也可以基于证据生成回答。

## 操作方法

### 启动 Web 管理页

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

常用入口：

- 首页：`http://127.0.0.1:8000`
- 系统配置：`http://127.0.0.1:8000/settings`
- 作品接口：`GET /api/works`
- 外部导入：`POST /api/import/external-work`
- 作品检索：`POST /api/works/{work_id}/retrieve`
- ReMem 创作任务：`POST /api/works/{work_id}/remem-task`

### 创建并管理作品

1. 打开首页。
2. 点击“新增作品”，输入作品名称。
3. 进入作品管理页查看六层记忆。
4. 进入任一层编辑 Markdown 内容。
5. 根据需要打开锁定开关，保护已确认的核心设定。
6. 保存后内容会写回作品目录。

### 创作记忆写入约束

外部系统或智能体需要写入、更新、沉淀创作记忆时，必须使用 ReMem 任务接口：

```text
POST /api/works/{work_id}/remem-task
```

或使用外部作品导入接口：

```text
POST /api/import/external-work
```

不要直接调用层级 Markdown 写入接口，例如 `PUT /api/works/{work_id}/layers/{layer_id}` 或类似路径来做创作记忆写入。直接改层文件会绕开 ReMem Agent 的 Think / Refine / Act、LLM 检索、冲突判断和记忆演化轨迹，只适合作品管理页内部进行人工维护。

### 运行 CLI

```bash
python3 -m src.cli run --llm deepseek --task "给出一个标准的 git 提交流程"
python3 -m src.cli interactive --llm kimi
```

CLI 默认使用 `./data/memory.json` 作为通用 ReMem 记忆文件，可通过 `--persist` 指定其他路径。

### 调用检索 API

```bash
curl -X POST http://127.0.0.1:8000/api/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "work_name": "作品名称",
    "query": "当前主要人物和情节概要",
    "target_layers": ["character_profile", "plot_context"],
    "include_answer": true
  }'
```

### 调用外部作品导入 API

```bash
curl -X POST http://127.0.0.1:8000/api/import/external-work \
  -H 'Content-Type: application/json' \
  -d '{
    "source_system": "external-system",
    "external_work_id": "work-001",
    "work_name": "作品名称",
    "source_url": "",
    "story": "故事梗概...",
    "script": "剧本正文...",
    "storyboard_script": "分镜脚本..."
  }'
```

## 配置

根目录 `config.yaml` 是 Web 管理页和短剧工作流的主要配置文件：

```yaml
memory:
  works_dir: "./works"
  persistence_path: "./data/memory.json"

local_llm:
  endpoint: "http://localhost:8317/v1/responses"
  model: "gpt-5.4"
  api_key: "your-api-key"

deepseek_backup:
  endpoint: "https://api.deepseek.com/chat/completions"
  model: "deepseek-v4-pro"
```

常用环境变量：

- `PM_MEM_WORKS_DIR`：覆盖作品 Markdown 目录。
- `DEEPSEEK_API_KEY`：DeepSeek API Key。
- `KIMI_API_KEY`：Kimi API Key。
- `MIMO_API_KEY`：Mimo API Key。
- `LLM_TIMEOUT`：CLI LLM 请求超时时间。
- `LLM_MAX_RETRIES`：CLI LLM 自动重试次数。

## 技术依赖

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- OpenAI Python SDK
- Requests
- PyYAML
- python-dotenv
- structlog

LLM 接口采用 OpenAI 兼容风格，当前内置 DeepSeek、Kimi、Mimo 以及本地 OpenAI Responses 兼容服务。记忆检索由 LLM 完成，不需要向量数据库或额外 embedding 服务。

## 发布目录建议

对外发布时建议保留：

```text
app.py
workflow.py
import_coordinator.py
local_llm_client.py
memory_manager.py
role_manager.py
src/
roles/
configs/
config.yaml
requirements.txt
pyproject.toml
quick-start.md
README.md
```

运行后产生的 `data/`、`works/`、`logs/`、缓存目录和本地密钥文件不应提交到公开仓库。
