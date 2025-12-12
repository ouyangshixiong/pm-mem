"""
提示词模板引擎

核心模板引擎，支持动态参数替换、条件逻辑和循环结构。
"""

import re
import json
from typing import Dict, Any, Optional, List, Union
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TemplateSyntax(Enum):
    """模板语法类型"""
    SIMPLE = "simple"      # 简单变量替换: {{variable}}
    CONDITIONAL = "conditional"  # 条件逻辑: {% if condition %}...{% endif %}
    LOOP = "loop"          # 循环结构: {% for item in items %}...{% endfor %}


@dataclass
class TemplateContext:
    """模板上下文"""
    variables: Dict[str, Any]
    parent: Optional["TemplateContext"] = None

    def get(self, key: str, default: Any = None) -> Any:
        """获取变量值，支持嵌套访问"""
        # 支持点号分隔的嵌套访问
        keys = key.split('.')
        current = self.variables

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                # 检查父上下文
                if self.parent:
                    return self.parent.get(key, default)
                return default

        return current

    def set(self, key: str, value: Any) -> None:
        """设置变量值"""
        self.variables[key] = value


class TemplateEngine:
    """模板引擎"""

    # 正则表达式模式
    VAR_PATTERN = r'\{\{\s*([^{}]+?)\s*\}\}'
    CONDITION_PATTERN = r'\{%\s*if\s+([^%}]+?)\s*%\}'
    ENDIF_PATTERN = r'\{%\s*endif\s*%\}'
    ELSE_PATTERN = r'\{%\s*else\s*%\}'
    FOR_PATTERN = r'\{%\s*for\s+(\w+)\s+in\s+([^%}]+?)\s*%\}'
    ENDFOR_PATTERN = r'\{%\s*endfor\s*%\}'

    def __init__(self, syntax: TemplateSyntax = TemplateSyntax.SIMPLE):
        """
        初始化模板引擎

        Args:
            syntax: 支持的语法类型
        """
        self.syntax = syntax
        self._compiled_templates = {}

    def render(self, template: str, context: Union[Dict[str, Any], TemplateContext]) -> str:
        """
        渲染模板

        Args:
            template: 模板字符串
            context: 上下文数据

        Returns:
            渲染后的字符串
        """
        if isinstance(context, dict):
            context = TemplateContext(variables=context)

        # 根据语法类型选择渲染方法
        if self.syntax == TemplateSyntax.SIMPLE:
            return self._render_simple(template, context)
        elif self.syntax == TemplateSyntax.CONDITIONAL:
            return self._render_with_conditionals(template, context)
        else:  # 完整语法
            return self._render_full(template, context)

    def _render_simple(self, template: str, context: TemplateContext) -> str:
        """简单变量替换"""
        def replace_var(match):
            var_name = match.group(1).strip()
            value = context.get(var_name, "")
            return str(value)

        return re.sub(self.VAR_PATTERN, replace_var, template)

    def _render_with_conditionals(self, template: str, context: TemplateContext) -> str:
        """支持条件逻辑的渲染"""
        # 先处理条件逻辑
        template = self._process_conditionals(template, context)
        # 再处理变量替换
        return self._render_simple(template, context)

    def _render_full(self, template: str, context: TemplateContext) -> str:
        """完整语法渲染（条件+循环）"""
        # 处理循环
        template = self._process_loops(template, context)
        # 处理条件
        template = self._process_conditionals(template, context)
        # 处理变量替换
        return self._render_simple(template, context)

    def _process_conditionals(self, template: str, context: TemplateContext) -> str:
        """处理条件逻辑"""
        pattern = re.compile(
            f'({self.CONDITION_PATTERN})(.*?)({self.ELSE_PATTERN})?(.*?)({self.ENDIF_PATTERN})',
            re.DOTALL
        )

        def replace_conditional(match):
            condition_expr = match.group(2).strip()
            true_block = match.group(3)
            has_else = match.group(4) is not None
            false_block = match.group(5) if has_else else ""
            endif = match.group(6)

            # 评估条件
            condition_met = self._evaluate_condition(condition_expr, context)

            if condition_met:
                return true_block
            else:
                return false_block

        return pattern.sub(replace_conditional, template)

    def _process_loops(self, template: str, context: TemplateContext) -> str:
        """处理循环结构"""
        pattern = re.compile(
            f'({self.FOR_PATTERN})(.*?)({self.ENDFOR_PATTERN})',
            re.DOTALL
        )

        def replace_loop(match):
            var_name = match.group(2).strip()
            iterable_expr = match.group(3).strip()
            loop_body = match.group(4)
            endfor = match.group(5)

            # 获取可迭代对象
            iterable = context.get(iterable_expr, [])
            if not isinstance(iterable, (list, tuple, range)):
                logger.warning(f"循环表达式 '{iterable_expr}' 不是可迭代对象")
                return ""

            # 渲染循环体
            results = []
            for item in iterable:
                # 创建子上下文
                child_context = TemplateContext(
                    variables={var_name: item},
                    parent=context
                )
                # 渲染循环体
                rendered = self._render_simple(loop_body, child_context)
                results.append(rendered)

            return "".join(results)

        return pattern.sub(replace_loop, template)

    def _evaluate_condition(self, condition_expr: str, context: TemplateContext) -> bool:
        """
        评估条件表达式

        Args:
            condition_expr: 条件表达式
            context: 模板上下文

        Returns:
            条件是否满足
        """
        # 支持简单的条件表达式
        # 1. 变量存在性检查: variable
        # 2. 相等性检查: variable == value
        # 3. 包含检查: variable in list

        condition_expr = condition_expr.strip()

        # 检查变量存在性
        if "==" in condition_expr:
            # 相等性检查
            left, right = condition_expr.split("==", 1)
            left = left.strip()
            right = right.strip()

            left_value = context.get(left)
            # 尝试解析右侧值
            try:
                right_value = json.loads(right)
            except json.JSONDecodeError:
                right_value = right.strip('"\'')

            return left_value == right_value

        elif " in " in condition_expr:
            # 包含检查
            var_name, container_expr = condition_expr.split(" in ", 1)
            var_name = var_name.strip()
            container_expr = container_expr.strip()

            var_value = context.get(var_name)
            container = context.get(container_expr, [])

            return var_value in container

        else:
            # 简单存在性检查
            value = context.get(condition_expr)
            if isinstance(value, bool):
                return value
            elif isinstance(value, (int, float)):
                return bool(value)
            elif isinstance(value, str):
                return bool(value.strip())
            elif value is not None:
                return True
            else:
                return False

    def compile(self, template: str) -> str:
        """
        编译模板（预解析）

        Args:
            template: 模板字符串

        Returns:
            编译后的模板ID
        """
        import hashlib
        template_hash = hashlib.md5(template.encode()).hexdigest()

        # 预解析模板
        if self.syntax == TemplateSyntax.SIMPLE:
            # 提取所有变量
            variables = set(re.findall(self.VAR_PATTERN, template))
            self._compiled_templates[template_hash] = {
                "variables": [v.strip() for v in variables],
                "template": template
            }
        else:
            # 更复杂的解析
            self._compiled_templates[template_hash] = {
                "template": template,
                "parsed": self._parse_template(template)
            }

        return template_hash

    def _parse_template(self, template: str) -> Dict[str, Any]:
        """解析模板结构"""
        # 简化实现：提取所有语法元素
        variables = set(re.findall(self.VAR_PATTERN, template))
        conditions = set(re.findall(self.CONDITION_PATTERN, template))
        loops = re.findall(self.FOR_PATTERN, template)

        return {
            "variables": [v.strip() for v in variables],
            "conditions": [c.strip() for c in conditions],
            "loops": [{"var": var.strip(), "iterable": iterable.strip()} for var, iterable in loops]
        }

    def get_required_variables(self, template: str) -> List[str]:
        """
        获取模板所需的变量列表

        Args:
            template: 模板字符串

        Returns:
            所需变量名列表
        """
        if self.syntax == TemplateSyntax.SIMPLE:
            variables = re.findall(self.VAR_PATTERN, template)
            return [v.strip() for v in variables]
        else:
            parsed = self._parse_template(template)
            return parsed["variables"]

    def validate_context(self, template: str, context: Dict[str, Any]) -> List[str]:
        """
        验证上下文是否满足模板要求

        Args:
            template: 模板字符串
            context: 上下文数据

        Returns:
            缺失的变量列表
        """
        required_vars = self.get_required_variables(template)
        missing = []

        for var in required_vars:
            # 支持嵌套变量访问
            keys = var.split('.')
            current = context

            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    missing.append(var)
                    break

        return missing

    def render_from_file(self, filepath: str, context: Dict[str, Any]) -> str:
        """
        从文件加载模板并渲染

        Args:
            filepath: 模板文件路径
            context: 上下文数据

        Returns:
            渲染后的字符串
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                template = f.read()

            return self.render(template, context)

        except Exception as e:
            logger.error(f"从文件渲染模板失败 {filepath}: {e}")
            raise