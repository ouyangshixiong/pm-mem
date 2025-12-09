"""
ReMem Agent主循环

实现完整的Think/Refine/Act状态机，支持最大迭代次数限制和强制终止机制。
"""

from typing import Dict, Any, List, Optional
import logging

from ..llm.llm_interface import LLMInterface
from ..memory.bank import MemoryBank
from ..memory.editor import RefineEditor
from ..memory.persistence import MemoryPersistence

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
            action = self.llm(prompt).strip()
            return action
        except Exception as e:
            logger.error(f"选择动作失败: {e}")
            return "act"  # 失败时默认执行Act

    def _think(self, task_input: str, retrieved_text: str, traces: List[str]) -> str:
        """执行Think动作（内部推理）"""
        prompt = f"""
Think: 请进行内部推理。

任务: {task_input}

相关经验:
{retrieved_text}

历史推理: {chr(10).join(traces) if traces else "无"}

请以 "Think:" 开头输出推理过程。
"""
        try:
            result = self.llm(prompt).strip()
            if not result.startswith("Think:"):
                result = f"Think: {result}"
            return result
        except Exception as e:
            logger.error(f"Think失败: {e}")
            return "Think: 推理过程中出现错误"

    def _refine(self, task_input: str, traces: List[str]) -> tuple:
        """执行Refine动作（记忆编辑）"""
        # 获取当前记忆列表
        memory_list = "\n".join([
            f"{i}. {e.to_text()}" for i, e in enumerate(self.M.entries)
        ])

        prompt = f"""
Refine: 允许 DELETE, ADD, MERGE, RELABEL 操作。

当前记忆:
{memory_list}

任务: {task_input}

历史推理: {chr(10).join(traces) if traces else "无"}

请输出Refine命令，例如：
DELETE 1,3; ADD{{new experience}}; MERGE 0&2; RELABEL 4 new-tag

请确保命令格式正确。
"""
        try:
            cmd = self.llm(prompt).strip()
            delta = RefineEditor.parse_command(cmd)
            return delta, cmd
        except Exception as e:
            logger.error(f"Refine失败: {e}")
            return {"delete": [], "add": [], "merge": [], "relabel": []}, ""

    def _act(self, task_input: str, retrieved_text: str, traces: List[str]) -> str:
        """执行Act动作（对外输出）"""
        prompt = f"""
Act: 请给出最终答案或动作。

任务: {task_input}

相关经验:
{retrieved_text}

推理轨迹: {chr(10).join(traces) if traces else "无"}

请以 "Act:" 开头输出最终答案或动作。
"""
        try:
            result = self.llm(prompt).strip()
            if not result.startswith("Act:"):
                result = f"Act: {result}"
            return result
        except Exception as e:
            logger.error(f"Act失败: {e}")
            return "Act: 执行动作时出现错误"

    def _apply_delta(self, delta: Dict[str, Any]) -> None:
        """应用Refine编辑操作"""
        try:
            # 执行删除操作
            if delta["delete"]:
                self.M.delete(delta["delete"])

            # 执行添加操作
            for text in delta["add"]:
                from ..memory.entry import MemoryEntry
                new_entry = MemoryEntry(
                    x="refine-added",
                    y=text,
                    feedback="refine-added",
                    tag="refine",
                )
                self.M.add(new_entry)

            # 执行合并操作
            for idx1, idx2 in delta["merge"]:
                try:
                    self.M.merge(idx1, idx2)
                except Exception as e:
                    logger.warning(f"合并失败 {idx1}&{idx2}: {e}")

            # 执行重标记操作
            for idx, tag in delta["relabel"]:
                try:
                    self.M.relabel(idx, tag)
                except Exception as e:
                    logger.warning(f"重标记失败 {idx}: {e}")

        except Exception as e:
            logger.error(f"应用Refine操作失败: {e}")

    def _add_new_memory(self, task_input: str, action_result: str, feedback: str) -> None:
        """添加新记忆条目"""
        from ..memory.entry import MemoryEntry

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