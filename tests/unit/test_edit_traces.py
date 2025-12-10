"""
编辑轨迹记录测试
"""

import pytest
import sys
import os
import json

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.memory.entry import MemoryEntry
from src.memory.bank import MemoryBank
from src.agent.remem_agent import ReMemAgent
from src.llm.mock_llm import MockLLM


class TestEditTraces:
    """编辑轨迹记录测试"""

    def setup_method(self):
        """测试设置"""
        # 创建模拟LLM
        self.mock_llm = MockLLM()

        # 创建记忆库并添加一些测试条目
        self.memory_bank = MemoryBank(max_entries=10)
        for i in range(3):
            entry = MemoryEntry(
                x=f"测试任务{i}",
                y=f"测试输出{i}",
                feedback=f"测试反馈{i}",
                tag=f"test{i}"
            )
            self.memory_bank.add(entry)

        # 创建ReMemAgent实例
        self.agent = ReMemAgent(
            llm=self.mock_llm,
            memory_bank=self.memory_bank,
            persist_path="./test_memory.json",
            max_iterations=5,
            retrieval_k=3,
            include_explanations=True
        )

    def test_edit_traces_basic(self):
        """测试基本编辑轨迹记录"""
        # 清空现有轨迹
        self.agent.clear_edit_traces()
        assert len(self.agent.get_edit_traces()) == 0

        # 创建一个测试的delta
        test_delta = {
            "delete": [0],
            "add": ["新的记忆内容"],
            "merge": [(1, 2)],
            "relabel": [(0, "new-tag")]
        }

        # 应用编辑操作
        self.agent._apply_delta_enhanced(test_delta, "测试命令", 1)

        # 检查轨迹记录
        traces = self.agent.get_edit_traces()
        assert len(traces) == 1

        trace = traces[0]
        assert trace["iteration"] == 1
        assert trace["raw_command"] == "测试命令"
        assert trace["parsed_delta"] == test_delta
        assert trace["success"] is True
        assert trace["error"] is None

        # 检查操作详情
        assert len(trace["operations"]) == 4

        # 检查删除操作
        delete_op = trace["operations"][0]
        assert delete_op["type"] == "delete"
        assert delete_op["indices"] == [0]
        assert delete_op["count"] == 1

        # 检查添加操作
        add_op = trace["operations"][1]
        assert add_op["type"] == "add"
        assert add_op["count"] == 1
        assert len(add_op["added_entry_ids"]) == 1

        # 检查合并操作
        merge_op = trace["operations"][2]
        assert merge_op["type"] == "merge"
        assert merge_op["pairs"] == [(1, 2)]
        assert merge_op["count"] == 1

        # 检查重标记操作
        relabel_op = trace["operations"][3]
        assert relabel_op["type"] == "relabel"
        assert relabel_op["items"] == [(0, "new-tag")]
        assert relabel_op["count"] == 1

    def test_edit_traces_memory_changes(self):
        """测试记忆变化的轨迹记录"""
        # 记录初始记忆数量
        initial_count = len(self.agent.M)

        # 创建一个测试的delta
        test_delta = {
            "delete": [0, 1],
            "add": ["内容1", "内容2"],
            "merge": [],
            "relabel": []
        }

        # 应用编辑操作
        self.agent._apply_delta_enhanced(test_delta, "DELETE 0,1; ADD{内容1}; ADD{内容2}", 2)

        # 检查轨迹记录
        traces = self.agent.get_edit_traces()
        assert len(traces) == 1

        trace = traces[0]
        assert trace["original_memory_count"] == initial_count
        assert trace["final_memory_count"] == len(self.agent.M)
        assert trace["memory_change"] == len(self.agent.M) - initial_count

        # 验证记忆数量变化
        # 删除了2个，添加了2个，所以总数应该不变
        assert trace["memory_change"] == 0
        assert len(self.agent.M) == initial_count

    def test_edit_traces_failure(self):
        """测试失败操作的轨迹记录"""
        # 创建一个会失败的delta（无效索引）
        test_delta = {
            "delete": [100],  # 无效索引
            "add": [],
            "merge": [],
            "relabel": []
        }

        # 应用编辑操作（应该失败）
        self.agent._apply_delta_enhanced(test_delta, "DELETE 100", 3)

        # 检查轨迹记录
        traces = self.agent.get_edit_traces()
        assert len(traces) == 1

        trace = traces[0]
        assert trace["success"] is False
        assert trace["error"] is not None
        assert "索引超出范围" in trace["error"]

        # 失败时不应该有operations字段
        assert "operations" not in trace

    def test_edit_traces_limit(self):
        """测试轨迹记录数量限制"""
        # 清空现有轨迹
        self.agent.clear_edit_traces()

        # 添加超过限制的轨迹记录
        for i in range(150):
            test_delta = {
                "delete": [],
                "add": [f"内容{i}"],
                "merge": [],
                "relabel": []
            }
            self.agent._apply_delta_enhanced(test_delta, f"ADD{{内容{i}}}", i)

        # 检查轨迹记录数量（应该被限制在100条）
        traces = self.agent.get_edit_traces()
        assert len(traces) == 100

        # 最早的50条应该被删除
        assert traces[0]["iteration"] == 50  # 第50次迭代
        assert traces[-1]["iteration"] == 149  # 最后一次迭代

    def test_get_edit_traces_with_limit(self):
        """测试带限制的轨迹记录获取"""
        # 清空现有轨迹
        self.agent.clear_edit_traces()

        # 添加一些轨迹记录
        for i in range(10):
            test_delta = {
                "delete": [],
                "add": [f"内容{i}"],
                "merge": [],
                "relabel": []
            }
            self.agent._apply_delta_enhanced(test_delta, f"ADD{{内容{i}}}", i)

        # 测试不同限制
        traces_all = self.agent.get_edit_traces()
        assert len(traces_all) == 10

        traces_5 = self.agent.get_edit_traces(limit=5)
        assert len(traces_5) == 5
        assert traces_5[0]["iteration"] == 5  # 第5次迭代
        assert traces_5[-1]["iteration"] == 9  # 最后一次迭代

        traces_0 = self.agent.get_edit_traces(limit=0)
        assert len(traces_0) == 0

        traces_20 = self.agent.get_edit_traces(limit=20)  # 超过实际数量
        assert len(traces_20) == 10

    def test_clear_edit_traces(self):
        """测试清空轨迹记录"""
        # 添加一些轨迹记录
        for i in range(5):
            test_delta = {
                "delete": [],
                "add": [f"内容{i}"],
                "merge": [],
                "relabel": []
            }
            self.agent._apply_delta_enhanced(test_delta, f"ADD{{内容{i}}}", i)

        # 检查轨迹记录
        traces = self.agent.get_edit_traces()
        assert len(traces) == 5

        # 清空轨迹记录
        self.agent.clear_edit_traces()
        traces = self.agent.get_edit_traces()
        assert len(traces) == 0

        # 清空后可以继续添加
        test_delta = {
            "delete": [],
            "add": ["新内容"],
            "merge": [],
            "relabel": []
        }
        self.agent._apply_delta_enhanced(test_delta, "ADD{新内容}", 10)

        traces = self.agent.get_edit_traces()
        assert len(traces) == 1

    def test_get_edit_statistics(self):
        """测试编辑统计信息"""
        # 清空现有轨迹
        self.agent.clear_edit_traces()

        # 添加各种类型的编辑操作
        operations = [
            ({"delete": [0], "add": [], "merge": [], "relabel": []}, "DELETE 0", 0),
            ({"delete": [], "add": ["内容1", "内容2"], "merge": [], "relabel": []}, "ADD{内容1}; ADD{内容2}", 1),
            ({"delete": [], "add": [], "merge": [(0, 1)], "relabel": []}, "MERGE 0&1", 2),
            ({"delete": [], "add": [], "merge": [], "relabel": [(0, "tag1"), (1, "tag2")]}, "RELABEL 0 tag1; RELABEL 1 tag2", 3),
            ({"delete": [100], "add": [], "merge": [], "relabel": []}, "DELETE 100", 4),  # 失败操作
        ]

        for delta, cmd, iteration in operations:
            self.agent._apply_delta_enhanced(delta, cmd, iteration)

        # 获取统计信息
        stats = self.agent.get_edit_statistics()

        assert stats["total_edits"] == 5
        assert stats["successful_edits"] == 4
        assert stats["failed_edits"] == 1
        assert stats["delete_count"] == 1
        assert stats["add_count"] == 2
        assert stats["merge_count"] == 1
        assert stats["relabel_count"] == 2
        assert stats["latest_edit"] is not None
        assert stats["latest_edit"]["iteration"] == 4

    def test_get_edit_statistics_empty(self):
        """测试空编辑统计信息"""
        # 清空现有轨迹
        self.agent.clear_edit_traces()

        # 获取空统计信息
        stats = self.agent.get_edit_statistics()

        assert stats["total_edits"] == 0
        assert stats["successful_edits"] == 0
        assert stats["failed_edits"] == 0
        assert stats["delete_count"] == 0
        assert stats["add_count"] == 0
        assert stats["merge_count"] == 0
        assert stats["relabel_count"] == 0
        assert stats["latest_edit"] is None

    def test_agent_statistics_with_edits(self):
        """测试包含编辑统计的Agent统计信息"""
        # 添加一些编辑操作
        test_delta = {
            "delete": [0],
            "add": ["新内容"],
            "merge": [(1, 2)],
            "relabel": [(0, "new-tag")]
        }
        self.agent._apply_delta_enhanced(test_delta, "测试命令", 1)

        # 获取Agent统计信息
        stats = self.agent.get_statistics()

        assert "memory_statistics" in stats
        assert "edit_statistics" in stats
        assert "max_iterations" in stats
        assert "retrieval_k" in stats
        assert "include_explanations" in stats
        assert "persistence_path" in stats

        # 检查编辑统计
        edit_stats = stats["edit_statistics"]
        assert edit_stats["total_edits"] == 1
        assert edit_stats["successful_edits"] == 1
        assert edit_stats["delete_count"] == 1
        assert edit_stats["add_count"] == 1
        assert edit_stats["merge_count"] == 1
        assert edit_stats["relabel_count"] == 1

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        # 测试旧的_apply_delta方法仍然可用
        test_delta = {
            "delete": [0],
            "add": ["兼容性测试"],
            "merge": [],
            "relabel": []
        }

        # 使用旧方法
        self.agent._apply_delta(test_delta)

        # 检查轨迹记录（应该有一条记录）
        traces = self.agent.get_edit_traces()
        assert len(traces) == 1

        trace = traces[0]
        assert trace["raw_command"] == "legacy_command"
        assert trace["iteration"] == 0
        assert trace["success"] is True

    def test_run_task_with_edit_traces(self):
        """测试run_task返回编辑轨迹"""
        # 配置模拟LLM返回Refine命令
        def mock_llm_response(prompt):
            if "Refine:" in prompt:
                return "DELETE 0; ADD{测试添加}; MERGE 1&2"
            elif "Act:" in prompt:
                return "Act: 测试动作"
            elif "Think:" in prompt:
                return "Think: 测试思考"
            else:
                return "Refine"  # 选择Refine动作

        self.mock_llm.set_response_function(mock_llm_response)

        # 运行任务
        result = self.agent.run_task("测试任务")

        # 检查结果中包含编辑轨迹
        assert "edit_traces" in result
        edit_traces = result["edit_traces"]
        assert len(edit_traces) > 0

        # 检查轨迹内容
        trace = edit_traces[0]
        assert trace["raw_command"] == "DELETE 0; ADD{测试添加}; MERGE 1&2"
        assert trace["success"] is True
        assert "operations" in trace

    def test_trace_timestamp(self):
        """测试轨迹时间戳"""
        test_delta = {
            "delete": [],
            "add": ["测试内容"],
            "merge": [],
            "relabel": []
        }

        # 应用编辑操作
        self.agent._apply_delta_enhanced(test_delta, "ADD{测试内容}", 1)

        # 检查时间戳
        traces = self.agent.get_edit_traces()
        trace = traces[0]

        assert "timestamp" in trace
        timestamp = trace["timestamp"]

        # 检查时间戳格式
        import datetime
        dt = datetime.datetime.fromisoformat(timestamp)
        assert isinstance(dt, datetime.datetime)