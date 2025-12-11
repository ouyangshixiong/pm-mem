"""
记忆编辑模块

支持DELETE/ADD/MERGE/RELABEL四种原子操作，实现严格的Refine命令语法解析器。
"""

import re
from typing import Dict, Any, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """命令类型枚举"""
    DELETE = "DELETE"
    ADD = "ADD"
    MERGE = "MERGE"
    RELABEL = "RELABEL"


@dataclass
class ParseResult:
    """解析结果数据类"""
    command_type: CommandType
    indices: List[int] = None
    text: str = None
    pairs: List[Tuple[int, int]] = None
    relabels: List[Tuple[int, str]] = None
    error: str = None


class RefineEditor:
    """记忆编辑模块，支持四种原子操作"""

    @staticmethod
    def parse_command(cmd: str) -> Dict[str, Any]:
        """
        解析Refine命令字符串

        支持的语法格式：
        - DELETE <idx> 或 DELETE <idx1>,<idx2>,...
        - ADD {<text>}
        - MERGE <idx1>&<idx2>
        - RELABEL <idx> <new-tag>

        多条命令可以用分号分隔。

        Args:
            cmd: Refine命令字符串

        Returns:
            解析后的命令字典，包含delete/add/merge/relabel操作
        """
        delta = {"delete": [], "add": [], "merge": [], "relabel": []}

        if not cmd or not cmd.strip():
            return delta

        # 标准化命令：去除多余空格，统一大小写
        normalized = cmd.strip()

        # 按分号分割多条命令
        command_segments = [s.strip() for s in normalized.split(";") if s.strip()]

        for segment in command_segments:
            try:
                # 使用增强的解析方法
                parse_result = RefineEditor._parse_segment(segment)

                if parse_result.error:
                    logger.warning(f"解析命令段失败 '{segment}': {parse_result.error}")
                    continue

                if parse_result.command_type == CommandType.DELETE:
                    delta["delete"].extend(parse_result.indices)
                elif parse_result.command_type == CommandType.ADD:
                    if parse_result.text:
                        delta["add"].append(parse_result.text)
                elif parse_result.command_type == CommandType.MERGE:
                    delta["merge"].extend(parse_result.pairs)
                elif parse_result.command_type == CommandType.RELABEL:
                    delta["relabel"].extend(parse_result.relabels)

            except Exception as e:
                logger.warning(f"解析命令段失败 '{segment}': {e}")

        logger.debug(f"解析Refine命令: {cmd} -> {delta}")
        return delta

    @staticmethod
    def _parse_segment(segment: str) -> ParseResult:
        """解析单个命令段"""
        # 检查命令类型
        segment_upper = segment.upper()

        if segment_upper.startswith("DELETE"):
            return RefineEditor._parse_delete_enhanced(segment)
        elif segment_upper.startswith("ADD{"):
            return RefineEditor._parse_add_enhanced(segment)
        elif segment_upper.startswith("MERGE"):
            return RefineEditor._parse_merge_enhanced(segment)
        elif segment_upper.startswith("RELABEL"):
            return RefineEditor._parse_relabel_enhanced(segment)
        else:
            return ParseResult(
                command_type=None,
                error=f"未知命令类型: {segment.split()[0] if segment.split() else segment}"
            )

    @staticmethod
    def _parse_delete_enhanced(segment: str) -> ParseResult:
        """增强版DELETE命令解析"""
        # 支持多种格式: DELETE 1, DELETE 1,2,3, DELETE 1 2 3
        pattern = r"^DELETE\s+([\d\s,]+)$"
        match = re.match(pattern, segment, re.IGNORECASE)

        if not match:
            return ParseResult(
                command_type=CommandType.DELETE,
                error=f"DELETE命令格式错误: {segment}"
            )

        numbers_str = match.group(1)
        indices = []

        # 支持逗号分隔和空格分隔
        for num in re.split(r'[,\s]+', numbers_str):
            num = num.strip()
            if num and num.isdigit():
                indices.append(int(num))

        if not indices:
            return ParseResult(
                command_type=CommandType.DELETE,
                error=f"DELETE命令中没有有效的索引: {segment}"
            )

        # 检查重复索引
        if len(indices) != len(set(indices)):
            return ParseResult(
                command_type=CommandType.DELETE,
                error=f"DELETE命令中有重复索引: {segment}"
            )

        return ParseResult(
            command_type=CommandType.DELETE,
            indices=indices
        )

    @staticmethod
    def _parse_add_enhanced(segment: str) -> ParseResult:
        """增强版ADD命令解析"""
        # 支持多种格式: ADD{text}, ADD {text}, ADD{ text }, ADD{}
        pattern = r"^ADD\s*\{(.*)\}$"
        match = re.match(pattern, segment, re.IGNORECASE)

        if not match:
            return ParseResult(
                command_type=CommandType.ADD,
                error=f"ADD命令格式错误: {segment}"
            )

        text = match.group(1).strip()

        if not text:
            return ParseResult(
                command_type=CommandType.ADD,
                error=f"ADD命令内容为空: {segment}"
            )

        return ParseResult(
            command_type=CommandType.ADD,
            text=text
        )

    @staticmethod
    def _parse_merge_enhanced(segment: str) -> ParseResult:
        """增强版MERGE命令解析"""
        # 支持多种格式: MERGE 1&2, MERGE 1 & 2, MERGE 1&2; MERGE 3&4
        pairs = []

        # 提取所有数字对
        pattern = r"MERGE\s*(\d+)\s*&\s*(\d+)"
        matches = re.findall(pattern, segment, re.IGNORECASE)

        if not matches:
            return ParseResult(
                command_type=CommandType.MERGE,
                error=f"MERGE命令格式错误: {segment}"
            )

        for idx1_str, idx2_str in matches:
            if idx1_str.isdigit() and idx2_str.isdigit():
                idx1, idx2 = int(idx1_str), int(idx2_str)

                # 检查是否合并同一个索引
                if idx1 == idx2:
                    return ParseResult(
                        command_type=CommandType.MERGE,
                        error=f"MERGE命令不能合并同一个索引: {idx1}"
                    )

                # 检查重复合并对
                if (idx1, idx2) in pairs or (idx2, idx1) in pairs:
                    return ParseResult(
                        command_type=CommandType.MERGE,
                        error=f"MERGE命令中有重复的合并对: {idx1}&{idx2}"
                    )

                pairs.append((idx1, idx2))

        if not pairs:
            return ParseResult(
                command_type=CommandType.MERGE,
                error=f"MERGE命令中没有有效的索引对: {segment}"
            )

        return ParseResult(
            command_type=CommandType.MERGE,
            pairs=pairs
        )

    @staticmethod
    def _parse_relabel_enhanced(segment: str) -> ParseResult:
        """增强版RELABEL命令解析"""
        # 支持多种格式: RELABEL 1 new-tag, RELABEL 1 "new tag"
        pattern = r"^RELABEL\s+(\d+)\s+(.+)$"
        match = re.match(pattern, segment, re.IGNORECASE)

        if not match:
            return ParseResult(
                command_type=CommandType.RELABEL,
                error=f"RELABEL命令格式错误: {segment}"
            )

        idx_str = match.group(1)
        new_tag = match.group(2).strip()

        # 去除可能的引号
        if new_tag.startswith('"') and new_tag.endswith('"'):
            new_tag = new_tag[1:-1]
        elif new_tag.startswith("'") and new_tag.endswith("'"):
            new_tag = new_tag[1:-1]

        if not idx_str.isdigit():
            return ParseResult(
                command_type=CommandType.RELABEL,
                error=f"RELABEL命令索引不是数字: {idx_str}"
            )

        if not new_tag:
            return ParseResult(
                command_type=CommandType.RELABEL,
                error=f"RELABEL命令新标签为空: {segment}"
            )

        return ParseResult(
            command_type=CommandType.RELABEL,
            relabels=[(int(idx_str), new_tag)]
        )

    @staticmethod
    def validate_command(cmd: str) -> Tuple[bool, str]:
        """
        验证Refine命令语法是否合法

        Args:
            cmd: 要验证的命令字符串

        Returns:
            (是否合法, 错误信息)
        """
        if not cmd or not cmd.strip():
            return True, "空命令"

        normalized = cmd.strip()
        segments = [s.strip() for s in normalized.split(";") if s.strip()]

        for i, segment in enumerate(segments):
            # 使用增强的解析方法进行验证
            parse_result = RefineEditor._parse_segment(segment)

            if parse_result.error:
                return False, f"第{i+1}段命令错误: {parse_result.error}"

            if parse_result.command_type is None:
                return False, f"第{i+1}段包含未知命令: {segment}"

        return True, "命令格式合法"

    @staticmethod
    def format_command(
        delete: List[int] = None,
        add: List[str] = None,
        merge: List[Tuple[int, int]] = None,
        relabel: List[Tuple[int, str]] = None,
    ) -> str:
        """
        格式化命令字典为Refine命令字符串

        Args:
            delete: 要删除的索引列表
            add: 要添加的文本列表
            merge: 要合并的索引对列表
            relabel: 要重新标记的(索引, 新标签)列表

        Returns:
            格式化的Refine命令字符串
        """
        commands = []

        if delete:
            # 去重并排序
            unique_indices = sorted(set(delete))
            indices_str = ",".join(str(i) for i in unique_indices)
            commands.append(f"DELETE {indices_str}")

        if add:
            for text in add:
                if text and isinstance(text, str):
                    # 确保文本中没有未匹配的花括号
                    safe_text = text.replace("}", "}}")
                    commands.append(f"ADD{{{safe_text}}}")

        if merge:
            # 去重并排序
            unique_pairs = []
            seen = set()
            for idx1, idx2 in merge:
                pair = tuple(sorted((idx1, idx2)))
                if pair not in seen:
                    seen.add(pair)
                    unique_pairs.append(pair)

            for idx1, idx2 in unique_pairs:
                commands.append(f"MERGE {idx1}&{idx2}")

        if relabel:
            # 去重
            unique_relabels = []
            seen_indices = set()
            for idx, tag in relabel:
                if idx not in seen_indices:
                    seen_indices.add(idx)
                    unique_relabels.append((idx, tag))

            for idx, tag in unique_relabels:
                # 如果标签包含空格，添加引号
                if " " in tag:
                    commands.append(f'RELABEL {idx} "{tag}"')
                else:
                    commands.append(f"RELABEL {idx} {tag}")

        return "; ".join(commands)

    @staticmethod
    def get_command_summary(cmd: str) -> Dict[str, Any]:
        """
        获取命令摘要信息

        Args:
            cmd: Refine命令字符串

        Returns:
            包含命令摘要信息的字典
        """
        delta = RefineEditor.parse_command(cmd)

        return {
            "total_operations": len(delta["delete"]) + len(delta["add"]) +
                               len(delta["merge"]) + len(delta["relabel"]),
            "delete_count": len(delta["delete"]),
            "add_count": len(delta["add"]),
            "merge_count": len(delta["merge"]),
            "relabel_count": len(delta["relabel"]),
            "is_valid": RefineEditor.validate_command(cmd)[0],
            "operations": delta
        }