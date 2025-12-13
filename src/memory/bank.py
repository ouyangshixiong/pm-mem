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

        # 如果已达到最大容量，删除最旧的条目以腾出空间
        if len(self.entries) >= self.max_entries:
            logger.warning(f"记忆库已达最大容量 {self.max_entries}，将删除最旧的条目")
            # 按时间排序，删除最旧的
            self.entries.sort(key=lambda e: e.timestamp)
            deleted_entry = self.entries.pop(0)
            # 记录删除操作
            self._record_operation(
                operation_type="prune",
                details={
                    "deleted_entry_id": deleted_entry.id,
                    "reason": "capacity_full"
                },
                success=True
            )
            logger.debug(f"删除最旧的记忆条目: {deleted_entry.id}")

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

        # PM-111: 改进的LLM提示词模板
        memory_text = "\n\n".join(
            [f"[{i}]\n{e.to_text()}" for i, e in enumerate(self.entries)]
        )

        prompt = f"""
# 记忆检索评估任务

你是一个专业的记忆检索器，需要评估记忆条目与用户查询的相关性。

## 用户查询
"{query}"

## 记忆条目列表（共{len(self.entries)}个）
{memory_text}

## 任务要求
请为每个记忆条目（索引0到{len(self.entries)-1}）评估其与查询的相关性，并严格输出有效的JSON对象（不要使用代码块标记，不要添加额外文字）。输出格式为一个对象，包含字段：
- "results": 数组，其中每个元素包含 "index"、"relevance_score"、"semantic_relevance"、"task_applicability"、"timeliness"、"explanation"

## 评估维度说明（评分范围：0.0-1.0，保留两位小数）

### 1. 语义相关性 (semantic_relevance)
评估记忆内容与查询的语义匹配程度：
- **1.0**: 完全匹配，记忆直接回答了查询中的问题
- **0.7-0.9**: 高度相关，记忆包含查询所需的核心信息
- **0.4-0.6**: 中等相关，记忆包含部分相关信息
- **0.1-0.3**: 低度相关，只有少量关联
- **0.0**: 完全不相关

### 2. 任务适用性 (task_applicability)
评估记忆中的解决方案是否适用于当前任务：
- **1.0**: 完全适用，可以直接应用解决方案
- **0.7-0.9**: 高度适用，需要少量调整
- **0.4-0.6**: 中等适用，需要中等程度的调整
- **0.1-0.3**: 低度适用，需要大量修改
- **0.0**: 完全不适用

### 3. 时效性 (timeliness)
评估记忆的新旧程度（越新越相关）：
- **1.0**: 非常新（最近创建，时效性高）
- **0.7-0.9**: 较新（近期创建）
- **0.4-0.6**: 中等新旧（有一定时间）
- **0.1-0.3**: 较旧（创建时间较长）
- **0.0**: 非常旧（过时的信息）

### 4. 总体相关性评分 (relevance_score)
综合以上三个维度的加权平均：
- **权重**: 语义相关性(50%) + 任务适用性(30%) + 时效性(20%)
- **计算公式**: 0.5*semantic_relevance + 0.3*task_applicability + 0.2*timeliness
- **注意**: 计算结果保留两位小数

## 输出规范

### 必须遵守的规则
1. **JSON格式**: 必须输出有效的JSON对象，包含"results"数组
2. **只输出前{k}个**: 仅返回与查询最相关的前{k}个条目，按relevance_score降序
3. **评分范围**: 所有评分必须在0.0-1.0范围内，保留两位小数
4. **解释质量**: 解释应该简洁明了（1-2句话），说明为什么相关或不相关
5. **索引对应**: 每个条目的index必须与记忆条目列表中的索引一致

### 错误预防提示
1. **不要排序**: 保持原始顺序，我们会按relevance_score排序
2. **不要省略**: 即使完全不相关，也要包含所有条目（评分可以为0.0）
3. **不要添加**: 输出中不要包含额外的文本、注释或说明
4. **格式正确**: 确保JSON格式正确，没有语法错误
5. **数值类型**: 所有评分必须是数字，不是字符串

## 示例说明

### 高度相关的记忆（示例项说明）
包含较高的 "semantic_relevance" 与 "task_applicability"，并且 "timeliness" 较高

### 中等相关的记忆（示例项说明）
相关信息部分匹配，需要适当调整，时效性一般

### 低度相关的记忆（示例项说明）
仅少量关联信息，难以直接应用，可能较旧

### 完全不相关的记忆（示例项说明）
与查询主题不相关，无法应用

## 开始评估

请严格按照上述要求，为记忆条目进行评估，并输出完整的JSON结果。
记住：只需返回前{k}个条目，不要添加额外文本。
"""
        try:
            # 调用LLM获取评估结果
            # 根据模型上下文长度动态裁剪提示
            model_info = {}
            try:
                model_info = llm.get_model_info()
            except Exception:
                model_info = {}
            context_len = int(model_info.get("context_length_tokens", 64000))
            # 估算字符预算（混合文本约0.5 token/char）
            char_budget = int((context_len - 2048) / 0.5)
            if len(prompt) > char_budget:
                # 尽量裁剪记忆部分，以保留任务与规则
                head_split = prompt.split("## 记忆条目列表", 1)
                if len(head_split) == 2:
                    head = head_split[0]
                    body = "## 记忆条目列表" + head_split[1]
                    keep_head = min(len(head), int(char_budget * 0.4))
                    keep_body = max(0, char_budget - keep_head)
                    prompt = head[:keep_head] + "\n...\n" + body[:keep_body]
                else:
                    prompt = prompt[:char_budget]
            result_text = llm(prompt)

            # PM-113: 使用健壮的JSON解析方法
            result_data = self._parse_json_response(result_text)
            if result_data is None:
                # JSON解析失败，使用回退检索
                logger.warning("JSON解析失败，使用回退检索")
                return self._fallback_retrieval(query, k, include_explanations)

            if "results" not in result_data:
                logger.error("响应中缺少'results'字段")
                return self._fallback_retrieval(query, k, include_explanations)

            # 提取评估结果
            evaluations = []
            for item in result_data["results"]:
                if "index" not in item or "relevance_score" not in item:
                    logger.warning(f"跳过无效的评估项: {item}")
                    continue

                idx = item["index"]

                # PM-112: 多维度评分解析和验证
                try:
                    score = self._validate_and_parse_score(item, "relevance_score")
                    semantic_relevance = self._validate_and_parse_score(item, "semantic_relevance", 0.0)
                    task_applicability = self._validate_and_parse_score(item, "task_applicability", 0.0)
                    timeliness = self._validate_and_parse_score(item, "timeliness", 0.0)
                except ValueError as e:
                    logger.warning(f"评分验证失败: {e}")
                    continue

                explanation = item.get("explanation", "")

                # 验证索引范围
                if 0 <= idx < len(self.entries):
                    evaluations.append({
                        "index": idx,
                        "score": score,
                        "semantic_relevance": semantic_relevance,
                        "task_applicability": task_applicability,
                        "timeliness": timeliness,
                        "explanation": explanation
                    })
                else:
                    logger.warning(f"索引超出范围: {idx}")

            # PM-121: 按相关性评分排序
            evaluations.sort(key=lambda x: x["score"], reverse=True)

            # PM-121: 取前k个结果
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

        except Exception as e:
            logger.error(f"LLM检索失败: {e}")
            # 回退到简单检索
            return self._fallback_retrieval(query, k, include_explanations)

    def _parse_json_response(self, result_text: str) -> Optional[Dict[str, Any]]:
        """
        PM-113: 健壮的JSON解析方法

        Args:
            result_text: LLM返回的文本

        Returns:
            解析后的JSON数据，如果解析失败返回None
        """
        if not result_text or not isinstance(result_text, str):
            logger.error("结果文本为空或不是字符串")
            return None

        # 如果存在代码块（```json ... ```），优先提取其中内容
        try:
            if "```json" in result_text:
                start = result_text.find("```json")
                end = result_text.find("```", start + 7)
                if end != -1:
                    fenced = result_text[start + 7:end].strip()
                    cleaned = fenced.replace("…", "").replace("...", "")
                    result_data = json.loads(cleaned)
                    logger.debug("从JSON代码块解析成功")
                    return result_data
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON代码块解析失败: {e}")

        # 尝试直接解析JSON
        try:
            result_data = json.loads(result_text)
            logger.debug("JSON解析成功")
            return result_data
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")

        # PM-113: 尝试提取JSON部分（处理LLM可能添加的额外文本）
        try:
            # 尝试查找JSON对象开始和结束位置
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}')

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = result_text[start_idx:end_idx + 1]
                json_str = json_str.replace("```", "").replace("…", "").replace("...", "")
                result_data = json.loads(json_str)
                logger.debug("从文本中提取JSON成功")
                return result_data
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"提取JSON失败: {e}")

        # PM-113: 尝试处理常见的JSON格式问题
        try:
            # 处理可能的单引号问题
            normalized_text = result_text.replace("'", '"')
            # 处理可能的尾部逗号
            normalized_text = normalized_text.replace(',\n}', '\n}').replace(',\n]', '\n]')
            # 去除代码块标记和省略号
            normalized_text = normalized_text.replace("```json", "").replace("```", "")
            normalized_text = normalized_text.replace("…", "").replace("...", "")
            result_data = json.loads(normalized_text)
            logger.debug("规范化后JSON解析成功")
            return result_data
        except json.JSONDecodeError as e:
            logger.warning(f"规范化JSON解析失败: {e}")

        # 尝试提取 "results" 数组并重构JSON
        try:
            key_idx = result_text.find('"results"')
            if key_idx != -1:
                # 找到数组起始 '['
                arr_start = result_text.find('[', key_idx)
                if arr_start != -1:
                    # 计数匹配 '[]' 边界，忽略对象内的大括号
                    depth = 0
                    i = arr_start
                    while i < len(result_text):
                        ch = result_text[i]
                        if ch == '[':
                            depth += 1
                        elif ch == ']':
                            depth -= 1
                            if depth == 0:
                                arr_end = i
                                break
                        i += 1
                    else:
                        arr_end = -1

                    if arr_end != -1:
                        array_str = result_text[arr_start:arr_end + 1]
                        # 清理常见噪音
                        array_str = array_str.replace("```json", "").replace("```", "")
                        array_str = array_str.replace("…", "").replace("...", "")
                        array_str = array_str.replace(",]", "]")
                        # 重构为标准JSON对象
                        reconstructed = f'{{"results": {array_str}}}'
                        result_data = json.loads(reconstructed)
                        # logger.debug("通过提取results数组重构JSON成功")
                        return result_data
        except Exception as e:
            logger.warning(f"提取results数组重构JSON失败: {e}")

        # 记录原始响应（前500个字符）用于调试
        # logger.error(f"无法解析JSON响应，原始响应前500字符: {result_text[:500]}...")
        return None

    def _validate_and_parse_score(self, item: Dict[str, Any], score_key: str, default: float = 0.5) -> float:
        """
        PM-112: 增强的多维度评分验证和解析方法

        Args:
            item: 评分项字典，包含各个维度的评分
            score_key: 评分键名（如'relevance_score', 'semantic_relevance'等）
            default: 默认评分值（当评分无效时使用），根据评分类型设置合理的默认值

        Returns:
            验证后的评分值（0.0-1.0），保留两位小数

        Raises:
            ValueError: 如果评分无效且无法恢复
        """
        # 参数验证
        if not isinstance(item, dict):
            logger.error(f"评分项必须是字典，实际类型: {type(item)}")
            raise ValueError(f"评分项必须是字典，实际类型: {type(item)}")

        if not isinstance(score_key, str) or not score_key.strip():
            logger.error(f"评分键名必须是非空字符串，实际值: {score_key}")
            raise ValueError(f"评分键名必须是非空字符串，实际值: {score_key}")

        if not isinstance(default, (int, float)) or not (0.0 <= default <= 1.0):
            logger.warning(f"默认值必须在0.0-1.0范围内，实际值: {default}，使用0.5")
            default = 0.5

        # 检查评分字段是否存在
        if score_key not in item:
            logger.warning(f"评分项中缺少'{score_key}'字段，使用默认值{default}")
            return round(default, 2)

        score_value = item[score_key]

        # 类型检查和处理
        if score_value is None:
            logger.warning(f"'{score_key}'字段值为None，使用默认值{default}")
            return round(default, 2)

        # 尝试转换为浮点数
        try:
            if isinstance(score_value, str):
                # 处理字符串类型的评分
                score_str = score_value.strip()
                if not score_str:
                    logger.warning(f"'{score_key}'字段为空字符串，使用默认值{default}")
                    return round(default, 2)

                # 尝试解析字符串
                score = float(score_str)
            elif isinstance(score_value, (int, float)):
                score = float(score_value)
            else:
                logger.warning(f"'{score_key}'字段类型不支持: {type(score_value)}，使用默认值{default}")
                return round(default, 2)

        except (ValueError, TypeError) as e:
            logger.warning(f"无法将'{score_key}'转换为数字: {score_value}，错误: {e}，使用默认值{default}")
            return round(default, 2)

        # 严格的范围验证
        if not (0.0 <= score <= 1.0):
            # 记录详细的错误信息
            logger.warning(
                f"'{score_key}'评分超出有效范围[0.0, 1.0]: {score}，"
                f"调整为默认值{default}"
            )

            # 对于轻微超出范围的情况，可以尝试修正
            if score < 0.0:
                logger.debug(f"负分修正为0.0: {score}")
                score = 0.0
            elif score > 1.0:
                logger.debug(f"超过1.0的分数修正为1.0: {score}")
                score = 1.0
            else:
                # 其他情况使用默认值
                return round(default, 2)

        # 精度处理：保留两位小数，确保在有效范围内
        score = round(score, 2)

        # 最终范围检查（处理四舍五入后可能超出范围的情况）
        if score < 0.0:
            score = 0.0
        elif score > 1.0:
            score = 1.0

        # 验证特定评分类型的合理性
        if score_key == "relevance_score":
            # 总体相关性评分应该与其他维度评分一致
            if "semantic_relevance" in item and "task_applicability" in item and "timeliness" in item:
                try:
                    semantic = float(item.get("semantic_relevance", 0.0))
                    task = float(item.get("task_applicability", 0.0))
                    time = float(item.get("timeliness", 0.0))

                    # 计算期望的加权评分
                    expected_score = 0.5 * semantic + 0.3 * task + 0.2 * time
                    expected_score = round(expected_score, 2)

                    # 如果实际评分与期望评分差异过大，记录警告
                    if abs(score - expected_score) > 0.2:  # 允许20%的差异
                        pass
                        # logger.debug(
                        #     f"'{score_key}'评分({score})与计算值({expected_score})差异较大。"
                        #     f"语义相关性: {semantic}, 任务适用性: {task}, 时效性: {time}"
                        # )
                except (ValueError, TypeError):
                    pass  # 忽略计算错误
        # logger.debug(f"成功解析'{score_key}'评分: {score}")
        return score

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

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆库统计信息（get_statistics的别名）

        Returns:
            包含统计信息的字典
        """
        return self.get_statistics()

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

    # ====== 新增方法：基础管理功能 ======

    def add_entry(self, entry: MemoryEntry) -> None:
        """
        添加记忆条目（add方法的别名，保持API一致性）

        Args:
            entry: 要添加的记忆条目
        """
        self.add(entry)

    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        根据ID获取记忆条目

        Args:
            entry_id: 记忆条目ID

        Returns:
            找到的记忆条目，如果不存在返回None
        """
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def delete_entry(self, entry_id: str) -> bool:
        """
        根据ID删除记忆条目

        Args:
            entry_id: 要删除的记忆条目ID

        Returns:
            是否成功删除
        """
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.delete([i])
                return True
        return False

    def update_entry(self, entry_id: str, **kwargs) -> bool:
        """
        更新记忆条目

        Args:
            entry_id: 要更新的记忆条目ID
            **kwargs: 要更新的字段和值

        Returns:
            是否成功更新
        """
        for entry in self.entries:
            if entry.id == entry_id:
                try:
                    # 更新允许的字段
                    allowed_fields = {"x", "y", "feedback", "tag", "timestamp"}
                    for field, value in kwargs.items():
                        if field in allowed_fields:
                            setattr(entry, field, value)

                    # 记录操作历史
                    self._record_operation(
                        operation_type="update",
                        details={
                            "entry_id": entry_id,
                            "updated_fields": list(kwargs.keys())
                        },
                        success=True
                    )

                    logger.debug(f"更新记忆条目: {entry_id}")
                    return True
                except Exception as e:
                    logger.error(f"更新记忆条目失败: {e}")
                    return False
        return False

    # ====== 新增方法：检索接口和统计功能 ======

    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """
        简单文本搜索（基于关键词匹配）

        Args:
            query: 搜索查询
            limit: 返回的最大结果数

        Returns:
            匹配的记忆条目列表
        """
        if not query or not query.strip():
            return []

        query_lower = query.lower()
        results = []

        for entry in self.entries:
            # 检查x、y、feedback、tag字段是否包含查询词
            if (query_lower in entry.x.lower() or
                query_lower in entry.y.lower() or
                query_lower in entry.feedback.lower() or
                query_lower in entry.tag.lower()):
                results.append(entry)

            if len(results) >= limit:
                break

        return results

    def filter_by_tag(self, tag: str) -> List[MemoryEntry]:
        """
        根据标签过滤记忆条目

        Args:
            tag: 标签名称

        Returns:
            具有指定标签的记忆条目列表
        """
        if not tag:
            return []

        return [entry for entry in self.entries if entry.tag == tag]

    def get_recent_entries(self, limit: int = 10) -> List[MemoryEntry]:
        """
        获取最近的记忆条目

        Args:
            limit: 返回的最大条目数

        Returns:
            最近的记忆条目列表（按时间戳降序）
        """
        sorted_entries = sorted(self.entries, key=lambda e: e.timestamp, reverse=True)
        return sorted_entries[:limit]

    def clear(self) -> None:
        """
        清空记忆库
        """
        original_count = len(self.entries)
        self.entries.clear()

        # 记录操作历史
        self._record_operation(
            operation_type="clear",
            details={
                "cleared_count": original_count
            },
            success=True
        )

        logger.info(f"清空记忆库，删除了 {original_count} 条记忆")

    def __len__(self) -> int:
        """返回记忆条目数量"""
        return len(self.entries)

    def __getitem__(self, idx: int) -> MemoryEntry:
        """通过索引获取记忆条目"""
        return self.entries[idx]

    def __repr__(self) -> str:
        """字符串表示"""
        return f"MemoryBank(entries={len(self.entries)}, max_entries={self.max_entries})"
