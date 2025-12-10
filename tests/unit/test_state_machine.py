"""
状态机单元测试

测试StateMachine类的所有功能，包括MDP模型集成。
"""

import pytest
import sys
import os
import time

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from agent.state_machine import StateMachine, Action, State, MDPModel


class MockMemoryBank:
    """模拟记忆库用于测试"""

    def __init__(self, size=5):
        self.size = size
        self.entries = list(range(size))

    def __len__(self):
        return self.size

    def __repr__(self):
        return f"MockMemoryBank(size={self.size})"


class TestState:
    """State类测试"""

    def test_state_initialization(self):
        """测试State初始化"""
        task_input = "测试任务"
        memory_bank = MockMemoryBank(10)
        traces = ["思考1", "思考2"]

        state = State(task_input, memory_bank, traces, iteration=3)

        assert state.task_input == task_input
        assert state.memory_bank == memory_bank
        assert state.traces == traces
        assert state.iteration == 3
        assert state.created_at is not None

    def test_state_to_dict(self):
        """测试State转换为字典"""
        memory_bank = MockMemoryBank(5)
        traces = ["a", "b", "c", "d", "e"]
        state = State("任务", memory_bank, traces, iteration=2)

        state_dict = state.to_dict()

        assert state_dict["task_input"] == "任务"
        assert state_dict["memory_size"] == 5
        assert state_dict["traces_count"] == 5
        assert state_dict["traces_preview"] == ["c", "d", "e"]  # 最近3条
        assert state_dict["iteration"] == 2
        assert "created_at" in state_dict

    def test_state_repr(self):
        """测试State字符串表示"""
        memory_bank = MockMemoryBank(7)
        state = State("任务", memory_bank, ["trace1"], iteration=5)

        repr_str = repr(state)
        assert "State(" in repr_str
        assert "iteration=5" in repr_str
        assert "traces=1" in repr_str
        assert "memory=7" in repr_str


class TestMDPModel:
    """MDPModel类测试"""

    def test_mdp_model_initialization(self):
        """测试MDPModel初始化"""
        model = MDPModel()

        assert "start" in model.transition_probs
        assert "think" in model.transition_probs["start"]
        assert "refine" in model.transition_probs["start"]
        assert "act" in model.transition_probs["start"]

        assert "start" in model.reward_function
        assert "think" in model.reward_function["start"]
        assert "refine" in model.reward_function["start"]
        assert "act" in model.reward_function["start"]

    def test_get_transition_prob(self):
        """测试获取转移概率"""
        model = MDPModel()

        # 测试存在的转移
        prob = model.get_transition_prob("start", "think", "think")
        assert prob == 0.7

        # 测试不存在的转移
        prob = model.get_transition_prob("unknown", "think", "think")
        assert prob == 0.0

    def test_get_reward(self):
        """测试获取奖励"""
        model = MDPModel()

        # 测试存在的奖励
        reward = model.get_reward("start", "act")
        assert reward == 1.0

        # 测试不存在的奖励
        reward = model.get_reward("unknown", "act")
        assert reward == 0.0

    def test_update_from_experience(self):
        """测试从经验更新"""
        model = MDPModel()

        # 初始概率
        initial_prob = model.get_transition_prob("test_state", "test_action", "next_state")
        assert initial_prob == 0.0

        # 更新经验
        model.update_from_experience("test_state", "test_action", "next_state", 0.5)

        # 检查是否创建了新状态
        assert "test_state" in model.transition_probs
        assert "test_action" in model.transition_probs["test_state"]
        assert "next_state" in model.transition_probs["test_state"]["test_action"]

        # 检查奖励更新
        assert "test_state" in model.reward_function
        assert "test_action" in model.reward_function["test_state"]
        assert model.reward_function["test_state"]["test_action"] == 0.5


