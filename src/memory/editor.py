"""
记忆编辑模块

支持DELETE/ADD/MERGE/RELABEL四种原子操作，实现严格的Refine命令语法解析器。
"""

import re
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


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
        normalized = cmd.strip().lower()

        # 按分号分割多条命令
        command_segments = [s.strip() for s in normalized.split(";") if s.strip()]

        for segment in command_segments:
            try:
                if segment.startswith("delete"):
                    indices = RefineEditor._parse_delete(segment)
                    delta["delete"].extend(indices)

                elif segment.startswith("add{"):
                    text = RefineEditor._parse_add(segment)
                    if text:
                        delta["add"].append(text)

                elif segment.startswith("merge"):
                    pairs = RefineEditor._parse_merge(segment)
                    delta["merge"].extend(pairs)

                elif segment.startswith("relabel"):
                    relabels = RefineEditor._parse_relabel(segment)
                    delta["relabel"].extend(relabels)

            except Exception as e:
                logger.warning(f"解析命令段失败 '{segment}': {e}")

        logger.debug(f"解析Refine命令: {cmd} -> {delta}")
        return delta

    @staticmethod
    def _parse_delete(segment: str) -> List[int]:
        """解析DELETE命令"""
        # 匹配格式: DELETE 1 或 DELETE 1,2,3
        pattern = r"delete\s+([\d\s,]+)"
        match = re.search(pattern, segment)

        if not match:
            return []

        numbers_str = match.group(1)
        indices = []
        for num in numbers_str.split(","):
            num = num.strip()
            if num.isdigit():
                indices.append(int(num))

        return indices

    @staticmethod
    def _parse_add(segment: str) -> str:
        """解析ADD命令"""
        # 匹配格式: ADD{text}
        pattern = r"add\{([^}]+)\}"
        match = re.search(pattern, segment)

        if not match:
            # 尝试匹配原始命令（可能保留大小写）
            alt_pattern = r"ADD\{([^}]+)\}"
            match = re.search(alt_pattern, cmd := segment)
            if not match:
                return ""

        return match.group(1).strip()

    @staticmethod
    def _parse_merge(segment: str) -> List[Tuple[int, int]]:
        """解析MERGE命令"""
        # 匹配格式: MERGE 1&2 或 MERGE 1&2; MERGE 3&4
        pairs = []

        # 提取所有数字对
        pattern = r"merge\s*(\d+)\s*&\s*(\d+)"
        matches = re.findall(pattern, segment)

        for idx1_str, idx2_str in matches:
            if idx1_str.isdigit() and idx2_str.isdigit():
                pairs.append((int(idx1_str), int(idx2_str)))

        return pairs

    @staticmethod
    def _parse_relabel(segment: str) -> List[Tuple[int, str]]:
        """解析RELABEL命令"""
        # 匹配格式: RELABEL 1 new-tag
        pattern = r"relabel\s+(\d+)\s+(.+)"
        match = re.search(pattern, segment)

        if not match:
            return []

        idx_str = match.group(1)
        new_tag = match.group(2).strip()

        if idx_str.isdigit():
            return [(int(idx_str), new_tag)]

        return []

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

        normalized = cmd.strip().lower()
        segments = [s.strip() for s in normalized.split(";") if s.strip()]

        for i, segment in enumerate(segments):
            if segment.startswith("delete"):
                if not re.match(r"delete\s+[\d\s,]+$", segment):
                    return False, f"第{i+1}段DELETE命令格式错误: {segment}"

            elif segment.startswith("add{"):
                if not re.match(r"add\{[^}]+\}$", segment):
                    return False, f"第{i+1}段ADD命令格式错误: {segment}"

            elif segment.startswith("merge"):
                if not re.match(r"merge\s*\d+\s*&\s*\d+$", segment):
                    return False, f"第{i+1}段MERGE命令格式错误: {segment}"

            elif segment.startswith("relabel"):
                if not re.match(r"relabel\s+\d+\s+.+$", segment):
                    return False, f"第{i+1}段RELABEL命令格式错误: {segment}"

            else:
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
            indices_str = ",".join(str(i) for i in delete)
            commands.append(f"DELETE {indices_str}")

        if add:
            for text in add:
                commands.append(f"ADD{{{text}}}")

        if merge:
            for idx1, idx2 in merge:
                commands.append(f"MERGE {idx1}&{idx2}")

        if relabel:
            for idx, tag in relabel:
                commands.append(f"RELABEL {idx} {tag}")

        return "; ".join(commands)