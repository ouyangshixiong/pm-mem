"""MemoryStore and TraceStore implementations for ReMemAgent."""

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import memory_manager
except ImportError:  # pragma: no cover - package-only deployments may omit it
    memory_manager = None

try:
    from .bank import MemoryBank
    from .entry import MemoryEntry
    from .llm_retrieval import LLMWorkRetriever
    from .persistence import MemoryPersistence
    from .retrieval_result import RetrievalResult
    from .schema import MemoryOperation, MemoryRecord, TaskContext
except ImportError:  # pragma: no cover
    from memory.bank import MemoryBank
    from memory.entry import MemoryEntry
    from memory.llm_retrieval import LLMWorkRetriever
    from memory.persistence import MemoryPersistence
    from memory.retrieval_result import RetrievalResult
    from memory.schema import MemoryOperation, MemoryRecord, TaskContext

logger = logging.getLogger(__name__)


class MemoryStore:
    """Storage backend interface used by ReMemAgent."""

    def retrieve(self, query: str, context, role, k: int) -> List[MemoryRecord]:
        raise NotImplementedError

    def apply_operations(
        self, operations: List[MemoryOperation], context, role
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def append_task_result(
        self,
        task_input: str,
        action_output: str,
        feedback: str,
        context,
        role,
    ) -> Optional[MemoryRecord]:
        raise NotImplementedError

    def save(self) -> bool:
        return True

    def memory_size(self) -> int:
        return 0


class JsonMemoryStore(MemoryStore):
    """Adapter that preserves the existing JSON MemoryBank behavior."""

    def __init__(
        self,
        memory_bank: Optional[MemoryBank] = None,
        persistence: Optional[MemoryPersistence] = None,
        llm: Optional[Any] = None,
        include_explanations: bool = True,
    ):
        self.memory_bank = memory_bank if memory_bank is not None else MemoryBank()
        self.persistence = persistence
        self.llm = llm
        self.include_explanations = include_explanations
        self.last_apply_result: Dict[str, Any] = {}

    def set_llm(self, llm: Any) -> None:
        self.llm = llm

    def retrieve(self, query: str, context, role, k: int) -> List[MemoryRecord]:
        if not self.memory_bank.entries:
            return []

        if self.llm is None:
            raise RuntimeError("LLM is required for memory retrieval")
        raw_results = self.memory_bank.retrieve(
            self.llm,
            query,
            k=k,
            include_explanations=self.include_explanations,
        )
        return [self._record_from_retrieval(item) for item in raw_results]

    def apply_operations(
        self, operations: List[MemoryOperation], context, role
    ) -> Dict[str, Any]:
        result = _empty_apply_result(operations)
        deleted_indices: List[int] = []
        for operation in operations:
            op_type = operation.operation_type
            try:
                if op_type == "no_op":
                    result["skipped"].append(
                        _operation_result(operation, "no_op", "no operation requested")
                    )
                    continue
                if op_type in {"add", "append"}:
                    entry = MemoryEntry(
                        x=context.task_type,
                        y=operation.content,
                        feedback="refine",
                        tag=str(operation.metadata.get("tag") or "refine"),
                    )
                    self.memory_bank.add(entry)
                    result["applied_operations"].append(
                        _operation_result(operation, "applied", entry.id)
                    )
                elif op_type == "delete":
                    indices = _operation_indices(operation)
                    self.memory_bank.delete(indices)
                    deleted_indices.extend(indices)
                    result["applied_operations"].append(
                        _operation_result(operation, "applied", {"indices": indices})
                    )
                elif op_type == "merge":
                    indices = _operation_indices(operation)
                    if len(indices) != 2:
                        raise ValueError("merge requires exactly two indices")
                    adjusted = [
                        _adjust_index_after_deletes(index, deleted_indices)
                        for index in indices
                    ]
                    if adjusted[0] is None or adjusted[1] is None:
                        result["skipped"].append(
                            _operation_result(
                                operation,
                                "skipped",
                                "merge target was deleted earlier in this batch",
                            )
                        )
                        continue
                    self.memory_bank.merge(adjusted[0], adjusted[1])
                    result["applied_operations"].append(
                        _operation_result(operation, "applied", {"indices": indices})
                    )
                elif op_type == "relabel":
                    indices = _operation_indices(operation)
                    if not indices:
                        raise ValueError("relabel requires an index")
                    adjusted_index = _adjust_index_after_deletes(
                        indices[0], deleted_indices
                    )
                    if adjusted_index is None:
                        if self.memory_bank.entries:
                            adjusted_index = min(indices[0], len(self.memory_bank.entries) - 1)
                        else:
                            result["skipped"].append(
                                _operation_result(
                                    operation,
                                    "skipped",
                                    "relabel target was deleted earlier in this batch",
                                )
                            )
                            continue
                    new_tag = operation.content or operation.metadata.get("new_tag")
                    self.memory_bank.relabel(adjusted_index, str(new_tag))
                    result["applied_operations"].append(
                        _operation_result(operation, "applied", {"index": adjusted_index})
                    )
                elif op_type == "replace":
                    self._replace_entry(operation)
                    result["applied_operations"].append(
                        _operation_result(operation, "applied", operation.target)
                    )
                elif op_type == "flag_conflict":
                    entry = MemoryEntry(
                        x=context.task_type,
                        y=operation.content,
                        feedback="conflict",
                        tag="conflict",
                    )
                    self.memory_bank.add(entry)
                    conflict = _operation_result(operation, "conflict", entry.id)
                    result["conflicts"].append(conflict)
                    result["applied_operations"].append(conflict)
                else:
                    result["skipped"].append(
                        _operation_result(operation, "unsupported", op_type)
                    )
            except Exception as exc:
                result["success"] = False
                result["skipped"].append(
                    _operation_result(operation, "error", str(exc))
                )
                logger.warning("JSON memory operation failed: %s", exc)

        self.last_apply_result = result
        return result

    def append_task_result(
        self,
        task_input: str,
        action_output: str,
        feedback: str,
        context,
        role,
    ) -> Optional[MemoryRecord]:
        content = _strip_act_prefix(action_output)
        entry = MemoryEntry(
            x=task_input,
            y=content,
            feedback=feedback,
            tag=str(context.metadata.get("result_tag") or "task"),
        )
        self.memory_bank.add(entry)
        record = self._record_from_entry(entry)
        self.last_apply_result = {
            "success": True,
            "total_operations": 1,
            "applied_operations": [
                {
                    "operation": {
                        "operation_type": "append_task_result",
                        "target": "json.memory_bank",
                        "content": content,
                        "metadata": {},
                    },
                    "status": "applied",
                    "detail": entry.id,
                }
            ],
            "conflicts": [],
            "skipped": [],
        }
        return record

    def save(self) -> bool:
        if self.persistence is None:
            return True
        return self.persistence.save(self.memory_bank)

    def memory_size(self) -> int:
        return len(self.memory_bank)

    def get_statistics(self) -> Dict[str, Any]:
        return self.memory_bank.get_statistics()

    def _replace_entry(self, operation: MemoryOperation) -> None:
        target = operation.target
        entry_id = operation.metadata.get("entry_id") or target
        index = operation.metadata.get("index")
        if isinstance(index, int):
            self.memory_bank.entries[index].y = operation.content
            return
        for entry in self.memory_bank.entries:
            if entry.id == entry_id:
                entry.y = operation.content
                return
        raise ValueError(f"entry not found: {entry_id}")

    def _record_from_retrieval(
        self, item: Union[MemoryEntry, RetrievalResult]
    ) -> MemoryRecord:
        if isinstance(item, RetrievalResult):
            entry = item.memory_entry
            metadata = {
                "type": "RetrievalResult",
                "memory_entry": entry.to_dict(),
                "explanation": item.explanation,
                "tag": entry.tag,
            }
            return MemoryRecord(
                id=entry.id,
                content=entry.to_text(),
                metadata=metadata,
                score=item.relevance_score,
            )
        return self._record_from_entry(item)

    def _record_from_entry(self, entry: MemoryEntry) -> MemoryRecord:
        return MemoryRecord(
            id=entry.id,
            content=entry.to_text(),
            metadata={"type": "MemoryEntry", "memory_entry": entry.to_dict()},
            score=None,
        )


class MarkdownLayerMemoryStore(MemoryStore):
    """MemoryStore backed by the six Markdown layers in ``works/{work_id}``."""

    def __init__(self):
        if memory_manager is None:
            raise RuntimeError("memory_manager module is required")
        self.last_apply_result: Dict[str, Any] = {}
        self._last_work_id = ""
        self.llm: Optional[Any] = None

    def set_llm(self, llm: Any) -> None:
        self.llm = llm

    def retrieve(self, query: str, context, role, k: int) -> List[MemoryRecord]:
        work_id = _work_id(context)
        self._last_work_id = work_id
        layer_ids = self._target_layers(context, role)
        if context.metadata.get("skip_retrieval") is True:
            return []
        if self.llm is None:
            raise RuntimeError("LLM retrieval requires a configured llm")
        run = LLMWorkRetriever(self.llm).retrieve(
            work_id=work_id,
            query=query,
            layer_ids=layer_ids,
            top_k=k,
            include_answer=False,
        )
        return [
            MemoryRecord(
                id=hit.chunk.chunk_id,
                content=(
                    f"## {hit.chunk.layer_name}\n"
                    f"### {' / '.join(hit.chunk.heading_path) or '无标题'}\n"
                    f"{hit.chunk.content}"
                ),
                metadata={
                    "work_id": work_id,
                    "layer_id": hit.chunk.layer_id,
                    "layer_name": hit.chunk.layer_name,
                    "layer_file": hit.chunk.layer_file,
                    "heading_path": list(hit.chunk.heading_path),
                    "reason": hit.reason,
                    "matched_facts": list(hit.matched_facts),
                    "retrieval_mode": "llm",
                },
                score=hit.score,
            )
            for hit in run.hits
        ]

    def apply_operations(
        self, operations: List[MemoryOperation], context, role
    ) -> Dict[str, Any]:
        self._last_work_id = _work_id(context)
        result = _empty_apply_result(operations)
        for operation in operations:
            op_type = operation.operation_type
            try:
                if op_type == "no_op":
                    result["skipped"].append(
                        _operation_result(operation, "no_op", "no operation requested")
                    )
                    continue
                if op_type == "flag_conflict":
                    conflict = self._record_conflict(operation, context, role)
                    result["conflicts"].append(conflict)
                    result["applied_operations"].append(conflict)
                    continue
                if op_type in {"delete", "relabel"}:
                    result["skipped"].append(
                        _operation_result(
                            operation,
                            "unsupported",
                            "MarkdownLayerMemoryStore does not delete or relabel text blocks",
                        )
                    )
                    continue

                layer_id = self._operation_layer_id(operation, context, role)
                if not layer_id:
                    result["skipped"].append(
                        _operation_result(operation, "skipped", "missing layer_id")
                    )
                    continue

                current = memory_manager.get_layer_content(_work_id(context), layer_id)
                if current.get("locked") and role.role_name != "制片人":
                    conflict = self._record_conflict(
                        MemoryOperation(
                            operation_type="flag_conflict",
                            target=operation.target,
                            content=operation.content,
                            metadata={
                                **operation.metadata,
                                "layer_id": layer_id,
                                "reason": "locked_layer",
                            },
                        ),
                        context,
                        role,
                    )
                    result["conflicts"].append(conflict)
                    result["skipped"].append(conflict)
                    continue

                next_content = self._next_layer_content(current["content"], operation)
                memory_manager.update_layer_content(
                    work_id=_work_id(context),
                    layer_id=layer_id,
                    content=next_content,
                    operator=role.role_name,
                    extra_metadata=self._extra_metadata(context, role, operation),
                )
                result["applied_operations"].append(
                    _operation_result(
                        operation,
                        "applied",
                        {
                            "work_id": _work_id(context),
                            "layer_id": layer_id,
                            "content_length": len(operation.content),
                        },
                    )
                )
            except Exception as exc:
                result["success"] = False
                result["skipped"].append(
                    _operation_result(operation, "error", str(exc))
                )
                logger.warning("Markdown memory operation failed: %s", exc)
        self.last_apply_result = result
        return result

    def append_task_result(
        self,
        task_input: str,
        action_output: str,
        feedback: str,
        context,
        role,
    ) -> Optional[MemoryRecord]:
        if context.metadata.get("update_memory") is False:
            self.last_apply_result = _empty_apply_result([])
            return None

        operations = self._operations_from_action_output(action_output, context, role)
        if not operations:
            default_layer = self._default_output_layer(context, role)
            if default_layer is None:
                self.last_apply_result = _empty_apply_result([])
                return None
            operations = [
                MemoryOperation(
                    operation_type="append",
                    target="memory.layer",
                    content=_strip_act_prefix(action_output),
                    metadata={"layer_id": default_layer, "source": "act_output"},
                )
            ]

        apply_result = self.apply_operations(operations, context, role)
        return MemoryRecord(
            id=f"{_work_id(context)}:{context.metadata.get('task_id', 'task_result')}",
            content=_strip_act_prefix(action_output),
            metadata={"apply_result": apply_result},
            score=None,
        )

    def save(self) -> bool:
        return True

    def memory_size(self) -> int:
        try:
            return len(memory_manager.get_work_layers(self._last_work_id))
        except Exception:
            return 0

    def _target_layers(self, context, role) -> List[str]:
        policy = role.retrieval_policy(context) or {}
        raw_layers = (
            policy.get("target_layers")
            or context.metadata.get("target_layers")
            or [layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS]
        )
        layer_ids = []
        valid_ids = {layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS}
        for layer_id in raw_layers:
            if layer_id in valid_ids and layer_id not in layer_ids:
                layer_ids.append(layer_id)
        return layer_ids

    def _operation_layer_id(self, operation, context, role) -> Optional[str]:
        candidates = [
            operation.metadata.get("layer_id"),
            operation.metadata.get("target_layer"),
            operation.target.replace("layer:", "") if operation.target else "",
            operation.target,
        ]
        valid_ids = {layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS}
        for candidate in candidates:
            if candidate in valid_ids:
                return candidate
        target_layers = context.metadata.get("target_layers") or []
        if len(target_layers) == 1 and target_layers[0] in valid_ids:
            return target_layers[0]
        return None

    def _next_layer_content(self, current_content: str, operation: MemoryOperation) -> str:
        content = operation.content.strip()
        mode = operation.metadata.get("mode") or operation.operation_type
        if mode == "replace" or operation.operation_type == "replace":
            return content
        old = current_content.rstrip()
        if not old:
            return content
        if not content:
            return old
        return f"{old}\n\n{content}"

    def _extra_metadata(
        self, context, role, operation: MemoryOperation
    ) -> Dict[str, Any]:
        extra = {
            "last_task_id": context.metadata.get("task_id", ""),
            "last_role_id": role.role_id,
            "last_role_name": role.role_name,
            "last_trace_id": context.metadata.get("trace_id", ""),
        }
        for key in ("llm_model", "llm_provider", "source_system", "external_work_id"):
            if context.metadata.get(key):
                extra[key] = context.metadata[key]
        layer_metadata = context.metadata.get("layer_metadata")
        if isinstance(layer_metadata, dict):
            extra.update(layer_metadata)
        operation_metadata = operation.metadata.get("extra_metadata")
        if isinstance(operation_metadata, dict):
            extra.update(operation_metadata)
        return extra

    def _operations_from_action_output(
        self, action_output: str, context, role
    ) -> List[MemoryOperation]:
        updates = []
        extract = getattr(memory_manager, "_extract_memory_updates", None)
        if callable(extract):
            updates = extract(action_output)
        else:
            updates = _extract_json_memory_updates(action_output)

        operations: List[MemoryOperation] = []
        for update in updates:
            layer_id = update.get("layer_id")
            content = update.get("content", "")
            if not layer_id or not isinstance(content, str):
                continue
            metadata = {
                "layer_id": layer_id,
                "mode": "replace" if update.get("mode") == "replace" else "append",
                "source": "act_memory_updates",
            }
            operations.append(
                MemoryOperation(
                    operation_type="replace" if metadata["mode"] == "replace" else "append",
                    target="memory.layer",
                    content=content,
                    metadata=metadata,
                )
            )
        return operations

    def _default_output_layer(self, context, role) -> Optional[str]:
        valid_layer_ids = {
            layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS
        }
        target_layers = [
            layer_id
            for layer_id in (context.metadata.get("target_layers") or [])
            if layer_id in valid_layer_ids
        ]
        if target_layers:
            if "script_archive" in target_layers:
                return "script_archive"
            return target_layers[-1]
        if role.role_id == "storyboard":
            return "storyboard_archive"
        if role.role_id == "producer":
            return "work_metadata"
        if role.role_id == "consistency_reviewer":
            return None
        return "script_archive"

    def _record_conflict(self, operation, context, role) -> Dict[str, Any]:
        conflict = _operation_result(
            operation,
            "conflict",
            {
                "work_id": _work_id(context),
                "layer_id": operation.metadata.get("layer_id"),
                "reason": operation.metadata.get("reason", "flag_conflict"),
                "role_id": role.role_id,
                "role_name": role.role_name,
            },
        )
        try:
            trace_dir = _work_trace_dir(_work_id(context))
            trace_dir.mkdir(parents=True, exist_ok=True)
            with (trace_dir / "conflicts.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(conflict, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("failed to write conflict log: %s", exc)
        return conflict


class InMemoryTraceStore:
    """TraceStore implementation useful for JSON memory and tests."""

    def __init__(self):
        self.traces: List[Dict[str, Any]] = []
        self._active: Dict[str, Dict[str, Any]] = {}

    def record_task_started(self, task_id: str, task_input: str, context, role) -> str:
        trace = {
            "task_id": task_id,
            "trace_id": context.metadata.get("trace_id") or task_id,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": "",
            "task_input": task_input,
            "context": context.to_dict(),
            "role": role.to_dict(),
            "events": [],
            "status": "running",
        }
        self._active[task_id] = trace
        self.traces.append(trace)
        self._persist(trace, context)
        return trace["trace_id"]

    def record_retrieval(self, task_id: str, records: List[MemoryRecord]) -> None:
        self._event(task_id, "retrieval", {"records": [r.to_dict() for r in records]})

    def record_think(self, task_id: str, output: str) -> None:
        self._event(task_id, "think", {"output": output})

    def record_refine(
        self,
        task_id: str,
        raw_output: str,
        operations: List[MemoryOperation],
        apply_result: Dict[str, Any],
    ) -> None:
        self._event(
            task_id,
            "refine",
            {
                "raw_output": raw_output,
                "operations": [operation.to_dict() for operation in operations],
                "apply_result": apply_result,
            },
        )

    def record_act(
        self,
        task_id: str,
        output: str,
        append_result: Optional[MemoryRecord],
        apply_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {"output": output}
        if append_result is not None:
            payload["append_result"] = append_result.to_dict()
        if apply_result is not None:
            payload["apply_result"] = apply_result
        self._event(task_id, "act", payload)

    def record_task_finished(
        self, task_id: str, status: str, result: Dict[str, Any]
    ) -> None:
        trace = self._active.get(task_id)
        if trace is None:
            return
        trace["finished_at"] = datetime.utcnow().isoformat()
        trace["status"] = status
        trace["result_summary"] = {
            key: value
            for key, value in result.items()
            if key
            in {
                "status",
                "iterations",
                "retrieved_count",
                "memory_updated",
                "conflicts",
            }
        }
        self._persist(trace, TaskContext.from_value(trace.get("context")))

    def list_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.traces[-limit:]

    def _event(self, task_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        trace = self._active.get(task_id)
        if trace is None:
            return
        trace["events"].append(
            {
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": payload,
            }
        )
        self._persist(trace, TaskContext.from_value(trace.get("context")))

    def _persist(self, trace: Dict[str, Any], context) -> None:
        return None


class JsonTraceStore(InMemoryTraceStore):
    """TraceStore that writes one JSON file per task."""

    def __init__(self, trace_dir: str = "./data/traces"):
        super().__init__()
        self.trace_dir = Path(trace_dir)

    def _persist(self, trace: Dict[str, Any], context) -> None:
        try:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            path = self.trace_dir / f"{trace['task_id']}.json"
            path.write_text(
                json.dumps(trace, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("failed to persist trace: %s", exc)


class MarkdownTraceStore(InMemoryTraceStore):
    """TraceStore that writes traces under ``works/{work_id}/.traces``."""

    def _persist(self, trace: Dict[str, Any], context) -> None:
        try:
            ctx = context if isinstance(context, TaskContext) else TaskContext.from_value(context)
            work_id = ctx.metadata.get("work_id")
            if not work_id:
                return
            trace_dir = _work_trace_dir(work_id)
            trace_dir.mkdir(parents=True, exist_ok=True)
            path = trace_dir / f"{trace['task_id']}.json"
            path.write_text(
                json.dumps(trace, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("failed to persist Markdown trace: %s", exc)


def _empty_apply_result(operations: List[MemoryOperation]) -> Dict[str, Any]:
    return {
        "success": True,
        "total_operations": len(operations),
        "applied_operations": [],
        "conflicts": [],
        "skipped": [],
    }


def _operation_result(
    operation: MemoryOperation, status: str, detail: Any
) -> Dict[str, Any]:
    return {
        "operation": operation.to_dict(),
        "status": status,
        "detail": detail,
    }


def _operation_indices(operation: MemoryOperation) -> List[int]:
    indices = operation.metadata.get("indices")
    if indices is None and "index" in operation.metadata:
        indices = [operation.metadata["index"]]
    if indices is None and operation.target:
        found = re.findall(r"\d+", operation.target)
        indices = [int(item) for item in found]
    if not isinstance(indices, list):
        indices = [indices]
    return [int(item) for item in indices]


def _adjust_index_after_deletes(idx: int, deleted_indices: List[int]) -> Optional[int]:
    if idx in deleted_indices:
        return None
    return idx - sum(1 for deleted_idx in deleted_indices if deleted_idx < idx)


def _strip_act_prefix(text: str) -> str:
    stripped = (text or "").strip()
    if stripped.startswith("Act:"):
        return stripped[4:].strip()
    return stripped


def _work_id(context) -> str:
    work_id = context.metadata.get("work_id")
    if not work_id:
        raise ValueError("TaskContext.metadata.work_id is required")
    return str(work_id)


def _work_trace_dir(work_id: str) -> Path:
    if memory_manager is not None and hasattr(memory_manager, "_work_dir"):
        return memory_manager._work_dir(work_id) / ".traces"
    return Path("works") / work_id / ".traces"


def _extract_json_memory_updates(text: str) -> List[Dict[str, Any]]:
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        updates = data.get("memory_updates")
        if isinstance(updates, list):
            return [item for item in updates if isinstance(item, dict)]
    return []


def new_task_id() -> str:
    return str(uuid.uuid4())
