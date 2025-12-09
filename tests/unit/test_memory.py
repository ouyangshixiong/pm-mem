"""
记忆模块单元测试
"""

import pytest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from memory.entry import MemoryEntry
from memory.bank import MemoryBank
from memory.editor import RefineEditor
from datetime import datetime


class TestMemoryEntry:
    """MemoryEntry类测试"""

    def test_create_entry(self):
        """测试创建记忆条目"""
        entry = MemoryEntry(
            x="测试任务",
            y="测试输出",
            feedback="测试反馈",
            tag="test",
        )

        assert entry.x == "测试任务"
        assert entry.y == "测试输出"
        assert entry.feedback == "测试反馈"
        assert entry.tag == "test"
        assert entry.id is not None
        assert isinstance(entry.timestamp, datetime)

    def test_to_text(self):
        """测试生成文本表示"""
        entry = MemoryEntry(
            x="任务输入",
            y="任务输出",
            feedback="反馈信息",
            tag="标签",
        )

        text = entry.to_text()
        assert "[Task]: 任务输入" in text
        assert "[Action]: 任务输出" in text
        assert "[Feedback]: 反馈信息" in text
        assert "[Tag]: 标签" in text
        assert "[Timestamp]:" in text

    def test_to_dict_from_dict(self):
        """测试字典序列化和反序列化"""
        entry = MemoryEntry(
            x="原始任务",
            y="原始输出",
            feedback="原始反馈",
            tag="original",
        )

        # 转换为字典
        data = entry.to_dict()
        assert data["x"] == "原始任务"
        assert data["y"] == "原始输出"
        assert data["feedback"] == "原始反馈"
        assert data["tag"] == "original"
        assert "id" in data
        assert "timestamp" in data

        # 从字典恢复
        restored = MemoryEntry.from_dict(data)
        assert restored.x == entry.x
        assert restored.y == entry.y
        assert restored.feedback == entry.feedback
        assert restored.tag == entry.tag
        assert restored.id == entry.id

    def test_equality(self):
        """测试相等性比较"""
        entry1 = MemoryEntry("任务1", "输出1", "反馈1", "tag1")
        entry2 = MemoryEntry("任务2", "输出2", "反馈2", "tag2")
        entry3 = MemoryEntry.from_dict(entry1.to_dict())

        assert entry1 == entry3
        assert entry1 != entry2
        assert entry2 != entry3


