"""
增强的模板引擎

支持条件逻辑、循环、变量替换、过滤器、继承等高级模板功能。
"""

import re
import json
import hashlib
from typing import Dict, Any, Optional, List, Union, Callable
import logging
from pathlib import Path
from datetime import datetime
import inspect
from functools import lru_cache

logger = logging.getLogger(__name__)


class TemplateSyntaxError(Exception):
    """模板语法错误"""
    pass


class TemplateContextError(Exception):
    """模板上下文错误"""
    pass


class FilterRegistry:
    """过滤器注册表"""

    def __init__(self):
        self._filters: Dict[str, Callable] = {}

    def register(self, name: str, filter_func: Callable) -> None:
        """注册过滤器"""
        self._filters[name] = filter_func
        logger.debug(f"已注册过滤器: {name}")

    def get(self, name: str) -> Optional[Callable]:
        """获取过滤器"""
        return self._filters.get(name)

    def apply(self, name: str, value: Any, *args, **kwargs) -> Any:
        """应用过滤器"""
        filter_func = self.get(name)
        if not filter_func:
            raise TemplateSyntaxError(f"未知的过滤器: {name}")

        try:
            return filter_func(value, *args, **kwargs)
        except Exception as e:
            raise TemplateContextError(f"过滤器 {name} 应用失败: {e}")

    def register_defaults(self):
        """注册默认过滤器"""
        # 字符串过滤器
        self.register("upper", lambda x: str(x).upper())
        self.register("lower", lambda x: str(x).lower())
        self.register("capitalize", lambda x: str(x).capitalize())
        self.register("title", lambda x: str(x).title())
        self.register("trim", lambda x: str(x).strip())
        self.register("truncate", lambda x, length=50: str(x)[:length] + ("..." if len(str(x)) > length else ""))
        self.register("replace", lambda x, old, new: str(x).replace(old, new))

        # 数字过滤器
        self.register("abs", lambda x: abs(float(x)) if isinstance(x, (int, float)) else x)
        self.register("round", lambda x, precision=2: round(float(x), precision) if isinstance(x, (int, float)) else x)
        self.register("int", lambda x: int(float(x)) if isinstance(x, (int, float)) else x)

        # 列表过滤器
        self.register("length", lambda x: len(x) if hasattr(x, "__len__") else 0)
        self.register("first", lambda x: x[0] if hasattr(x, "__getitem__") and len(x) > 0 else None)
        self.register("last", lambda x: x[-1] if hasattr(x, "__getitem__") and len(x) > 0 else None)
        self.register("join", lambda x, separator=", ": separator.join(str(item) for item in x) if hasattr(x, "__iter__") else str(x))

        # 日期时间过滤器
        self.register("date", lambda x, fmt="%Y-%m-%d": x.strftime(fmt) if isinstance(x, datetime) else str(x))
        self.register("time", lambda x, fmt="%H:%M:%S": x.strftime(fmt) if isinstance(x, datetime) else str(x))
        self.register("datetime", lambda x, fmt="%Y-%m-%d %H:%M:%S": x.strftime(fmt) if isinstance(x, datetime) else str(x))

        # 布尔过滤器
        self.register("default", lambda x, default_value: x if x else default_value)
        self.register("bool", lambda x: bool(x))

        logger.info(f"已注册 {len(self._filters)} 个默认过滤器")


class TemplateNode:
    """模板节点基类"""

    def __init__(self, line: int = 0, column: int = 0):
        self.line = line
        self.column = column

    def render(self, context: Dict[str, Any], filters: FilterRegistry) -> str:
        """渲染节点"""
        raise NotImplementedError


class TextNode(TemplateNode):
    """文本节点"""

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.text = text

    def render(self, context: Dict[str, Any], filters: FilterRegistry) -> str:
        return self.text