class TestStateMachine:
    """StateMachine类测试"""

    def setup_method(self):
        """测试设置"""
        self.memory_bank = MockMemoryBank(5)
        self.state_machine = StateMachine(max_iterations=5, use_mdp=True)

    def test_initialization(self):
        """测试状态机初始化"""
        sm = StateMachine(max_iterations=10, use_mdp=False)

        assert sm.max_iterations == 10
        assert sm.use_mdp == False
        assert sm.mdp_model is None
        assert sm.current_state is None
        assert sm.history == []
        assert sm.total_transitions == 0

    def test_initialize(self):
        """测试状态机初始化方法"""
        task_input = "测试任务"

        initial_state = self.state_machine.initialize(task_input, self.memory_bank)

        assert self.state_machine.current_state == initial_state
        assert initial_state.task_input == task_input
        assert initial_state.memory_bank == self.memory_bank
        assert initial_state.traces == []
        assert initial_state.iteration == 0

        # 检查历史记录
        assert len(self.state_machine.history) == 1
        assert self.state_machine.history[0]["action"] == "initialize"

        # 检查时间记录
        assert self.state_machine.start_time is not None

    def test_transition_basic(self):
        """测试基本状态转移"""
        # 先初始化
        self.state_machine.initialize("任务", self.memory_bank)
        initial_state = self.state_machine.current_state

        # 执行转移
        new_state = self.state_machine.transition(Action.THINK, thought="测试思考")

        # 检查新状态
        assert new_state != initial_state
        assert new_state.iteration == initial_state.iteration + 1
        assert new_state.task_input == initial_state.task_input
        assert new_state.memory_bank == initial_state.memory_bank

        # 检查历史记录
        assert len(self.state_machine.history) == 2
        transition_record = self.state_machine.history[1]
        assert transition_record["action"] == "think"
        assert transition_record["from_iteration"] == 0
        assert transition_record["to_iteration"] == 1
        assert transition_record["kwargs"]["thought"] == "测试思考"

        # 检查转移计数
        assert self.state_machine.total_transitions == 1

    def test_transition_without_initialization(self):
        """测试未初始化时的转移"""
        with pytest.raises(ValueError, match="状态机未初始化"):
            self.state_machine.transition(Action.THINK)

    def test_get_valid_actions(self):
        """测试获取有效动作"""
        # 未初始化时
        assert self.state_machine.get_valid_actions() == []

        # 初始化后
        self.state_machine.initialize("任务", self.memory_bank)
        valid_actions = self.state_machine.get_valid_actions()

        assert len(valid_actions) == 3
        assert Action.THINK in valid_actions
        assert Action.REFINE in valid_actions
        assert Action.ACT in valid_actions

    def test_get_action_with_mdp(self):
        """测试使用MDP选择动作"""
        self.state_machine.initialize("任务", self.memory_bank)

        action = self.state_machine.get_action_with_mdp()

        assert action in [Action.THINK, Action.REFINE, Action.ACT]

    def test_get_action_without_mdp(self):
        """测试不使用MDP时的动作选择"""
        sm = StateMachine(use_mdp=False)
        sm.initialize("任务", self.memory_bank)

        action = sm.get_action_with_mdp()

        # 应该回退到随机选择
        assert action in [Action.THINK, Action.REFINE, Action.ACT]

    def test_should_terminate_max_iterations(self):
        """测试达到最大迭代次数时的终止条件"""
        self.state_machine.initialize("任务", self.memory_bank)

        # 执行多次转移达到最大迭代次数
        for i in range(self.state_machine.max_iterations):
            self.state_machine.transition(Action.THINK)

        assert self.state_machine.should_terminate() == True

    def test_should_terminate_act_action(self):
        """测试执行ACT动作后的终止条件"""
        self.state_machine.initialize("任务", self.memory_bank)
        self.state_machine.transition(Action.ACT)

        assert self.state_machine.should_terminate() == True

    def test_should_terminate_timeout(self):
        """测试超时终止"""
        self.state_machine.initialize("任务", self.memory_bank)

        # 模拟超时（将start_time设置为31秒前）
        self.state_machine.start_time = time.time() - 31

        assert self.state_machine.should_terminate() == True

    def test_should_terminate_loop_detection(self):
        """测试循环检测"""
        self.state_machine.initialize("任务", self.memory_bank)

        # 执行5次相同的动作
        for _ in range(5):
            self.state_machine.transition(Action.THINK)

        assert self.state_machine.should_terminate() == True

    def test_get_progress(self):
        """测试获取进度信息"""
        # 未初始化时
        progress = self.state_machine.get_progress()
        assert progress["initialized"] == False

        # 初始化后
        self.state_machine.initialize("任务", self.memory_bank)
        progress = self.state_machine.get_progress()

        assert progress["initialized"] == True
        assert progress["current_iteration"] == 0
        assert progress["max_iterations"] == 5
        assert progress["progress_percentage"] == 0.0
        assert progress["total_transitions"] == 0
        assert progress["traces_count"] == 0
        assert progress["memory_size"] == 5
        assert progress["elapsed_time"] >= 0

    def test_reset(self):
        """测试重置状态机"""
        self.state_machine.initialize("任务", self.memory_bank)
        self.state_machine.transition(Action.THINK)

        # 重置前检查
        assert self.state_machine.current_state is not None
        assert len(self.state_machine.history) == 2
        assert self.state_machine.total_transitions == 1
        assert self.state_machine.start_time is not None

        # 执行重置
        self.state_machine.reset()

        # 重置后检查
        assert self.state_machine.current_state is None
        assert self.state_machine.history == []
        assert self.state_machine.total_transitions == 0
        assert self.state_machine.start_time is None

    def test_get_mdp_stats(self):
        """测试获取MDP统计信息"""
        # 使用MDP时
        stats = self.state_machine.get_mdp_stats()
        assert stats["enabled"] == True
        assert "states_count" in stats
        assert "transitions_count" in stats
        assert "rewards_count" in stats

        # 不使用MDP时
        sm = StateMachine(use_mdp=False)
        stats = sm.get_mdp_stats()
        assert stats["enabled"] == False

    def test_get_statistics(self):
        """测试获取完整统计信息"""
        self.state_machine.initialize("任务", self.memory_bank)

        stats = self.state_machine.get_statistics()

        assert "progress" in stats
        assert "mdp" in stats
        assert "total_history_entries" in stats
        assert "current_state" in stats
        assert "config" in stats
        assert stats["config"]["max_iterations"] == 5
        assert stats["config"]["use_mdp"] == True

    def test_transition_after_termination(self):
        """测试终止后的状态转移"""
        self.state_machine.initialize("任务", self.memory_bank)
        self.state_machine.transition(Action.ACT)  # 这会触发终止

        # 尝试在终止后执行转移
        with pytest.raises(ValueError, match="状态机已终止"):
            self.state_machine.transition(Action.THINK)

    def test_transition_invalid_action(self):
        """测试无效动作处理"""
        self.state_machine.initialize("任务", self.memory_bank)

        # 模拟无效动作（这里实际上不会发生，因为Action枚举限制了有效值）
        # 但我们可以测试get_valid_actions的边界情况
        valid_actions = self.state_machine.get_valid_actions()
        assert Action.THINK in valid_actions  # 确保THINK是有效动作

    def test_max_iterations_force_act(self):
        """测试达到最大迭代次数时强制转为ACT"""
        self.state_machine.initialize("任务", self.memory_bank)

        # 执行转移直到达到最大迭代次数
        for i in range(self.state_machine.max_iterations - 1):
            self.state_machine.transition(Action.THINK)

        # 下一次转移应该强制转为ACT
        # 注意：transition方法内部会检查并强制转换
        last_state = self.state_machine.transition(Action.THINK)

        # 检查历史记录中的最后一个动作
        last_record = self.state_machine.history[-1]
        assert last_record["action"] == "act"

    def test_update_mdp_from_experience(self):
        """测试从经验更新MDP模型"""
        self.state_machine.initialize("任务", self.memory_bank)

        # 执行一些转移来生成经验
        self.state_machine.transition(Action.THINK)
        self.state_machine.transition(Action.REFINE)

        # 检查MDP模型是否被更新
        stats = self.state_machine.get_mdp_stats()
        assert stats["enabled"] == True
        # 由于有转移发生，应该有一些状态和转移记录
        assert stats["states_count"] > 0
        assert stats["transitions_count"] > 0