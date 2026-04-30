"""Domain-neutral memory evolution data structures."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TaskContext:
    """Metadata carried by one ReMem task.

    Domain-specific fields belong in ``metadata`` so the agent core can stay
    independent from short-drama or import workflows.
    """

    task_type: str = "generic_task"
    source: str = "remem_agent"
    role_id: str = "generic"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Optional[Any]) -> "TaskContext":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(
                task_type=str(value.get("task_type", "generic_task")),
                source=str(value.get("source", "remem_agent")),
                role_id=str(value.get("role_id", "generic")),
                metadata=dict(value.get("metadata") or {}),
            )
        raise TypeError(f"unsupported TaskContext value: {type(value)}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "source": self.source,
            "role_id": self.role_id,
            "metadata": dict(self.metadata),
        }


@dataclass
class MemoryRecord:
    """Unified memory unit visible to ReMemAgent."""

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": dict(self.metadata),
            "score": self.score,
        }


@dataclass
class MemoryOperation:
    """Unified operation emitted by Refine or derived from Act output."""

    operation_type: str
    target: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "MemoryOperation":
        if not isinstance(value, dict):
            raise TypeError("memory operation must be a dict")
        return cls(
            operation_type=str(
                value.get("operation_type") or value.get("type") or "no_op"
            ).strip().lower(),
            target=str(value.get("target") or ""),
            content=str(value.get("content") or ""),
            metadata=dict(value.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_type": self.operation_type,
            "target": self.target,
            "content": self.content,
            "metadata": dict(self.metadata),
        }
