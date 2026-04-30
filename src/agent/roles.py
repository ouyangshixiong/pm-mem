"""Injectable roles for domain-neutral ReMem execution."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Type


class MemoryRole:
    """Role interface used by ReMemAgent prompts and storage policies."""

    role_id = "generic"
    role_name = "通用智能体"

    def __init__(self, prompt: str = "", roles_dir: str = "./roles"):
        self.prompt = prompt
        self.roles_dir = roles_dir

    def system_prompt(self) -> str:
        return self.prompt or "你是通用记忆演化智能体，依据任务和记忆完成分析、更新与输出。"

    def retrieval_policy(self, context) -> Dict[str, Any]:
        return {"k": None, "target_layers": context.metadata.get("target_layers")}

    def think_instructions(self, context) -> str:
        return "分析任务目标、相关记忆、潜在冲突和下一步策略。"

    def refine_instructions(self, context) -> str:
        return (
            "提取值得长期保存的事实、偏好、约束或冲突。"
            "不要直接写文件，只输出结构化 MemoryOperation。"
        )

    def act_instructions(self, context) -> str:
        return "给出可直接交付给用户的最终输出，必要时附带可沉淀的记忆更新。"

    def allowed_operations(self, context) -> List[str]:
        return [
            "add",
            "append",
            "replace",
            "delete",
            "merge",
            "relabel",
            "flag_conflict",
            "no_op",
        ]

    def memory_update_schema(self, context) -> Dict[str, Any]:
        return {
            "memory_operations": [
                {
                    "operation_type": "append",
                    "target": "memory.layer",
                    "content": "需要写入的记忆内容",
                    "metadata": {"layer_id": "目标层或由存储后端解释的目标"},
                }
            ]
        }

    def to_dict(self) -> Dict[str, str]:
        return {"role_id": self.role_id, "role_name": self.role_name}


class GenericRole(MemoryRole):
    role_id = "generic"
    role_name = "通用智能体"


class ProducerRole(MemoryRole):
    role_id = "producer"
    role_name = "制片人"

    def think_instructions(self, context) -> str:
        return "重点判断核心设定、题材定位、商业方向、锁定层和不可随意改写的规则。"

    def refine_instructions(self, context) -> str:
        return "只沉淀稳定设定、作品元数据、审核结论和需要用户确认的核心冲突。"


class ScreenwriterRole(MemoryRole):
    role_id = "screenwriter"
    role_name = "编剧"

    def retrieval_policy(self, context) -> Dict[str, Any]:
        return {
            "k": None,
            "target_layers": context.metadata.get(
                "target_layers",
                [
                    "core_setting",
                    "character_profile",
                    "plot_context",
                    "script_archive",
                ],
            ),
        }

    def think_instructions(self, context) -> str:
        return "重点分析人物动机、性格、对白口吻、情节因果和分集连续性。"

    def refine_instructions(self, context) -> str:
        return "从输出中提取新增人物事实、剧情事实、分集档案和需要标记的冲突。"

    def act_instructions(self, context) -> str:
        return "输出符合短剧节奏的剧本或创作结果，并保持人物、情节和对白一致。"


class StoryboardRole(MemoryRole):
    role_id = "storyboard"
    role_name = "分镜师"

    def retrieval_policy(self, context) -> Dict[str, Any]:
        return {
            "k": None,
            "target_layers": context.metadata.get(
                "target_layers",
                [
                    "core_setting",
                    "character_profile",
                    "plot_context",
                    "script_archive",
                    "storyboard_archive",
                ],
            ),
        }

    def think_instructions(self, context) -> str:
        return "重点分析场景、景别、镜头顺序、人物站位、道具和视觉连续性。"

    def refine_instructions(self, context) -> str:
        return "沉淀可复用视觉记忆、分镜档案、场景调度和视觉冲突。"

    def act_instructions(self, context) -> str:
        return "输出清晰可拍摄的分镜内容，包含镜头、画面、动作和视觉线索。"


class ConsistencyReviewerRole(MemoryRole):
    role_id = "consistency_reviewer"
    role_name = "一致性校验员"

    def think_instructions(self, context) -> str:
        return "重点检查设定、人物行为、时间线、剧情因果、剧本和分镜之间的冲突。"

    def refine_instructions(self, context) -> str:
        return "不要覆盖核心设定；发现冲突时输出 flag_conflict 或 no_op。"

    def allowed_operations(self, context) -> List[str]:
        return ["flag_conflict", "no_op", "append"]

    def act_instructions(self, context) -> str:
        return "输出冲突报告、风险等级、依据和修正建议。"


class RoleFactory:
    """Load built-in roles and optional prompts from ``roles/*.md``."""

    ROLE_CLASSES: Dict[str, Type[MemoryRole]] = {
        "generic": GenericRole,
        "通用智能体": GenericRole,
        "producer": ProducerRole,
        "制片人": ProducerRole,
        "screenwriter": ScreenwriterRole,
        "编剧": ScreenwriterRole,
        "storyboard": StoryboardRole,
        "storyboarder": StoryboardRole,
        "分镜师": StoryboardRole,
        "consistency_reviewer": ConsistencyReviewerRole,
        "consistency": ConsistencyReviewerRole,
        "一致性校验员": ConsistencyReviewerRole,
    }

    @classmethod
    def create(cls, role_id: Optional[str] = None, roles_dir: str = "./roles") -> MemoryRole:
        key = (role_id or "generic").strip()
        role_cls = cls.ROLE_CLASSES.get(key, GenericRole)
        prompt = cls._load_prompt(role_cls, key, roles_dir)
        return role_cls(prompt=prompt, roles_dir=roles_dir)

    @classmethod
    def _load_prompt(
        cls, role_cls: Type[MemoryRole], requested_id: str, roles_dir: str
    ) -> str:
        base = Path(roles_dir)
        candidates = [
            base / f"{requested_id}.md",
            base / f"{role_cls.role_name}.md",
            base / f"{role_cls.role_id}.md",
        ]
        for path in candidates:
            try:
                if path.is_file():
                    return path.read_text(encoding="utf-8").strip()
            except Exception:
                continue
        return ""
