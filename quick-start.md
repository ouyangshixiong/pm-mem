# Quick Start

本文档提供 pm-mem 的最短启动路径。

## 1. 准备环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 配置模型

复制环境变量模板：

```bash
cp .env.example .env
```

至少配置一个可用模型：

```bash
DEEPSEEK_API_KEY=your_deepseek_key
KIMI_API_KEY=your_kimi_key
MIMO_API_KEY=your_mimo_key
```

短剧外部导入默认优先使用 `config.yaml` 中的本地 OpenAI Responses 兼容服务：

```yaml
local_llm:
  endpoint: "http://localhost:8317/v1/responses"
  model: "gpt-5.4"
  api_key: "your-api-key"
```

如果本地服务不可用，系统可使用 DeepSeek 备用通道。备用通道 API Key 可通过 `config.yaml` 或 `DEEPSEEK_API_KEY` 配置。

## 3. 启动 Web 管理页

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

浏览器访问：

```text
http://127.0.0.1:8000
```

## 4. 创建作品

1. 在首页点击“新增作品”。
2. 输入作品名称。
3. 进入作品管理页。
4. 编辑六层 Markdown 记忆。
5. 对已确认的核心层打开锁定开关。

作品默认保存在：

```text
works/{WORK_UUID}/
```

可通过环境变量修改保存目录：

```bash
export PM_MEM_WORKS_DIR=/path/to/works
```

## 5. 运行 CLI

```bash
python3 -m src.cli run --llm deepseek --task "给出一个标准的 git 提交流程"
python3 -m src.cli interactive --llm kimi
```

常用参数：

- `--llm`：`deepseek`、`kimi`、`mimo` 或 `mock`。
- `--persist`：通用 ReMem JSON 记忆文件路径，默认 `./data/memory.json`。
- `--max-iterations`：Think / Refine / Act 最大迭代次数。
- `--retrieval-k`：每轮检索返回的记忆数量。

## 6. 检索作品记忆

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

## 7. 导入外部作品

```bash
curl -X POST http://127.0.0.1:8000/api/import/external-work \
  -H 'Content-Type: application/json' \
  -d '{
    "source_system": "external-system",
    "external_work_id": "work-001",
    "work_name": "作品名称",
    "story": "故事梗概...",
    "script": "剧本正文...",
    "storyboard_script": "分镜脚本..."
  }'
```
