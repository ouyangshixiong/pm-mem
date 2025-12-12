"""
记忆条目数据结构定义

实现MemoryEntry类，包含id/x/y/feedback/timestamp/tag字段，符合ReMem论文定义。
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional


class MemoryEntry:
    """记忆条目类，表示单个记忆单元"""

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

    # Property getter/setter methods
    @property
    def id(self) -> str:
        """获取记忆条目ID"""
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        """设置记忆条目ID"""
        if not isinstance(value, str):
            raise TypeError(f"id必须是字符串，实际类型: {type(value)}")
        if not value.strip():
            raise ValueError("id不能为空")
        self._id = value

    @property
    def x(self) -> str:
        """获取任务输入/触发情境"""
        return self._x

    @x.setter
    def x(self, value: str) -> None:
        """设置任务输入/触发情境"""
        if not isinstance(value, str):
            raise TypeError(f"x必须是字符串，实际类型: {type(value)}")
        self._x = value

    @property
    def y(self) -> str:
        """获取智能体输出/存储知识"""
        return self._y

    @y.setter
    def y(self, value: str) -> None:
        """设置智能体输出/存储知识"""
        if not isinstance(value, str):
            raise TypeError(f"y必须是字符串，实际类型: {type(value)}")
        self._y = value

    @property
    def feedback(self) -> str:
        """获取环境反馈"""
        return self._feedback

    @feedback.setter
    def feedback(self, value: str) -> None:
        """设置环境反馈"""
        if not isinstance(value, str):
            raise TypeError(f"feedback必须是字符串，实际类型: {type(value)}")
        self._feedback = value

    @property
    def tag(self) -> str:
        """获取记忆标签"""
        return self._tag

    @tag.setter
    def tag(self, value: str) -> None:
        """设置记忆标签"""
        if not isinstance(value, str):
            raise TypeError(f"tag必须是字符串，实际类型: {type(value)}")
        self._tag = value

    @property
    def timestamp(self) -> datetime:
        """获取时间戳"""
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: datetime) -> None:
        """设置时间戳"""
        if not isinstance(value, datetime):
            raise TypeError(f"timestamp必须是datetime对象，实际类型: {type(value)}")
        self._timestamp = value

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

    def __repr__(self) -> str:
        """字符串表示"""
        return f"MemoryEntry(id={self.id}, x={self.x[:20]}..., tag={self.tag})"