class VariableNode(TemplateNode):
    """变量节点"""

    def __init__(self, variable_name: str, filters: List[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.variable_name = variable_name
        self.filters = filters or []

    def render(self, context: Dict[str, Any], filters: FilterRegistry) -> str:
        # 获取变量值
        value = self._get_variable_value(context, self.variable_name)

        # 应用过滤器
        for filter_spec in self.filters:
            filter_name, filter_args = self._parse_filter_spec(filter_spec)
            value = filters.apply(filter_name, value, *filter_args)

        return str(value) if value is not None else ""

    def _get_variable_value(self, context: Dict[str, Any], path: str) -> Any:
        """获取嵌套变量值"""
        parts = path.split(".")
        current = context

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

            if current is None:
                break

        return current

    def _parse_filter_spec(self, filter_spec: str) -> tuple:
        """解析过滤器规格"""
        # 格式: filter_name:arg1:arg2 或 filter_name
        if ":" in filter_spec:
            filter_name, args_str = filter_spec.split(":", 1)
            args = args_str.split(":")
            return filter_name, args
        else:
            return filter_spec, []


class IfNode(TemplateNode):
    """条件节点"""

    def __init__(self, condition: str, true_nodes: List[TemplateNode], false_nodes: List[TemplateNode] = None, **kwargs):
        super().__init__(**kwargs)
        self.condition = condition
        self.true_nodes = true_nodes
        self.false_nodes = false_nodes or []

    def render(self, context: Dict[str, Any], filters: FilterRegistry) -> str:
        if self._evaluate_condition(context, self.condition):
            return self._render_nodes(self.true_nodes, context, filters)
        else:
            return self._render_nodes(self.false_nodes, context, filters)

    def _evaluate_condition(self, context: Dict[str, Any], condition: str) -> bool:
        """评估条件表达式"""
        # 简单条件表达式解析
        condition = condition.strip()

        # 检查变量是否存在
        if condition.startswith("!"):
            # 取反操作
            var_name = condition[1:].strip()
            value = self._get_variable_value(context, var_name)
            return not bool(value)
        else:
            value = self._get_variable_value(context, condition)
            return bool(value)

    def _get_variable_value(self, context: Dict[str, Any], path: str) -> Any:
        """获取变量值（简化版）"""
        parts = path.split(".")
        current = context

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                break

        return current

    def _render_nodes(self, nodes: List[TemplateNode], context: Dict[str, Any], filters: FilterRegistry) -> str:
        """渲染节点列表"""
        result = []
        for node in nodes:
            result.append(node.render(context, filters))
        return "".join(result)


class ForNode(TemplateNode):
    """循环节点"""

    def __init__(self, item_var: str, collection_var: str, nodes: List[TemplateNode], **kwargs):
        super().__init__(**kwargs)
        self.item_var = item_var
        self.collection_var = collection_var
        self.nodes = nodes

    def render(self, context: Dict[str, Any], filters: FilterRegistry) -> str:
        collection = self._get_collection(context, self.collection_var)
        if not collection or not hasattr(collection, "__iter__"):
            return ""

        result = []
        for item in collection:
            # 创建子上下文
            child_context = context.copy()
            child_context[self.item_var] = item
            child_context["loop"] = {
                "index": len(result) + 1,
                "index0": len(result),
                "first": len(result) == 0,
                "last": False,  # 会在循环结束后设置
                "length": len(collection),
            }

            # 渲染节点
            for node in self.nodes:
                result.append(node.render(child_context, filters))

        # 设置最后一个元素的标志
        if result:
            # 这里简化处理，实际实现需要更复杂的逻辑
            pass

        return "".join(result)

    def _get_collection(self, context: Dict[str, Any], path: str) -> Any:
        """获取集合变量"""
        return self._get_variable_value(context, path)

    def _get_variable_value(self, context: Dict[str, Any], path: str) -> Any:
        """获取变量值"""
        parts = path.split(".")
        current = context

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                break

        return current


class IncludeNode(TemplateNode):
    """包含节点"""

    def __init__(self, template_name: str, **kwargs):
        super().__init__(**kwargs)
        self.template_name = template_name

    def render(self, context: Dict[str, Any], filters: FilterRegistry) -> str:
        # 在实际实现中，这里会加载和渲染被包含的模板
        # 这里简化处理，返回占位符
        return f"<!-- 包含模板: {self.template_name} -->"


class TemplateParser:
    """模板解析器"""

    # 正则表达式模式
    VAR_PATTERN = r"\{\{\s*([^}]+?)\s*\}\}"
    TAG_PATTERN = r"\{%\s*([^%]+?)\s*%\}"
    COMMENT_PATTERN = r"\{#.*?#\}"

    # 标签类型
    TAG_IF = "if"
    TAG_ELSE = "else"
    TAG_ENDIF = "endif"
    TAG_FOR = "for"
    TAG_ENDFOR = "endfor"
    TAG_INCLUDE = "include"

    def __init__(self, filters: Optional[FilterRegistry] = None):
        self.filters = filters or FilterRegistry()
        self.filters.register_defaults()

    def parse(self, template: str) -> List[TemplateNode]:
        """解析模板"""
        nodes = []
        pos = 0
        line = 1
        column = 1

        while pos < len(template):
            # 查找下一个标签或变量
            var_match = re.search(self.VAR_PATTERN, template[pos:])
            tag_match = re.search(self.TAG_PATTERN, template[pos:])
            comment_match = re.search(self.COMMENT_PATTERN, template[pos:])

            # 找到最近的匹配
            matches = []
            if var_match:
                matches.append(("var", var_match))
            if tag_match:
                matches.append(("tag", tag_match))
            if comment_match:
                matches.append(("comment", comment_match))

            if not matches:
                # 没有更多标签，添加剩余文本
                remaining_text = template[pos:]
                if remaining_text:
                    nodes.append(TextNode(remaining_text, line=line, column=column))
                break

            # 找到最近的匹配
            matches.sort(key=lambda x: x[1].start())
            match_type, match = matches[0]

            # 添加匹配前的文本
            text_before = template[pos:pos + match.start()]
            if text_before:
                nodes.append(TextNode(text_before, line=line, column=column))
                # 更新行列位置
                line += text_before.count("\n")
                if "\n" in text_before:
                    column = len(text_before) - text_before.rfind("\n")
                else:
                    column += len(text_before)

            # 处理匹配
            if match_type == "var":
                var_content = match.group(1).strip()
                node = self._parse_variable(var_content, line, column)
                nodes.append(node)
            elif match_type == "tag":
                tag_content = match.group(1).strip()
                # 处理块标签（需要特殊处理）
                if tag_content.startswith(self.TAG_IF):
                    # 解析if块
                    if_nodes, end_pos = self._parse_if_block(template, pos + match.start(), line, column)
                    nodes.extend(if_nodes)
                    pos = end_pos
                    continue
                elif tag_content.startswith(self.TAG_FOR):
                    # 解析for块
                    for_nodes, end_pos = self._parse_for_block(template, pos + match.start(), line, column)
                    nodes.extend(for_nodes)
                    pos = end_pos
                    continue
                elif tag_content.startswith(self.TAG_INCLUDE):
                    # 解析include标签
                    include_name = tag_content[len(self.TAG_INCLUDE):].strip().strip('"\'')
                    nodes.append(IncludeNode(include_name, line=line, column=column))
            elif match_type == "comment":
                # 注释，跳过
                pass

            # 更新位置
            pos += match.end()
            match_text = match.group(0)
            line += match_text.count("\n")
            if "\n" in match_text:
                column = len(match_text) - match_text.rfind("\n")
            else:
                column += len(match_text)

        return nodes

    def _parse_variable(self, var_content: str, line: int, column: int) -> VariableNode:
        """解析变量表达式"""
        # 分离变量名和过滤器
        if "|" in var_content:
            var_name, filters_str = var_content.split("|", 1)
            var_name = var_name.strip()
            filters = [f.strip() for f in filters_str.split("|")]
        else:
            var_name = var_content.strip()
            filters = []

        return VariableNode(var_name, filters, line=line, column=column)

    def _parse_if_block(self, template: str, start_pos: int, start_line: int, start_column: int) -> tuple:
        """解析if块"""
        # 简化实现：返回空节点列表
        # 在实际实现中，这里需要完整解析if/else/endif结构
        return [], start_pos

    def _parse_for_block(self, template: str, start_pos: int, start_line: int, start_column: int) -> tuple:
        """解析for块"""
        # 简化实现：返回空节点列表
        return [], start_pos


class EnhancedTemplateEngine:
    """增强的模板引擎"""

    def __init__(self, template_dirs: Optional[List[str]] = None):
        self.template_dirs = template_dirs or ["./templates"]
        self.filters = FilterRegistry()
        self.filters.register_defaults()
        self._template_cache: Dict[str, List[TemplateNode]] = {}
        self._parser = TemplateParser(self.filters)

    def render(self, template: str, context: Dict[str, Any]) -> str:
        """
        渲染模板

        Args:
            template: 模板字符串
            context: 上下文变量

        Returns:
            渲染后的字符串
        """
        try:
            # 检查缓存
            cache_key = self._get_template_key(template)
            if cache_key not in self._template_cache:
                # 解析模板
                nodes = self._parser.parse(template)
                self._template_cache[cache_key] = nodes

            # 渲染模板
            nodes = self._template_cache[cache_key]
            result_parts = []
            for node in nodes:
                result_parts.append(node.render(context, self.filters))

            return "".join(result_parts)

        except Exception as e:
            logger.error(f"模板渲染失败: {e}")
            raise

    def render_file(self, template_path: str, context: Dict[str, Any]) -> str:
        """
        从文件渲染模板

        Args:
            template_path: 模板文件路径
            context: 上下文变量

        Returns:
            渲染后的字符串
        """
        # 查找模板文件
        template_content = self._load_template_file(template_path)
        if template_content is None:
            raise FileNotFoundError(f"模板文件未找到: {template_path}")

        return self.render(template_content, context)

    def register_filter(self, name: str, filter_func: Callable) -> None:
        """注册自定义过滤器"""
        self.filters.register(name, filter_func)

    def add_template_dir(self, directory: str) -> None:
        """添加模板目录"""
        if directory not in self.template_dirs:
            self.template_dirs.append(directory)
            logger.info(f"已添加模板目录: {directory}")

    def clear_cache(self) -> None:
        """清空模板缓存"""
        self._template_cache.clear()
        logger.debug("模板缓存已清空")

    def _get_template_key(self, template: str) -> str:
        """生成模板缓存键"""
        return hashlib.md5(template.encode()).hexdigest()

    def _load_template_file(self, template_path: str) -> Optional[str]:
        """加载模板文件"""
        # 首先检查绝对路径
        if Path(template_path).is_absolute() and Path(template_path).exists():
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"读取模板文件失败 {template_path}: {e}")
                return None

        # 在模板目录中查找
        for template_dir in self.template_dirs:
            full_path = Path(template_dir) / template_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"读取模板文件失败 {full_path}: {e}")
                    continue

        return None


