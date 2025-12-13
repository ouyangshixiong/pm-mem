# DeepSeek API 功能测试报告（pm-mem）

## 概览
- 目标：验证 pm-mem 使用 DeepSeek API 的端到端能力，包括检索（JSON 输出）、推理（Think）与行动（Act）三段闭环，以及上下文长度与解析鲁棒性
- 模型：`deepseek-chat`（通过 `DEEPSEEK_MODEL` 强制），上下文长度预置为 `64,000 tokens`
- 测试用例（3条）：
  1. 检查服务器健康接口并给出验证命令
  2. 提供 Nginx 反向代理 `location` 配置示例
  3. 提供 Git 变基冲突解决步骤与命令
- 结论：三条用例稳定完成；检索 JSON 成功解析；Think 给予背景分析；Act 提供可执行结果；上下文预算与解析器增强显著提升鲁棒性

## 环境与配置
- `.env`（示例）：
  - `DEEPSEEK_API_KEY=<你的真实密钥>`
  - `DEEPSEEK_API_BASE=https://api.deepseek.com`（可选）
  - `DEEPSEEK_MODEL=deepseek-chat`（用于强制模型）
- 运行方式：
  - 单次任务：`python -m src.cli run --llm deepseek --task "<任务文本>"`
  - 推荐参数：`LLM_TIMEOUT=90 LLM_MAX_RETRIES=5`，提升稳定性
- 关键代码位置：
  - CLI 与 dotenv 加载：`src/cli.py:7`
  - 模型上下文配置：`src/llm/deepseek_models.py`
  - DeepSeek 客户端上下文预算与日志：`src/llm/deepseek_client.py:96-110, 111, 132-149, 169-176`
  - 检索提示与解析增强：`src/memory/bank.py:405-418, 438-455, 581-635`

## 测试用例 1：健康接口验证命令
- 命令：  
  `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "检查服务器健康接口并给出验证命令"`
- 原始响应概述：
  - 检索 JSON：返回前 k 条最相关条目，解释包含健康检查命令与阿里云场景上下文
  - Think：分析安全组限制与反代路径映射（80→3000），明确下一步
  - Act：输出 `curl -I http://<服务器IP>/site-name/health`
- 结果与评价：
  - 相关性：高（命令与场景完全匹配）
  - 可操作性：强（占位符替换即用）
  - 鲁棒性：检索 JSON 成功解析，原始响应日志完整打印

## 测试用例 2：Nginx 反向代理 location 配置示例
- 命令：  
  `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "提供反向代理location配置示例"`
- 原始响应概述：
  - 检索 JSON：定位到多条“反向代理配置”相关记忆
  - Think：给出场景与路径映射策略
  - Act：输出完整 `nginx` 配置片段（`server`/`location` 与 `proxy_pass`），包含常用请求头、超时与 WebSocket 注释，并附部署与 reload 步骤
- 结果与评价：
  - 相关性：高（直击“location 配置示例”）
  - 可操作性：强（片段可直接落地，步骤清晰）
  - 鲁棒性：JSON 解析与日志可观测，长度受控

## 测试用例 3：Git 变基冲突解决步骤与命令
- 命令：  
  `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "提供 Git 变基冲突解决步骤与命令"`
- 原始响应概述：
  - 检索 JSON：选取包含 rebase 命令与冲突处理的条目
  - Think：将通用冲突解决流程对齐至“变基语境”
  - Act：输出完整流程与命令（`git rebase <base>`→冲突识别→编辑冲突标记→`git add`→`git rebase --continue`/`--abort`），强调“变基重写历史”的协作风险
- 结果与评价：
  - 相关性：高（覆盖 rebase 与冲突解决）
  - 可操作性：强（流程线性清晰）
  - 稳定性：良好（日志与解析均正常）

## 上下文预算与解析策略
- 模型上下文长度（预置）：`deepseek-chat=64,000 tokens`  
  - 客户端在调用前估算输入 tokens，预留生成余量（chat≈1024），必要时截断提示并调整 `max_tokens`
  - 检索阶段根据 `llm.get_model_info()` 的上下文长度裁剪提示，优先保留任务与规则，压缩记忆段落
- JSON 解析器增强：
  - 仅请求前 k 项，降低生成长度
  - 支持代码块围栏与从全文提取 `results` 数组重构 JSON
  - 失败时采用回退检索，避免流程中断

## 调试与可观测性
- 打印 DeepSeek 原始响应：`src/llm/deepseek_client.py:111`  
  打印检索解析原始字符串：`src/memory/bank.py:534`  
  便于定位格式错误、未闭合 JSON 或超长截断问题

## 结论
- 三条用例验证了 pm-mem 结合 DeepSeek API 的端到端能力：
  - 检索—推理—行动闭环稳定
  - Act 输出具备生产可操作性（命令清单、配置片段、流程步骤）
  - 上下文预算与解析器增强使响应更稳健，原始日志便于排错
- 建议：
  - 如模型/接口支持，尝试 `response_format={"type":"json_object"}`，进一步降低 JSON 解析风险
  - 记录与利用 `response.usage`（prompt/completion tokens）替代启发式估算，做更精确的预算策略
  - 对超长记忆列表采用“分批评估+合并”策略，确保极端规模下也能稳定解析

## 复现命令（附）
- 健康检查命令：  
  `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "检查服务器健康接口并给出验证命令"`
- 反向代理配置示例：  
  `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "提供反向代理location配置示例"`
- Git 变基冲突解决：  
  `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "提供 Git 变基冲突解决步骤与命令"`

