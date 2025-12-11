"""
PM-112: 多维度评分机制测试
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


class TestPM112ScoreValidation:
    """PM-112: 多维度评分机制测试"""

    def setup_method(self):
        """测试设置"""
        self.bank = MemoryBank(max_entries=10)

    def test_valid_score_parsing(self):
        """测试有效评分的解析"""
        # 测试各种有效评分
        test_cases = [
            # (评分值, 期望结果)
            (0.0, 0.0),
            (0.5, 0.5),
            (1.0, 1.0),
            (0.75, 0.75),
            (0.333, 0.33),  # 四舍五入
            (0.666, 0.67),  # 四舍五入
            ("0.5", 0.5),   # 字符串数字
            ("0.75", 0.75), # 字符串数字
            ("1", 1.0),     # 整数字符串
            (1, 1.0),       # 整数
        ]

        for score_value, expected in test_cases:
            item = {"relevance_score": score_value}
            result = self.bank._validate_and_parse_score(item, "relevance_score")
            assert result == expected, f"评分解析失败: {score_value} -> {result}, 期望: {expected}"

    def test_invalid_score_handling(self):
        """测试无效评分的处理"""
        # 测试各种无效评分
        test_cases = [
            # (评分值, 默认值, 期望结果)
            (None, 0.5, 0.5),          # None值
            ("", 0.3, 0.3),            # 空字符串
            ("   ", 0.4, 0.4),         # 空白字符串
            ("invalid", 0.5, 0.5),     # 无效字符串
            ([1, 2], 0.5, 0.5),        # 列表类型
            ({"key": "value"}, 0.5, 0.5),  # 字典类型
        ]

        for score_value, default, expected in test_cases:
            item = {"relevance_score": score_value}
            result = self.bank._validate_and_parse_score(item, "relevance_score", default)
            assert result == expected, f"无效评分处理失败: {score_value} -> {result}, 期望: {expected}"

    def test_score_range_validation(self):
        """测试评分范围验证"""
        # 测试超出范围的评分
        test_cases = [
            # (评分值, 期望结果)
            (-0.1, 0.0),    # 轻微负分修正为0.0
            (-1.0, 0.0),    # 严重负分修正为0.0
            (1.1, 1.0),     # 轻微超分修正为1.0
            (2.0, 1.0),     # 严重超分修正为1.0
            (-0.5, 0.0),    # 负分修正为0.0
        ]

        for score_value, expected in test_cases:
            item = {"relevance_score": score_value}
            result = self.bank._validate_and_parse_score(item, "relevance_score")
            assert result == expected, f"范围验证失败: {score_value} -> {result}, 期望: {expected}"

    def test_edge_case_score_correction(self):
        """测试边界情况评分修正"""
        # 测试边界值的修正
        test_cases = [
            # (评分值, 期望结果)
            (-0.001, 0.0),   # 轻微负分修正为0.0
            (1.001, 1.0),    # 轻微超分修正为1.0
            (-0.0, 0.0),     # 负零
            (0.9999, 1.0),   # 四舍五入到1.0
            (0.0001, 0.0),   # 四舍五入到0.0
        ]

        for score_value, expected in test_cases:
            item = {"relevance_score": score_value}
            result = self.bank._validate_and_parse_score(item, "relevance_score")
            assert abs(result - expected) < 0.01, f"边界修正失败: {score_value} -> {result}, 期望: {expected}"

    def test_multiple_score_dimensions(self):
        """测试多维度评分解析"""
        # 测试同时解析多个评分维度
        item = {
            "relevance_score": 0.85,
            "semantic_relevance": 0.9,
            "task_applicability": 0.8,
            "timeliness": 0.7,
            "explanation": "测试解释"
        }

        # 解析各个维度
        relevance = self.bank._validate_and_parse_score(item, "relevance_score")
        semantic = self.bank._validate_and_parse_score(item, "semantic_relevance", 0.0)
        task = self.bank._validate_and_parse_score(item, "task_applicability", 0.0)
        time = self.bank._validate_and_parse_score(item, "timeliness", 0.0)

        assert relevance == 0.85
        assert semantic == 0.9
        assert task == 0.8
        assert time == 0.7

    def test_missing_score_field(self):
        """测试缺失评分字段的处理"""
        item = {
            "semantic_relevance": 0.9,
            "task_applicability": 0.8,
            # 缺少relevance_score
        }

        # 使用默认值
        result = self.bank._validate_and_parse_score(item, "relevance_score", 0.5)
        assert result == 0.5

        # 使用不同的默认值
        result = self.bank._validate_and_parse_score(item, "relevance_score", 0.3)
        assert result == 0.3

    def test_score_precision(self):
        """测试评分精度处理"""
        # 测试保留两位小数
        test_cases = [
            (0.123456, 0.12),
            (0.987654, 0.99),
            (0.555555, 0.56),
            (0.444444, 0.44),
            (0.999999, 1.0),
            (0.000001, 0.0),
        ]

        for score_value, expected in test_cases:
            item = {"relevance_score": score_value}
            result = self.bank._validate_and_parse_score(item, "relevance_score")
            assert result == expected, f"精度处理失败: {score_value} -> {result}, 期望: {expected}"

    def test_relevance_score_consistency_check(self):
        """测试总体相关性评分一致性检查"""
        # 测试评分一致性检查
        item = {
            "relevance_score": 0.85,
            "semantic_relevance": 0.9,
            "task_applicability": 0.8,
            "timeliness": 0.7
        }

        # 计算期望的加权评分
        expected = 0.5 * 0.9 + 0.3 * 0.8 + 0.2 * 0.7  # = 0.45 + 0.24 + 0.14 = 0.83
        expected = round(expected, 2)  # 0.83

        # 解析评分（应该记录差异警告）
        result = self.bank._validate_and_parse_score(item, "relevance_score")

        # 实际评分0.85与期望0.83差异为0.02，小于0.2阈值，应该通过
        assert abs(result - expected) < 0.2

    def test_relevance_score_large_discrepancy(self):
        """测试总体相关性评分大差异情况"""
        # 测试评分差异较大的情况（应该记录警告）
        item = {
            "relevance_score": 0.5,      # 实际评分
            "semantic_relevance": 0.9,   # 语义相关性高
            "task_applicability": 0.8,   # 任务适用性高
            "timeliness": 0.7            # 时效性中等
        }

        # 计算期望的加权评分
        expected = 0.5 * 0.9 + 0.3 * 0.8 + 0.2 * 0.7  # = 0.45 + 0.24 + 0.14 = 0.83
        expected = round(expected, 2)  # 0.83

        # 实际评分0.5与期望0.83差异为0.33，大于0.2阈值
        # 应该记录警告但返回实际评分
        result = self.bank._validate_and_parse_score(item, "relevance_score")
        assert result == 0.5

    def test_invalid_default_value(self):
        """测试无效默认值的处理"""
        item = {"relevance_score": "invalid"}

        # 测试无效默认值（超出范围）
        result = self.bank._validate_and_parse_score(item, "relevance_score", 1.5)
        assert result == 0.5  # 应该修正为0.5

        # 测试无效默认值（负值）
        result = self.bank._validate_and_parse_score(item, "relevance_score", -0.5)
        assert result == 0.5  # 应该修正为0.5

        # 测试无效默认值（非数字）
        result = self.bank._validate_and_parse_score(item, "relevance_score", "invalid")
        assert result == 0.5  # 应该修正为0.5

    def test_parameter_validation(self):
        """测试参数验证"""
        # 测试无效item参数
        with pytest.raises(ValueError, match="评分项必须是字典"):
            self.bank._validate_and_parse_score("not a dict", "relevance_score")

        # 测试无效score_key参数
        with pytest.raises(ValueError, match="评分键名必须是非空字符串"):
            self.bank._validate_and_parse_score({}, "")

        with pytest.raises(ValueError, match="评分键名必须是非空字符串"):
            self.bank._validate_and_parse_score({}, None)

    def test_integration_with_retrieval(self):
        """测试与检索功能的集成"""
        # 创建测试记忆条目
        entry1 = MemoryEntry("任务1", "输出1", "反馈1", "tag1")
        entry2 = MemoryEntry("任务2", "输出2", "反馈2", "tag2")
        self.bank.add(entry1)
        self.bank.add(entry2)

        # 模拟LLM返回包含各种评分的响应
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.85,
                    "semantic_relevance": 0.9,
                    "task_applicability": 0.8,
                    "timeliness": 0.7,
                    "explanation": "高度相关"
                },
                {
                    "index": 1,
                    "relevance_score": "0.65",  # 字符串评分
                    "semantic_relevance": 0.7,
                    "task_applicability": 0.6,
                    "timeliness": 0.5,
                    "explanation": "中等相关"
                }
            ]
        }
        mock_llm.return_value = json.dumps(mock_response)

        # 执行检索
        results = self.bank.retrieve(mock_llm, "测试查询", k=2)

        # 验证结果
        assert len(results) == 2
        assert results[0].relevance_score == 0.85
        assert results[1].relevance_score == 0.65

    def test_error_recovery(self):
        """测试错误恢复机制"""
        # 测试部分评分无效的情况
        item = {
            "relevance_score": 0.85,
            "semantic_relevance": "invalid",  # 无效评分
            "task_applicability": 0.8,
            "timeliness": None  # None值
        }

        # 应该能成功解析有效评分，无效评分使用默认值
        relevance = self.bank._validate_and_parse_score(item, "relevance_score")
        semantic = self.bank._validate_and_parse_score(item, "semantic_relevance", 0.0)
        task = self.bank._validate_and_parse_score(item, "task_applicability", 0.0)
        time = self.bank._validate_and_parse_score(item, "timeliness", 0.0)

        assert relevance == 0.85
        assert semantic == 0.0  # 使用默认值
        assert task == 0.8
        assert time == 0.0  # 使用默认值

    def test_performance_with_large_dataset(self):
        """测试大数据集下的性能"""
        import time

        # 创建大量测试数据
        test_items = []
        for i in range(1000):
            item = {
                "relevance_score": i / 1000.0,
                "semantic_relevance": (i % 100) / 100.0,
                "task_applicability": ((i + 1) % 100) / 100.0,
                "timeliness": ((i + 2) % 100) / 100.0
            }
            test_items.append(item)

        # 测量解析性能
        start_time = time.time()

        for item in test_items:
            self.bank._validate_and_parse_score(item, "relevance_score")
            self.bank._validate_and_parse_score(item, "semantic_relevance", 0.0)
            self.bank._validate_and_parse_score(item, "task_applicability", 0.0)
            self.bank._validate_and_parse_score(item, "timeliness", 0.0)

        end_time = time.time()
        processing_time = end_time - start_time

        # 验证性能（1000个条目应该在1秒内完成）
        assert processing_time < 1.0, f"评分解析性能不足: {processing_time:.3f}秒"

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        # 确保原有功能仍然工作
        item = {"relevance_score": 0.75}

        # 原有调用方式应该仍然工作
        result = self.bank._validate_and_parse_score(item, "relevance_score")
        assert result == 0.75

        # 原有默认值应该仍然工作
        item2 = {}
        result = self.bank._validate_and_parse_score(item2, "relevance_score", 0.5)
        assert result == 0.5

    def test_logging_behavior(self):
        """测试日志记录行为"""
        import logging
        from io import StringIO

        # 设置日志捕获
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)

        # 获取bank的logger并添加handler
        bank_logger = logging.getLogger("memory.bank")
        original_handlers = bank_logger.handlers[:]
        bank_logger.handlers = [handler]
        bank_logger.setLevel(logging.DEBUG)

        try:
            # 测试正常情况下的日志
            item = {"relevance_score": 0.85}
            self.bank._validate_and_parse_score(item, "relevance_score")

            logs = log_capture.getvalue()
            assert "成功解析" in logs or "relevance_score" in logs

            # 清空日志
            log_capture.truncate(0)
            log_capture.seek(0)

            # 测试错误情况下的日志
            item2 = {"relevance_score": "invalid"}
            self.bank._validate_and_parse_score(item2, "relevance_score")

            logs = log_capture.getvalue()
            assert "无法将" in logs or "invalid" in logs or "使用默认值" in logs

        finally:
            # 恢复原始handlers
            bank_logger.handlers = original_handlers