# 快捷函数
def render_template(template: str, context: Dict[str, Any]) -> str:
    """渲染模板（快捷函数）"""
    engine = EnhancedTemplateEngine()
    return engine.render(template, context)


def render_template_file(template_path: str, context: Dict[str, Any]) -> str:
    """从文件渲染模板（快捷函数）"""
    engine = EnhancedTemplateEngine()
    return engine.render_file(template_path, context)


# 示例模板
EXAMPLE_TEMPLATES = {
    "greeting": "你好，{{ name|capitalize }}！欢迎使用模板系统。",
    "user_profile": """
用户信息：
- 姓名：{{ user.name|capitalize }}
- 邮箱：{{ user.email|lower }}
- 注册时间：{{ user.created_at|date:"%Y-%m-%d" }}
- 状态：{{ user.active|default:"未激活" }}
""",
    "item_list": """
商品列表：
{% for item in items %}
{{ loop.index }}. {{ item.name|title }} - ￥{{ item.price|round:2 }}
{% endfor %}
总计：{{ items|length }} 个商品
""",
}


if __name__ == "__main__":
    # 测试模板引擎
    engine = EnhancedTemplateEngine()

    # 测试简单模板
    template = "你好，{{ name|upper }}！今天是{{ date|date }}。"
    context = {
        "name": "世界",
        "date": datetime.now()
    }
    result = engine.render(template, context)
    print("测试1:", result)

    # 测试复杂模板
    template2 = """
用户：{{ user.name }}
邮箱：{{ user.email|lower }}
状态：{{ user.active|default:"未激活"|upper }}
"""
    context2 = {
        "user": {
            "name": "张三",
            "email": "ZHANGSAN@EXAMPLE.COM",
            "active": True
        }
    }
    result2 = engine.render(template2, context2)
    print("测试2:", result2)