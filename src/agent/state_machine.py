"""
状态机定义

实现ReMem的Think/Refine/Act状态机，符合MDP形式的状态机定义。
"""

from enum import Enum
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class Action(Enum):
    """ReMem动作枚举"""
    THINK = "think"
    REFINE = "refine"
    ACT = "act"


class State:
    """状态类，表示ReMem Agent的当前状态"""

    def __init__(
        self,
        task_input: str,
        memory_bank: Any,  # MemoryBank实例
        traces: List[str],
        iteration: int = 0,
    ):
        """
        初始化状态

        Args:
            task_input: 任务输入 x_t
            memory_bank: 记忆库实例
            traces: 历史推理轨迹
            iteration: 当前迭代次数
        """
        self.task_input = task_input
        self.memory_bank = memory_bank
        self.traces = traces.copy()  # 复制列表以避免修改原列表
        self.iteration = iteration

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "task_input": self.task_input,
            "memory_size": len(self.memory_bank),
            "traces_count": len(self.traces),
            "traces_preview": self.traces[-3:] if self.traces else [],  # 最近3条轨迹
            "iteration": self.iteration,
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"State(iteration={self.iteration}, traces={len(self.traces)}, memory={len(self.memory_bank)})"


class StateMachine:
    """ReMem状态机"""

    def __init__(self, max_iterations: int = 8):
        """
        初始化状态机

        Args:
            max_iterations: 最大迭代次数
        """
        self.max_iterations = max_iterations
        self.current_state: Optional[State] = None
        self.history: List[Dict[str, Any]] = []

    def initialize(self, task_input: str, memory_bank: Any) -> State:
        """
        初始化状态机

        Args:
            task_input: 任务输入
            memory_bank: 记忆库

        Returns:
            初始状态
        """
        self.current_state = State(task_input, memory_bank, [], iteration=0)
        self.history = [{"action": "initialize", "state": self.current_state.to_dict()}]
        logger.debug(f"状态机初始化: {self.current_state}")
        return self.current_state

    def transition(self, action: Action, **kwargs) -> State:
        """
        状态转移

        Args:
            action: 要执行的动作
            **kwargs: 动作参数

        Returns:
            新状态

        Raises:
            ValueError: 如果状态机未初始化或动作无效
        """
        if self.current_state is None:
            raise ValueError("状态机未初始化")

        if self.current_state.iteration >= self.max_iterations:
            logger.warning(f"达到最大迭代次数 {self.max_iterations}，强制转为ACT")
            action = Action.ACT

        # 创建新状态（递增迭代次数）
        new_state = State(
            task_input=self.current_state.task_input,
            memory_bank=self.current_state.memory_bank,
            traces=self.current_state.traces,
            iteration=self.current_state.iteration + 1,
        )

        # 记录转移
        transition_record = {
            "action": action.value,
            "from_iteration": self.current_state.iteration,
            "to_iteration": new_state.iteration,
            "kwargs": kwargs,
        }
        self.history.append(transition_record)

        # 更新当前状态
        self.current_state = new_state
        logger.debug(f"状态转移: {action.value} (迭代 {new_state.iteration})")

        return new_state

    def get_valid_actions(self) -> List[Action]:
        """
        获取当前有效动作

        Returns:
            有效动作列表
        """
        if self.current_state is None:
            return []

        # 所有动作始终有效
        return [Action.THINK, Action.REFINE, Action.ACT]

    def should_terminate(self) -> bool:
        """
        判断是否应该终止

        Returns:
            是否应该终止
        """
        if self.current_state is None:
            return True

        # 检查是否达到最大迭代次数
        if self.current_state.iteration >= self.max_iterations:
            return True

        # 检查最近的动作是否为ACT（如果历史中存在ACT动作，则终止）
        if self.history and len(self.history) > 1:
            last_action = self.history[-1].get("action")
            if last_action == Action.ACT.value:
                return True

        return False

    def get_history(self) -> List[Dict[str, Any]]:
        """获取状态转移历史"""
        return self.history.copy()

    def get_current_state(self) -> Optional[State]:
        """获取当前状态"""
        return self.current_state

    def reset(self) -> None:
        """重置状态机"""
        self.current_state = None
        self.history = []
        logger.debug("状态机已重置")