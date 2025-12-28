"""
LLM模块

提供统一的LLM调用接口，支持DeepSeek、Kimi、Mimo API和模拟LLM。
"""

from .llm_interface import LLMInterface, LLMClientBase
try:
    from .deepseek_client import DeepSeekClient
except Exception:
    DeepSeekClient = None
try:
    from .kimi_client import KimiClient
except Exception:
    KimiClient = None
try:
    from .mimo_client import MimoClient
except Exception:
    MimoClient = None
from .mock_llm import MockLLM, DeterministicMockLLM, MockLLMAdapter
from .llm_interface_enhanced import EnhancedLLMInterface, EnhancedLLMClientBase, LLMResponse, LLMCallMode
try:
    from .deepseek_client_enhanced import EnhancedDeepSeekClient
except Exception:
    EnhancedDeepSeekClient = None
try:
    from .kimi_client_enhanced import EnhancedKimiClient
except Exception:
    EnhancedKimiClient = None
try:
    from .mimo_client_enhanced import EnhancedMimoClient
except Exception:
    EnhancedMimoClient = None

__all__ = [
    # 基础接口
    "LLMInterface",
    "LLMClientBase",

    # DeepSeek客户端
    "DeepSeekClient",
    "EnhancedDeepSeekClient",

    # Kimi客户端
    "KimiClient",
    "EnhancedKimiClient",

    # Mimo客户端
    "MimoClient",
    "EnhancedMimoClient",

    # 模拟LLM
    "MockLLM",
    "DeterministicMockLLM",
    "MockLLMAdapter",

    # 增强接口
    "EnhancedLLMInterface",
    "EnhancedLLMClientBase",
    "LLMResponse",
    "LLMCallMode",
]

__version__ = "1.0.0"
