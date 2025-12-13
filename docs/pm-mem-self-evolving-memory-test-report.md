# 《pm-mem项目自演化（Self-Evolving Memory）功能测试报告》

**版本**：v1.0  
**日期**：2025-12-13  
**对象**：pm-mem 项目（目录 `/Users/ouyang/app/context-engineering-for-pm-mem/pm-mem`）

---

## 一、测试目的与方法

- 目标：验证 pm-mem 在真实 CLI 调用流程中，是否具备“自演化记忆”能力，即：
  - 能将历史任务的经验持久化到 `data/memory.json`；
  - 在后续相似任务中检索并利用这些记忆；
  - 在环境发生变化时，通过追加或调整记忆，让行为随之演化，而不是固定死在旧经验上。
- 方法：
  - 参考“python vs python3”示例，再额外设计两个随机场景，每个场景按照“两步场景 + 回归验证”的模式：
    1. 第一步：询问通用建议（无环境约束）。
    2. 第二步：加入新的环境约束或团队约定，要求“重新给出”答案。
    3. 第三步：用稍微改写（但同义）的任务再次提问，观察是否体现了对前两步记忆的利用和演化。
  - 所有任务通过 CLI 执行，命令形如：
    - `DEEPSEEK_MODEL=deepseek-chat python -m src.cli run --llm deepseek --task "..."`
  - 通过查看 `data/memory.json` 的新增条目，验证记忆的持久化与演化（末尾条目参考 `data/memory.json:455-500`）。

---

## 二、场景一：Git 提交流程与默认远程分支约定

### 1.1 测试设计

核心想法：  
先让 Agent 给出一个“标准 git 提交流程”，再引入团队约定“默认远程分支是 develop”，要求重新给命令。最后再问一次“标准流程”，看回答是否会“自动记得” develop 这件事，或者仍然停留在最初的通用答案上。

三步命令：

1. 第一次询问（无环境约束）  
   ```bash
   DEEPSEEK_MODEL=deepseek-chat \
   python -m src.cli run --llm deepseek \
     --task "给出一个标准的git提交流程命令"
   ```

2. 第二次询问（加入团队约定）  
   ```bash
   DEEPSEEK_MODEL=deepseek-chat \
   python -m src.cli run --llm deepseek \
     --task "团队约定默认远程分支是develop，请重新给出git提交流程命令，所有推送都推送到origin develop"
   ```

3. 第三次询问（回归到通用问法）  
   ```bash
   DEEPSEEK_MODEL=deepseek-chat \
   python -m src.cli run --llm deepseek \
     --task "再次给出一个标准的git提交流程命令"
   ```

### 1.2 实际输出

第一次：标准 git 提交流程：

```text
Act: 一个标准的 Git 提交流程通常包含以下三个核心命令：
1. `git add .` 或 `git add <file>` - 将工作区的更改添加到暂存区。
2. `git commit -m "提交信息"` - 将暂存区的内容提交到本地仓库，并附上描述。
3. `git push` - 将本地仓库的提交推送到远程仓库。
```

对应记忆条目写入 `data/memory.json`：

- `x`: `给出一个标准的git提交流程命令`
- `y`: 同上文本（含 `git push` 而未指定分支）  
  位置：`data/memory.json:455-460`

第二次：引入 develop 作为默认远程分支：

```text
Act: 根据团队约定（默认远程分支是develop），完整的 Git 提交流程命令如下：
1. `git add .` 或 `git add <具体文件>` - 将工作区的更改添加到暂存区。
2. `git commit -m "提交信息"` - 将暂存区的内容提交到本地仓库。
3. `git push -u origin develop` - 将本地提交推送到远程仓库的 `develop` 分支，并设置其为上游分支（后续在该本地分支可直接使用 `git push`）。
```

对应记忆条目：

- `x`: `团队约定默认远程分支是develop，请重新给出git提交流程命令，所有推送都推送到origin develop`
- `y`: 上述包含 `git push -u origin develop` 的完整流程  
  位置：`data/memory.json:462-468`

