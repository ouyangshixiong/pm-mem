"""
ReMem Agent主循环

实现完整的Think/Refine/Act状态机，支持最大迭代次数限制和强制终止机制。
"""

from typing import Dict, Any, List, Optional
import logging
import re

from llm.llm_interface import LLMInterface
from memory.bank import MemoryBank
from memory.editor import RefineEditor
from memory.persistence import MemoryPersistence

logger = logging.getLogger(__name__)


class ReMemAgent:
    """ReMem Agent主类"""

    def __init__(
        self,
        llm: LLMInterface,
        memory_bank: Optional[MemoryBank] = None,
        persist_path: str = "./data/memory.json",
        max_iterations: int = 8,
        retrieval_k: int = 5,
    ):
        """
        初始化ReMem Agent

        Args:
            llm: LLM接口实例
            memory_bank: 记忆库实例，如为None则创建新实例
            persist_path: 持久化存储路径
            max_iterations: 最大迭代次数
            retrieval_k: 检索返回的最相关记忆数量
        """
        self.llm = llm
        self.M = memory_bank or MemoryBank()
        self.persistence = MemoryPersistence(persist_path)
        self.max_iterations = max_iterations
        self.retrieval_k = retrieval_k

        # 加载现有记忆
        self.M = self.persistence.load(self.M)

        logger.info(
            f"ReMem Agent已初始化 - 最大迭代次数: {max_iterations}, "
            f"检索数量: {retrieval_k}, 记忆条目: {len(self.M)}"
        )

    def run_task(self, task_input: str) -> Dict[str, Any]:
        """
        运行单步任务

        Args:
            task_input: 任务输入 x_t

        Returns:
            包含执行结果的字典
        """
        traces: List[str] = []
        retrieved_memories = []
        retrieved_text = ""

        logger.info(f"开始处理任务: {task_input[:100]}...")

        for iteration in range(self.max_iterations):
            logger.debug(f"第 {iteration + 1}/{self.max_iterations} 次迭代")

            # 检索相关记忆
            retrieved_memories = self.M.retrieve(self.llm, task_input, k=self.retrieval_k)
            retrieved_text = "\n".join([e.to_text() for e in retrieved_memories])

            # 让LLM选择动作
            action = self._select_action(task_input, retrieved_text, traces)
            action_lower = action.strip().lower()

            if action_lower == "think":
                result = self._think(task_input, retrieved_text, traces)
                traces.append(result)
                logger.debug(f"Think: {result[:100]}...")

            elif action_lower == "refine":
                delta, raw_cmd = self._refine(task_input, traces)
                traces.append(raw_cmd)

                # 应用编辑操作
                self._apply_delta(delta)
                logger.debug(f"Refine: {raw_cmd}")

            elif action_lower == "act":
                result = self._act(task_input, retrieved_text, traces)
                feedback = self._get_feedback(result)  # 模拟反馈，实际应从环境获取

                # 添加新记忆条目
                self._add_new_memory(task_input, result, feedback)
                logger.debug(f"Act: {result[:100]}...")

                # 持久化记忆库
                self.persistence.save(self.M)

                return {
                    "action": result,
                    "traces": traces,
                    "memory_size": len(self.M),
                    "iterations": iteration + 1,
                    "retrieved_count": len(retrieved_memories),
                    "status": "completed",
                }

            else:
                logger.warning(f"未知动作: {action}，强制转为Act")
                traces.append(f"invalid action: {action}")

                # 强制执行Act
                result = self._act(task_input, retrieved_text, traces)
                feedback = "forced"
                self._add_new_memory(task_input, result, feedback)
                self.persistence.save(self.M)

                return {
                    "action": result,
                    "traces": traces,
                    "memory_size": len(self.M),
                    "iterations": iteration + 1,
                    "retrieved_count": len(retrieved_memories),
                    "status": "forced",
                }

        # 超过最大迭代次数仍未Act，强制终止
        logger.warning(f"达到最大迭代次数 {self.max_iterations}，强制终止")
        result = self._act(task_input, retrieved_text, traces)
        feedback = "max_iterations_exceeded"
        self._add_new_memory(task_input, result, feedback)
        self.persistence.save(self.M)

        return {
            "action": result,
            "traces": traces,
            "memory_size": len(self.M),
            "iterations": self.max_iterations,
            "retrieved_count": len(retrieved_memories),
            "status": "max_iterations_exceeded",
        }

    def _select_action(self, task_input: str, retrieved_text: str, traces: List[str]) -> str:
        """选择下一步动作（Think/Refine/Act）"""
        prompt = f"""
任务: {task_input}

相关记忆:
{retrieved_text}

历史推理轨迹:
{chr(10).join(traces) if traces else "无"}

请选择下一步动作：Think / Refine / Act
只需输出动作名称。
"""
        try:
            action = self.llm(prompt).strip().lower()
            # 验证动作有效性
            valid_actions = {"think", "refine", "act"}
            if action not in valid_actions:
                logger.warning(f"无效动作选择: {action}，默认使用act")
                return "act"
            return action
        except Exception as e:
            logger.error(f"选择动作失败: {e}")
            return "act"  # 失败时默认执行Act

    def _think(self, task_input: str, retrieved_text: str, traces: List[str]) -> str:
        """执行Think动作（内部推理）"""
        # 验证输入参数
        if not task_input or not isinstance(task_input, str):
            logger.error("Think: 无效的任务输入")
            return "Think: 无效的任务输入"

        if not isinstance(traces, list):
            logger.error("Think: traces参数必须是列表")
            return "Think: 内部错误 - traces参数无效"

        # 构建提示词
        prompt = f"""
Think: 请进行内部推理。

任务: {task_input}

相关经验:
{retrieved_text if retrieved_text else "无相关经验"}

历史推理:
{chr(10).join(traces[-3:]) if traces else "无历史推理"}

请以 "Think:" 开头输出推理过程。
推理应该：
1. 分析任务需求
2. 结合相关经验
3. 考虑历史推理
4. 提出下一步思路

请确保推理内容具体、有逻辑。
"""
        try:
            # 调用LLM
            result = self.llm(prompt).strip()

            # 验证输出格式
            if not result:
                logger.warning("Think: LLM返回空结果")
                return "Think: 推理结果为空"

            # 确保以"Think:"开头
            if not result.startswith("Think:"):
                result = f"Think: {result}"

            # 验证推理内容长度
            if len(result) < 20:
                logger.warning(f"Think: 推理内容过短: {len(result)}字符")
                result += " (推理内容需要更详细)"

            # 检查推理质量（简单启发式）
            think_content = result[6:].strip()  # 去掉"Think:"
            if len(think_content.split()) < 10:
                logger.warning("Think: 推理内容可能不够详细")

            logger.info(f"Think完成: {result[:50]}...")
            return result

        except Exception as e:
            logger.error(f"Think失败: {e}")
            return "Think: 推理过程中出现错误"

    def _refine(self, task_input: str, traces: List[str]) -> tuple:
        """执行Refine动作（记忆编辑）"""
        # 验证输入参数
        if not task_input or not isinstance(task_input, str):
            logger.error("Refine: 无效的任务输入")
            return {"delete": [], "add": [], "merge": [], "relabel": []}, "Refine: 无效输入"

        if not isinstance(traces, list):
            logger.error("Refine: traces参数必须是列表")
            return {"delete": [], "add": [], "merge": [], "relabel": []}, "Refine: traces参数错误"

        # 检查记忆库是否为空
        if len(self.M.entries) == 0:
            logger.warning("Refine: 记忆库为空，无法进行编辑操作")
            return {"delete": [], "add": [], "merge": [], "relabel": []}, "Refine: 记忆库为空"

        # 获取当前记忆列表
        memory_list = "\n".join([
            f"{i}. {e.to_text()}" for i, e in enumerate(self.M.entries)
        ])

        # 构建详细的提示词
        prompt = f"""
Refine: 请对记忆库进行编辑操作。

当前记忆库 ({len(self.M.entries)} 条记忆):
{memory_list}

当前任务:
{task_input}

历史推理轨迹:
{chr(10).join(traces[-3:]) if traces else "无历史推理"}

可用的编辑操作:
1. DELETE <index1>,<index2>,... - 删除指定索引的记忆
2. ADD{{<new_experience>}} - 添加新记忆（用花括号包裹内容）
3. MERGE <index1>&<index2> - 合并两个记忆
4. RELABEL <index> <new_tag> - 重新标记记忆

编辑原则:
- 删除冗余或无关的记忆
- 添加重要的新经验
- 合并相似或重复的记忆
- 重新标记不准确的标签

请输出Refine命令，例如：
DELETE 1,3; ADD{{用户喜欢简洁的界面设计}}; MERGE 0&2; RELABEL 4 ui-preference

请确保命令格式正确，索引在有效范围内。
"""
        try:
            # 调用LLM获取编辑命令
            cmd = self.llm(prompt).strip()

            if not cmd:
                logger.warning("Refine: LLM返回空命令")
                return {"delete": [], "add": [], "merge": [], "relabel": []}, "Refine: 空命令"

            # 验证命令格式
            if not self._validate_refine_command(cmd):
                logger.warning(f"Refine: 命令格式无效: {cmd}")
                return {"delete": [], "add": [], "merge": [], "relabel": []}, f"Refine: 格式无效: {cmd}"

            # 解析命令
            delta = RefineEditor.parse_command(cmd)

            # 验证解析结果
            if not self._validate_refine_delta(delta):
                logger.warning(f"Refine: 解析结果无效: {delta}")
                return {"delete": [], "add": [], "merge": [], "relabel": []}, f"Refine: 解析失败: {cmd}"

            # 验证索引范围
            if not self._validate_indices(delta):
                logger.warning(f"Refine: 索引超出范围: {delta}")
                return {"delete": [], "add": [], "merge": [], "relabel": []}, f"Refine: 索引无效: {cmd}"

            logger.info(f"Refine命令解析成功: {cmd}")
            return delta, cmd

        except Exception as e:
            logger.error(f"Refine失败: {e}")
            return {"delete": [], "add": [], "merge": [], "relabel": []}, f"Refine异常: {str(e)}"

    def _validate_refine_command(self, cmd: str) -> bool:
        """验证Refine命令格式"""
        if not cmd or not isinstance(cmd, str):
            return False

        # 基本格式检查：应该包含至少一个操作
        operations = [op.strip() for op in cmd.split(';') if op.strip()]
        if not operations:
            return False

        # 检查每个操作的基本格式
        for op in operations:
            if not op:
                return False
            # 检查是否是已知的操作类型
            if not (op.upper().startswith('DELETE ') or
                    op.upper().startswith('ADD{') or
                    op.upper().startswith('MERGE ') or
                    op.upper().startswith('RELABEL ')):
                return False

        return True

    def _validate_refine_delta(self, delta: Dict[str, Any]) -> bool:
        """验证Refine解析结果"""
        if not isinstance(delta, dict):
            return False

        required_keys = {"delete", "add", "merge", "relabel"}
        if not all(key in delta for key in required_keys):
            return False

        # 检查数据类型
        if not isinstance(delta["delete"], list):
            return False
        if not isinstance(delta["add"], list):
            return False
        if not isinstance(delta["merge"], list):
            return False
        if not isinstance(delta["relabel"], list):
            return False

        return True

    def _validate_indices(self, delta: Dict[str, Any]) -> bool:
        """验证索引是否在有效范围内"""
        max_index = len(self.M.entries) - 1

        # 验证删除索引
        for idx in delta["delete"]:
            if not isinstance(idx, int) or idx < 0 or idx > max_index:
                return False

        # 验证合并索引
        for idx1, idx2 in delta["merge"]:
            if not (isinstance(idx1, int) and isinstance(idx2, int)):
                return False
            if idx1 < 0 or idx1 > max_index or idx2 < 0 or idx2 > max_index:
                return False
            if idx1 == idx2:
                return False  # 不能合并同一个索引

        # 验证重标记索引
        for idx, _ in delta["relabel"]:
            if not isinstance(idx, int) or idx < 0 or idx > max_index:
                return False

        return True

    def _act(self, task_input: str, retrieved_text: str, traces: List[str]) -> str:
        """执行Act动作（对外输出）"""
        # 验证输入参数
        if not task_input or not isinstance(task_input, str):
            logger.error("Act: 无效的任务输入")
            return "Act: 无效的任务输入"

        if not isinstance(traces, list):
            logger.error("Act: traces参数必须是列表")
            return "Act: 内部错误 - traces参数无效"

        # 构建详细的提示词
        prompt = f"""
Act: 请给出最终答案或动作。

当前任务:
{task_input}

相关经验（来自记忆库）:
{retrieved_text if retrieved_text else "无相关经验"}

推理轨迹（历史思考过程）:
{chr(10).join(traces[-5:]) if traces else "无推理轨迹"}

请以 "Act:" 开头输出最终答案或动作。
你的回答应该：

1. **直接回应任务需求** - 明确解决任务中提出的问题
2. **基于相关经验** - 参考上面的相关经验（如果存在）
3. **考虑推理轨迹** - 结合上面的思考过程
4. **清晰具体** - 提供明确的答案或可执行的动作
5. **完整自包含** - 答案应该是完整的，不需要额外解释

如果是复杂任务，可以分步骤回答。
如果是决策任务，请给出明确的决定和理由。
如果是创作任务，请提供具体的内容。

示例格式：
Act: [你的答案或动作]
"""
        try:
            # 调用LLM
            result = self.llm(prompt).strip()

            # 验证输出格式
            if not result:
                logger.warning("Act: LLM返回空结果")
                return "Act: 执行结果为空"

            # 确保以"Act:"开头
            if not result.startswith("Act:"):
                result = f"Act: {result}"

            # 验证内容长度
            act_content = result[4:].strip()  # 去掉"Act:"
            if len(act_content) < 10:
                logger.warning(f"Act: 内容过短: {len(act_content)}字符")
                result += " (需要更具体的回答)"

            # 检查内容质量
            if len(act_content.split()) < 5:
                logger.warning("Act: 内容可能不够详细")

            # 验证内容相关性（简单启发式）
            task_keywords = set(task_input.lower().split()[:10])
            act_keywords = set(act_content.lower().split()[:20])
            common_keywords = task_keywords.intersection(act_keywords)

            if len(common_keywords) < 1 and len(task_keywords) > 0:
                logger.warning(f"Act: 回答可能与任务相关性较低，共同关键词: {len(common_keywords)}")

            logger.info(f"Act完成: {result[:80]}...")
            return result

        except Exception as e:
            logger.error(f"Act失败: {e}")
            return "Act: 执行动作时出现错误"

    def _apply_delta(self, delta: Dict[str, Any]) -> None:
        """应用Refine编辑操作"""
        try:
            # 记录原始记忆数量
            original_count = len(self.M.entries)

            # 执行删除操作（从大到小排序，避免索引变化）
            if delta["delete"]:
                delete_indices = sorted(delta["delete"], reverse=True)
                self.M.delete(delete_indices)
                logger.info(f"Refine: 删除了 {len(delete_indices)} 条记忆")

            # 执行添加操作
            if delta["add"]:
                from memory.entry import MemoryEntry
                added_count = 0
                for text in delta["add"]:
                    if text and isinstance(text, str):
                        new_entry = MemoryEntry(
                            x="refine-added",
                            y=text,
                            feedback="refine-added",
                            tag="refine",
                        )
                        self.M.add(new_entry)
                        added_count += 1
                logger.info(f"Refine: 添加了 {added_count} 条新记忆")

            # 执行合并操作
            if delta["merge"]:
                merged_count = 0
                for idx1, idx2 in delta["merge"]:
                    try:
                        # 调整索引（因为之前的删除操作可能改变了索引）
                        adjusted_idx1 = self._adjust_index(idx1, delta["delete"])
                        adjusted_idx2 = self._adjust_index(idx2, delta["delete"])

                        if adjusted_idx1 is not None and adjusted_idx2 is not None:
                            self.M.merge(adjusted_idx1, adjusted_idx2)
                            merged_count += 1
                    except Exception as e:
                        logger.warning(f"合并失败 {idx1}&{idx2}: {e}")
                logger.info(f"Refine: 合并了 {merged_count} 对记忆")

            # 执行重标记操作
            if delta["relabel"]:
                relabeled_count = 0
                for idx, tag in delta["relabel"]:
                    try:
                        # 调整索引
                        adjusted_idx = self._adjust_index(idx, delta["delete"])
                        if adjusted_idx is not None:
                            self.M.relabel(adjusted_idx, tag)
                            relabeled_count += 1
                    except Exception as e:
                        logger.warning(f"重标记失败 {idx}: {e}")
                logger.info(f"Refine: 重标记了 {relabeled_count} 条记忆")

            # 记录最终结果
            final_count = len(self.M.entries)
            logger.info(f"Refine完成: 记忆数量从 {original_count} 变为 {final_count}")

        except Exception as e:
            logger.error(f"应用Refine操作失败: {e}")

    def _adjust_index(self, idx: int, deleted_indices: List[int]) -> Optional[int]:
        """
        调整索引，考虑删除操作的影响

        Args:
            idx: 原始索引
            deleted_indices: 已删除的索引列表（已排序，从大到小）

        Returns:
            调整后的索引，如果索引已被删除则返回None
        """
        # 检查索引是否已被删除
        if idx in deleted_indices:
            return None

        # 计算有多少个更小的索引被删除
        adjustment = sum(1 for di in deleted_indices if di < idx)
        return idx - adjustment

    def _add_new_memory(self, task_input: str, action_result: str, feedback: str) -> None:
        """添加新记忆条目"""
        from memory.entry import MemoryEntry

        # 提取实际动作内容（去掉"Act:"前缀）
        if action_result.startswith("Act:"):
            action_content = action_result[4:].strip()
        else:
            action_content = action_result

        new_entry = MemoryEntry(
            x=task_input,
            y=action_content,
            feedback=feedback,
            tag="task",
        )
        self.M.add(new_entry)

        # 检查是否需要清理
        if len(self.M) >= self.M.max_entries:
            self.M._prune()

    def _get_feedback(self, action_result: str) -> str:
        """获取环境反馈（模拟实现）"""
        # 实际应用中应从环境获取真实反馈
        # 这里返回模拟反馈
        return "success"

    def get_statistics(self) -> Dict[str, Any]:
        """获取Agent统计信息"""
        mem_stats = self.M.get_statistics()
        return {
            "memory_statistics": mem_stats,
            "max_iterations": self.max_iterations,
            "retrieval_k": self.retrieval_k,
            "persistence_path": self.persistence.filepath,
        }

    def save_memory(self) -> bool:
        """保存记忆库"""
        return self.persistence.save(self.M)

    def load_memory(self) -> bool:
        """加载记忆库"""
        try:
            self.M = self.persistence.load(self.M)
            return True
        except Exception as e:
            logger.error(f"加载记忆库失败: {e}")
            return False
