"""
PM-111: 改进的LLM提示词模板测试
"""

import pytest
import sys
import os
import json
from unittest.mock import Mock, patch

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from memory.entry import MemoryEntry
from memory.bank import MemoryBank
from datetime import datetime, timedelta


class TestPM111PromptTemplate:
    """PM-111: 改进的LLM提示词模板测试"""

    def setup_method(self):
        """测试设置"""
        self.bank = MemoryBank(max_entries=10)

        # 创建不同时间戳的记忆条目
        now = datetime.now()
        self.entry1 = MemoryEntry(
            "如何优化Python代码性能",
            "使用列表推导式、避免全局变量、使用局部变量",
            "性能提升明显",
            "python-performance",
            timestamp=now - timedelta(days=1)
        )
        self.entry2 = MemoryEntry(
            "处理数据库连接错误",
            "检查连接字符串、增加重试机制、使用连接池",
            "解决了连接超时问题",
            "database-error",
            timestamp=now - timedelta(days=7)
        )
        self.entry3 = MemoryEntry(
            "机器学习模型训练技巧",
            "数据预处理、特征工程、超参数调优",
            "模型准确率提升",
            "ml-training",
            timestamp=now - timedelta(days=30)
        )

        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

    def test_prompt_structure_improvements(self):
        """测试prompt结构改进"""
        # 模拟LLM返回有效的JSON响应
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.85,
                    "semantic_relevance": 0.9,
                    "task_applicability": 0.8,
                    "timeliness": 0.7,
                    "explanation": "记忆直接回答了查询问题"
                },
                {
                    "index": 1,
                    "relevance_score": 0.65,
                    "semantic_relevance": 0.7,
                    "task_applicability": 0.6,
                    "timeliness": 0.5,
                    "explanation": "记忆包含相关信息"
                },
                {
                    "index": 2,
                    "relevance_score": 0.45,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.4,
                    "timeliness": 0.3,
                    "explanation": "记忆只有少量关联"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        # 执行检索
        results = self.bank.retrieve(mock_llm, "如何优化Python代码", k=2)

        # 验证LLM被调用
        assert mock_llm.called

        # 获取prompt内容
        prompt = mock_llm.call_args[0][0]

        # 验证prompt包含改进的结构
        assert "# 记忆检索评估任务" in prompt
        assert "## 用户查询" in prompt
        assert "## 记忆条目列表" in prompt
        assert "## 任务要求" in prompt
        assert "## 评估维度说明" in prompt
        assert "## 输出规范" in prompt
        assert "## 示例说明" in prompt
        assert "## 开始评估" in prompt

        # 验证包含所有评估维度
        assert "语义相关性 (semantic_relevance)" in prompt
        assert "任务适用性 (task_applicability)" in prompt
        assert "时效性 (timeliness)" in prompt
        assert "总体相关性评分 (relevance_score)" in prompt

        # 验证包含计算公式
        assert "0.5*semantic_relevance + 0.3*task_applicability + 0.2*timeliness" in prompt

        # 验证包含错误预防提示
        assert "不要排序" in prompt
        assert "不要省略" in prompt
        assert "不要添加" in prompt
        assert "格式正确" in prompt
        assert "数值类型" in prompt

    def test_prompt_contains_all_entries(self):
        """测试prompt包含所有记忆条目"""
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                },
                {
                    "index": 1,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                },
                {
                    "index": 2,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        self.bank.retrieve(mock_llm, "测试查询", k=1)

        prompt = mock_llm.call_args[0][0]

        # 验证包含所有条目
        assert "如何优化Python代码性能" in prompt
        assert "处理数据库连接错误" in prompt
        assert "机器学习模型训练技巧" in prompt

        # 验证包含正确的条目数量
        assert f"共{len(self.bank)}个" in prompt
        assert f"索引0到{len(self.bank)-1}" in prompt

    def test_prompt_examples_quality(self):
        """测试prompt示例质量"""
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        self.bank.retrieve(mock_llm, "测试查询", k=1)

        prompt = mock_llm.call_args[0][0]

        # 验证包含多种示例
        assert "高度相关的记忆" in prompt
        assert "中等相关的记忆" in prompt
        assert "低度相关的记忆" in prompt
        assert "完全不相关的记忆" in prompt

        # 验证示例包含完整的JSON结构
        assert '"index": 0' in prompt
        assert '"relevance_score": 0.92' in prompt
        assert '"semantic_relevance": 0.95' in prompt
        assert '"task_applicability": 0.90' in prompt
        assert '"timeliness": 0.85' in prompt
        assert '"explanation":' in prompt

    def test_prompt_evaluation_guidance(self):
        """测试prompt评估指导"""
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        self.bank.retrieve(mock_llm, "测试查询", k=1)

        prompt = mock_llm.call_args[0][0]

        # 验证详细的评估指导
        assert "评分范围：0.0-1.0，保留两位小数" in prompt

        # 验证语义相关性指导 - 使用实际存在的文本
        assert "完全匹配，记忆直接回答了查询中的问题" in prompt
        assert "高度相关，记忆包含查询所需的核心信息" in prompt
        assert "中等相关，记忆包含部分相关信息" in prompt
        assert "低度相关，只有少量关联" in prompt
        assert "完全不相关" in prompt

        # 验证任务适用性指导
        assert "完全适用，可以直接应用解决方案" in prompt
        assert "高度适用，需要少量调整" in prompt
        assert "中等适用，需要中等程度的调整" in prompt
        assert "低度适用，需要大量修改" in prompt
        assert "完全不适用" in prompt

        # 验证时效性指导
        assert "非常新（最近创建，时效性高）" in prompt
        assert "较新（近期创建）" in prompt
        assert "中等新旧（有一定时间）" in prompt
        assert "较旧（创建时间较长）" in prompt
        assert "非常旧（过时的信息）" in prompt

    def test_prompt_error_prevention(self):
        """测试prompt错误预防提示"""
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        self.bank.retrieve(mock_llm, "测试查询", k=1)

        prompt = mock_llm.call_args[0][0]

        # 验证错误预防提示
        assert "必须遵守的规则" in prompt
        assert "错误预防提示" in prompt

        # 验证具体规则
        assert "JSON格式" in prompt
        assert "完整性" in prompt
        assert "评分范围" in prompt
        assert "解释质量" in prompt
        assert "索引对应" in prompt

        # 验证预防提示
        assert "不要排序" in prompt
        assert "不要省略" in prompt
        assert "不要添加" in prompt
        assert "格式正确" in prompt
        assert "数值类型" in prompt

    def test_prompt_with_different_query_lengths(self):
        """测试不同长度查询的prompt生成"""
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        # 测试短查询
        short_query = "Python"
        self.bank.retrieve(mock_llm, short_query, k=1)
        prompt_short = mock_llm.call_args[0][0]
        assert f'"{short_query}"' in prompt_short

        # 重置mock
        mock_llm.reset_mock()
        mock_llm.return_value = json.dumps(mock_response)

        # 测试长查询
        long_query = "如何优化Python代码性能，特别是在处理大数据集时的内存使用和计算效率问题"
        self.bank.retrieve(mock_llm, long_query, k=1)
        prompt_long = mock_llm.call_args[0][0]
        assert f'"{long_query}"' in prompt_long

        # 验证两个prompt都包含完整的结构
        assert "# 记忆检索评估任务" in prompt_short
        assert "# 记忆检索评估任务" in prompt_long

    def test_prompt_with_empty_bank(self):
        """测试空记忆库的prompt生成"""
        empty_bank = MemoryBank()

        # 空记忆库应该直接返回空列表
        mock_llm = Mock()
        results = empty_bank.retrieve(mock_llm, "测试查询", k=1)

        # 验证返回空列表
        assert results == []
        # 验证LLM没有被调用
        assert not mock_llm.called

    def test_prompt_with_single_entry(self):
        """测试只有一个记忆条目的prompt生成"""
        single_bank = MemoryBank()
        single_entry = MemoryEntry("单一条目", "输出", "反馈", "tag")
        single_bank.add(single_entry)

        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        single_bank.retrieve(mock_llm, "测试查询", k=1)

        prompt = mock_llm.call_args[0][0]

        # 验证包含正确的条目数量
        assert "共1个" in prompt
        assert "索引0到0" in prompt
        assert "单一条目" in prompt

    def test_prompt_backward_compatibility(self):
        """测试prompt向后兼容性"""
        # 验证prompt仍然包含原有的核心要素
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.5,
                    "semantic_relevance": 0.5,
                    "task_applicability": 0.5,
                    "timeliness": 0.5,
                    "explanation": "测试"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        self.bank.retrieve(mock_llm, "测试查询", k=1)

        prompt = mock_llm.call_args[0][0]

        # 验证仍然包含原有的核心要素
        assert "你是一个专业的记忆检索器" in prompt
        assert "JSON格式" in prompt
        assert "results" in prompt
        assert "relevance_score" in prompt
        assert "semantic_relevance" in prompt
        assert "task_applicability" in prompt
        assert "timeliness" in prompt
        assert "explanation" in prompt

    def test_prompt_performance(self):
        """测试prompt生成性能"""
        import time

        # 创建大量记忆条目
        large_bank = MemoryBank(max_entries=100)
        for i in range(50):
            entry = MemoryEntry(f"任务{i}", f"输出{i}", f"反馈{i}", f"tag{i}")
            large_bank.add(entry)

        mock_llm = Mock()
        mock_response = {"results": []}
        mock_llm.return_value = json.dumps(mock_response)

        # 测量prompt生成时间
        start_time = time.time()
        large_bank.retrieve(mock_llm, "性能测试查询", k=5)
        end_time = time.time()

        generation_time = end_time - start_time

        # 验证prompt生成在合理时间内完成（小于1秒）
        assert generation_time < 1.0, f"Prompt生成时间过长: {generation_time:.3f}秒"

        # 验证prompt包含所有条目
        prompt = mock_llm.call_args[0][0]
        assert "任务0" in prompt
        assert "任务49" in prompt
        assert "共50个" in prompt