第三次：再次询问“标准 git 提交流程”：

```text
Act: 一个标准的 Git 提交流程包含以下三个核心命令：
1. `git add .` 或 `git add <file>` - 将工作区的更改添加到暂存区。
2. `git commit -m "提交信息"` - 将暂存区的内容提交到本地仓库，并附上描述。
3. `git push` - 将本地仓库的提交推送到远程仓库。
```

对应记忆条目：

- `x`: `再次给出一个标准的git提交流程命令`
- `y`: 回到了通用版的 `git push`，没有自动带上 `origin develop`  
  位置：`data/memory.json:471-476`

### 1.3 场景一结论

- 记忆持久化：
  - 三次调用都被写入 `data/memory.json`，ID 分别为：
    - `823b80b9-...`：第一次标准流程（`git push`）（`data/memory.json:455-460`）
    - `7df9c96e-...`：团队约定 develop（包含 `git push -u origin develop`）（`data/memory.json:462-468`）
    - `2da16a3f-...`：再次标准流程（仍为 `git push`）（`data/memory.json:471-476`）
- 自演化行为分析：
  - 对于带有团队约定的任务，Agent 成功生成了符合约定的命令，并将其持久化。
  - 但在第三次“通用问法”的任务中，Agent 没有把 develop 约定应用到“标准流程”的定义里，而是回到了最早那条记忆的风格。
  - 这说明当前记忆检索的语义局部性较强：会尊重“当前问题的具体表达”，而不会把某个记忆自动提升为“对所有相关问题都适用的硬约束”。
- 评价：
  - 在这个场景中，pm-mem 展现了对特定任务的记忆和再利用能力，但没有将新约定推广到更泛化的问题上，自演化程度相对局部。

---

## 三、场景二：Nginx 健康检查路径自适应（/site-name/health → /myapp/health）

### 2.1 测试设计

核心想法：  
围绕“在阿里云服务器上如何用 curl 检查 Node 服务健康接口”这个主题，先让 Agent 给出一个默认路径（如 `/site-name/health`），再告诉它“实际对外只暴露路径 `/myapp/health`”，要求重新给命令。最后再次问“在阿里云服务器上检查 Node 服务健康接口的 curl 命令”，看是否体现对新路径的适配或泛化。

三步命令：

1. 第一次询问（默认情况）  
   ```bash
   DEEPSEEK_MODEL=deepseek-chat \
   python -m src.cli run --llm deepseek \
     --task "在阿里云服务器上检查Node服务健康接口的curl命令"
   ```

2. 第二次询问（给出实际暴露路径 /myapp/health）  
   ```bash
   DEEPSEEK_MODEL=deepseek-chat \
   python -m src.cli run --llm deepseek \
     --task "实际对外只暴露了nginx路径 /myapp/health，请重新给出Node服务健康检查的curl命令"
   ```

3. 第三次询问（回归泛化问法）  
   ```bash
   DEEPSEEK_MODEL=deepseek-chat \
   python -m src.cli run --llm deepseek \
     --task "再次在阿里云服务器上检查Node服务健康接口的curl命令"
   ```

### 2.2 实际输出

第一次：默认健康检查路径：

```text
Act: 在阿里云服务器上检查Node服务健康接口，请使用以下curl命令：
`curl -I http://<服务器IP>/site-name/health`

说明：
1. 替换 `<服务器IP>` 为实际公网 IP 或域名；
2. `/site-name/health` 需根据 Nginx 的 location 规则调整；
3. 通过 80 端口 Nginx 反向代理访问后端 Node 服务（通常在 3000 端口）。
```

对应记忆条目：

- `x`: `在阿里云服务器上检查Node服务健康接口的curl命令`
- `y`: 包含 `curl -I http://<服务器IP>/site-name/health`  
  位置：`data/memory.json:479-484`

第二次：指定暴露路径 `/myapp/health`：

