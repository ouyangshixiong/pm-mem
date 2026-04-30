"""
Short-drama workflow adapter.

This module keeps the existing LLM clients reusable while routing all short
drama memory reads and writes through memory_manager.py.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import memory_manager
from src.agent.remem_agent import ReMemAgent
from src.agent.roles import RoleFactory
from src.memory.schema import TaskContext
from src.memory.stores import MarkdownLayerMemoryStore, MarkdownTraceStore


DEFAULT_PROMPT_LAYERS = [
    "work_metadata",
    "core_setting",
    "character_profile",
    "plot_context",
    "script_archive",
    "storyboard_archive",
]


class ShortDramaWorkflow:
    """LLM-driven workflow for short-drama writing with Markdown memory."""

    def __init__(
        self,
        llm: Callable[[str], str],
        roles_dir: str = "./roles",
        default_layers: Optional[List[str]] = None,
    ):
        self.llm = llm
        self.roles_dir = Path(roles_dir)
        self.default_layers = default_layers or DEFAULT_PROMPT_LAYERS
        memory_manager.init_work_space()
        self.agent = ReMemAgent(
            llm=llm,
            memory_store=MarkdownLayerMemoryStore(),
            trace_store=MarkdownTraceStore(),
        )

    def create_work(self, work_name: str) -> str:
        return memory_manager.create_work(work_name)

    def build_prompt(
        self,
        work_id: str,
        task: str,
        role_name: str = "编剧",
        layer_id_list: Optional[List[str]] = None,
    ) -> str:
        layers = layer_id_list or self.default_layers
        memory_context = memory_manager.get_layer_content_for_prompt(work_id, layers)
        role_prompt = self._load_role_prompt(role_name)
        return f"""# 短剧创作任务

## 当前角色
{role_name}

## 角色能力定义
{role_prompt}

## 分层记忆
{memory_context}

## 用户任务
{task}

## 输出要求
1. 先完成用户任务所需的创作、校验或分镜内容。
2. 如果产生了需要沉淀的设定、人物、情节、剧本或分镜记忆，请在答案末尾追加一个 JSON 代码块。
3. JSON 格式固定为：
```json
{{
  "memory_updates": [
    {{"layer_id": "script_archive", "mode": "append", "content": "需要写入记忆层的Markdown正文"}}
  ]
}}
```
4. 可用 layer_id 为：work_metadata, core_setting, character_profile, plot_context, script_archive, storyboard_archive。
5. 不要改写已锁定设定；需要冲突处理时，优先指出冲突并给出修正建议。
"""

    def run_step(
        self,
        work_id: str,
        task: str,
        role_name: str = "编剧",
        layer_id_list: Optional[List[str]] = None,
        update_memory: bool = True,
        task_type: str = "generic_workflow_step",
    ) -> Dict[str, Any]:
        layers = layer_id_list or self.default_layers
        role = RoleFactory.create(role_name, roles_dir=str(self.roles_dir))
        context = TaskContext(
            task_type=task_type,
            source="short_drama_workflow",
            role_id=role.role_id,
            metadata={
                "work_id": work_id,
                "target_layers": layers,
                "update_memory": update_memory,
            },
        )
        result = self.agent.run_task(task, role=role, context=context)
        output = result["action_output"]
        return {
            "work_id": work_id,
            "role_name": role_name,
            "prompt": "",
            "output": output,
            "memory_updated": result.get("memory_updated", False),
            "remem_result": result,
        }

    def create_script_episode(self, work_id: str, episode_task: str) -> Dict[str, Any]:
        return self.run_step(
            work_id=work_id,
            task=episode_task,
            role_name="编剧",
            task_type="script_generation",
            layer_id_list=[
                "work_metadata",
                "core_setting",
                "character_profile",
                "plot_context",
                "script_archive",
            ],
        )

    def create_storyboard(self, work_id: str, storyboard_task: str) -> Dict[str, Any]:
        return self.run_step(
            work_id=work_id,
            task=storyboard_task,
            role_name="分镜师",
            task_type="storyboard_generation",
            layer_id_list=[
                "core_setting",
                "character_profile",
                "plot_context",
                "script_archive",
                "storyboard_archive",
            ],
        )

    def consistency_check(self, work_id: str, check_task: str) -> Dict[str, Any]:
        return self.run_step(
            work_id=work_id,
            task=check_task,
            role_name="一致性校验员",
            layer_id_list=DEFAULT_PROMPT_LAYERS,
            update_memory=False,
            task_type="consistency_check",
        )

    def lock_layer(self, work_id: str, layer_id: str, locked: bool = True) -> bool:
        return memory_manager.toggle_layer_lock(work_id, layer_id, locked)

    def _load_role_prompt(self, role_name: str) -> str:
        exact_path = self.roles_dir / f"{role_name}.md"
        if exact_path.exists():
            return exact_path.read_text(encoding="utf-8").strip()

        default_path = self.roles_dir / "编剧.md"
        if default_path.exists():
            return default_path.read_text(encoding="utf-8").strip()

        return "你是短剧创作智能体，严格依据分层记忆完成任务，并维护角色、情节和场景一致性。"
