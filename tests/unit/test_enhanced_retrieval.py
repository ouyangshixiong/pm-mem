"""
增强检索功能测试

测试PM-11到PM-13实现的增强检索功能：
1. PM-11: 基于LLM的文本相关性检索核心功能
2. PM-12: Top-k结果返回和空记忆库处理机制
3. PM-13: 检索结果相关性解释功能
"""

import pytest
import sys
import os
import json
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from memory.entry import MemoryEntry
from memory.bank import MemoryBank
from memory.retrieval_result import RetrievalResult


class TestEnhancedRetrieval:
    """增强检索功能测试"""

    def setup_method(self):
        """测试设置"""
        self.bank = MemoryBank(max_entries=10)

        # 创建测试记忆条目
        self.entries = [
            MemoryEntry(
                x="如何编写Python单元测试",
                y="使用pytest框架，编写test_开头的函数",
                feedback="测试通过",
                tag="python-testing",
                timestamp=datetime(2024, 1, 1)
            ),
            MemoryEntry(
                x="如何调试Python代码",
                y="使用pdb或print语句进行调试",
                feedback="调试成功",
                tag="python-debugging",
                timestamp=datetime(2024, 1, 2)
            ),
            MemoryEntry(
                x="如何优化Python性能",
                y="使用列表推导式、避免全局变量",
                feedback="性能提升",
                tag="python-optimization",
                timestamp=datetime(2024, 1, 3)
            ),
            MemoryEntry(
                x="如何部署Web应用",
                y="使用Docker容器化部署",
                feedback="部署成功",
                tag="web-deployment",
                timestamp=datetime(2024, 1, 4)
            ),
            MemoryEntry(
                x="如何设计数据库模式",
                y="遵循第三范式，建立适当索引",
                feedback="设计合理",
                tag="database-design",
                timestamp=datetime(2024, 1, 5)
            )
        ]

        # 添加到记忆库
        for entry in self.entries:
            self.bank.add(entry)

    def test_pm12_empty_memory_bank(self):
        """PM-12测试：空记忆库处理"""
        empty_bank = MemoryBank()

        class MockLLM:
            def __call__(self, prompt):
                return "[]"

        mock_llm = MockLLM()
        results = empty_bank.retrieve(mock_llm, "测试查询", k=5)

        assert len(results) == 0
        assert results == []

    def test_pm12_invalid_k_value(self):
        """PM-12测试：无效k值处理"""
        class MockLLM:
            def __call__(self, prompt):
                return json.dumps({
                    "results": [
                        {"index": 0, "relevance_score": 0.8, "explanation": "相关"}
                    ]
                })

        mock_llm = MockLLM()

        # k <= 0 应该返回空列表
        results = self.bank.retrieve(mock_llm, "测试查询", k=0)
        assert len(results) == 0

        results = self.bank.retrieve(mock_llm, "测试查询", k=-1)
        assert len(results) == 0

    def test_pm12_k_greater_than_memory_size(self):
        """PM-12测试：k大于记忆库大小"""
        class MockLLM:
            def __call__(self, prompt):
                # 模拟LLM返回所有条目的评估
                results = []
                for i in range(5):
                    results.append({
                        "index": i,
                        "relevance_score": 0.5 + i * 0.1,
                        "explanation": f"记忆{i}相关"
                    })
                return json.dumps({"results": results})

        mock_llm = MockLLM()

        # k=10，但记忆库只有5个条目
        results = self.bank.retrieve(mock_llm, "测试查询", k=10)

        # 应该只返回5个结果
        assert len(results) == 5
        assert len(results) <= len(self.bank)

    def test_pm11_improved_prompt_and_scoring(self):
        """PM-11测试：改进的提示词和评分机制"""
        class MockLLM:
            def __call__(self, prompt):
                # 验证提示词包含改进的内容
                assert "评估每个记忆条目与查询的相关性" in prompt
                assert "语义相关性" in prompt
                assert "任务适用性" in prompt
                assert "时效性" in prompt
                assert "JSON格式" in prompt

                # 返回模拟评估结果
                results = []
                for i in range(5):
                    results.append({
                        "index": i,
                        "relevance_score": 0.7 + i * 0.05,
                        "explanation": f"记忆{i}与查询相关，因为..."
                    })
                return json.dumps({"results": results})

        mock_llm = MockLLM()
        results = self.bank.retrieve(mock_llm, "如何编写Python代码", k=3)

        # 应该返回3个结果
        assert len(results) == 3

        # 结果应该是RetrievalResult对象
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert hasattr(result, 'relevance_score')
            assert hasattr(result, 'explanation')
            assert 0.0 <= result.relevance_score <= 1.0
            assert len(result.explanation) > 0

    def test_pm13_relevance_explanations(self):
        """PM-13测试：相关性解释功能"""
        class MockLLM:
            def __call__(self, prompt):
                results = []
                for i in range(5):
                    results.append({
                        "index": i,
                        "relevance_score": 0.8,
                        "explanation": f"这个记忆与查询相关，因为它涉及Python编程"
                    })
                return json.dumps({"results": results})

        mock_llm = MockLLM()

        # 测试包含解释的检索
        results = self.bank.retrieve(mock_llm, "Python编程", k=3, include_explanations=True)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert result.explanation == "这个记忆与查询相关，因为它涉及Python编程"

        # 测试不包含解释的检索（向后兼容）
        results = self.bank.retrieve(mock_llm, "Python编程", k=3, include_explanations=False)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, MemoryEntry)
            assert not isinstance(result, RetrievalResult)

    def test_fallback_retrieval(self):
        """测试回退检索机制"""
        class FailingLLM:
            def __call__(self, prompt):
                raise Exception("LLM调用失败")

        failing_llm = FailingLLM()

        # LLM失败时应该使用回退机制
        results = self.bank.retrieve(failing_llm, "测试查询", k=3, include_explanations=True)

        # 应该返回结果
        assert len(results) == 3

        # 回退结果应该是RetrievalResult对象
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert result.relevance_score == 0.5  # 回退默认评分
            assert result.explanation == "回退检索：按时间顺序返回"

    def test_json_parsing_error_handling(self):
        """测试JSON解析错误处理"""
        class InvalidJSONLLM:
            def __call__(self, prompt):
                return "这不是有效的JSON"

        invalid_llm = InvalidJSONLLM()

        # JSON解析失败时应该使用回退机制
        results = self.bank.retrieve(invalid_llm, "测试查询", k=2, include_explanations=True)

        # 应该返回回退结果
        assert len(results) == 2
        for result in results:
            assert isinstance(result, RetrievalResult)

    def test_retrieval_result_dataclass(self):
        """测试RetrievalResult数据结构"""
        memory_entry = self.entries[0]
        result = RetrievalResult(
            memory_entry=memory_entry,
            relevance_score=0.85,
            explanation="这个记忆非常相关"
        )

        # 测试属性
        assert result.memory_entry == memory_entry
        assert result.relevance_score == 0.85
        assert result.explanation == "这个记忆非常相关"

        # 测试评分范围限制
        result2 = RetrievalResult(memory_entry, relevance_score=1.5, explanation="测试")
        assert result2.relevance_score == 1.0  # 应该被限制到1.0

        result3 = RetrievalResult(memory_entry, relevance_score=-0.5, explanation="测试")
        assert result3.relevance_score == 0.0  # 应该被限制到0.0

        # 测试字典转换
        result_dict = result.to_dict()
        assert "memory_entry" in result_dict
        assert "relevance_score" in result_dict
        assert "explanation" in result_dict
        assert result_dict["relevance_score"] == 0.85

        # 测试从字典恢复
        restored = RetrievalResult.from_dict(result_dict)
        assert restored.memory_entry.id == memory_entry.id
        assert restored.relevance_score == 0.85
        assert restored.explanation == "这个记忆非常相关"

    def test_retrieval_ordering(self):
        """测试检索结果排序"""
        class ScoringLLM:
            def __call__(self, prompt):
                # 返回不同的评分，测试排序
                results = [
                    {"index": 0, "relevance_score": 0.5, "explanation": "中等相关"},
                    {"index": 1, "relevance_score": 0.9, "explanation": "高度相关"},
                    {"index": 2, "relevance_score": 0.3, "explanation": "低度相关"},
                    {"index": 3, "relevance_score": 0.7, "explanation": "较高相关"},
                    {"index": 4, "relevance_score": 0.6, "explanation": "中高相关"}
                ]
                return json.dumps({"results": results})

        scoring_llm = ScoringLLM()
        results = self.bank.retrieve(scoring_llm, "测试查询", k=5, include_explanations=True)

        # 结果应该按评分降序排列
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

        # 最高分应该是0.9（索引1）
        assert results[0].relevance_score == 0.9
        assert results[0].memory_entry == self.entries[1]

    def test_retrieval_with_specific_query(self):
        """测试特定查询的检索"""
        # 使用闭包捕获self.entries
        entries = self.entries

        class PythonFocusedLLM:
            def __call__(self, prompt):
                # 模拟LLM认为Python相关的记忆更相关
                results = []
                for i, entry in enumerate(entries):
                    score = 0.3  # 默认评分
                    explanation = "一般相关"

                    if "Python" in entry.x or "python" in entry.tag:
                        score = 0.9
                        explanation = "与Python编程高度相关"
                    elif "数据库" in entry.x or "database" in entry.tag:
                        score = 0.6
                        explanation = "与数据存储相关"

                    results.append({
                        "index": i,
                        "relevance_score": score,
                        "explanation": explanation
                    })
                return json.dumps({"results": results})

        python_llm = PythonFocusedLLM()
        results = self.bank.retrieve(python_llm, "Python编程问题", k=3, include_explanations=True)

        # 应该返回3个结果
        assert len(results) == 3

        # 检查结果类型
        for result in results:
            assert isinstance(result, RetrievalResult)

        # 验证评分和解释
        # 注意：由于模拟LLM的实现，前3个结果应该是评分最高的
        # 前3个应该是Python相关的（索引0,1,2），评分0.9
        python_scores = [r.relevance_score for r in results]
        # 至少有一个应该是0.9
        assert max(python_scores) == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])