```text
Act: 使用命令 `curl -I http://<服务器IP或域名>/myapp/health` 来检查Node服务的健康状态。
请将 `<服务器IP或域名>` 替换为您的实际服务器公网IP地址或域名。
该命令通过Nginx反向代理访问后端服务的健康检查端点。
```

对应记忆条目：

- `x`: `实际对外只暴露了nginx路径 /myapp/health，请重新给出Node服务健康检查的curl命令`
- `y`: 使用 `/myapp/health` 的 curl 命令  
  位置：`data/memory.json:487-492`

第三次：再次询问阿里云健康检查命令：

```text
Think: 推理内容可能不够详细
Act: 在阿里云服务器上检查Node服务健康接口，请使用以下curl命令：
`curl -I http://<服务器IP或域名>/<路径>/health`

说明与操作指引：
1. 将 `<服务器IP或域名>` 替换为实际服务器公网IP或域名。
2. 将 `<路径>` 替换为 Nginx 为 Node 服务配置的反向代理路径（例如 `site-name` 或 `myapp`）。
3. 此命令通过服务器80端口的Nginx反向代理，访问后端Node服务（通常运行在3000端口）的健康检查端点，以绕过安全组对非标准端口的限制。
```

对应记忆条目：

- `x`: `再次在阿里云服务器上检查Node服务健康接口的curl命令`
- `y`: 使用泛化形式 `/<路径>/health`，并在说明中举例 `site-name` 和 `myapp`  
  位置：`data/memory.json:495-500`

### 2.3 场景二结论

- 记忆持久化：
  - 三条相关记忆顺序写入：
    - `0bbb1b6e-...`：默认 `/site-name/health`（`data/memory.json:479-484`）
    - `7891ca6a-...`：给出 `/myapp/health`（`data/memory.json:487-492`）
    - `a4290e67-...`：再次询问得到泛化 `<路径>` 模板（`data/memory.json:495-500`）
- 自演化行为分析：
  - 初始回答偏向具体路径 `/site-name/health`。
  - 在知道“仅暴露 `/myapp/health`”后，系统不仅给出正确的 `/myapp/health` 命令，还将此经验写入记忆。
  - 再次询问时，Agent 没有简单地“固定在某一条路径”，而是：
    - 总结出一个更通用的模板：`http://<服务器IP或域名>/<路径>/health`。
    - 在解释中同时举例 `site-name` 和 `myapp` 两种可能。
- 评价：
  - 与场景一相比，该场景中 pm-mem 展现出更明显的知识泛化能力：在多次交互后抽象出了“路径占位符 + 示例”的模式，符合自演化记忆对策略进行精炼的目标。

---

## 四、总体评价：自演化记忆能力分析

结合本次两大场景以及之前的 python/python3 场景，可以对 pm-mem 的 Self-Evolving Memory 能力作如下评价。

### 4.1 已验证的能力

1. 记忆持久化与多次会话共享：
   - 每次 `Act` 结果都会以 `MemoryEntry` 的形式写入 `MemoryBank`，并通过 `MemoryPersistence.save()` 持久化到 `data/memory.json`。
   - 后续 CLI 调用都会重新加载该文件，实现跨任务/跨命令的记忆共享。

2. 基于相关性的记忆检索与上下文利用：
   - `ReMemAgent.run_task` 在每一轮迭代中调用 `self.M.retrieve(...)` 检索相关记忆，并将检索结果格式化为 `retrieved_text` 注入提示词。
   - 在 python/python3 场景中，即便后续问题不再提到“本机只有 python3”，回答仍自动参考这一事实，说明记忆检索确实影响了行为。

3. 对特定情境的记忆更新与应用：
   - Git 场景中，对带有“develop 分支约定”的任务，系统能给出符合约定的命令，并在记忆中保留这一经验。
   - Nginx 场景中，在知道“仅暴露 `/myapp/health`”之后，系统给出了正确路径，并在下一次回答中将其作为候选示例写入说明。

