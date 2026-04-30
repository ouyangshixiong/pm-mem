# 短剧创作系统使用说明

## 1. 启动 Web 记忆管理页

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问 `http://127.0.0.1:8000`。系统无登录、无鉴权，打开即可管理全部作品和记忆层。

## 2. Markdown 记忆目录

默认目录为 `works/`，可在根目录 `config.yaml` 中修改：

```yaml
memory:
  works_dir: "./works"
```

也可以用环境变量覆盖：

```bash
export PM_MEM_WORKS_DIR=/path/to/works
```

每个作品独立存放在 `works/{WORK_UUID}/`，包含 `.work_config.yaml` 和 6 个固定分层 Markdown 文件：

- `01_作品元数据层.md`
- `02_核心设定层.md`
- `03_人物档案层.md`
- `04_情节脉络层.md`
- `05_剧本档案层.md`
- `06_分镜档案层.md`

## 3. Web 操作流程

1. 首页点击“新增作品”，输入作品名称。
2. 点击“进入管理”，查看作品 6 个分层记忆。
3. 点击任一分层“编辑”，在左侧 textarea 修改 Markdown，右侧实时预览。
4. 打开“锁定”开关后，该分层只允许 `制片人` 或 `用户手动修改` 写入。
5. 点击“保存修改”，内容会写回对应 Markdown 文件。

## 4. 角色 prompt 配置

角色 prompt 存放在 `roles/`：

- `roles/编剧.md`
- `roles/制片人.md`
- `roles/分镜师.md`
- `roles/一致性校验员.md`

修改这些文件后，`workflow.py` 会在每次构建 prompt 时重新读取，无需重启创作流程。

## 5. 短剧工作流示例

```python
from src.llm.mock_llm import MockLLM
from workflow import ShortDramaWorkflow

llm = MockLLM(default_response="Act: 第一集开场完成")
workflow = ShortDramaWorkflow(llm)

work_id = workflow.create_work("都市逆袭短剧")
workflow.lock_layer(work_id, "core_setting", True)

result = workflow.create_script_episode(
    work_id,
    "写第1集开场，要求突出女主被误解后的反击动机。",
)
print(result["output"])
```

工作流会通过 `get_layer_content_for_prompt` 注入分层记忆正文，并通过 `update_memory_from_llm_output` 将 LLM 输出中的结构化记忆更新写回 Markdown。

## 6. LLM 本地记忆检索 API

pm-mem 提供只读的类 RAG 检索接口。它不使用向量库或 embedding，而是把作品的 Markdown 记忆层切成可追溯片段，交给 LLM 逐批判断相关性，再返回 top-k 证据；可选再基于证据生成答案。

按作品 ID 检索：

```bash
curl -X POST http://localhost:8000/api/works/{work_id}/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "职场见闻 当前主要人物和情节概要",
    "target_layers": ["core_setting", "character_profile", "plot_context"],
    "top_k": 6,
    "include_answer": true
  }'
```

按作品名检索：

```bash
curl -X POST http://localhost:8000/api/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "work_name": "职场见闻",
    "query": "当前主要人物和情节概要",
    "target_layers": ["character_profile", "plot_context"],
    "include_answer": true
  }'
```

常用字段：

- `query`：必填，检索问题。
- `target_layers`：可选，默认按角色策略选择层；编剧默认读取核心设定、人物档案、情节脉络、剧本档案。
- `top_k`：返回证据片段数量，默认 5。
- `include_answer`：是否基于检索片段生成最终回答，默认 true。
- `include_content`：是否返回证据正文，默认 true。

该接口不会写入或演化记忆。检索必须由 LLM 完成；如果 LLM 不可用、返回非 JSON 或评分字段无效，接口会直接返回错误。`/api/works/{work_id}/remem-task` 使用同一套 LLM 检索；如只是查询，还应传入 `"update_memory": false`。

## 7. 测试与验收

当前项目所在 Python 环境会自动加载外部 pytest 插件时，可能受非本项目依赖影响。建议运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

本次验收结果：`305 passed`。
