"""
增强版RefineEditor测试
"""

import pytest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from memory.editor import RefineEditor, CommandType, ParseResult


class TestEnhancedRefineEditor:
    """增强版RefineEditor测试"""

    def test_parse_delete_enhanced(self):
        """测试增强版DELETE命令解析"""
        # 测试正常情况
        result = RefineEditor._parse_delete_enhanced("DELETE 1,3,5")
        assert result.command_type == CommandType.DELETE
        assert result.indices == [1, 3, 5]
        assert result.error is None

        # 测试空格分隔
        result = RefineEditor._parse_delete_enhanced("DELETE 1 3 5")
        assert result.indices == [1, 3, 5]

        # 测试混合分隔
        result = RefineEditor._parse_delete_enhanced("DELETE 1, 3, 5")
        assert result.indices == [1, 3, 5]

        # 测试大小写不敏感
        result = RefineEditor._parse_delete_enhanced("delete 1,3,5")
        assert result.indices == [1, 3, 5]

        # 测试无效格式
        result = RefineEditor._parse_delete_enhanced("DELETE abc")
        assert result.error is not None
        assert "格式错误" in result.error

        # 测试重复索引
        result = RefineEditor._parse_delete_enhanced("DELETE 1,1,2")
        assert result.error is not None
        assert "重复索引" in result.error

    def test_parse_add_enhanced(self):
        """测试增强版ADD命令解析"""
        # 测试正常情况
        result = RefineEditor._parse_add_enhanced("ADD{新的记忆内容}")
        assert result.command_type == CommandType.ADD
        assert result.text == "新的记忆内容"
        assert result.error is None

        # 测试带空格的花括号
        result = RefineEditor._parse_add_enhanced("ADD { 带空格的内容 }")
        assert result.text == "带空格的内容"

        # 测试大小写不敏感
        result = RefineEditor._parse_add_enhanced("add{小写命令}")
        assert result.text == "小写命令"

        # 测试空内容
        result = RefineEditor._parse_add_enhanced("ADD{}")
        assert result.error is not None
        assert "内容为空" in result.error

        # 测试无效格式
        result = RefineEditor._parse_add_enhanced("ADD 没有花括号")
        assert result.error is not None
        assert "格式错误" in result.error

    def test_parse_merge_enhanced(self):
        """测试增强版MERGE命令解析"""
        # 测试正常情况
        result = RefineEditor._parse_merge_enhanced("MERGE 1&2")
        assert result.command_type == CommandType.MERGE
        assert result.pairs == [(1, 2)]
        assert result.error is None

        # 测试带空格的格式
        result = RefineEditor._parse_merge_enhanced("MERGE 1 & 2")
        assert result.pairs == [(1, 2)]

        # 测试大小写不敏感
        result = RefineEditor._parse_merge_enhanced("merge 1&2")
        assert result.pairs == [(1, 2)]

        # 测试多个合并
        result = RefineEditor._parse_merge_enhanced("MERGE 1&2; MERGE 3&4")
        assert result.pairs == [(1, 2), (3, 4)]

        # 测试合并同一个索引
        result = RefineEditor._parse_merge_enhanced("MERGE 1&1")
        assert result.error is not None
        assert "不能合并同一个索引" in result.error

        # 测试重复合并对
        result = RefineEditor._parse_merge_enhanced("MERGE 1&2; MERGE 2&1")
        assert result.error is not None
        assert "重复的合并对" in result.error

    def test_parse_relabel_enhanced(self):
        """测试增强版RELABEL命令解析"""
        # 测试正常情况
        result = RefineEditor._parse_relabel_enhanced("RELABEL 1 new-tag")
        assert result.command_type == CommandType.RELABEL
        assert result.relabels == [(1, "new-tag")]
        assert result.error is None

        # 测试带引号的标签
        result = RefineEditor._parse_relabel_enhanced('RELABEL 1 "带空格的标签"')
        assert result.relabels == [(1, "带空格的标签")]

        # 测试大小写不敏感
        result = RefineEditor._parse_relabel_enhanced("relabel 1 tag")
        assert result.relabels == [(1, "tag")]

        # 测试空标签
        result = RefineEditor._parse_relabel_enhanced("RELABEL 1 ")
        assert result.error is not None
        assert "新标签为空" in result.error

        # 测试无效索引
        result = RefineEditor._parse_relabel_enhanced("RELABEL abc tag")
        assert result.error is not None
        assert "索引不是数字" in result.error

    def test_parse_segment(self):
        """测试命令段解析"""
        # 测试DELETE命令
        result = RefineEditor._parse_segment("DELETE 1,2,3")
        assert result.command_type == CommandType.DELETE
        assert result.indices == [1, 2, 3]

        # 测试ADD命令
        result = RefineEditor._parse_segment("ADD{测试内容}")
        assert result.command_type == CommandType.ADD
        assert result.text == "测试内容"

        # 测试MERGE命令
        result = RefineEditor._parse_segment("MERGE 1&2")
        assert result.command_type == CommandType.MERGE
        assert result.pairs == [(1, 2)]

        # 测试RELABEL命令
        result = RefineEditor._parse_segment("RELABEL 3 标签")
        assert result.command_type == CommandType.RELABEL
        assert result.relabels == [(3, "标签")]

        # 测试未知命令
        result = RefineEditor._parse_segment("UNKNOWN 1")
        assert result.command_type is None
        assert result.error is not None
        assert "未知命令" in result.error

    def test_parse_command_enhanced(self):
        """测试增强版命令解析"""
        # 测试多条命令
        cmd = "DELETE 1,3; ADD{新内容}; MERGE 0&2; RELABEL 4 新标签"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == [1, 3]
        assert delta["add"] == ["新内容"]
        assert delta["merge"] == [(0, 2)]
        assert delta["relabel"] == [(4, "新标签")]

        # 测试大小写混合
        cmd = "delete 1,3; add{内容}; merge 0&2; relabel 4 标签"
        delta = RefineEditor.parse_command(cmd)

        assert delta["delete"] == [1, 3]
        assert delta["add"] == ["内容"]
        assert delta["merge"] == [(0, 2)]
        assert delta["relabel"] == [(4, "标签")]

        # 测试带空格和引号的标签
        cmd = 'RELABEL 1 "带空格的标签"'
        delta = RefineEditor.parse_command(cmd)
        assert delta["relabel"] == [(1, "带空格的标签")]

        # 测试无效命令（应该被忽略）
        cmd = "DELETE 1,2; INVALID 3; ADD{有效内容}"
        delta = RefineEditor.parse_command(cmd)
        assert delta["delete"] == [1, 2]
        assert delta["add"] == ["有效内容"]
        assert delta["merge"] == []
        assert delta["relabel"] == []

    def test_validate_command_enhanced(self):
        """测试增强版命令验证"""
        # 测试有效命令
        valid, msg = RefineEditor.validate_command("DELETE 1,3")
        assert valid is True
        assert "合法" in msg

        valid, msg = RefineEditor.validate_command("ADD{内容}")
        assert valid is True

        valid, msg = RefineEditor.validate_command("MERGE 1&2")
        assert valid is True

        valid, msg = RefineEditor.validate_command('RELABEL 1 "带空格的标签"')
        assert valid is True

        # 测试无效命令
        valid, msg = RefineEditor.validate_command("DELETE abc")
        assert valid is False
        assert "错误" in msg

        valid, msg = RefineEditor.validate_command("ADD{")
        assert valid is False

        valid, msg = RefineEditor.validate_command("MERGE 1&")
        assert valid is False

        valid, msg = RefineEditor.validate_command("RELABEL 1")
        assert valid is False

        # 测试多条命令中的错误
        valid, msg = RefineEditor.validate_command("DELETE 1,2; ADD{内容}; INVALID 3")
        assert valid is False
        assert "未知命令" in msg

    def test_format_command_enhanced(self):
        """测试增强版命令格式化"""
        # 测试完整格式化
        cmd = RefineEditor.format_command(
            delete=[1, 3, 1],  # 包含重复
            add=["内容1", "内容2"],
            merge=[(0, 2), (2, 0)],  # 包含重复对
            relabel=[(4, "标签1"), (4, "标签2")]  # 包含重复索引
        )

        # 检查去重
        assert "DELETE 1,3" in cmd
        assert "DELETE 1,3,1" not in cmd  # 应该去重

        assert "ADD{内容1}" in cmd
        assert "ADD{内容2}" in cmd

        assert "MERGE 0&2" in cmd
        assert cmd.count("MERGE") == 1  # 应该只有一个合并命令

        assert "RELABEL 4" in cmd
        assert cmd.count("RELABEL") == 1  # 应该只有一个重标记命令

        # 测试带空格的标签
        cmd = RefineEditor.format_command(relabel=[(1, "带空格的标签")])
        assert 'RELABEL 1 "带空格的标签"' in cmd

        # 测试空参数
        cmd = RefineEditor.format_command()
        assert cmd == ""

        # 测试花括号转义
        cmd = RefineEditor.format_command(add=["包含}花括号的内容"])
        assert "ADD{包含}}花括号的内容}" in cmd

    def test_get_command_summary(self):
        """测试命令摘要"""
        cmd = "DELETE 1,3; ADD{新内容}; MERGE 0&2; RELABEL 4 新标签"
        summary = RefineEditor.get_command_summary(cmd)

        assert summary["total_operations"] == 4
        assert summary["delete_count"] == 2
        assert summary["add_count"] == 1
        assert summary["merge_count"] == 1
        assert summary["relabel_count"] == 1
        assert summary["is_valid"] is True
        assert "operations" in summary

        # 测试无效命令
        cmd = "INVALID 1"
        summary = RefineEditor.get_command_summary(cmd)
        assert summary["is_valid"] is False
        assert summary["total_operations"] == 0

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空命令
        delta = RefineEditor.parse_command("")
        assert delta == {"delete": [], "add": [], "merge": [], "relabel": []}

        delta = RefineEditor.parse_command("   ")
        assert delta == {"delete": [], "add": [], "merge": [], "relabel": []}

        # 测试只有分号的命令
        delta = RefineEditor.parse_command(";")
        assert delta == {"delete": [], "add": [], "merge": [], "relabel": []}

        # 测试带多余空格的命令
        cmd = "  DELETE   1 , 3  ;  ADD{ 内容 }  ;  MERGE  0  &  2  "
        delta = RefineEditor.parse_command(cmd)
        assert delta["delete"] == [1, 3]
        assert delta["add"] == ["内容"]
        assert delta["merge"] == [(0, 2)]

        # 测试验证空命令
        valid, msg = RefineEditor.validate_command("")
        assert valid is True
        assert "空命令" in msg