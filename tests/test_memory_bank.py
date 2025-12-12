"""
MemoryBank单元测试
"""

import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.memory.bank import MemoryBank
from src.memory.entry import MemoryEntry
from src.memory.retrieval_result import RetrievalResult


class TestMemoryBank(unittest.TestCase):
    """MemoryBank类单元测试"""

    def setUp(self):
        """测试前准备"""
        self.bank = MemoryBank(max_entries=10)

        # 创建测试记忆条目
        self.entry1 = MemoryEntry(
            x="如何配置Python环境",
            y="使用venv创建虚拟环境：python -m venv myenv",
            feedback="配置成功，项目可以正常运行",
            tag="python",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            id="entry-1"
        )

        self.entry2 = MemoryEntry(
            x="如何安装依赖包",
            y="使用pip install package_name",
            feedback="包安装成功，功能正常",
            tag="python",
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            id="entry-2"
        )

        self.entry3 = MemoryEntry(
            x="如何调试代码",
            y="使用print语句或调试器",
            feedback="找到并修复了bug",
            tag="debugging",
            timestamp=datetime(2024, 1, 3, 10, 0, 0),
            id="entry-3"
        )

        # 添加条目到记忆库
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

    def test_initialization(self):
        """测试初始化"""
        bank = MemoryBank(max_entries=100)
        self.assertEqual(bank.max_entries, 100)
        self.assertEqual(len(bank), 0)
        self.assertEqual(len(bank.operation_history), 0)

    def test_add_entry(self):
        """测试添加记忆条目"""
        bank = MemoryBank(max_entries=5)

        # 测试正常添加
        bank.add(self.entry1)
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank[0], self.entry1)

        # 测试添加非MemoryEntry对象
        with self.assertRaises(ValueError):
            bank.add("not-an-entry")

        # 测试操作历史记录
        history = bank.get_operation_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["operation_type"], "add")

    def test_add_entry_alias(self):
        """测试add_entry别名方法"""
        bank = MemoryBank()
        bank.add_entry(self.entry1)
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank[0], self.entry1)

    def test_delete_by_indices(self):
        """测试按索引删除"""
        # 删除第一个条目
        self.bank.delete([0])
        self.assertEqual(len(self.bank), 2)
        self.assertEqual(self.bank[0].id, "entry-2")

        # 删除多个条目
        self.bank.delete([0, 1])
        self.assertEqual(len(self.bank), 0)

        # 测试无效索引
        with self.assertRaises(IndexError):
            self.bank.delete([10])

        # 测试无效参数类型
        with self.assertRaises(ValueError):
            self.bank.delete("not-a-list")

    def test_delete_entry_by_id(self):
        """测试按ID删除"""
        # 删除存在的条目
        result = self.bank.delete_entry("entry-1")
        self.assertTrue(result)
        self.assertEqual(len(self.bank), 2)

        # 删除不存在的条目
        result = self.bank.delete_entry("non-existent")
        self.assertFalse(result)
        self.assertEqual(len(self.bank), 2)

    def test_get_entry(self):
        """测试获取条目"""
        # 获取存在的条目
        entry = self.bank.get_entry("entry-1")
        self.assertEqual(entry, self.entry1)

        # 获取不存在的条目
        entry = self.bank.get_entry("non-existent")
        self.assertIsNone(entry)

    def test_update_entry(self):
        """测试更新条目"""
        # 更新存在的条目
        result = self.bank.update_entry(
            "entry-1",
            x="更新后的任务输入",
            tag="updated-tag"
        )
        self.assertTrue(result)

        updated_entry = self.bank.get_entry("entry-1")
        self.assertEqual(updated_entry.x, "更新后的任务输入")
        self.assertEqual(updated_entry.tag, "updated-tag")
        self.assertEqual(updated_entry.y, self.entry1.y)  # 未修改的字段保持不变

        # 更新不存在的条目
        result = self.bank.update_entry("non-existent", x="new")
        self.assertFalse(result)

        # 测试操作历史记录
        history = self.bank.get_operation_history()
        self.assertEqual(history[-1]["operation_type"], "update")

    def test_merge_entries(self):
        """测试合并条目"""
        # 合并两个条目
        self.bank.merge(0, 1)

        self.assertEqual(len(self.bank), 2)  # 合并后减少一个条目

        merged_entry = self.bank[0]
        self.assertIn("merged", merged_entry.tag)
        self.assertIn("python", merged_entry.tag)

        # 测试无效索引
        with self.assertRaises(IndexError):
            self.bank.merge(0, 10)

        # 测试相同索引
        with self.assertRaises(ValueError):
            self.bank.merge(0, 0)

    def test_relabel_entry(self):
        """测试重新标记"""
        # 重新标记
        self.bank.relabel(0, "new-label")

        self.assertEqual(self.bank[0].tag, "new-label")

        # 测试无效标签
        with self.assertRaises(ValueError):
            self.bank.relabel(0, "")

        # 测试无效索引
        with self.assertRaises(IndexError):
            self.bank.relabel(10, "new-label")

    def test_search(self):
        """测试搜索功能"""
        # 搜索存在的关键词
        results = self.bank.search("Python")
        self.assertEqual(len(results), 2)  # entry1和entry2都包含Python相关内容

        # 搜索不存在的关键词
        results = self.bank.search("nonexistent")
        self.assertEqual(len(results), 0)

        # 搜索空查询
        results = self.bank.search("")
        self.assertEqual(len(results), 0)

        # 测试大小写不敏感
        results = self.bank.search("python")
        self.assertEqual(len(results), 2)

    def test_filter_by_tag(self):
        """测试按标签过滤"""
        # 过滤存在的标签
        python_entries = self.bank.filter_by_tag("python")
        self.assertEqual(len(python_entries), 2)

        debugging_entries = self.bank.filter_by_tag("debugging")
        self.assertEqual(len(debugging_entries), 1)

        # 过滤不存在的标签
        no_entries = self.bank.filter_by_tag("nonexistent")
        self.assertEqual(len(no_entries), 0)

        # 过滤空标签
        empty_entries = self.bank.filter_by_tag("")
        self.assertEqual(len(empty_entries), 0)

    def test_get_recent_entries(self):
        """测试获取最近条目"""
        # 添加更多条目
        for i in range(4, 8):
            entry = MemoryEntry(
                x=f"任务{i}",
                y=f"输出{i}",
                feedback=f"反馈{i}",
                tag=f"tag{i}",
                timestamp=datetime(2024, 1, i, 10, 0, 0)
            )
            self.bank.add(entry)

        # 获取最近3个条目
        recent = self.bank.get_recent_entries(3)
        self.assertEqual(len(recent), 3)

        # 检查时间顺序（最新的在前）
        self.assertEqual(recent[0].tag, "tag7")
        self.assertEqual(recent[1].tag, "tag6")
        self.assertEqual(recent[2].tag, "tag5")

    def test_clear(self):
        """测试清空记忆库"""
        self.bank.clear()
        self.assertEqual(len(self.bank), 0)

        # 检查操作历史记录
        history = self.bank.get_operation_history()
        self.assertEqual(history[-1]["operation_type"], "clear")

    def test_get_statistics(self):
        """测试获取统计信息"""
        stats = self.bank.get_statistics()

        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["max_entries"], 10)
        self.assertIn("python", stats["tag_distribution"])
        self.assertEqual(stats["tag_distribution"]["python"], 2)
        self.assertEqual(stats["tag_distribution"]["debugging"], 1)

        # 测试空记忆库
        empty_bank = MemoryBank()
        empty_stats = empty_bank.get_statistics()
        self.assertEqual(empty_stats["total_entries"], 0)
        self.assertEqual(empty_stats["tag_distribution"], {})

    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        # 序列化
        data = self.bank.to_dict()
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["id"], "entry-1")

        # 反序列化
        new_bank = MemoryBank.from_dict(data, max_entries=20)
        self.assertEqual(len(new_bank), 3)
        self.assertEqual(new_bank.max_entries, 20)
        self.assertEqual(new_bank[0].id, "entry-1")

        # 测试无效数据
        invalid_data = [{"invalid": "data"}]
        invalid_bank = MemoryBank.from_dict(invalid_data)
        self.assertEqual(len(invalid_bank), 0)  # 应该跳过无效条目

    def test_prune(self):
        """测试清理功能"""
        # 创建达到容量限制的记忆库
        bank = MemoryBank(max_entries=3)

        # 添加4个条目（超过容量）
        for i in range(4):
            entry = MemoryEntry(
                x=f"任务{i}",
                y=f"输出{i}",
                feedback=f"反馈{i}",
                timestamp=datetime(2024, 1, i+1, 10, 0, 0)
            )
            bank.add(entry)

        # 应该触发清理
        self.assertEqual(len(bank), 3)  # 清理后应该只剩3个

        # 检查操作历史记录（最后一条应该是add，倒数第二条应该是prune）
        history = bank.get_operation_history()
        self.assertEqual(history[-2]["operation_type"], "prune")
        self.assertEqual(history[-1]["operation_type"], "add")

    def test_batch_operations(self):
        """测试批量操作"""
        operations = [
            {
                "type": "add",
                "params": {
                    "entry": {
                        "x": "批量任务1",
                        "y": "批量输出1",
                        "feedback": "批量反馈1",
                        "tag": "batch"
                    }
                }
            },
            {
                "type": "relabel",
                "params": {
                    "idx": 0,
                    "new_tag": "relabeled"
                }
            },
            {
                "type": "delete",
                "params": {
                    "indices": [0]
                }
            }
        ]

        results = self.bank.batch_operations(operations)

        self.assertEqual(results["total_operations"], 3)
        self.assertEqual(results["successful"], 3)
        self.assertEqual(results["failed"], 0)

        # 测试包含失败操作的批量操作
        invalid_operations = [
            {
                "type": "add",
                "params": {}  # 缺少entry参数
            }
        ]

        results = self.bank.batch_operations(invalid_operations)
        self.assertEqual(results["failed"], 1)
        self.assertEqual(len(results["errors"]), 1)

    def test_retrieve_with_mock_llm(self):
        """测试检索功能（使用模拟LLM）"""
        # 创建模拟LLM
        mock_llm = Mock()
        mock_response = {
            "results": [
                {
                    "index": 0,
                    "relevance_score": 0.9,
                    "semantic_relevance": 0.95,
                    "task_applicability": 0.85,
                    "timeliness": 0.8,
                    "explanation": "高度相关"
                },
                {
                    "index": 1,
                    "relevance_score": 0.7,
                    "semantic_relevance": 0.75,
                    "task_applicability": 0.65,
                    "timeliness": 0.7,
                    "explanation": "中等相关"
                },
                {
                    "index": 2,
                    "relevance_score": 0.3,
                    "semantic_relevance": 0.35,
                    "task_applicability": 0.25,
                    "timeliness": 0.3,
                    "explanation": "低度相关"
                }
            ]
        }

        mock_llm.return_value = json.dumps(mock_response)

        # 测试检索
        results = self.bank.retrieve(mock_llm, "Python环境配置", k=2)

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], RetrievalResult)
        self.assertEqual(results[0].relevance_score, 0.9)
        self.assertEqual(results[1].relevance_score, 0.7)

        # 测试不包含解释的检索
        results = self.bank.retrieve(mock_llm, "Python", k=1, include_explanations=False)
        self.assertIsInstance(results[0], MemoryEntry)

    def test_retrieve_empty_bank(self):
        """测试空记忆库检索"""
        empty_bank = MemoryBank()
        mock_llm = Mock()

        results = empty_bank.retrieve(mock_llm, "查询")
        self.assertEqual(len(results), 0)

        # LLM不应该被调用
        mock_llm.assert_not_called()

    def test_retrieve_invalid_k(self):
        """测试无效k值检索"""
        mock_llm = Mock()

        # k=0
        results = self.bank.retrieve(mock_llm, "查询", k=0)
        self.assertEqual(len(results), 0)

        # k为负数
        results = self.bank.retrieve(mock_llm, "查询", k=-1)
        self.assertEqual(len(results), 0)

        # k大于记忆库大小
        results = self.bank.retrieve(mock_llm, "查询", k=10)
        self.assertEqual(len(results), 3)

    def test_operation_history(self):
        """测试操作历史记录"""
        # 执行一些操作
        self.bank.add(MemoryEntry(x="新任务", y="新输出", feedback="新反馈"))
        self.bank.delete([0])
        self.bank.clear_operation_history()

        # 检查历史记录是否被清空
        history = self.bank.get_operation_history()
        self.assertEqual(len(history), 0)

    def test_len_and_getitem(self):
        """测试长度和索引访问"""
        self.assertEqual(len(self.bank), 3)
        self.assertEqual(self.bank[0], self.entry1)
        self.assertEqual(self.bank[1], self.entry2)
        self.assertEqual(self.bank[2], self.entry3)

        # 测试索引越界
        with self.assertRaises(IndexError):
            _ = self.bank[10]

    def test_str_representation(self):
        """测试字符串表示"""
        # 测试__repr__方法
        repr_str = repr(self.bank)
        self.assertIn("MemoryBank", repr_str)
        self.assertIn("entries=3", repr_str)


if __name__ == "__main__":
    unittest.main()