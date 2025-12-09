"""
提示词模板系统

实现Think/Refine/Act的标准提示词模板，支持模板参数化填充和版本管理。
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PromptTemplate:
    """提示词模板基类"""

    def __init__(self, template: str, version: str = "1.0.0"):
        """
        初始化提示词模板

        Args:
            template: 模板字符串，使用{变量名}格式
            version: 模板版本
        """
        self.template = template
        self.version = version

    def format(self, **kwargs) -> str:
        """
        格式化模板

        Args:
            **kwargs: 模板变量

        Returns:
            格式化后的提示词
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.error(f"模板变量缺失: {e}")
            raise
        except Exception as e:
            logger.error(f"格式化模板失败: {e}")
            raise

    def get_info(self) -> Dict[str, Any]:
        """获取模板信息"""
        return {
            "version": self.version,
            "variables": self._extract_variables(),
            "template_preview": self.template[:200] + "..." if len(self.template) > 200 else self.template,
        }

    def _extract_variables(self) -> list:
        """提取模板中的变量名"""
        import re
        variables = re.findall(r'{(\w+)}', self.template)
        return list(set(variables))  # 去重


class PromptSystem:
    """提示词系统管理器"""

    def __init__(self):
        """初始化提示词系统"""
        self.templates: Dict[str, PromptTemplate] = {}
        self._init_default_templates()

    def _init_default_templates(self) -> None:
        """初始化默认模板"""
        # Think模板
        think_template = """Think: 请进行内部推理。

任务: {task_input}

相关经验:
{retrieved_memories}

历史推理:
{traces}

请以 "Think:" 开头输出推理过程。推理应分析当前任务与相关经验的关系，考虑可能的解决方案，并评估不同方案的优缺点。"""
        self.register_template("think", think_template, "1.0.0")

        # Refine模板
        refine_template = """Refine: 允许以下操作修改记忆库：
1. DELETE <索引> - 删除指定索引的记忆
2. ADD {{文本}} - 添加新记忆
3. MERGE <索引1>&<索引2> - 合并两个记忆
4. RELABEL <索引> <新标签> - 重新标记记忆

当前记忆库:
{memory_list}

任务: {task_input}

历史推理:
{traces}

请输出Refine命令。可以同时执行多个操作，用分号分隔。
示例: DELETE 1,3; ADD{{新经验}}; MERGE 0&2; RELABEL 4 new-tag

请确保命令格式正确。"""
        self.register_template("refine", refine_template, "1.0.0")

        # Act模板
        act_template = """Act: 请给出最终答案或动作。

任务: {task_input}

相关经验:
{retrieved_memories}

推理轨迹:
{traces}

请以 "Act:" 开头输出最终答案或动作。答案应基于相关经验和推理过程，直接解决任务需求。"""
        self.register_template("act", act_template, "1.0.0")

        # 动作选择模板
        action_selection_template = """请选择下一步动作：Think / Refine / Act

任务: {task_input}

相关记忆:
{retrieved_memories}

历史推理轨迹:
{traces}

选择依据：
- 如果还需要更多内部推理，选择 Think
- 如果需要修改记忆库（删除冗余、添加新知识、合并相似记忆、更新标签），选择 Refine
- 如果已经可以给出最终答案或执行动作，选择 Act

只需输出动作名称。"""
        self.register_template("action_selection", action_selection_template, "1.0.0")

        # 检索模板
        retrieval_template = """你是一个专业的记忆检索器。给定用户任务：
{query}

以下是全部记忆条目，请按相关性从高到低排序，输出最相关的前 {k} 个索引：

{memory_text}

请仅输出索引列表，例如：1,5,2
确保索引在有效范围内。"""
        self.register_template("retrieval", retrieval_template, "1.0.0")

    def register_template(self, name: str, template: str, version: str = "1.0.0") -> None:
        """
        注册新模板

        Args:
            name: 模板名称
            template: 模板字符串
            version: 模板版本
        """
        self.templates[name] = PromptTemplate(template, version)
        logger.debug(f"注册模板: {name} v{version}")

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """
        获取模板

        Args:
            name: 模板名称

        Returns:
            模板实例，如不存在则返回None
        """
        return self.templates.get(name)

    def format(self, name: str, **kwargs) -> str:
        """
        格式化指定模板

        Args:
            name: 模板名称
            **kwargs: 模板变量

        Returns:
            格式化后的提示词

        Raises:
            KeyError: 模板不存在
        """
        template = self.get_template(name)
        if not template:
            raise KeyError(f"模板不存在: {name}")

        return template.format(**kwargs)

    def get_all_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模板信息"""
        return {
            name: template.get_info()
            for name, template in self.templates.items()
        }

    def update_template(self, name: str, template: str, version: str = None) -> bool:
        """
        更新模板

        Args:
            name: 模板名称
            template: 新模板字符串
            version: 新版本号，如为None则自动递增

        Returns:
            更新是否成功
        """
        if name not in self.templates:
            logger.warning(f"尝试更新不存在的模板: {name}")
            return False

        old_template = self.templates[name]
        if version is None:
            # 自动递增版本号
            import re
            match = re.match(r'(\d+)\.(\d+)\.(\d+)', old_template.version)
            if match:
                major, minor, patch = map(int, match.groups())
                version = f"{major}.{minor}.{patch + 1}"
            else:
                version = "1.0.1"

        self.templates[name] = PromptTemplate(template, version)
        logger.info(f"更新模板: {name} v{old_template.version} -> v{version}")
        return True

    def export_templates(self) -> Dict[str, Any]:
        """导出所有模板（用于持久化）"""
        return {
            "system_version": "1.0.0",
            "templates": {
                name: {
                    "template": template.template,
                    "version": template.version,
                }
                for name, template in self.templates.items()
            },
        }

    def import_templates(self, data: Dict[str, Any]) -> None:
        """
        导入模板

        Args:
            data: 模板数据（export_templates输出的格式）
        """
        templates_data = data.get("templates", {})
        for name, template_info in templates_data.items():
            template = template_info.get("template", "")
            version = template_info.get("version", "1.0.0")
            self.register_template(name, template, version)

        logger.info(f"导入了 {len(templates_data)} 个模板")


# 全局提示词系统实例
prompt_system = PromptSystem()


def get_prompt_system() -> PromptSystem:
    """获取全局提示词系统实例"""
    return prompt_system