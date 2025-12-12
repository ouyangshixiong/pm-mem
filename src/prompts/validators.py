"""
模板验证器

验证模板的语法、结构和有效性。
"""

import re
from typing import Dict, Any, List, Optional, Tuple
import logging
from enum import Enum

from .template_engine import TemplateSyntax

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    BASIC = "basic"      # 基本验证（语法检查）
    STANDARD = "standard"  # 标准验证（结构检查）
    STRICT = "strict"    # 严格验证（完整检查）


class ValidationResult:
    """验证结果"""

    def __init__(self, is_valid: bool = True):
        self.is_valid = is_valid
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def add_error(self, message: str) -> None:
        """添加错误"""
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """添加警告"""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """添加信息"""
        self.info.append(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }

    def __str__(self) -> str:
        """字符串表示"""
        lines = [f"验证结果: {'通过' if self.is_valid else '失败'}"]
        if self.errors:
            lines.append("错误:")
            lines.extend(f"  - {error}" for error in self.errors)
        if self.warnings:
            lines.append("警告:")
            lines.extend(f"  - {warning}" for warning in self.warnings)
        if self.info:
            lines.append("信息:")
            lines.extend(f"  - {info}" for info in self.info)
        return "\n".join(lines)


class TemplateValidator:
    """模板验证器"""

    # 正则表达式模式
    VAR_PATTERN = r'\{\{\s*([^{}]+?)\s*\}\}'
    CONDITION_START_PATTERN = r'\{%\s*if\s+([^%}]+?)\s*%\}'
    CONDITION_END_PATTERN = r'\{%\s*endif\s*%\}'
    ELSE_PATTERN = r'\{%\s*else\s*%\}'
    FOR_START_PATTERN = r'\{%\s*for\s+(\w+)\s+in\s+([^%}]+?)\s*%\}'
    FOR_END_PATTERN = r'\{%\s*endfor\s*%\}'

    def __init__(self, syntax: TemplateSyntax = TemplateSyntax.SIMPLE):
        """
        初始化模板验证器

        Args:
            syntax: 模板语法
        """
        self.syntax = syntax

    def validate(
        self,
        template: str,
        level: ValidationLevel = ValidationLevel.STANDARD,
        context_variables: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        验证模板

        Args:
            template: 模板字符串
            level: 验证级别
            context_variables: 可用的上下文变量列表

        Returns:
            验证结果
        """
        result = ValidationResult()

        # 基本验证
        self._validate_basic(template, result)

        # 根据语法进行验证
        if self.syntax == TemplateSyntax.SIMPLE:
            self._validate_simple_syntax(template, result)
        elif self.syntax == TemplateSyntax.CONDITIONAL:
            self._validate_conditional_syntax(template, result)
        else:  # 完整语法
            self._validate_full_syntax(template, result)

        # 标准验证
        if level in [ValidationLevel.STANDARD, ValidationLevel.STRICT]:
            self._validate_standard(template, result, context_variables)

        # 严格验证
        if level == ValidationLevel.STRICT:
            self._validate_strict(template, result)

        return result

    def _validate_basic(self, template: str, result: ValidationResult) -> None:
        """基本验证"""
        # 检查模板是否为空
        if not template or not template.strip():
            result.add_error("模板不能为空")
            return

        # 检查模板长度
        if len(template) > 10000:
            result.add_warning("模板过长，可能影响性能")

        # 检查编码问题
        try:
            template.encode('utf-8')
        except UnicodeEncodeError:
            result.add_error("模板包含无效的UTF-8字符")

    def _validate_simple_syntax(self, template: str, result: ValidationResult) -> None:
        """简单语法验证"""
        # 检查变量语法
        self._validate_variable_syntax(template, result)

        # 检查是否有条件或循环语法（不应该出现）
        if re.search(self.CONDITION_START_PATTERN, template):
            result.add_warning("简单语法模板中发现了条件语法，建议使用条件语法或完整语法")
        if re.search(self.FOR_START_PATTERN, template):
            result.add_warning("简单语法模板中发现了循环语法，建议使用完整语法")

    def _validate_conditional_syntax(self, template: str, result: ValidationResult) -> None:
        """条件语法验证"""
        # 检查变量语法
        self._validate_variable_syntax(template, result)

        # 检查条件语法
        self._validate_condition_syntax(template, result)

        # 检查是否有循环语法（不应该出现）
        if re.search(self.FOR_START_PATTERN, template):
            result.add_warning("条件语法模板中发现了循环语法，建议使用完整语法")

    def _validate_full_syntax(self, template: str, result: ValidationResult) -> None:
        """完整语法验证"""
        # 检查变量语法
        self._validate_variable_syntax(template, result)

        # 检查条件语法
        self._validate_condition_syntax(template, result)

        # 检查循环语法
        self._validate_loop_syntax(template, result)

    def _validate_variable_syntax(self, template: str, result: ValidationResult) -> None:
        """验证变量语法"""
        # 查找所有变量
        variables = re.findall(self.VAR_PATTERN, template)

        for var in variables:
            var = var.strip()

            # 检查变量名有效性
            if not var:
                result.add_error("发现空的变量名")
                continue

            # 检查变量名格式
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', var):
                result.add_error(f"变量名 '{var}' 格式无效，只能包含字母、数字、下划点和点号，且不能以数字开头")

            # 检查嵌套变量深度
            depth = var.count('.')
            if depth > 5:
                result.add_warning(f"变量 '{var}' 嵌套过深（{depth}层），可能影响可读性")

    def _validate_condition_syntax(self, template: str, result: ValidationResult) -> None:
        """验证条件语法"""
        # 查找所有条件块
        condition_starts = list(re.finditer(self.CONDITION_START_PATTERN, template))
        condition_ends = list(re.finditer(self.CONDITION_END_PATTERN, template))
        else_blocks = list(re.finditer(self.ELSE_PATTERN, template))

        # 检查条件块数量匹配
        if len(condition_starts) != len(condition_ends):
            result.add_error(f"条件块数量不匹配: {len(condition_starts)} 个开始 vs {len(condition_ends)} 个结束")

        # 检查条件表达式
        for match in condition_starts:
            condition_expr = match.group(1).strip()
            if not condition_expr:
                result.add_error("发现空的条件表达式")

            # 检查条件表达式语法
            if not self._is_valid_condition_expr(condition_expr):
                result.add_warning(f"条件表达式 '{condition_expr}' 语法可能无效")

        # 检查else块位置
        for match in else_blocks:
            # 检查else前面是否有if
            before_else = template[:match.start()]
            if_after_last_endif = list(re.finditer(self.CONDITION_START_PATTERN, before_else))
            endif_before_else = list(re.finditer(self.CONDITION_END_PATTERN, before_else))

            if len(if_after_last_endif) <= len(endif_before_else):
                result.add_error("else块没有对应的if块")

    def _validate_loop_syntax(self, template: str, result: ValidationResult) -> None:
        """验证循环语法"""
        # 查找所有循环块
        for_starts = list(re.finditer(self.FOR_START_PATTERN, template))
        for_ends = list(re.finditer(self.FOR_END_PATTERN, template))

        # 检查循环块数量匹配
        if len(for_starts) != len(for_ends):
            result.add_error(f"循环块数量不匹配: {len(for_starts)} 个开始 vs {len(for_ends)} 个结束")

        # 检查循环变量和迭代器
        for match in for_starts:
            var_name = match.group(1).strip()
            iterable_expr = match.group(2).strip()

            if not var_name:
                result.add_error("发现空的循环变量名")

            if not iterable_expr:
                result.add_error("发现空的迭代器表达式")

            # 检查循环变量名
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                result.add_error(f"循环变量名 '{var_name}' 格式无效")

            # 检查迭代器表达式
            if not self._is_valid_iterable_expr(iterable_expr):
                result.add_warning(f"迭代器表达式 '{iterable_expr}' 可能无效")

    def _validate_standard(
        self,
        template: str,
        result: ValidationResult,
        context_variables: Optional[List[str]],
    ) -> None:
        """标准验证"""
        # 提取所有变量
        all_variables = self._extract_all_variables(template)

        # 检查变量是否在上下文中可用
        if context_variables is not None:
            missing_vars = []
            for var in all_variables:
                # 检查变量或前缀是否在上下文中
                found = False
                for ctx_var in context_variables:
                    if var == ctx_var or ctx_var.startswith(var + '.'):
                        found = True
                        break
                if not found:
                    missing_vars.append(var)

            if missing_vars:
                result.add_warning(f"以下变量可能不在上下文中: {', '.join(missing_vars)}")

        # 检查模板复杂度
        complexity_score = self._calculate_complexity(template)
        if complexity_score > 50:
            result.add_warning(f"模板复杂度较高（得分: {complexity_score}），建议简化")

        # 检查是否有未闭合的标签
        self._check_unclosed_tags(template, result)

    def _validate_strict(self, template: str, result: ValidationResult) -> None:
        """严格验证"""
        # 检查模板安全性
        self._check_security_issues(template, result)

        # 检查最佳实践
        self._check_best_practices(template, result)

        # 检查性能问题
        self._check_performance_issues(template, result)

    def _extract_all_variables(self, template: str) -> List[str]:
        """提取模板中的所有变量"""
        variables = set()

        # 从变量语法中提取
        var_matches = re.findall(self.VAR_PATTERN, template)
        variables.update(var.strip() for var in var_matches)

        # 从条件表达式中提取
        condition_matches = re.findall(self.CONDITION_START_PATTERN, template)
        for expr in condition_matches:
            # 简单提取变量名（实际应该解析表达式）
            parts = expr.strip().split()
            for part in parts:
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', part) and part not in ['in', 'not', 'and', 'or']:
                    variables.add(part)

        # 从循环表达式中提取
        for_matches = re.findall(self.FOR_START_PATTERN, template)
        for var_name, iterable_expr in for_matches:
            variables.add(iterable_expr.strip())

        return list(variables)

    def _calculate_complexity(self, template: str) -> int:
        """计算模板复杂度"""
        score = 0

        # 变量数量
        variables = len(re.findall(self.VAR_PATTERN, template))
        score += variables * 1

        # 条件块数量
        conditions = len(re.findall(self.CONDITION_START_PATTERN, template))
        score += conditions * 3

        # 循环块数量
        loops = len(re.findall(self.FOR_START_PATTERN, template))
        score += loops * 5

        # 嵌套深度（简化计算）
        lines = template.split('\n')
        indent_level = 0
        max_indent = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('{%'):
                if 'endif' in stripped or 'endfor' in stripped:
                    indent_level = max(0, indent_level - 1)
                else:
                    indent_level += 1
                    max_indent = max(max_indent, indent_level)

        score += max_indent * 2

        return score

    def _check_unclosed_tags(self, template: str, result: ValidationResult) -> None:
        """检查未闭合的标签"""
        stack = []
        lines = template.split('\n')

        for line_num, line in enumerate(lines, 1):
            # 检查开始标签
            if_match = re.search(self.CONDITION_START_PATTERN, line)
            if if_match:
                stack.append(('if', line_num, if_match.group(1)))

            for_match = re.search(self.FOR_START_PATTERN, line)
            if for_match:
                stack.append(('for', line_num, f"{for_match.group(1)} in {for_match.group(2)}"))

            # 检查结束标签
            if re.search(self.CONDITION_END_PATTERN, line):
                if stack and stack[-1][0] == 'if':
                    stack.pop()
                else:
                    result.add_error(f"第{line_num}行: 多余的endif标签")

            if re.search(self.FOR_END_PATTERN, line):
                if stack and stack[-1][0] == 'for':
                    stack.pop()
                else:
                    result.add_error(f"第{line_num}行: 多余的endfor标签")

        # 报告未闭合的标签
        for tag_type, line_num, expr in stack:
            result.add_error(f"第{line_num}行: 未闭合的{tag_type}标签: {expr}")

    def _check_security_issues(self, template: str, result: ValidationResult) -> None:
        """检查安全问题"""
        # 检查可能的注入攻击
        dangerous_patterns = [
            (r'\{\{.*?\b(exec|eval|__import__|open|file|system)\b.*?\}\}', "危险的Python函数调用"),
            (r'\{\{.*?\b(os|subprocess|sys|importlib)\..*?\}\}', "危险的标准库调用"),
            (r'\{\{.*?\.\./.*?\}\}', "可能的路径遍历攻击"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, template, re.IGNORECASE):
                result.add_error(f"发现安全问题: {message}")

        # 检查过长的变量名（可能用于DoS）
        variables = re.findall(self.VAR_PATTERN, template)
        for var in variables:
            if len(var) > 100:
                result.add_warning(f"变量名过长（{len(var)}字符），可能影响性能")

    def _check_best_practices(self, template: str, result: ValidationResult) -> None:
        """检查最佳实践"""
        # 检查是否有注释
        if not re.search(r'\{#.*?#\}', template) and not re.search(r'<!--.*?-->', template):
            result.add_info("模板缺少注释，建议添加说明")

        # 检查变量命名一致性
        variables = re.findall(self.VAR_PATTERN, template)
        naming_styles = set()

        for var in variables:
            var = var.strip()
            if '_' in var:
                naming_styles.add('snake_case')
            elif any(c.isupper() for c in var if c.isalpha()):
                naming_styles.add('mixed_case')

        if len(naming_styles) > 1:
            result.add_warning("变量命名风格不一致")

        # 检查模板结构
        lines = template.strip().split('\n')
        if len(lines) > 50:
            result.add_info("模板较长，考虑拆分为多个小模板")

    def _check_performance_issues(self, template: str, result: ValidationResult) -> None:
        """检查性能问题"""
        # 检查嵌套深度
        max_nesting = self._calculate_max_nesting(template)
        if max_nesting > 5:
            result.add_warning(f"模板嵌套过深（{max_nesting}层），可能影响性能")

        # 检查循环中的复杂操作
        for_matches = list(re.finditer(self.FOR_START_PATTERN, template))
        for_end_matches = list(re.finditer(self.FOR_END_PATTERN, template))

        for i, (start_match, end_match) in enumerate(zip(for_matches, for_end_matches)):
            loop_body = template[start_match.end():end_match.start()]
            # 检查循环体中是否有其他循环
            if re.search(self.FOR_START_PATTERN, loop_body):
                result.add_warning(f"第{i+1}个循环中包含嵌套循环，可能影响性能")

            # 检查循环体中是否有复杂条件
            condition_count = len(re.findall(self.CONDITION_START_PATTERN, loop_body))
            if condition_count > 3:
                result.add_warning(f"第{i+1}个循环中包含多个条件判断，可能影响性能")

    def _calculate_max_nesting(self, template: str) -> int:
        """计算最大嵌套深度"""
        lines = template.split('\n')
        current_depth = 0
        max_depth = 0

        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('{%'):
                if 'endif' in stripped or 'endfor' in stripped:
                    current_depth = max(0, current_depth - 1)
                else:
                    current_depth += 1
                    max_depth = max(max_depth, current_depth)

        return max_depth

    def _is_valid_condition_expr(self, expr: str) -> bool:
        """检查条件表达式是否有效"""
        # 简单检查：表达式不能为空，且包含有效字符
        if not expr or not expr.strip():
            return False

        # 检查基本语法
        tokens = expr.split()
        if len(tokens) == 1:
            # 单个变量
            return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', tokens[0]))
        elif len(tokens) == 3 and tokens[1] in ['==', '!=', 'in']:
            # 比较表达式
            return (re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', tokens[0]) and
                    re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$|^".*"$|^\'.*\'$|^\d+$', tokens[2]))
        else:
            # 其他复杂表达式
            return True  # 暂时认为有效

    def _is_valid_iterable_expr(self, expr: str) -> bool:
        """检查迭代器表达式是否有效"""
        # 简单检查：表达式不能为空
        if not expr or not expr.strip():
            return False

        # 检查是否为有效变量名或列表表达式
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', expr):
            return True
        elif expr.startswith('[') and expr.endswith(']'):
            return True
        else:
            return False

    def validate_template_file(self, filepath: str, **kwargs) -> ValidationResult:
        """
        验证模板文件

        Args:
            filepath: 模板文件路径
            **kwargs: 传递给validate方法的参数

        Returns:
            验证结果
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                template = f.read()

            return self.validate(template, **kwargs)

        except Exception as e:
            result = ValidationResult(False)
            result.add_error(f"读取模板文件失败: {e}")
            return result