class TestMemoryBank:
    """MemoryBank类测试"""

    def setup_method(self):
        """测试设置"""
        self.bank = MemoryBank(max_entries=10)
        self.entry1 = MemoryEntry("任务1", "输出1", "反馈1", "tag1")
        self.entry2 = MemoryEntry("任务2", "输出2", "反馈2", "tag2")
        self.entry3 = MemoryEntry("任务3", "输出3", "反馈3", "tag3")

    def test_add_entry(self):
        """测试添加记忆条目"""
        self.bank.add(self.entry1)
        assert len(self.bank) == 1
        assert self.bank[0] == self.entry1

    def test_delete_entry(self):
        """测试删除记忆条目"""
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

        assert len(self.bank) == 3

        # 删除第二个条目
        self.bank.delete([1])
        assert len(self.bank) == 2
        assert self.bank[0] == self.entry1
        assert self.bank[1] == self.entry3

        # 删除多个条目
        self.bank.delete([0, 1])
        assert len(self.bank) == 0

    def test_merge_entries(self):
        """测试合并记忆条目"""
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

        # 合并条目0和1
        self.bank.merge(0, 1)
        assert len(self.bank) == 2  # 减少一个条目

        # 检查合并后的条目
        merged = self.bank[0]
        assert "任务1" in merged.x
        assert "任务2" in merged.x
        assert "输出1" in merged.y
        assert "输出2" in merged.y
        assert "反馈1" in merged.feedback
        assert "反馈2" in merged.feedback
        assert "merged" in merged.tag.lower()

    def test_relabel_entry(self):
        """测试重新标记记忆条目"""
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)

        assert self.bank[0].tag == "tag1"
        self.bank.relabel(0, "new-tag")
        assert self.bank[0].tag == "new-tag"

    def test_retrieve_with_mock_llm(self):
        """测试检索功能（使用模拟LLM）"""
        # 添加测试条目
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)
        self.bank.add(self.entry3)

        # 创建模拟LLM
        class MockLLM:
            def __call__(self, prompt):
                # 总是返回前两个索引
                return "0,1"

        mock_llm = MockLLM()
        results = self.bank.retrieve(mock_llm, "测试查询", k=2)

        assert len(results) == 2
        assert results[0] == self.entry1
        assert results[1] == self.entry2

    def test_statistics(self):
        """测试统计信息"""
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)

        stats = self.bank.get_statistics()
        assert stats["total_entries"] == 2
        assert stats["max_entries"] == 10
        assert "tag_distribution" in stats
        assert stats["tag_distribution"]["tag1"] == 1
        assert stats["tag_distribution"]["tag2"] == 1

    def test_to_dict_from_dict(self):
        """测试记忆库序列化和反序列化"""
        self.bank.add(self.entry1)
        self.bank.add(self.entry2)

        # 转换为字典列表
        data = self.bank.to_dict()
        assert isinstance(data, list)
        assert len(data) == 2

        # 从字典列表恢复
        new_bank = MemoryBank.from_dict(data, max_entries=20)
        assert len(new_bank) == 2
        assert new_bank.max_entries == 20
        assert new_bank[0].x == self.entry1.x
        assert new_bank[1].x == self.entry2.x


class TestRefineEditor:
    """RefineEditor类测试"""

    def test_parse_delete_command(self):
        """测试解析DELETE命令"""
        cmd = "DELETE 1,3,5"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == [1, 3, 5]
        assert delta["add"] == []
        assert delta["merge"] == []
        assert delta["relabel"] == []

    def test_parse_add_command(self):
        """测试解析ADD命令"""
        cmd = "ADD{新的记忆内容}"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == []
        assert delta["add"] == ["新的记忆内容"]
        assert delta["merge"] == []
        assert delta["relabel"] == []

    def test_parse_merge_command(self):
        """测试解析MERGE命令"""
        cmd = "MERGE 1&2"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == []
        assert delta["add"] == []
        assert delta["merge"] == [(1, 2)]
        assert delta["relabel"] == []

    def test_parse_relabel_command(self):
        """测试解析RELABEL命令"""
        cmd = "RELABEL 3 new-tag"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == []
        assert delta["add"] == []
        assert delta["merge"] == []
        assert delta["relabel"] == [(3, "new-tag")]

    def test_parse_multiple_commands(self):
        """测试解析多条命令"""
        cmd = "DELETE 1,3; ADD{新内容}; MERGE 0&2; RELABEL 4 新标签"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == [1, 3]
        assert delta["add"] == ["新内容"]
        assert delta["merge"] == [(0, 2)]
        assert delta["relabel"] == [(4, "新标签")]

    def test_validate_command(self):
        """测试命令验证"""
        # 有效命令
        valid, msg = RefineEditor.validate_command("DELETE 1,3")
        assert valid is True
        assert "合法" in msg

        # 无效命令
        valid, msg = RefineEditor.validate_command("DELETE abc")
        assert valid is False
        assert "格式错误" in msg

        # 未知命令
        valid, msg = RefineEditor.validate_command("UNKNOWN 1")
        assert valid is False
        assert "未知命令" in msg

    def test_format_command(self):
        """测试命令格式化"""
        cmd = RefineEditor.format_command(
            delete=[1, 3],
            add=["新内容"],
            merge=[(0, 2)],
            relabel=[(4, "新标签")],
        )

        assert "DELETE 1,3" in cmd
        assert "ADD{新内容}" in cmd
        assert "MERGE 0&2" in cmd
        assert "RELABEL 4 新标签" in cmd