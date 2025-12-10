"""
记忆库管理

实现MemoryBank类管理记忆条目集合，支持添加、删除、合并、重标签操作，提供基于LLM的检索接口。
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import logging
import json

from .entry import MemoryEntry
from .retrieval_result import RetrievalResult

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
        self.operation_history: List[Dict[str, Any]] = []  # 操作历史记录

    def add(self, entry: MemoryEntry) -> None:
        """
        添加记忆条目

        Args:
            entry: 要添加的记忆条目

        Raises:
            ValueError: 如果entry不是MemoryEntry实例
        """
        if not isinstance(entry, MemoryEntry):
            raise ValueError(f"entry必须是MemoryEntry实例，实际类型: {type(entry)}")

        if len(self.entries) >= self.max_entries:
            logger.warning(f"记忆库已达最大容量 {self.max_entries}，将执行清理")
            self._prune()

        self.entries.append(entry)

        # 记录操作历史
        self._record_operation(
            operation_type="add",
            details={"entry_id": entry.id, "tag": entry.tag},
            success=True
        )

        logger.debug(f"添加记忆条目: {entry.id}")

    def delete(self, indices: List[int]) -> None:
        """
        删除指定索引的记忆条目

        Args:
            indices: 要删除的索引列表

        Raises:
            ValueError: 如果indices不是列表或包含无效值
            IndexError: 如果索引超出范围
        """
        if not isinstance(indices, list):
            raise ValueError(f"indices必须是列表，实际类型: {type(indices)}")

        if not indices:
            logger.warning("删除操作：索引列表为空")
            return

        # 验证索引
        valid_indices = []
        deleted_entries = []

        for idx in indices:
            if not isinstance(idx, int):
                raise ValueError(f"索引必须是整数，实际值: {idx} (类型: {type(idx)})")

            if 0 <= idx < len(self.entries):
                valid_indices.append(idx)
                deleted_entries.append(self.entries[idx])
            else:
                raise IndexError(f"索引超出范围: {idx} (有效范围: 0-{len(self.entries)-1})")

        if not valid_indices:
            logger.warning("删除操作：没有有效的索引")
            return

        # 按降序排序以避免索引偏移
        for idx in sorted(valid_indices, reverse=True):
            deleted_entry = self.entries[idx]
            del self.entries[idx]
            logger.debug(f"删除记忆条目 {idx}: {deleted_entry.id}")

        # 记录操作历史
        self._record_operation(
            operation_type="delete",
            details={
                "indices": valid_indices,
                "deleted_count": len(valid_indices),
                "deleted_entries": [e.id for e in deleted_entries]
            },
            success=True
        )

    def merge(self, idx1: int, idx2: int) -> None:
        """
        合并两个记忆条目

        Args:
            idx1: 第一个条目的索引（合并后的条目将保留在此位置）
            idx2: 第二个条目的索引（将被删除）

        Raises:
            ValueError: 如果索引相同
            IndexError: 索引超出范围
        """
        # 验证索引类型
        if not isinstance(idx1, int) or not isinstance(idx2, int):
            raise ValueError(f"索引必须是整数，实际值: idx1={idx1}, idx2={idx2}")

        # 验证索引范围
        if not (0 <= idx1 < len(self.entries) and 0 <= idx2 < len(self.entries)):
            raise IndexError(f"合并索引超出范围: {idx1}, {idx2} (有效范围: 0-{len(self.entries)-1})")

        # 验证索引不相同
        if idx1 == idx2:
            raise ValueError(f"不能合并同一个索引: {idx1}")

        e1, e2 = self.entries[idx1], self.entries[idx2]

        # 记录原始条目信息
        original_ids = [e1.id, e2.id]

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

        # 记录操作历史
        self._record_operation(
            operation_type="merge",
            details={
                "indices": [idx1, idx2],
                "original_ids": original_ids,
                "merged_id": merged.id,
                "merged_tag": merged.tag
            },
            success=True
        )

        logger.debug(f"合并记忆条目 {idx1} 和 {idx2} -> {merged.id}")

    def relabel(self, idx: int, new_tag: str) -> None:
        """
        重新标记记忆条目

        Args:
            idx: 要重新标记的索引
            new_tag: 新标签

        Raises:
            ValueError: 如果new_tag为空或不是字符串
            IndexError: 索引超出范围
        """
        # 验证索引类型
        if not isinstance(idx, int):
            raise ValueError(f"索引必须是整数，实际值: {idx} (类型: {type(idx)})")

        # 验证索引范围
        if not (0 <= idx < len(self.entries)):
            raise IndexError(f"重标记索引超出范围: {idx} (有效范围: 0-{len(self.entries)-1})")

        # 验证新标签
        if not isinstance(new_tag, str):
            raise ValueError(f"new_tag必须是字符串，实际类型: {type(new_tag)}")

        if not new_tag.strip():
            raise ValueError("new_tag不能为空")

        # 记录原始标签
        original_tag = self.entries[idx].tag

        # 更新标签
        self.entries[idx].tag = new_tag

        # 记录操作历史
        self._record_operation(
            operation_type="relabel",
            details={
                "index": idx,
                "original_tag": original_tag,
                "new_tag": new_tag,
                "entry_id": self.entries[idx].id
            },
            success=True
        )

        logger.debug(f"重新标记记忆条目 {idx}: {original_tag} -> {new_tag}")

    def batch_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量执行操作

        Args:
            operations: 操作列表，每个操作包含type和参数

        Returns:
            包含执行结果的字典
        """
        results = {
            "total_operations": len(operations),
            "successful": 0,
            "failed": 0,
            "errors": []
        }

        for i, op in enumerate(operations):
            try:
                op_type = op.get("type")
                params = op.get("params", {})

                if op_type == "add":
                    entry_data = params.get("entry")
                    if isinstance(entry_data, dict):
                        entry = MemoryEntry.from_dict(entry_data)
                        self.add(entry)
                    else:
                        raise ValueError("add操作需要entry参数")
                elif op_type == "delete":
                    indices = params.get("indices", [])
                    self.delete(indices)
                elif op_type == "merge":
                    idx1 = params.get("idx1")
                    idx2 = params.get("idx2")
                    self.merge(idx1, idx2)
                elif op_type == "relabel":
                    idx = params.get("idx")
                    new_tag = params.get("new_tag")
                    self.relabel(idx, new_tag)
                else:
                    raise ValueError(f"未知操作类型: {op_type}")

                results["successful"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "operation_index": i,
                    "operation": op,
                    "error": str(e)
                })
                logger.error(f"批量操作失败 (索引 {i}): {e}")

        return results

    def _record_operation(self, operation_type: str, details: Dict[str, Any], success: bool = True) -> None:
        """记录操作历史"""
        operation_record = {
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            "details": details,
            "success": success,
            "memory_count_before": len(self.entries) - (1 if operation_type == "add" else 0),
            "memory_count_after": len(self.entries)
        }

        # 限制历史记录大小
        if len(self.operation_history) >= 1000:
            self.operation_history.pop(0)

        self.operation_history.append(operation_record)

    def get_operation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取操作历史记录

        Args:
            limit: 返回的最大记录数

        Returns:
            操作历史记录列表
        """
        return self.operation_history[-limit:] if self.operation_history else []

    def clear_operation_history(self) -> None:
        """清空操作历史记录"""
        self.operation_history.clear()

    def retrieve(
        self, llm, query: str, k: int = 5, include_explanations: bool = True
    ) -> List[Union[MemoryEntry, RetrievalResult]]:
        """
        基于LLM的文本相关性检索（改进版）

        Args:
            llm: LLM调用接口，需要实现 __call__(prompt: str) -> str 方法
            query: 查询文本
            k: 返回的最相关记忆数量
            include_explanations: 是否包含相关性解释

        Returns:
            最相关的k个记忆条目或检索结果列表
        """
        # PM-12: 空记忆库处理
        if not self.entries:
            logger.info("记忆库为空，返回空列表")
            return []

        # PM-12: 边界条件处理
        if k <= 0:
            logger.warning(f"无效的k值: {k}，返回空列表")
            return []

        # 如果k大于记忆库大小，调整为记忆库大小
        k = min(k, len(self.entries))

        # PM-11: 改进的LLM提示词
        memory_text = "\n\n".join(
            [f"[{i}]\n{e.to_text()}" for i, e in enumerate(self.entries)]
        )

        prompt = f"""
