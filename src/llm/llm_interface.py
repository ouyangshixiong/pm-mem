"""
LLM抽象接口定义

定义统一的LLM调用接口，支持不同的LLM实现（DeepSeek、模拟LLM等）。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class LLMInterface(ABC):
    """LLM抽象接口"""

    @abstractmethod
    def call(self, prompt: str, **kwargs) -> str:
        """
        调用LLM生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数（温度、最大令牌数等）

        Returns:
            LLM生成的文本
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            包含模型信息的字典
        """
        pass

    def __call__(self, prompt: str, **kwargs) -> str:
        """使实例可调用，方便使用"""
        return self.call(prompt, **kwargs)


class LLMClientBase(LLMInterface):
    """LLM客户端基类，提供通用功能"""

    def __init__(
        self,
        model_name: str = "deepseek-chat",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        初始化LLM客户端

        Args:
            model_name: 模型名称
            max_tokens: 最大生成令牌数
            temperature: 温度参数
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

    @abstractmethod
    def call(self, prompt: str, **kwargs) -> str:
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

    def _validate_prompt(self, prompt: str) -> bool:
        """验证提示词是否有效"""
        if not prompt or not prompt.strip():
            logger.warning("提示词为空")
            return False
        return True

    def _log_call(self, prompt: str, response: str) -> None:
        """记录LLM调用日志"""
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        response_preview = response[:100] + "..." if len(response) > 100 else response

        logger.debug(
            f"LLM调用 - 模型: {self.model_name}\n"
            f"提示词预览: {prompt_preview}\n"
            f"响应预览: {response_preview}"
        )