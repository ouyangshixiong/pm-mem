"""
提示词构建器

提供高级API来构建和组合提示词，支持模板组合、上下文管理和变量替换。
"""

from typing import Dict, Any, Optional, List, Union
import logging
from dataclasses import dataclass, field
from enum import Enum

from .template_engine import TemplateEngine, TemplateSyntax
from .template_manager import TemplateManager, TemplateCategory

logger = logging.getLogger(__name__)


class PromptRole(Enum):
    """提示词角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class PromptMessage:
    """提示词消息"""
    role: PromptRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为OpenAI API格式"""
        return {
            "role": self.role.value,
            "content": self.content,
            **self.metadata
        }


@dataclass
class PromptContext:
    """提示词上下文"""
    variables: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[PromptMessage] = field(default_factory=list)
    system_prompts: List[str] = field(default_factory=list)

    def add_message(self, role: PromptRole, content: str, **metadata) -> None:
        """添加消息到对话历史"""
        message = PromptMessage(role=role, content=content, metadata=metadata)
        self.conversation_history.append(message)

    def get_recent_messages(self, limit: int = 10) -> List[PromptMessage]:
        """获取最近的N条消息"""
        return self.conversation_history[-limit:] if self.conversation_history else []

    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history.clear()

    def merge(self, other: "PromptContext") -> "PromptContext":
        """合并两个上下文"""
        merged = PromptContext(
            variables={**self.variables, **other.variables},
            conversation_history=self.conversation_history + other.conversation_history,
            system_prompts=self.system_prompts + other.system_prompts,
        )
        return merged


