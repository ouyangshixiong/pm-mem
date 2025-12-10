"""
检索结果数据结构定义

实现RetrievalResult类，包含记忆条目、相关性评分和解释。
"""

from dataclasses import dataclass
from typing import Optional
from .entry import MemoryEntry


@dataclass
class RetrievalResult:
    """检索结果类，包含记忆条目、相关性评分和解释"""

    memory_entry: MemoryEntry
    relevance_score: float  # 相关性评分，0.0-1.0
    explanation: str  # 相关性解释

    def __init__(
        self,
        memory_entry: MemoryEntry,
        relevance_score: float = 0.0,
        explanation: str = ""
    ):
        """
        初始化检索结果

        Args:
            memory_entry: 记忆条目
            relevance_score: 相关性评分（0.0-1.0）
            explanation: 相关性解释
        """
        self.memory_entry = memory_entry
        self.relevance_score = max(0.0, min(1.0, relevance_score))  # 确保在0-1范围内
        self.explanation = explanation or ""

    def to_dict(self):
        """转换为字典表示"""
        return {
            "memory_entry": self.memory_entry.to_dict(),
            "relevance_score": self.relevance_score,
            "explanation": self.explanation
        }

    @classmethod
    def from_dict(cls, data):
        """从字典创建实例"""
        from .entry import MemoryEntry
        memory_entry = MemoryEntry.from_dict(data["memory_entry"])
        return cls(
            memory_entry=memory_entry,
            relevance_score=data.get("relevance_score", 0.0),
            explanation=data.get("explanation", "")
        )

    def __repr__(self):
        """字符串表示"""
        return f"RetrievalResult(score={self.relevance_score:.2f}, explanation={self.explanation[:50]}...)"

    def __lt__(self, other):
        """小于比较，用于排序（按相关性评分降序）"""
        if not isinstance(other, RetrievalResult):
            return NotImplemented
        return self.relevance_score > other.relevance_score  # 降序排序