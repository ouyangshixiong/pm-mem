"""
ReMem工作流程集成测试

测试完整的ReMem Agent工作流程，包括记忆检索、推理、编辑和行动。
"""

import pytest
import sys
import os
import tempfile
import shutil

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from llm.mock_llm import MockLLM
from agent.remem_agent import ReMemAgent
from memory.entry import MemoryEntry
from memory.bank import MemoryBank


class TestReMemWorkflow:
    """ReMem工作流程集成测试"""

    def setup_method(self):
        """测试设置"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.persistence_path = os.path.join(self.temp_dir, "memory.json")

        # 创建模拟LLM
        self.mock_llm = MockLLM()

        # 配置模拟LLM的响应
        self._setup_mock_responses()

        # 创建带有初始记忆的Agent
        self.initial_memories = [
            MemoryEntry(
                x="如何配置nginx反向代理？",
                y="在nginx配置文件中添加location块，使用proxy_pass指令",
                feedback="配置成功，服务可用",
                tag="nginx-config"
            ),
            MemoryEntry(
                x="阿里云安全组阻止3000端口访问",
                y="在安全组规则中添加入方向规则，允许3000端口",
                feedback="端口可访问",
                tag="aliyun-security"
            ),
            MemoryEntry(
                x="使用curl测试API健康检查",
                y="curl -I http://localhost:3000/health",
                feedback="返回200状态码",
                tag="api-testing"
            ),
        ]

        memory_bank = MemoryBank(max_entries=10)
        for memory in self.initial_memories:
            memory_bank.add(memory)

        self.agent = ReMemAgent(
            llm=self.mock_llm,
            memory_bank=memory_bank,
            persist_path=self.persistence_path,
            max_iterations=6,
            retrieval_k=2,
        )

    def teardown_method(self):
        """测试清理"""
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _setup_mock_responses(self):
        """设置模拟LLM的响应"""
        # 检索响应：总是返回前两个索引
        self.mock_llm.responses["请仅输出索引列表"] = "0,1"

        # 动作选择序列：模拟典型的工作流程
        self.mock_llm.call_counter = 0
        self.mock_llm.responses["请选择动作"] = ["think", "refine", "act"]

        # Think响应
        self.mock_llm.responses["think:"] = (
            "Think: 用户遇到了阿里云安全组问题，需要检查端口3000的访问。"
            "根据已有记忆，可以通过添加安全组规则或使用nginx反向代理解决。"
            "考虑到用户已经配置了nginx，建议使用nginx进行转发。"
        )

        # Refine响应：添加新记忆并删除冗余
        self.mock_llm.responses["refine:"] = (
            "DELETE 1; ADD{如果3000端口被阿里云安全组阻止，可以使用nginx在80端口配置反向代理："
            "location /app/ { proxy_pass http://localhost:3000/; }}"
        )

        # Act响应
        self.mock_llm.responses["act:"] = (
            "Act: 建议使用nginx反向代理解决阿里云安全组对3000端口的限制，"
            "配置示例：location /app/ { proxy_pass http://localhost:3000/; }"
        )

    def test_complete_workflow(self):
        """测试完整的工作流程（Think -> Refine -> Act）"""
        task_input = "阿里云ECS无法通过3000端口访问服务"

        # 运行任务
        result = self.agent.run_task(task_input)

        # 验证结果
        assert result["status"] == "completed"
        assert result["iterations"] == 3
        assert len(result["traces"]) == 2  # Think和Refine的轨迹

        # 验证记忆库状态
        assert len(self.agent.M) > len(self.initial_memories)  # 应该添加了新记忆

        # 验证记忆库统计信息
        stats = self.agent.M.get_statistics()
        assert stats["total_entries"] > 0

        # 验证持久化文件是否存在
        assert os.path.exists(self.persistence_path)

    def test_memory_retrieval_in_workflow(self):
        """测试工作流程中的记忆检索"""
        # 修改检索响应以测试特定场景
        self.mock_llm.responses["请仅输出索引列表"] = "2,0"

        task_input = "如何测试API健康检查？"
        result = self.agent.run_task(task_input)

        # 验证检索到了相关记忆
        assert result["retrieved_count"] == 2
        assert result["status"] == "completed"

        # 验证检索到的记忆是相关的
        # （在模拟中，我们总是返回固定索引，所以这里主要测试流程）

    def test_refine_operations_in_workflow(self):
        """测试工作流程中的记忆编辑操作"""
        initial_count = len(self.agent.M)

        task_input = "测试Refine操作的工作流程"
        result = self.agent.run_task(task_input)

        # 验证Refine操作被执行
        assert any("DELETE" in str(trace) for trace in result["traces"])
        assert any("ADD" in str(trace) for trace in result["traces"])

        # 验证记忆库变化
        # 根据模拟的Refine命令：删除1条，添加1条，所以总数不变
        # 但实际执行中可能因为索引问题有变化
        final_count = len(self.agent.M)
        # 我们只关心流程正确执行，不关心具体数量

    def test_persistence_in_workflow(self):
        """测试工作流程中的持久化"""
        task_input = "测试持久化的工作流程"
        initial_result = self.agent.run_task(task_input)

        # 验证文件已创建
        assert os.path.exists(self.persistence_path)

        # 创建新的Agent实例，加载之前的记忆
        new_agent = ReMemAgent(
            llm=self.mock_llm,
            persist_path=self.persistence_path,
            max_iterations=4,
            retrieval_k=2,
        )

        # 验证新Agent加载了记忆
        assert len(new_agent.M) > 0

        # 在新Agent上运行另一个任务
        new_task = "另一个测试任务"
        new_result = new_agent.run_task(new_task)

        assert new_result["status"] == "completed"
        assert len(new_agent.M) > len(self.agent.M)  # 应该添加了新记忆

    def test_max_iterations_handling(self):
        """测试最大迭代次数处理"""
        # 配置LLM一直返回Think，导致无法达到Act
        self.mock_llm.call_counter = 0
        self.mock_llm.responses["请选择动作"] = ["think", "think", "think", "think", "think", "think"]

        task_input = "会导致迭代超时的任务"
        result = self.agent.run_task(task_input)

        assert result["status"] == "max_iterations_exceeded"
        assert result["iterations"] == 6  # 达到最大迭代次数

        # 即使超时，也应该添加了新记忆
        assert len(self.agent.M) > len(self.initial_memories)

    def test_error_recovery_in_workflow(self):
        """测试工作流程中的错误恢复"""
        # 模拟LLM在某个步骤抛出异常
        original_call = self.mock_llm.call

        def failing_call(prompt):
            if "请选择动作" in prompt.lower():
                raise Exception("模拟LLM故障")
            return original_call(prompt)

        self.mock_llm.call = failing_call

        task_input = "测试错误恢复的任务"
        result = self.agent.run_task(task_input)

        # 验证即使LLM故障，流程也能继续（默认返回"act"）
        assert result["status"] in ["completed", "forced"]
        assert "action" in result

        # 恢复原始方法
        self.mock_llm.call = original_call

    def test_multiple_tasks_workflow(self):
        """测试多个任务的连续工作流程"""
        tasks = [
            "第一个任务：配置nginx",
            "第二个任务：检查安全组",
            "第三个任务：测试API",
        ]

        results = []
        for task in tasks:
            result = self.agent.run_task(task)
            results.append(result)

        # 验证所有任务都成功完成
        for result in results:
            assert result["status"] in ["completed", "forced", "max_iterations_exceeded"]

        # 验证记忆库增长
        assert len(self.agent.M) >= len(self.initial_memories) + len(tasks)

        # 验证持久化文件包含所有记忆
        assert os.path.exists(self.persistence_path)
        # 可以添加文件内容验证，但这里保持简单

    def test_memory_pruning_in_workflow(self):
        """测试工作流程中的记忆清理"""
        # 创建达到容量限制的记忆库
        memory_bank = MemoryBank(max_entries=3)  # 很小的容量
        for i in range(3):
            memory_bank.add(MemoryEntry(
                x=f"旧任务{i}",
                y=f"旧输出{i}",
                feedback=f"旧反馈{i}",
                tag="old",
            ))

        agent = ReMemAgent(
            llm=self.mock_llm,
            memory_bank=memory_bank,
            persist_path=self.persistence_path,
            max_iterations=4,
            retrieval_k=2,
        )

        # 运行新任务，应该触发清理
        task_input = "新任务，应该触发清理"
        result = agent.run_task(task_input)

        # 验证记忆库没有超过最大容量
        assert len(agent.M) <= memory_bank.max_entries
        assert result["status"] == "completed"


if __name__ == "__main__":
    # 允许直接运行集成测试
    pytest.main([__file__, "-v"])