"""
模拟LLM用于测试

提供轻量模拟器，根据prompt的特征返回不同结果，用于本地demo和单元测试。
"""

import re
from typing import Dict, Any, Optional
import logging

from .llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class MockLLM(LLMInterface):
    """
    模拟LLM，用于测试和开发

    根据prompt的特征返回预设结果，避免调用真实API。
    """

    def __init__(
        self,
        responses: Optional[Dict[str, str]] = None,
        default_response: str = "模拟LLM响应",
        enable_pattern_matching: bool = True,
    ):
        """
        初始化模拟LLM

        Args:
            responses: 预设响应映射 {关键词: 响应文本}
            default_response: 默认响应文本
            enable_pattern_matching: 是否启用模式匹配
        """
        self.responses = responses or {}
        self.default_response = default_response
        self.enable_pattern_matching = enable_pattern_matching
        self.call_history = []  # 记录调用历史
        self.call_counter = 0  # 调用计数器

        # 默认响应模式
        self._init_default_responses()

    def _init_default_responses(self) -> None:
        """初始化默认响应模式"""
        if not self.responses:
            self.responses = {
                # 检索排序请求
                "请仅输出索引列表": "0,1,2",
                "请僅輸出索引列表": "0,1,2",
                # 动作选择
                "请选择动作": self._get_action_sequence(),
                # Refine命令
                "refine:": "DELETE 0; ADD {nginx 反向代理已用于绕过阿里云安全组对 3000 端口的封禁}",
                # Think推理
                "think:": (
                    "Think: 用户尝试使用 curl -I http://x.x.x.x:3000/health 进行健康检测。"
                    "阿里云安全组通常默认拒绝 3000 端口的入站请求，因此需要检查安全组放行状况。"
                    "如果无法放行 3000，则应通过 nginx 在 80 端口配置反向代理，将 /site-name/health 转发至 3000 端口的 /health。"
                ),
                # Act动作
                "act:": "Act: curl -I http://x.x.x.x/site-name/health",
            }

    def _get_action_sequence(self) -> str:
        """获取动作序列（模拟智能体决策过程）"""
        actions = ["think", "refine", "act", "act"]
        if self.call_counter < len(actions):
            action = actions[self.call_counter]
        else:
            action = "act"
        self.call_counter += 1
        return action

    def call(self, prompt: str, **kwargs) -> str:
        """
        模拟LLM调用

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数（忽略）

        Returns:
            模拟响应文本
        """
        self.call_history.append({
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "timestamp": self.call_counter,
        })

        # 查找匹配的响应
        response = self._find_matching_response(prompt)
        logger.debug(f"MockLLM调用 - 提示词长度: {len(prompt)}, 响应: {response[:100]}...")

        return response

    def _find_matching_response(self, prompt: str) -> str:
        """查找匹配的响应文本"""
        prompt_lower = prompt.lower()

        if self.enable_pattern_matching:
            # 模式匹配
            for pattern, response in self.responses.items():
                pattern_lower = pattern.lower()
                if pattern_lower in prompt_lower:
                    # 如果是动作选择模式，需要动态获取
                    if pattern_lower == "请选择动作":
                        return self._get_action_sequence()
                    return response

        # 检查是否包含特定关键词
        if "索引" in prompt_lower and "列表" in prompt_lower:
            return self.responses.get("请仅输出索引列表", "0,1")

        if "选择动作" in prompt_lower:
            return self._get_action_sequence()

        if "refine:" in prompt_lower:
            return self.responses.get("refine:", "DELETE 0")

        if "think:" in prompt_lower:
            return self.responses.get("think:", "Think: 模拟推理过程")

        if "act:" in prompt_lower:
            return self.responses.get("act:", "Act: 模拟动作")

        # 返回默认响应
        return self.default_response

    def get_model_info(self) -> Dict[str, Any]:
        """获取模拟LLM信息"""
        return {
            "model_name": "mock-llm",
            "provider": "Mock",
            "description": "模拟LLM用于测试和开发",
            "total_calls": len(self.call_history),
            "responses_configured": len(self.responses),
        }

    def get_call_history(self) -> list:
        """获取调用历史"""
        return self.call_history.copy()

    def clear_history(self) -> None:
        """清空调用历史"""
        self.call_history = []
        self.call_counter = 0

    def add_response(self, pattern: str, response: str) -> None:
        """
        添加响应模式

        Args:
            pattern: 匹配模式（关键词）
            response: 响应文本
        """
        self.responses[pattern] = response

    def set_default_response(self, response: str) -> None:
        """
        设置默认响应

        Args:
            response: 默认响应文本
        """
        self.default_response = response


class DeterministicMockLLM(MockLLM):
    """
    确定性模拟LLM

    总是返回相同的响应，用于需要可重复结果的测试。
    """

    def __init__(self, fixed_response: str = "固定响应"):
        """
        初始化确定性模拟LLM

        Args:
            fixed_response: 固定响应文本
        """
        super().__init__(
            responses={},
            default_response=fixed_response,
            enable_pattern_matching=False,
        )
        self.fixed_response = fixed_response

    def call(self, prompt: str, **kwargs) -> str:
        """总是返回固定响应"""
        self.call_history.append({
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "timestamp": self.call_counter,
        })
        self.call_counter += 1
        return self.fixed_response