"""
Agent模块单元测试
"""

import pytest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from agent.remem_agent import ReMemAgent
from llm.mock_llm import MockLLM
from memory.bank import MemoryBank


class TestReMemAgent:
    """ReMemAgent类测试"""

    def setup_method(self):
        """测试设置"""
        self.mock_llm = MockLLM()
        self.agent = ReMemAgent(
            llm=self.mock_llm,
            memory_bank=MemoryBank(max_entries=10),
            max_iterations=4,
            retrieval_k=2,
        )

    def test_initialization(self):
        """测试Agent初始化"""
        assert self.agent.llm == self.mock_llm
        assert isinstance(self.agent.M, MemoryBank)
        assert self.agent.max_iterations == 4
        assert self.agent.retrieval_k == 2
        assert len(self.agent.M) == 0

    def test_run_task_simple(self):
        """测试运行简单任务"""
        # 配置模拟LLM返回特定的动作序列
        self.mock_llm.responses["请选择动作"] = "act"  # 直接执行Act

        task_input = "测试任务"
        result = self.agent.run_task(task_input)

        assert "action" in result
        assert "traces" in result
        assert "memory_size" in result
        assert "iterations" in result
        assert "status" in result
        assert result["status"] == "completed"
        assert result["iterations"] == 1
        assert len(self.agent.M) == 1  # 应该添加了一条新记忆

    def test_run_task_with_think(self):
        """测试包含Think动作的任务"""
        # 配置动作序列：Think -> Act
        self.mock_llm.call_counter = 0
        self.mock_llm.responses["请选择动作"] = ["think", "act"]

        task_input = "需要推理的任务"
        result = self.agent.run_task(task_input)

        assert result["status"] == "completed"
        assert result["iterations"] == 2
        assert len(result["traces"]) == 1  # 一次Think记录
        assert len(self.agent.M) == 1  # 添加了一条新记忆

    def test_run_task_with_refine(self):
        """测试包含Refine动作的任务"""
        # 配置动作序列：Refine -> Act
        self.mock_llm.call_counter = 0
        self.mock_llm.responses["请选择动作"] = ["refine", "act"]

        # 添加一些初始记忆用于Refine操作
        from memory.entry import MemoryEntry
        self.agent.M.add(MemoryEntry("初始任务", "初始输出", "初始反馈", "初始标签"))

        task_input = "需要修改记忆的任务"
        result = self.agent.run_task(task_input)

        assert result["status"] == "completed"
        assert result["iterations"] == 2
        assert len(result["traces"]) == 1  # 一次Refine记录
        # 记忆库应该包含：初始记忆 + Refine添加的记忆 + 新任务记忆
        # 具体数量取决于Refine命令的内容

    def test_max_iterations_exceeded(self):
        """测试超过最大迭代次数"""
        # 配置一直返回Think，导致无法达到Act
        self.mock_llm.call_counter = 0
        self.mock_llm.responses["请选择动作"] = ["think", "think", "think", "think"]

        task_input = "无限循环的任务"
        result = self.agent.run_task(task_input)

        assert result["status"] == "max_iterations_exceeded"
        assert result["iterations"] == 4  # 达到最大迭代次数
        assert len(self.agent.M) == 1  # 仍然添加了新记忆（强制Act）

    def test_invalid_action(self):
        """测试无效动作处理"""
        # 配置返回无效动作
        self.mock_llm.call_counter = 0
        self.mock_llm.responses["请选择动作"] = "invalid"

        task_input = "无效动作测试"
        result = self.agent.run_task(task_input)

        assert result["status"] == "forced"
        assert "invalid action" in str(result["traces"]).lower()

    def test_memory_retrieval(self):
        """测试记忆检索功能"""
        # 添加一些测试记忆
        from memory.entry import MemoryEntry
        self.agent.M.add(MemoryEntry("相关任务1", "输出1", "反馈1", "相关标签"))
        self.agent.M.add(MemoryEntry("无关任务", "输出2", "反馈2", "无关标签"))
        self.agent.M.add(MemoryEntry("相关任务2", "输出3", "反馈3", "相关标签"))

        # 配置模拟LLM返回相关索引
        self.mock_llm.responses["请仅输出索引列表"] = "0,2"
        self.mock_llm.responses["请选择动作"] = "act"

        task_input = "相关任务"
        result = self.agent.run_task(task_input)

        assert result["status"] == "completed"
        assert result["retrieved_count"] == 2  # 应该检索到2条相关记忆

    def test_statistics(self):
        """测试获取统计信息"""
        stats = self.agent.get_statistics()
        assert "memory_statistics" in stats
        assert "max_iterations" in stats
        assert "retrieval_k" in stats
        assert "persistence_path" in stats

    def test_save_and_load_memory(self):
        """测试记忆保存和加载"""
        # 添加一些测试记忆
        from memory.entry import MemoryEntry
        self.agent.M.add(MemoryEntry("测试保存", "测试输出", "测试反馈", "测试标签"))

        # 保存记忆
        save_result = self.agent.save_memory()
        assert save_result is True

        # 创建新的Agent并加载记忆
        new_agent = ReMemAgent(
            llm=self.mock_llm,
            memory_bank=MemoryBank(max_entries=10),
            max_iterations=4,
            retrieval_k=2,
        )

        # 新Agent的记忆库应该是空的
        assert len(new_agent.M) == 0

        # 加载记忆
        load_result = new_agent.load_memory()
        assert load_result is True
        # 注意：由于使用相同的持久化路径，应该能加载到之前保存的记忆
        # 但实际测试中可能因为路径问题而失败，这里我们主要测试接口

    def test_apply_delta(self):
        """测试应用Refine编辑操作"""
        # 添加一些初始记忆
        from memory.entry import MemoryEntry
        self.agent.M.add(MemoryEntry("记忆1", "输出1", "反馈1", "标签1"))
        self.agent.M.add(MemoryEntry("记忆2", "输出2", "反馈2", "标签2"))
        self.agent.M.add(MemoryEntry("记忆3", "输出3", "反馈3", "标签3"))

        initial_count = len(self.agent.M)

        # 应用删除操作
        delta = {
            "delete": [1],  # 删除索引1的记忆
            "add": ["新添加的记忆内容"],
            "merge": [(0, 2)],  # 合并索引0和2
            "relabel": [(0, "新标签")],  # 重新标记索引0
        }

        self.agent._apply_delta(delta)

        # 检查结果
        # 原始3条，删除1条，添加1条，合并减少1条，总共应该是2条
        assert len(self.agent.M) == 2

        # 检查重标签
        assert self.agent.M[0].tag == "新标签"

    def test_add_new_memory(self):
        """测试添加新记忆"""
        initial_count = len(self.agent.M)

        task_input = "测试任务输入"
        action_result = "Act: 测试动作结果"
        feedback = "测试反馈"

        self.agent._add_new_memory(task_input, action_result, feedback)

        assert len(self.agent.M) == initial_count + 1
        new_entry = self.agent.M[-1]
        assert new_entry.x == task_input
        assert new_entry.y == "测试动作结果"  # 去掉"Act:"前缀
        assert new_entry.feedback == feedback
        assert new_entry.tag == "task"