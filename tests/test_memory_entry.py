"""
MemoryEntry单元测试
"""

import unittest
from datetime import datetime
from src.memory.entry import MemoryEntry


class TestMemoryEntry(unittest.TestCase):
    """MemoryEntry类单元测试"""

    def setUp(self):
        """测试前准备"""
        self.test_entry = MemoryEntry(
            x="测试任务输入",
            y="测试智能体输出",
            feedback="测试环境反馈",
            tag="test",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            id="test-id-123"
        )

    def test_initialization(self):
        """测试初始化"""
        entry = MemoryEntry(
            x="任务输入",
            y="智能体输出",
            feedback="环境反馈",
            tag="test-tag"
        )

        self.assertEqual(entry.x, "任务输入")
        self.assertEqual(entry.y, "智能体输出")
        self.assertEqual(entry.feedback, "环境反馈")
        self.assertEqual(entry.tag, "test-tag")
        self.assertIsInstance(entry.id, str)
        self.assertIsInstance(entry.timestamp, datetime)

    def test_property_getters(self):
        """测试属性getter方法"""
        self.assertEqual(self.test_entry.id, "test-id-123")
        self.assertEqual(self.test_entry.x, "测试任务输入")
        self.assertEqual(self.test_entry.y, "测试智能体输出")
        self.assertEqual(self.test_entry.feedback, "测试环境反馈")
        self.assertEqual(self.test_entry.tag, "test")
        self.assertEqual(self.test_entry.timestamp, datetime(2024, 1, 1, 12, 0, 0))

    def test_property_setters(self):
        """测试属性setter方法"""
        # 测试正常设置
        self.test_entry.x = "新的任务输入"
        self.assertEqual(self.test_entry.x, "新的任务输入")

        self.test_entry.y = "新的智能体输出"
        self.assertEqual(self.test_entry.y, "新的智能体输出")

        self.test_entry.feedback = "新的环境反馈"
        self.assertEqual(self.test_entry.feedback, "新的环境反馈")

        self.test_entry.tag = "new-tag"
        self.assertEqual(self.test_entry.tag, "new-tag")

        new_timestamp = datetime(2024, 1, 2, 12, 0, 0)
        self.test_entry.timestamp = new_timestamp
        self.assertEqual(self.test_entry.timestamp, new_timestamp)

    def test_property_setters_validation(self):
        """测试属性setter验证"""
        # 测试id验证
        with self.assertRaises(TypeError):
            self.test_entry.id = 123  # 类型错误

        with self.assertRaises(ValueError):
            self.test_entry.id = ""  # 空值错误

        # 测试x验证
        with self.assertRaises(TypeError):
            self.test_entry.x = 123

        # 测试y验证
        with self.assertRaises(TypeError):
            self.test_entry.y = 123

        # 测试feedback验证
        with self.assertRaises(TypeError):
            self.test_entry.feedback = 123

        # 测试tag验证
        with self.assertRaises(TypeError):
            self.test_entry.tag = 123

        # 测试timestamp验证
        with self.assertRaises(TypeError):
            self.test_entry.timestamp = "2024-01-01"

    def test_to_text(self):
        """测试to_text方法"""
        text = self.test_entry.to_text()
        self.assertIn("[Task]: 测试任务输入", text)
        self.assertIn("[Action]: 测试智能体输出", text)
        self.assertIn("[Feedback]: 测试环境反馈", text)
        self.assertIn("[Tag]: test", text)
        self.assertIn("[Timestamp]: 2024-01-01T12:00:00", text)

    def test_to_dict(self):
        """测试to_dict方法"""
        data = self.test_entry.to_dict()
        self.assertEqual(data["id"], "test-id-123")
        self.assertEqual(data["x"], "测试任务输入")
        self.assertEqual(data["y"], "测试智能体输出")
        self.assertEqual(data["feedback"], "测试环境反馈")
        self.assertEqual(data["tag"], "test")
        self.assertEqual(data["timestamp"], "2024-01-01T12:00:00")

    def test_from_dict(self):
        """测试from_dict方法"""
        data = {
            "id": "test-id-456",
            "x": "字典任务输入",
            "y": "字典智能体输出",
            "feedback": "字典环境反馈",
            "tag": "dict-test",
            "timestamp": "2024-01-02T12:00:00"
        }

        entry = MemoryEntry.from_dict(data)
        self.assertEqual(entry.id, "test-id-456")
        self.assertEqual(entry.x, "字典任务输入")
        self.assertEqual(entry.y, "字典智能体输出")
        self.assertEqual(entry.feedback, "字典环境反馈")
        self.assertEqual(entry.tag, "dict-test")
        self.assertEqual(entry.timestamp, datetime(2024, 1, 2, 12, 0, 0))

    def test_from_dict_without_timestamp(self):
        """测试from_dict方法（无时间戳）"""
        data = {
            "id": "test-id-789",
            "x": "任务输入",
            "y": "智能体输出",
            "feedback": "环境反馈",
            "tag": "no-timestamp"
        }

        entry = MemoryEntry.from_dict(data)
        # 当timestamp字段不存在时，应该自动生成当前时间
        self.assertIsNotNone(entry.timestamp)
        self.assertIsInstance(entry.timestamp, datetime)

    def test_equality(self):
        """测试相等性比较"""
        entry1 = MemoryEntry(
            x="任务1",
            y="输出1",
            feedback="反馈1",
            id="same-id"
        )

        entry2 = MemoryEntry(
            x="任务2",  # 不同内容
            y="输出2",
            feedback="反馈2",
            id="same-id"  # 相同ID
        )

        entry3 = MemoryEntry(
            x="任务1",
            y="输出1",
            feedback="反馈1",
            id="different-id"  # 不同ID
        )

        self.assertEqual(entry1, entry2)  # ID相同，应该相等
        self.assertNotEqual(entry1, entry3)  # ID不同，应该不相等
        self.assertNotEqual(entry1, "not-an-entry")  # 不同类型，应该不相等

    def test_hash(self):
        """测试哈希函数"""
        entry1 = MemoryEntry(
            x="任务1",
            y="输出1",
            feedback="反馈1",
            id="test-hash-id"
        )

        entry2 = MemoryEntry(
            x="任务2",
            y="输出2",
            feedback="反馈2",
            id="test-hash-id"  # 相同ID
        )

        self.assertEqual(hash(entry1), hash(entry2))

        # 测试可以作为字典键
        test_dict = {entry1: "value"}
        self.assertEqual(test_dict[entry2], "value")

    def test_repr(self):
        """测试字符串表示"""
        repr_str = repr(self.test_entry)
        self.assertIn("MemoryEntry", repr_str)
        self.assertIn("test-id-123", repr_str)
        self.assertIn("test", repr_str)

    def test_serialization_roundtrip(self):
        """测试序列化往返"""
        # 原始对象 -> 字典 -> 新对象
        original = MemoryEntry(
            x="往返测试任务",
            y="往返测试输出",
            feedback="往返测试反馈",
            tag="roundtrip"
        )

        data = original.to_dict()
        restored = MemoryEntry.from_dict(data)

        self.assertEqual(original.id, restored.id)
        self.assertEqual(original.x, restored.x)
        self.assertEqual(original.y, restored.y)
        self.assertEqual(original.feedback, restored.feedback)
        self.assertEqual(original.tag, restored.tag)
        self.assertEqual(original.timestamp, restored.timestamp)

    def test_empty_tag(self):
        """测试空标签"""
        entry = MemoryEntry(
            x="任务",
            y="输出",
            feedback="反馈",
            tag=""  # 空标签
        )
        self.assertEqual(entry.tag, "")

    def test_none_timestamp(self):
        """测试None时间戳"""
        entry = MemoryEntry(
            x="任务",
            y="输出",
            feedback="反馈",
            timestamp=None
        )
        self.assertIsNotNone(entry.timestamp)  # 应该自动生成当前时间


if __name__ == "__main__":
    unittest.main()