你是一个专业的记忆检索器。给定用户任务：
"{query}"

以下是全部记忆条目：

{memory_text}

请评估每个记忆条目与查询的相关性，并按照以下JSON格式输出：
{{
    "results": [
        {{
            "index": 0,
            "relevance_score": 0.85,
            "explanation": "这个记忆与查询相关，因为..."
        }},
        ...
    ]
}}

评估标准：
1. 语义相关性：记忆内容与查询的语义匹配程度（0.0-1.0）
2. 任务适用性：记忆中的解决方案是否适用于当前任务（0.0-1.0）
3. 时效性：记忆的新旧程度（越新越相关，0.0-1.0）

请为每个记忆条目提供：
1. 相关性评分（0.0-1.0，保留两位小数）
2. 简要解释为什么这个记忆相关

请确保：
1. 输出有效的JSON格式
2. 包含所有记忆条目
3. 评分在0.0-1.0范围内
4. 解释简洁明了
"""
        try:
            # 调用LLM获取评估结果
            result_text = llm(prompt)

            # 解析JSON响应
            try:
                result_data = json.loads(result_text)
                if "results" not in result_data:
                    raise ValueError("响应中缺少'results'字段")

                # 提取评估结果
                evaluations = []
                for item in result_data["results"]:
                    if "index" not in item or "relevance_score" not in item:
                        logger.warning(f"跳过无效的评估项: {item}")
                        continue

                    idx = item["index"]
                    score = float(item["relevance_score"])
                    explanation = item.get("explanation", "")

                    # 验证索引范围
                    if 0 <= idx < len(self.entries):
                        evaluations.append({
                            "index": idx,
                            "score": score,
                            "explanation": explanation
                        })
                    else:
                        logger.warning(f"索引超出范围: {idx}")

                # 按相关性评分排序
                evaluations.sort(key=lambda x: x["score"], reverse=True)

                # 取前k个结果
                top_k = evaluations[:k]

                # 构建返回结果
                results = []
                for eval_item in top_k:
                    idx = eval_item["index"]
                    memory_entry = self.entries[idx]

                    if include_explanations:
                        # 返回RetrievalResult对象
                        result = RetrievalResult(
                            memory_entry=memory_entry,
                            relevance_score=eval_item["score"],
                            explanation=eval_item["explanation"]
                        )
                    else:
                        # 返回原始MemoryEntry对象（向后兼容）
                        result = memory_entry

                    results.append(result)

                logger.info(f"检索完成: 查询='{query[:50]}...', 返回{len(results)}个结果")
                return results

            except json.JSONDecodeError as e:
                logger.error(f"LLM返回的不是有效JSON: {e}")
                logger.debug(f"原始响应: {result_text[:200]}...")
                # 回退到简单检索
                return self._fallback_retrieval(query, k, include_explanations)

        except Exception as e:
            logger.error(f"LLM检索失败: {e}")
            # 回退到简单检索
            return self._fallback_retrieval(query, k, include_explanations)

    def _fallback_retrieval(
        self, query: str, k: int, include_explanations: bool
    ) -> List[Union[MemoryEntry, RetrievalResult]]:
        """
        回退检索机制（当LLM调用失败时使用）

        Args:
            query: 查询文本
            k: 返回数量
            include_explanations: 是否包含解释

        Returns:
            检索结果列表
        """
        logger.warning("使用回退检索机制")

        # 简单实现：返回前k个条目
        k = min(k, len(self.entries))
        results = []

        for i in range(k):
            memory_entry = self.entries[i]

            if include_explanations:
                # 创建简单的RetrievalResult
                result = RetrievalResult(
                    memory_entry=memory_entry,
                    relevance_score=0.5,  # 默认评分
                    explanation="回退检索：按时间顺序返回"
                )
            else:
                result = memory_entry

            results.append(result)

        return results

    def _prune(self, target_ratio: float = 0.2) -> None:
        """
        清理记忆库（当达到最大容量时）

        Args:
            target_ratio: 目标删除比例（20-30%）
        """
        if len(self.entries) <= self.max_entries:
            return

        # 记录清理前的数量
        original_count = len(self.entries)

        # 简单实现：按时间排序，删除最旧的条目
        self.entries.sort(key=lambda e: e.timestamp)
        delete_count = int(len(self.entries) * target_ratio)
        delete_count = max(1, min(delete_count, len(self.entries) - self.max_entries))

        # 记录被删除的条目
        deleted_entries = self.entries[:delete_count]

        # 删除最旧的条目
        del self.entries[:delete_count]

        # 记录清理操作
        self._record_operation(
            operation_type="prune",
            details={
                "original_count": original_count,
                "deleted_count": delete_count,
                "remaining_count": len(self.entries),
                "deleted_entries": [e.id for e in deleted_entries]
            },
            success=True
        )

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
                "operation_history_count": len(self.operation_history),
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
            "operation_history_count": len(self.operation_history),
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