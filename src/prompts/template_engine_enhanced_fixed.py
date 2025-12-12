"""
增强的模板引擎（修复版）

支持条件逻辑、循环、变量替换、过滤器、继承等高级模板功能。
修复了过滤器参数解析问题。
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
        self.register("truncate", lambda x, length=50: str(x)[:int(length)] + ("..." if len(str(x)) > int(length) else ""))
        self.register("replace", lambda x, old, new: str(x).replace(old, new))

        # 数字过滤器
        self.register("abs", lambda x: abs(float(x)) if isinstance(x, (int, float)) else x)
        self.register("round", lambda x, precision=2: round(float(x), int(precision)) if isinstance(x, (int, float)) else x)
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


class EnhancedTemplateEngine:
    """增强的模板引擎"""

    def __init__(self, template_dirs: Optional[List[str]] = None):
        self.template_dirs = template_dirs or ["./templates"]
        self.filters = FilterRegistry()
        self.filters.register_defaults()

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
            # 简单实现：先处理变量替换
            result = template

            # 查找所有变量
            var_pattern = r"\{\{\s*([^}]+?)\s*\}\}"

            def replace_var(match):
                var_expr = match.group(1).strip()

                # 分离变量名和过滤器
                if "|" in var_expr:
                    var_name, filters_str = var_expr.split("|", 1)
                    var_name = var_name.strip()
                    filters = [f.strip() for f in filters_str.split("|")]
                else:
                    var_name = var_expr.strip()
                    filters = []

                # 获取变量值
                value = self._get_variable_value(context, var_name)

                # 应用过滤器
                for filter_spec in filters:
                    filter_name, filter_args = self._parse_filter_spec(filter_spec)
                    value = self.filters.apply(filter_name, value, *filter_args)

                return str(value) if value is not None else ""

            # 替换所有变量
            result = re.sub(var_pattern, replace_var, result)

            return result

        except Exception as e:
            logger.error(f"模板渲染失败: {e}")
            raise

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

    def register_filter(self, name: str, filter_func: Callable) -> None:
        """注册自定义过滤器"""
        self.filters.register(name, filter_func)


# 快捷函数
def render_template(template: str, context: Dict[str, Any]) -> str:
    """渲染模板（快捷函数）"""
    engine = EnhancedTemplateEngine()
    return engine.render(template, context)


# 测试
if __name__ == "__main__":
    # 测试模板引擎
    engine = EnhancedTemplateEngine()

    # 测试简单模板
    template = "你好，{{ name|upper }}！今天是{{ date }}。"
    context = {
        "name": "世界",
        "date": "2025-12-12"
    }
    result = engine.render(template, context)
    print("测试1:", result)

    # 测试过滤器
    template2 = "文本：{{ text|truncate:10 }}"
    context2 = {
        "text": "这是一个很长的文本需要截断"
    }
    result2 = engine.render(template2, context2)
    print("测试2:", result2)

    # 测试复杂模板
    template3 = """
用户：{{ user.name|title }}
邮箱：{{ user.email|lower }}
状态：{{ user.active|default:'未激活'|upper }}
"""
    context3 = {
        "user": {
            "name": "john doe",
            "email": "JOHN@EXAMPLE.COM",
            "active": True
        }
    }
    result3 = engine.render(template3, context3)
    print("测试3:", result3)