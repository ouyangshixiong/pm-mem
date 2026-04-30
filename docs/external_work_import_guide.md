# 外部作品导入 pm-mem 记忆操作文档

本文档给 AI 智能体使用。目标是把任意外部创作系统中的故事、剧本和分镜剧本导入 pm-mem，由 pm-mem 生成六层 Markdown 记忆，并让用户能在 Web 管理页面查看、审核和修改。

外部系统在本流程中是黑盒。pm-mem 不关心外部系统的技术栈、数据库、页面路由或内部实现，只接收外部智能体已经读取好的文本内容。

## 1. 前提

pm-mem 项目路径：

```bash
/Users/ouyang/app/pm-mem
```

pm-mem Web 服务已启动：

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

pm-mem Web 页面：

```text
http://localhost:8000
```

## 2. 职责边界

外部智能体负责：

- 打开或访问外部创作系统。
- 读取某部作品的故事、剧本和分镜剧本。
- 提取作品名称、外部作品 ID、来源 URL 等基础信息。
- 调用 pm-mem 的导入接口。

pm-mem 负责：

- 接收标准化导入请求。
- 读取 `roles/*.md` 中配置好的角色 prompt。
- 由多个分层记忆智能体携带角色 prompt 调用 local proxy OpenAI Responses 兼容模型，对六层 Markdown 记忆进行处理和提炼；必要时自动使用 DeepSeek 备用通道。
- 按作品物理隔离写入 `works/{PM_MEM_WORK_UUID}/`。
- 在 Web 管理页展示这些记忆，供用户审核和修改。

## 3. 标准导入接口

接口：

```text
POST http://localhost:8000/api/import/external-work
```

请求体：

```json
{
  "source_system": "外部创作系统名称",
  "external_work_id": "外部作品ID",
  "work_name": "作品名称",
  "source_url": "外部作品页面URL，可为空",
  "story": "外部系统读取到的故事内容",
  "script": "外部系统读取到的剧本内容",
  "storyboard_script": "外部系统读取到的分镜剧本内容",
  "images": [
    "https://example.local/page-1.png",
    "/absolute/path/to/local-page-2.png"
  ],
  "raw_payload": {
    "optional": "可选，保留外部系统原始结构化数据"
  },
  "dry_run": false
}
```

字段说明：

- `source_system`：外部来源名称，用于追溯和去重。
- `external_work_id`：外部作品 ID，用于重复导入时定位同一作品。
- `work_name`：导入到 pm-mem 后显示的作品名称。
- `source_url`：外部作品地址，可为空。
- `story`：故事正文。
- `script`：剧本正文。
- `storyboard_script`：分镜剧本正文。
- `images`：可选，随 local proxy LLM 请求附加的图片 URL 或本地图片路径；本地路径会自动转换为 base64 data URL。
- `raw_payload`：可选，原始结构化数据，方便以后追溯。
- `dry_run`：`true` 表示只返回六层草稿，不写入 Markdown；`false` 表示写入 pm-mem。

## 4. 导入模型配置

默认导入流程固定调用 local proxy OpenAI Responses 兼容接口；如果 local proxy 请求失败或返回空文本，则自动使用 DeepSeek `chat/completions` 作为备用通道。两路都失败时，接口直接返回错误信息，不写入作品记忆，也不会保留确定性草稿。

```yaml
local_llm:
  endpoint: "http://localhost:8317/v1/responses"
  model: "gpt-5.4"
  api_key: "your-api-key-1"
  timeout: 60
  stream: true

deepseek_backup:
  endpoint: "https://api.deepseek.com/chat/completions"
  model: "deepseek-v4-pro"
  api_key: ""  # 推荐通过 DEEPSEEK_API_KEY 或 PM_MEM_DEEPSEEK_API_KEY 配置
  timeout: 120
  thinking_enabled: true
  reasoning_effort: "high"

import_llm:
  max_prompt_chars: 24000
```

等价调用形态：

```bash
curl -N http://localhost:8317/v1/responses \
  -H "Authorization: Bearer your-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.4",
    "input": [
      {
        "role": "user",
        "content": [
          {"type": "input_text", "text": "角色 prompt + 导入素材 + 目标记忆层规则"}
        ]
      }
    ],
    "stream": true
  }'
```

pm-mem 会优先从流式事件里的 `response.output_text.done` 取完整文本，再兜底读取 `response.output_item.done`。这是为了避开部分 Responses 服务在最终 `response.completed` 包里返回 `response.output: []` 的问题。

DeepSeek 备用通道等价调用形态：

```bash
curl https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${DEEPSEEK_API_KEY}" \
  -d '{
        "model": "deepseek-v4-pro",
        "messages": [
          {"role": "system", "content": "你是 pm-mem 外部作品导入的备用大模型。请严格遵守用户提示，只输出可直接写入目标记忆层的 Markdown 正文。"},
          {"role": "user", "content": "角色 prompt + 导入素材 + 目标记忆层规则"}
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "stream": false
      }'
```

## 5. 调用示例

```bash
curl -X POST http://localhost:8000/api/import/external-work \
  -H "Content-Type: application/json" \
  -d '{
    "source_system": "外部创作系统",
    "external_work_id": "143",
    "work_name": "职场见闻第一集",
    "source_url": "http://example.local/works/143",
    "story": "新人林夏入职第一天，发现直属领导把功劳占为己有。",
    "script": "第1场 办公室 日。林夏：这份方案是我昨晚做的。",
    "storyboard_script": "镜头1：开放办公区全景。镜头2：林夏攥紧文件夹。",
    "dry_run": false
  }'
```

