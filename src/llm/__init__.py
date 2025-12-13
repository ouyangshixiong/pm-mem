"""
LLM模块

提供统一的LLM调用接口，支持DeepSeek API和模拟LLM。
"""

from .llm_interface import LLMInterface, LLMClientBase
try:
    from .deepseek_client import DeepSeekClient
except Exception:
    DeepSeekClient = None
from .mock_llm import MockLLM, DeterministicMockLLM, MockLLMAdapter
from .llm_interface_enhanced import EnhancedLLMInterface, EnhancedLLMClientBase, LLMResponse, LLMCallMode
try:
    from .deepseek_client_enhanced import EnhancedDeepSeekClient
except Exception:
    EnhancedDeepSeekClient = None

__all__ = [
    # 基础接口
    "LLMInterface",
    "LLMClientBase",

    # DeepSeek客户端
    "DeepSeekClient",

    # 模拟LLM
    "MockLLM",
    "DeterministicMockLLM",
    "MockLLMAdapter",

    # 增强接口
    "EnhancedLLMInterface",
    "EnhancedLLMClientBase",
    "LLMResponse",
    "LLMCallMode",

    # 增强DeepSeek客户端
    "EnhancedDeepSeekClient",
]

__version__ = "1.0.0"
