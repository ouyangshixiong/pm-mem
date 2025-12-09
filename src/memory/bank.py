"""
记忆库管理

实现MemoryBank类管理记忆条目集合，支持添加、删除、合并、重标签操作，提供基于LLM的检索接口。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .entry import MemoryEntry

logger = logging.getLogger(__name__)


class MemoryBank:
    """记忆库类，管理记忆条目集合"""

    def __init__(self, max_entries: int = 1000):
        """
        初始化记忆库

        Args:
            max_entries: 最大记忆容量
        """
        self.entries: List[MemoryEntry] = []
        self.max_entries = max_entries

    def add(self, entry: MemoryEntry) -> None:
        """
        添加记忆条目

        Args:
            entry: 要添加的记忆条目
        """
        if len(self.entries) >= self.max_entries:
            logger.warning(f"记忆库已达最大容量 {self.max_entries}，将执行清理")
            self._prune()

        self.entries.append(entry)
        logger.debug(f"添加记忆条目: {entry.id}")

    def delete(self, indices: List[int]) -> None:
        """
        删除指定索引的记忆条目

        Args:
            indices: 要删除的索引列表
        """
        # 按降序排序以避免索引偏移
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(self.entries):
                deleted_entry = self.entries[idx]
                del self.entries[idx]
                logger.debug(f"删除记忆条目 {idx}: {deleted_entry.id}")
            else:
                logger.warning(f"尝试删除无效索引: {idx}")

    def merge(self, idx1: int, idx2: int) -> None:
        """
        合并两个记忆条目

        Args:
            idx1: 第一个条目的索引（合并后的条目将保留在此位置）
            idx2: 第二个条目的索引（将被删除）

        Raises:
            IndexError: 索引超出范围
        """
        if not (0 <= idx1 < len(self.entries) and 0 <= idx2 < len(self.entries)):
            raise IndexError(f"合并索引超出范围: {idx1}, {idx2}")

        e1, e2 = self.entries[idx1], self.entries[idx2]

        # 创建合并后的记忆条目
        merged = MemoryEntry(
            x=f"{e1.x}\n---\n{e2.x}",
            y=f"{e1.y}\n---\n{e2.y}",
            feedback=f"{e1.feedback}; {e2.feedback}",
            tag=f"merged({e1.tag},{e2.tag})",
            timestamp=max(e1.timestamp, e2.timestamp),
        )

        # 用合并条目替换 idx1，删除 idx2
        self.entries[idx1] = merged

        # 删除较大索引以避免位移问题
        if idx2 > idx1:
            del self.entries[idx2]
        else:
            del self.entries[idx1 + 1]

        logger.debug(f"合并记忆条目 {idx1} 和 {idx2} -> {merged.id}")

    def relabel(self, idx: int, new_tag: str) -> None:
        """
        重新标记记忆条目

        Args:
            idx: 要重新标记的索引
            new_tag: 新标签
        """
        if 0 <= idx < len(self.entries):
            self.entries[idx].tag = new_tag
            logger.debug(f"重新标记记忆条目 {idx}: {new_tag}")
        else:
            logger.warning(f"尝试重新标记无效索引: {idx}")

    def retrieve(
        self, llm, query: str, k: int = 5
    ) -> List[MemoryEntry]:
        """
        基于LLM的文本相关性检索

        Args:
            llm: LLM调用接口，需要实现 __call__(prompt: str) -> str 方法
            query: 查询文本
            k: 返回的最相关记忆数量

        Returns:
            最相关的k个记忆条目列表
        """
        if not self.entries:
            return []

        # 构造供LLM排序的记忆文本（每条带索引）
        memory_text = "\n\n".join(
            [f"[{i}]\n{e.to_text()}" for i, e in enumerate(self.entries)]
        )

        prompt = f"""
你是一个专业的记忆检索器。给定用户任务：
{query}

以下是全部记忆条目，请按相关性从高到低排序，输出最相关的前 {k} 个索引：

{memory_text}

请仅输出索引列表，例如：1,5,2
"""
        try:
            result = llm(prompt)
            # 解析LLM返回的索引列表
            indices = [
                int(x.strip())
                for x in result.split(",")
                if x.strip().isdigit()
            ]
        except Exception as e:
            logger.error(f"LLM检索失败: {e}")
            # 失败时返回前k个条目
            indices = list(range(min(k, len(self.entries))))

        indices = indices[:k]
        retrieved = [
            self.entries[i] for i in indices if 0 <= i < len(self.entries)
        ]

        logger.debug(f"检索到 {len(retrieved)} 条相关记忆")
        return retrieved

    def _prune(self, target_ratio: float = 0.2) -> None:
        """
        清理记忆库（当达到最大容量时）

        Args:
            target_ratio: 目标删除比例（20-30%）
        """
        if len(self.entries) <= self.max_entries:
            return

        # 简单实现：按时间排序，删除最旧的条目
        self.entries.sort(key=lambda e: e.timestamp)
        delete_count = int(len(self.entries) * target_ratio)
        delete_count = max(1, min(delete_count, len(self.entries) - self.max_entries))

        # 删除最旧的条目
        del self.entries[:delete_count]
        logger.info(f"清理记忆库，删除 {delete_count} 条最旧的记忆")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取记忆库统计信息

        Returns:
            包含统计信息的字典
        """
        if not self.entries:
            return {
                "total_entries": 0,
                "max_entries": self.max_entries,
                "oldest_timestamp": None,
                "newest_timestamp": None,
                "tag_distribution": {},
            }

        timestamps = [e.timestamp for e in self.entries]
        tag_counts = {}
        for e in self.entries:
            tag_counts[e.tag] = tag_counts.get(e.tag, 0) + 1

        return {
            "total_entries": len(self.entries),
            "max_entries": self.max_entries,
            "oldest_timestamp": min(timestamps).isoformat(),
            "newest_timestamp": max(timestamps).isoformat(),
            "tag_distribution": tag_counts,
        }

    def to_dict(self) -> List[Dict[str, Any]]:
        """
        转换为字典列表，用于序列化

        Returns:
            记忆条目字典列表
        """
        return [e.to_dict() for e in self.entries]

    @classmethod
    def from_dict(cls, data: List[Dict[str, Any]], max_entries: int = 1000) -> "MemoryBank":
        """
        从字典列表创建MemoryBank实例

        Args:
            data: 记忆条目字典列表
            max_entries: 最大记忆容量

        Returns:
            MemoryBank实例
        """
        bank = cls(max_entries=max_entries)
        for item in data:
            try:
                entry = MemoryEntry.from_dict(item)
                bank.entries.append(entry)
            except Exception as e:
                logger.warning(f"加载记忆条目失败: {e}")
        return bank

    def __len__(self) -> int:
        """返回记忆条目数量"""
        return len(self.entries)

    def __getitem__(self, idx: int) -> MemoryEntry:
        """通过索引获取记忆条目"""
        return self.entries[idx]