成功响应会包含：

```json
{
  "success": true,
  "dry_run": false,
  "created": true,
  "work_id": "pm-mem生成的UUID",
  "work_name": "职场见闻第一集",
  "source_system": "外部创作系统",
  "external_work_id": "143",
  "layers": {
    "work_metadata": "...",
    "core_setting": "...",
    "character_profile": "...",
    "plot_context": "...",
    "script_archive": "...",
    "storyboard_archive": "..."
  },
  "review": "...",
  "web_url": "/work/pm-mem生成的UUID"
}
```

## 6. 多智能体分层写入逻辑

pm-mem 导入接口内部会调用多个分层记忆智能体：

- `作品元数据导入智能体`：携带 `制片人` prompt，生成 `01_作品元数据层.md`。
- `核心设定整理智能体`：携带 `制片人` prompt，生成 `02_核心设定层.md`。
- `人物档案整理智能体`：携带 `编剧` prompt，生成 `03_人物档案层.md`。
- `情节脉络整理智能体`：携带 `编剧` prompt，生成 `04_情节脉络层.md`。
- `剧本档案归档智能体`：携带 `编剧` prompt，生成 `05_剧本档案层.md`。
- `分镜档案归档智能体`：携带 `分镜师` prompt，生成 `06_分镜档案层.md`。
- `导入一致性校验智能体`：携带 `一致性校验员` prompt，检查故事、剧本、分镜剧本是否齐全，并返回检查结果。

每层写入 Markdown 时会在 front matter 中记录处理元数据，包括 `processed_by_role_name`、`role_prompt_hash`、`llm_processed`、`llm_model`、`llm_endpoint` 和 `llm_error`。

导入后，用户可以在 Web 管理页继续审核、修改和锁定各层。

## 7. 六层记忆内容规则

### 01_作品元数据层.md

写入：

- 作品名称
- 来源系统
- 外部作品 ID
- 来源 URL
- 导入时间
- 导入方式
- 原始字段摘要

### 02_核心设定层.md

写入：

- 题材
- 世界观
- 职场/生活/情感等背景
- 核心冲突
- 风格基调
- 必须保持一致的设定

### 03_人物档案层.md

写入：

- 角色姓名
- 身份/岗位
- 性格
- 目标
- 关系
- 口吻和行为习惯
- 已出现的重要事实

### 04_情节脉络层.md

写入：

- 故事起点
- 关键事件
- 因果关系
- 冲突升级
- 结尾钩子
- 时间线和场景连续性

### 05_剧本档案层.md

写入：

- 分场
- 场景
- 人物行动
- 对白
- 旁白
- 已成型剧情文本

### 06_分镜档案层.md

写入：

- 镜头/漫画格编号
- 景别
- 画面描述
- 人物位置
- 表情动作
- 对白气泡
- 场景道具
- 视觉风格提示

## 8. 预览模式

如果外部智能体想先检查分层草稿，不写入文件，把 `dry_run` 设置为 `true`：

```bash
curl -X POST http://localhost:8000/api/import/external-work \
  -H "Content-Type: application/json" \
  -d '{
    "source_system": "外部创作系统",
    "external_work_id": "143",
    "work_name": "职场见闻第一集",
    "story": "故事内容",
    "script": "剧本内容",
    "storyboard_script": "分镜剧本内容",
    "dry_run": true
  }'
```

此时接口返回 `layers` 草稿，但不会创建 pm-mem 作品，也不会写入 `works/`。

## 9. 重复导入和多作品导入

重复导入同一作品时，pm-mem 会依据：

- `source_system`
- `external_work_id`

查找已导入作品。

如果已存在，则更新已有作品的六层内容；如果不存在，则创建新作品。外部智能体不要自己修改 `works_index.yaml`，也不要自己创建作品目录。

多作品导入时，外部智能体按作品列表循环调用接口即可。

## 10. 验收步骤

导入完成后，在 pm-mem 项目根目录执行：

```bash
python - <<'PY'
import memory_manager

for work in memory_manager.list_works():
    print(work["work_name"], work["work_id"], work["update_time"])
PY
```

然后打开：

```text
http://localhost:8000
```

验收标准：

1. 首页能看到导入作品。
2. 进入作品详情后能看到 6 个分层记忆。
3. `01_作品元数据层.md` 中包含来源系统、外部作品 ID 和来源 URL。
4. 故事、人物、情节、剧本、分镜内容分别落入对应层。
5. 再次导入同一 `source_system + external_work_id` 时，不创建重复作品，而是更新已有作品。
6. 作品详情页能看到角色 Prompt 配置、导入模型配置，以及每层的处理角色和模型处理状态。

## 11. 注意事项

1. 外部系统是黑盒，pm-mem 不依赖外部系统内部接口。
2. 外部智能体必须先完成读取，再调用 pm-mem 标准导入接口。
3. 不要手动修改 Markdown front matter。
4. 用户最终在 Web 管理页审核和修改导入结果。
5. 如果导入内容为空，pm-mem 会保留待补充提示，便于人工继续编辑。
