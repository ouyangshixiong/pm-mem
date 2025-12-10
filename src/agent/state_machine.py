"""
状态机定义

实现ReMem的Think/Refine/Act状态机，符合MDP形式的状态机定义。
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
import logging
import random
import time

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
        self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "task_input": self.task_input,
            "memory_size": len(self.memory_bank),
            "traces_count": len(self.traces),
            "traces_preview": self.traces[-3:] if self.traces else [],  # 最近3条轨迹
            "iteration": self.iteration,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"State(iteration={self.iteration}, traces={len(self.traces)}, memory={len(self.memory_bank)})"


class MDPModel:
    """MDP模型，管理状态转移概率和奖励函数"""

    def __init__(self):
        """初始化MDP模型"""
        # 状态转移概率表：state -> action -> next_state -> probability
        self.transition_probs: Dict[str, Dict[str, Dict[str, float]]] = {}

        # 奖励函数：state -> action -> reward
        self.reward_function: Dict[str, Dict[str, float]] = {}

        # 默认配置
        self._initialize_defaults()

    def _initialize_defaults(self):
        """初始化默认的转移概率和奖励"""
        # 默认转移概率：倾向于Think -> Refine -> Act的序列
        self.transition_probs = {
            "start": {
                "think": {"think": 0.7, "refine": 0.2, "act": 0.1},
                "refine": {"think": 0.3, "refine": 0.5, "act": 0.2},
                "act": {"act": 1.0}  # Act是终止动作
            }
        }

        # 默认奖励：鼓励有效的状态转移
        self.reward_function = {
            "start": {
                "think": 0.1,    # Think获得基础奖励
                "refine": 0.2,   # Refine获得较高奖励
                "act": 1.0       # Act获得最高奖励
            }
        }

    def get_transition_prob(self, state: str, action: str, next_state: str) -> float:
        """
        获取状态转移概率

        Args:
            state: 当前状态
            action: 执行的动作
            next_state: 下一个状态

        Returns:
            转移概率
        """
        try:
            return self.transition_probs.get(state, {}).get(action, {}).get(next_state, 0.0)
        except KeyError:
            return 0.0

    def get_reward(self, state: str, action: str) -> float:
        """
        获取动作奖励

        Args:
            state: 当前状态
            action: 执行的动作

        Returns:
            奖励值
        """
        try:
            return self.reward_function.get(state, {}).get(action, 0.0)
        except KeyError:
            return 0.0

    def update_from_experience(self, state: str, action: str, next_state: str, reward: float):
        """
        根据经验更新MDP模型

        Args:
            state: 当前状态
            action: 执行的动作
            next_state: 下一个状态
            reward: 获得的奖励
        """
        # 简化实现：更新转移概率
        if state not in self.transition_probs:
            self.transition_probs[state] = {}
        if action not in self.transition_probs[state]:
            self.transition_probs[state][action] = {}

        # 增加该转移的概率
        current_prob = self.transition_probs[state][action].get(next_state, 0.0)
        self.transition_probs[state][action][next_state] = current_prob + 0.1

        # 归一化
        total = sum(self.transition_probs[state][action].values())
        if total > 0:
            for ns in self.transition_probs[state][action]:
                self.transition_probs[state][action][ns] /= total

        # 更新奖励函数
        if state not in self.reward_function:
            self.reward_function[state] = {}
        self.reward_function[state][action] = reward


class StateMachine:
    """ReMem状态机"""

    def __init__(self, max_iterations: int = 8, use_mdp: bool = True):
        """
        初始化状态机

        Args:
            max_iterations: 最大迭代次数
            use_mdp: 是否使用MDP模型
        """
        self.max_iterations = max_iterations
        self.current_state: Optional[State] = None
        self.history: List[Dict[str, Any]] = []
        self.use_mdp = use_mdp
        self.start_time: Optional[float] = None
        self.total_transitions = 0

        if use_mdp:
            self.mdp_model = MDPModel()
        else:
            self.mdp_model = None

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
        self.start_time = time.time()
        self.total_transitions = 0
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

        # 检查是否应该终止
        if self.should_terminate():
            logger.warning("状态机已终止，无法进行状态转移")
            raise ValueError("状态机已终止")

        # 检查是否达到最大迭代次数（下一次转移会使iteration达到max_iterations）
        if self.current_state.iteration >= self.max_iterations - 1:
            logger.warning(f"即将达到最大迭代次数 {self.max_iterations}，强制转为ACT")
            action = Action.ACT

        # 验证动作有效性
        valid_actions = self.get_valid_actions()
        if action not in valid_actions:
            logger.warning(f"无效动作: {action}，有效动作: {valid_actions}")
            # 回退到默认动作
            if Action.ACT in valid_actions:
                action = Action.ACT
            else:
                action = valid_actions[0] if valid_actions else Action.THINK

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
            "timestamp": time.time(),
        }

        # 如果使用MDP模型，计算奖励
        if self.use_mdp and self.mdp_model:
            state_key = f"iteration_{self.current_state.iteration}"
            reward = self.mdp_model.get_reward(state_key, action.value)
            transition_record["reward"] = reward
            logger.debug(f"状态转移奖励: {reward}")

        self.history.append(transition_record)
        self.total_transitions += 1

        # 更新当前状态
        previous_state = self.current_state
        self.current_state = new_state
        logger.debug(f"状态转移: {action.value} (迭代 {new_state.iteration})")

        # 如果使用MDP模型，更新经验
        if self.use_mdp and self.mdp_model:
            prev_state_key = f"iteration_{previous_state.iteration}"
            next_state_key = f"iteration_{new_state.iteration}"
            reward = transition_record.get("reward", 0.0)
            self.mdp_model.update_from_experience(prev_state_key, action.value, next_state_key, reward)

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

    def get_action_with_mdp(self) -> Action:
        """
        使用MDP模型选择动作

        Returns:
            选择的动作
        """
        if not self.use_mdp or self.mdp_model is None:
            # 回退到随机选择
            return random.choice(list(Action))

        if self.current_state is None:
            return random.choice(list(Action))

        state_key = f"iteration_{self.current_state.iteration}"
        valid_actions = self.get_valid_actions()

        # 简化实现：基于奖励选择动作
        best_action = valid_actions[0]
        best_reward = -float('inf')

        for action in valid_actions:
            reward = self.mdp_model.get_reward(state_key, action.value)
            if reward > best_reward:
                best_reward = reward
                best_action = action

        logger.debug(f"MDP选择动作: {best_action.value}, 奖励: {best_reward}")
        return best_action

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
            logger.info(f"达到最大迭代次数: {self.max_iterations}")
            return True

        # 检查最近的动作是否为ACT（如果历史中存在ACT动作，则终止）
        if self.history and len(self.history) > 1:
            last_action = self.history[-1].get("action")
            if last_action == Action.ACT.value:
                logger.info("检测到ACT动作，状态机终止")
                return True

        # 检查是否超时（30秒超时）
        if self.start_time and (time.time() - self.start_time) > 30:
            logger.warning("状态机超时（30秒）")
            return True

        # 检查是否陷入循环（最近5次状态相同）
        if len(self.history) >= 5:
            recent_actions = [h.get("action") for h in self.history[-5:]]
            if len(set(recent_actions)) == 1:  # 所有动作相同
                logger.warning(f"检测到循环动作: {recent_actions[0]}")
                return True

        return False

    def get_progress(self) -> Dict[str, Any]:
        """
        获取状态机进度信息

        Returns:
            进度信息字典
        """
        if self.current_state is None:
            return {"initialized": False}

        progress_percentage = min(100, (self.current_state.iteration / self.max_iterations) * 100)

        return {
            "initialized": True,
            "current_iteration": self.current_state.iteration,
            "max_iterations": self.max_iterations,
            "progress_percentage": progress_percentage,
            "total_transitions": self.total_transitions,
            "traces_count": len(self.current_state.traces),
            "memory_size": len(self.current_state.memory_bank),
            "elapsed_time": time.time() - self.start_time if self.start_time else 0,
        }

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
        self.start_time = None
        self.total_transitions = 0
        logger.debug("状态机已重置")

    def update_mdp_from_experience(self, state: str, action: str, next_state: str, reward: float):
        """
        根据经验更新MDP模型

        Args:
            state: 状态标识
            action: 执行的动作
            next_state: 下一个状态
            reward: 获得的奖励
        """
        if self.use_mdp and self.mdp_model:
            self.mdp_model.update_from_experience(state, action, next_state, reward)
            logger.debug(f"MDP模型更新: {state} -> {action} -> {next_state}, 奖励: {reward}")

    def get_mdp_stats(self) -> Dict[str, Any]:
        """
        获取MDP模型统计信息

        Returns:
            MDP统计信息字典
        """
        if not self.use_mdp or self.mdp_model is None:
            return {"enabled": False}

        return {
            "enabled": True,
            "states_count": len(self.mdp_model.transition_probs),
            "transitions_count": sum(
                len(actions) for actions in self.mdp_model.transition_probs.values()
            ),
            "rewards_count": len(self.mdp_model.reward_function),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取状态机统计信息

        Returns:
            统计信息字典
        """
        mdp_stats = self.get_mdp_stats()
        progress = self.get_progress()

        return {
            "progress": progress,
            "mdp": mdp_stats,
            "total_history_entries": len(self.history),
            "current_state": self.current_state.to_dict() if self.current_state else None,
            "config": {
                "max_iterations": self.max_iterations,
                "use_mdp": self.use_mdp,
            }
        }