4. 从多条经验中抽象更通用策略：
   - Nginx 场景的第三次回答不再执着于单一路径，而是给出了“`/<路径>/health` + 示例路径”的抽象形式，体现出一定的知识泛化与策略精炼能力。

### 4.2 局限与不足

1. 局部更新而非全局约束：
   - Git 场景说明：团队对 develop 作为默认分支的约定，只在带有该上下文的任务中被使用；当问题回到“标准的 git 提交流程”这一更泛化表达时，系统仍给出原始的 `git push`。
   - 这体现了当前记忆检索的语义局部性：它会尊重当前任务的具体表达，而不会自动将某条记忆提升为对所有相关问题都生效的硬规则。

2. 旧记忆不会被自动删除或直接重写：
   - 无论是 python → python3、develop 分支、还是 `/site-name/health` → `/myapp/health`，系统采用的都是“追加新记忆 + 检索偏好”的方式：
     - 旧条目仍然存在于 `data/memory.json` 中。
     - 是否使用旧条目，取决于检索排序和 prompt 上下文。
   - 当前 CLI 流程中，Refine 动作（DELETE/MERGE/RELABEL）在这些任务里没有被显式触发。

3. “规则提升”的自动化程度有限：
   - 在 python/python3 和 Nginx 场景中，出现了良好的泛化（如默认使用 python3、抽象 `<路径>`）。
   - 但在 Git 场景中，“develop 是默认分支”这一事实并未被自动提升为规则级记忆，说明在“将局部事实升级为全局约束”方面还有提升空间。

### 4.3 综合结论

- 在当前版本下，pm-mem 已具备实用级别的自演化记忆能力：
  - 能把用户明确给出的环境/约束事实写入记忆，并在相似任务中持续利用。
  - 能在部分领域从多次交互中抽象出更泛化的回答模板。
- 这种自演化主要表现为：
  - 通过追加新记忆、改变检索排序和回答模板来演化行为；
  - 而不是依赖全局规则引擎或直接覆盖旧记忆。

---

## 五、优化建议

1. 引入显式的 Refine 触发模式：
   - 在用户给出“事实型”前缀时（如 `fact:`、或“团队统一约定”、“强制要求”等明显信号），优先触发 Refine 流程，对相关记忆执行：
     - MERGE：将多条类似经验合并为一条更抽象的规则型记忆。
     - RELABEL：对规则型记忆打上高优先级标签。
     - 必要时 DELETE：删除已明显错误或过期的记忆。

2. 强化“规则记忆”与“场景记忆”的区分：
   - 在 `MemoryEntry.tag` 中对“规则型知识”和“具体事件”做区分，例如：
     - `rule:git-default-branch` vs `task`。
   - 检索时对 `rule:*` 类记忆赋予更高权重，使其在相关问题中更容易被采用。

3. 为关键领域定制 Refine 模式：
   - 针对常见运维/开发主题（Python 环境、Git 流程、Nginx 反代等），设计专门的 Refine 提示模板，引导 LLM 在产生新答案时自动检查并更新对应记忆。

---

## 六、小结

通过两组新场景测试，可以明确：

- pm-mem 的自演化记忆机制在实践中是有效工作的：
  - 每一次 CLI 调用的“经验”都被记录在案，可在 `data/memory.json` 中回溯。
  - 后续任务会利用这些经验，产生与历史一致且更贴近当前环境的回答。
- 同时，自演化表现为：
  - 对环境约束的持续记忆与再利用。
  - 对部分场景的抽象与泛化。
- 其局限主要在于：
  - 规则级事实不会自动全局生效。
  - 旧记忆仍然保留，尚需更主动的 Refine 策略来清理和整合。

整体来看，在典型用例（python/python3、Git develop 分支约定、Nginx 健康检查路径）上，pm-mem 已展现出符合 ReMem 思想的 Self-Evolving Memory 行为，并为在更大规模场景上持续演化打下了基础。

