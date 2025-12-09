"""
记忆条目数据结构定义

实现MemoryEntry类，包含id/x/y/feedback/timestamp/tag字段，符合ReMem论文定义。
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class MemoryEntry:
    """记忆条目类，表示单个记忆单元"""

    id: str
    x: str  # 任务输入/触发情境
    y: str  # 智能体输出/存储知识
    feedback: str  # 环境反馈
    timestamp: datetime  # 时间戳（UTC格式）
    tag: str  # 记忆标签

    def __init__(
        self,
        x: str,
        y: str,
        feedback: str,
        tag: str = "",
        timestamp: Optional[datetime] = None,
        id: Optional[str] = None,
    ):
        """
        初始化记忆条目

        Args:
            x: 任务输入/触发情境
            y: 智能体输出/存储知识
            feedback: 环境反馈
            tag: 记忆标签
            timestamp: 时间戳（UTC格式），默认为当前时间
            id: 唯一标识符，默认为UUID
        """
        self.id = id or str(uuid.uuid4())
        self.x = x
        self.y = y
        self.feedback = feedback
        self.tag = tag
        self.timestamp = timestamp or datetime.utcnow()

    def to_text(self) -> str:
        """
        生成标准化文本表示

        Returns:
            标准化的文本表示，用于检索和显示
        """
        return f"""[Task]: {self.x}
[Action]: {self.y}
[Feedback]: {self.feedback}
[Tag]: {self.tag}
[Timestamp]: {self.timestamp.isoformat()}"""

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典表示，用于序列化

        Returns:
            字典格式的记忆条目
        """
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "feedback": self.feedback,
            "tag": self.tag,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """
        从字典创建MemoryEntry实例

        Args:
            data: 字典格式的记忆条目数据

        Returns:
            MemoryEntry实例
        """
        # 解析时间戳
        timestamp = datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None

        return cls(
            id=data.get("id"),
            x=data["x"],
            y=data["y"],
            feedback=data["feedback"],
            tag=data.get("tag", ""),
            timestamp=timestamp,
        )

    def __eq__(self, other: object) -> bool:
        """比较两个记忆条目是否相等（基于id）"""
        if not isinstance(other, MemoryEntry):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """哈希函数（基于id）"""
        return hash(self.id)