class PromptBuilder:
    """提示词构建器"""

    def __init__(
        self,
        template_manager: Optional[TemplateManager] = None,
        default_syntax: TemplateSyntax = TemplateSyntax.SIMPLE,
    ):
        """
        初始化提示词构建器

        Args:
            template_manager: 模板管理器
            default_syntax: 默认模板语法
        """
        self.template_manager = template_manager or TemplateManager()
        self.default_syntax = default_syntax
        self._engine_cache = {}

    def _get_engine(self, syntax: Optional[TemplateSyntax] = None) -> TemplateEngine:
        """获取模板引擎"""
        syntax = syntax or self.default_syntax
        if syntax not in self._engine_cache:
            self._engine_cache[syntax] = TemplateEngine(syntax)
        return self._engine_cache[syntax]

    def build_from_template(
        self,
        template_id: str,
        context: Union[Dict[str, Any], PromptContext],
        version: Optional[str] = None,
    ) -> Optional[str]:
        """
        从模板构建提示词

        Args:
            template_id: 模板ID
            context: 上下文数据
            version: 模板版本

        Returns:
            构建的提示词，如失败返回None
        """
        if self.template_manager is None:
            logger.error("模板管理器未初始化")
            return None

        # 提取变量
        variables = context.variables if isinstance(context, PromptContext) else context

        return self.template_manager.render_template(template_id, variables, version)

    def build_from_string(
        self,
        template: str,
        context: Union[Dict[str, Any], PromptContext],
        syntax: Optional[TemplateSyntax] = None,
    ) -> str:
        """
        从字符串模板构建提示词

        Args:
            template: 模板字符串
            context: 上下文数据
            syntax: 模板语法

        Returns:
            构建的提示词
        """
        # 提取变量
        variables = context.variables if isinstance(context, PromptContext) else context

        engine = self._get_engine(syntax)
        return engine.render(template, variables)

    def build_conversation(
        self,
        context: PromptContext,
        user_message: str,
        include_system: bool = True,
        include_history: bool = True,
        history_limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        构建对话格式的提示词

        Args:
            context: 提示词上下文
            user_message: 用户消息
            include_system: 是否包含系统提示
            include_history: 是否包含对话历史
            history_limit: 历史消息限制

        Returns:
            OpenAI API格式的消息列表
        """
        messages = []

        # 添加系统提示
        if include_system and context.system_prompts:
            system_content = "\n".join(context.system_prompts)
            messages.append(PromptMessage(PromptRole.SYSTEM, system_content).to_dict())

        # 添加对话历史
        if include_history and context.conversation_history:
            recent_messages = context.get_recent_messages(history_limit)
            for msg in recent_messages:
                messages.append(msg.to_dict())

        # 添加当前用户消息
        messages.append(PromptMessage(PromptRole.USER, user_message).to_dict())

        return messages

    def build_with_template_combination(
        self,
        template_ids: List[str],
        context: Union[Dict[str, Any], PromptContext],
        separator: str = "\n\n",
    ) -> Optional[str]:
        """
        组合多个模板构建提示词

        Args:
            template_ids: 模板ID列表
            context: 上下文数据
            separator: 模板之间的分隔符

        Returns:
            组合后的提示词
        """
        if self.template_manager is None:
            logger.error("模板管理器未初始化")
            return None

        parts = []

        for template_id in template_ids:
            rendered = self.build_from_template(template_id, context)
            if rendered:
                parts.append(rendered)

        if not parts:
            return None

        return separator.join(parts)

    def create_memory_retrieval_prompt(
        self,
        query: str,
        memory_context: Dict[str, Any],
        include_instructions: bool = True,
    ) -> str:
        """
        创建记忆检索提示词

        Args:
            query: 查询文本
            memory_context: 记忆上下文
            include_instructions: 是否包含检索指令

        Returns:
            记忆检索提示词
        """
        # 基础模板
        template = """
基于以下记忆上下文，回答用户的问题。

记忆上下文：
{{memory_context}}

用户问题：{{query}}
"""

        if include_instructions:
            template += """

请按照以下要求回答：
1. 基于记忆上下文提供准确信息
2. 如果记忆上下文没有相关信息，请明确说明
3. 保持回答简洁明了
"""

        variables = {
            "query": query,
            "memory_context": str(memory_context)
        }

        return self.build_from_string(template, variables)

    def create_memory_editing_prompt(
        self,
        operation: str,
        target: str,
        content: str,
        existing_memory: Optional[str] = None,
    ) -> str:
        """
        创建记忆编辑提示词

        Args:
            operation: 操作类型（add, update, delete, merge）
            target: 目标记忆
            content: 编辑内容
            existing_memory: 现有记忆（用于更新或合并）

        Returns:
            记忆编辑提示词
        """
        templates = {
            "add": """
添加新记忆：
目标：{{target}}
内容：{{content}}

请将上述信息整合到记忆系统中。
""",
            "update": """
更新现有记忆：
目标：{{target}}
现有记忆：{{existing_memory}}
新内容：{{content}}

请更新记忆，保持一致性。
""",
            "delete": """
删除记忆：
目标：{{target}}
原因：{{content}}

请从记忆系统中移除该记忆。
""",
            "merge": """
合并记忆：
目标：{{target}}
现有记忆1：{{existing_memory}}
现有记忆2：{{content}}

请合并这两个记忆，消除矛盾，保留重要信息。
"""
        }

        template = templates.get(operation, templates["add"])
        variables = {
            "target": target,
            "content": content,
            "existing_memory": existing_memory or "无"
        }

        return self.build_from_string(template, variables)

    def create_analysis_prompt(
        self,
        data: Any,
        analysis_type: str,
        criteria: Optional[List[str]] = None,
    ) -> str:
        """
        创建分析提示词

        Args:
            data: 待分析数据
            analysis_type: 分析类型
            criteria: 分析标准

        Returns:
            分析提示词
        """
        criteria_text = ""
        if criteria:
            criteria_text = "分析标准：\n" + "\n".join(f"- {c}" for c in criteria)

        template = f"""
请对以下数据进行{{analysis_type}}分析：

数据：
{{data}}

{criteria_text}

请提供详细的分析报告。
"""

        variables = {
            "analysis_type": analysis_type,
            "data": str(data),
            "criteria": criteria_text
        }

        return self.build_from_string(template, variables)

    def validate_prompt(
        self,
        prompt: str,
        context: Union[Dict[str, Any], PromptContext],
        syntax: Optional[TemplateSyntax] = None,
    ) -> Dict[str, Any]:
        """
        验证提示词

        Args:
            prompt: 提示词
            context: 上下文数据
            syntax: 模板语法

        Returns:
            验证结果
        """
        # 提取变量
        variables = context.variables if isinstance(context, PromptContext) else context

        engine = self._get_engine(syntax)
        missing_vars = engine.validate_context(prompt, variables)

        # 检查提示词长度
        prompt_length = len(prompt)
        rendered_length = len(engine.render(prompt, variables))

        return {
            "valid": len(missing_vars) == 0,
            "missing_variables": missing_vars,
            "prompt_length": prompt_length,
            "rendered_length": rendered_length,
            "variables_provided": list(variables.keys()),
            "variables_required": engine.get_required_variables(prompt),
        }

    def optimize_prompt(
        self,
        prompt: str,
        target_length: Optional[int] = None,
        remove_redundancy: bool = True,
        simplify_language: bool = False,
    ) -> str:
        """
        优化提示词

        Args:
            prompt: 原始提示词
            target_length: 目标长度
            remove_redundancy: 是否移除冗余
            simplify_language: 是否简化语言

        Returns:
            优化后的提示词
        """
        optimized = prompt

        # 移除冗余空白
        if remove_redundancy:
            import re
            # 移除多余的空行
            optimized = re.sub(r'\n\s*\n+', '\n\n', optimized)
            # 移除行首行尾空白
            optimized = '\n'.join(line.strip() for line in optimized.split('\n'))

        # 简化语言（简单实现）
        if simplify_language:
            # 替换复杂的表达为简单表达
            replacements = {
                "in order to": "to",
                "with the purpose of": "to",
                "due to the fact that": "because",
                "at this point in time": "now",
                "in the event that": "if",
            }
            for complex_word, simple_word in replacements.items():
                optimized = optimized.replace(complex_word, simple_word)

        # 长度控制
        if target_length and len(optimized) > target_length:
            # 简单截断，保留完整句子
            if len(optimized) > target_length:
                truncated = optimized[:target_length]
                # 找到最后一个句号
                last_period = truncated.rfind('.')
                if last_period > target_length * 0.8:  # 如果截断位置在句子附近
                    optimized = truncated[:last_period + 1]
                else:
                    optimized = truncated + "..."

        return optimized

    def create_context_from_template(
        self,
        template_id: str,
        base_context: PromptContext,
        version: Optional[str] = None,
    ) -> PromptContext:
        """
        从模板创建上下文

        Args:
            template_id: 模板ID
            base_context: 基础上下文
            version: 模板版本

        Returns:
            新的提示词上下文
        """
        if self.template_manager is None:
            logger.error("模板管理器未初始化")
            return base_context

        template = self.template_manager.get_template(template_id)
        if not template:
            logger.error(f"模板不存在: {template_id}")
            return base_context

        # 获取模板内容
        content = template.get_version(version).content

        # 渲染模板
        rendered = self.build_from_string(content, base_context, template.metadata.syntax)

        # 创建新上下文
        new_context = PromptContext(
            variables=base_context.variables.copy(),
            conversation_history=base_context.conversation_history.copy(),
            system_prompts=base_context.system_prompts + [rendered],
        )

        return new_context

    def batch_build(
        self,
        templates: List[Dict[str, Any]],
        context: Union[Dict[str, Any], PromptContext],
    ) -> List[str]:
        """
        批量构建提示词

        Args:
            templates: 模板列表，每个元素包含template_id或template字段
            context: 上下文数据

        Returns:
            构建的提示词列表
        """
        results = []

        for template_info in templates:
            if "template_id" in template_info:
                # 使用模板管理器
                prompt = self.build_from_template(
                    template_info["template_id"],
                    context,
                    template_info.get("version")
                )
            elif "template" in template_info:
                # 使用字符串模板
                prompt = self.build_from_string(
                    template_info["template"],
                    context,
                    TemplateSyntax(template_info.get("syntax", "simple"))
                )
            else:
                logger.error("模板信息必须包含template_id或template字段")
                prompt = None

            if prompt:
                results.append(prompt)

        return results


# 全局提示词构建器实例
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder(
    template_manager: Optional[TemplateManager] = None,
) -> PromptBuilder:
    """
    获取全局提示词构建器实例

    Args:
        template_manager: 模板管理器

    Returns:
        PromptBuilder实例
    """
    global _prompt_builder

    if _prompt_builder is None:
        _prompt_builder = PromptBuilder(template_manager)

    return _prompt_builder