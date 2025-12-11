"""
增强版MemoryBank测试
"""

import pytest
import sys
import os
import json

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from memory.entry import MemoryEntry
from memory.bank import MemoryBank
from datetime import datetime


class TestEnhancedMemoryBank:
    """增强版MemoryBank测试"""

    def setup_method(self):
        """测试设置"""
        self.bank = MemoryBank(max_entries=10)
        self.entry1 = MemoryEntry("任务1", "输出1", "反馈1", "tag1")
        self.entry2 = MemoryEntry("任务2", "输出2", "反馈2", "tag2")
        self.entry3 = MemoryEntry("任务3", "输出3", "反馈3", "tag3")
        self.entry4 = MemoryEntry("任务4", "输出4", "反馈4", "tag4")

    def test_add_validation(self):
        """测试添加操作的验证"""
        # 测试正常添加
        self.bank.add(self.entry1)
        assert len(self.bank) == 1

        # 测试无效参数类型
        with pytest.raises(ValueError, match="必须是MemoryEntry实例"):
            self.bank.add("不是MemoryEntry")

        with pytest.raises(ValueError, match="必须是MemoryEntry实例"):
            self.bank.add({"x": "任务", "y": "输出"})

    def test_delete_validation(self):
        """测试删除操作的验证"""
        # 先添加一些条目
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

        # 测试正常删除
        self.bank.delete([1])
        assert len(self.bank) == 2
        assert self.bank[0] == self.entry1
        assert self.bank[1] == self.entry3

        # 测试无效参数类型
        with pytest.raises(ValueError, match="必须是列表"):
            self.bank.delete("不是列表")

        with pytest.raises(ValueError, match="必须是整数"):
            self.bank.delete(["不是整数"])

        # 测试索引超出范围
        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.delete([10])

        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.delete([-1])

        # 测试空索引列表
        self.bank.delete([])
        assert len(self.bank) == 2  # 应该没有变化

        # 测试多个索引删除
        self.bank.delete([0, 1])
        assert len(self.bank) == 0

    def test_merge_validation(self):
        """测试合并操作的验证"""
        # 先添加一些条目
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

        # 测试正常合并
        self.bank.merge(0, 1)
        assert len(self.bank) == 2
        merged = self.bank[0]
        assert "任务1" in merged.x
        assert "任务2" in merged.x

        # 测试无效参数类型
        with pytest.raises(ValueError, match="必须是整数"):
            self.bank.merge("不是整数", 1)

        with pytest.raises(ValueError, match="必须是整数"):
            self.bank.merge(0, "不是整数")

        # 测试索引超出范围
        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.merge(10, 1)

        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.merge(0, 10)

        # 测试合并同一个索引
        with pytest.raises(ValueError, match="不能合并同一个索引"):
            self.bank.merge(0, 0)

    def test_relabel_validation(self):
        """测试重标记操作的验证"""
        # 先添加一个条目
        self.bank.add(self.entry1)

        # 测试正常重标记
        self.bank.relabel(0, "new-tag")
        assert self.bank[0].tag == "new-tag"

        # 测试无效参数类型
        with pytest.raises(ValueError, match="必须是整数"):
            self.bank.relabel("不是整数", "tag")

        with pytest.raises(ValueError, match="必须是字符串"):
            self.bank.relabel(0, 123)

        # 测试索引超出范围
        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.relabel(10, "tag")

        # 测试空标签
        with pytest.raises(ValueError, match="不能为空"):
            self.bank.relabel(0, "")

        with pytest.raises(ValueError, match="不能为空"):
            self.bank.relabel(0, "   ")

    def test_batch_operations(self):
        """测试批量操作"""
        # 准备批量操作
        operations = [
            {
                "type": "add",
                "params": {"entry": self.entry1.to_dict()}
            },
            {
                "type": "add",
                "params": {"entry": self.entry2.to_dict()}
            },
            {
                "type": "add",
                "params": {"entry": self.entry3.to_dict()}
            },
            {
                "type": "delete",
                "params": {"indices": [0]}
            },
            {
                "type": "merge",
                "params": {"idx1": 0, "idx2": 1}
            },
            {
                "type": "relabel",
                "params": {"idx": 0, "new_tag": "batch-tag"}
            }
        ]

        # 执行批量操作
        results = self.bank.batch_operations(operations)

        assert results["total_operations"] == 6
        assert results["successful"] == 6
        assert results["failed"] == 0
        assert len(results["errors"]) == 0

        # 验证结果
        assert len(self.bank) == 1
        assert "batch-tag" in self.bank[0].tag

    def test_batch_operations_with_errors(self):
        """测试包含错误的批量操作"""
        # 先添加一个条目
        self.bank.add(self.entry1)

        # 准备包含错误的批量操作
        operations = [
            {
                "type": "add",
                "params": {"entry": self.entry2.to_dict()}
            },
            {
                "type": "delete",
                "params": {"indices": [10]}  # 无效索引
            },
            {
                "type": "unknown",  # 未知操作类型
                "params": {}
            },
            {
                "type": "merge",
                "params": {"idx1": 0, "idx2": 1}  # 有效操作
            }
        ]

        # 执行批量操作
        results = self.bank.batch_operations(operations)

        assert results["total_operations"] == 4
        assert results["successful"] == 2  # add和merge成功
        assert results["failed"] == 2  # delete和unknown失败
        assert len(results["errors"]) == 2

        # 验证错误信息
        assert results["errors"][0]["operation_index"] == 1
        assert "索引超出范围" in results["errors"][0]["error"]

        assert results["errors"][1]["operation_index"] == 2
        assert "未知操作类型" in results["errors"][1]["error"]

    def test_operation_history(self):
        """测试操作历史记录"""
        # 执行一些操作
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.delete([0])
        self.bank.relabel(0, "new-tag")

        # 获取操作历史
        history = self.bank.get_operation_history()
        assert len(history) == 4

        # 检查操作类型
        op_types = [op["operation_type"] for op in history]
        assert op_types == ["add", "add", "delete", "relabel"]

        # 检查操作详情
        add_op = history[0]
        assert add_op["operation_type"] == "add"
        assert "entry_id" in add_op["details"]
        assert add_op["success"] is True

        delete_op = history[2]
        assert delete_op["operation_type"] == "delete"
        assert "indices" in delete_op["details"]
        assert delete_op["details"]["deleted_count"] == 1

        # 测试限制返回数量
        limited_history = self.bank.get_operation_history(limit=2)
        assert len(limited_history) == 2
        assert limited_history[0]["operation_type"] == "delete"
        assert limited_history[1]["operation_type"] == "relabel"

    def test_clear_operation_history(self):
        """测试清空操作历史"""
        # 执行一些操作
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)

        # 检查历史记录
        history = self.bank.get_operation_history()
        assert len(history) == 2

        # 清空历史记录
        self.bank.clear_operation_history()
        history = self.bank.get_operation_history()
        assert len(history) == 0

        # 继续执行操作
        self.bank.delete([0])
        history = self.bank.get_operation_history()
        assert len(history) == 1
        assert history[0]["operation_type"] == "delete"

    def test_prune_with_history(self):
        """测试清理操作的历史记录"""
        # 添加足够多的条目以触发清理
        for i in range(15):
            entry = MemoryEntry(f"任务{i}", f"输出{i}", f"反馈{i}", f"tag{i}")
            self.bank.add(entry)

        # 检查是否触发了清理
        history = self.bank.get_operation_history()
        prune_ops = [op for op in history if op["operation_type"] == "prune"]

        if prune_ops:
            prune_op = prune_ops[-1]
            assert "original_count" in prune_op["details"]
            assert "deleted_count" in prune_op["details"]
            assert "remaining_count" in prune_op["details"]
            assert prune_op["success"] is True

    def test_statistics_with_history(self):
        """测试包含历史记录的统计信息"""
        # 执行一些操作
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.delete([0])

        # 获取统计信息
        stats = self.bank.get_statistics()

        assert stats["total_entries"] == 1
        assert stats["max_entries"] == 10
        assert "operation_history_count" in stats
        assert stats["operation_history_count"] == 3

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空记忆库的操作
        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.delete([0])

        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.merge(0, 1)

        with pytest.raises(IndexError, match="索引超出范围"):
            self.bank.relabel(0, "tag")

        # 测试批量操作空列表
        results = self.bank.batch_operations([])
        assert results["total_operations"] == 0
        assert results["successful"] == 0
        assert results["failed"] == 0
        assert len(results["errors"]) == 0

        # 测试获取空历史记录
        history = self.bank.get_operation_history()
        assert len(history) == 0

    def test_concurrent_operations(self):
        """测试连续操作对索引的影响"""
        # 添加多个条目
        entries = []
        for i in range(5):
            entry = MemoryEntry(f"任务{i}", f"输出{i}", f"反馈{i}", f"tag{i}")
            entries.append(entry)
            self.bank.add(entry)

        # 执行一系列操作
        self.bank.delete([1, 3])  # 删除索引1和3
        assert len(self.bank) == 3

        # 验证剩余条目的正确性
        # 原始索引: 0,1,2,3,4
        # 删除索引1和3后: 0,2,4
        assert self.bank[0].x == "任务0"
        assert self.bank[1].x == "任务2"
        assert self.bank[2].x == "任务4"

        # 合并剩余的两个条目
        self.bank.merge(0, 1)
        assert len(self.bank) == 2

        # 重标记最后一个条目
        self.bank.relabel(1, "final-tag")
        assert self.bank[1].tag == "final-tag"