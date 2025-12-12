"""
模拟LLM用于测试

提供与DeepSeek API完全兼容的模拟LLM接口，支持适配器模式无缝切换。
"""

import re
import time
from typing import Dict, Any, Optional, Callable, List, Union, Generator
import logging

from .llm_interface import LLMClientBase

logger = logging.getLogger(__name__)


class MockLLM(LLMClientBase):
    """
    模拟LLM，用于测试和开发

    与DeepSeekClient完全兼容，支持相同的参数和方法。
    支持适配器模式，可在测试和生产环境之间无缝切换。
    """

    def __init__(
        self,
        model_name: str = "mock-llm",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 30,
        max_retries: int = 3,
        responses: Optional[Dict[str, Any]] = None,
        default_response: str = "模拟LLM响应",
        enable_pattern_matching: bool = True,
        enable_latency_simulation: bool = False,
        latency_range: tuple = (0.01, 0.1),
        **kwargs,  # 接受额外参数以保持兼容性
    ):
        """
        初始化模拟LLM

        Args:
            model_name: 模型名称（与DeepSeekClient兼容）
            max_tokens: 最大生成令牌数（与DeepSeekClient兼容）
            temperature: 温度参数（与DeepSeekClient兼容）
            timeout: 请求超时时间（秒）（与DeepSeekClient兼容）
            max_retries: 最大重试次数（与DeepSeekClient兼容）
            responses: 预设响应映射 {关键词: 响应文本或可调用函数}
            default_response: 默认响应文本
            enable_pattern_matching: 是否启用模式匹配
            enable_latency_simulation: 是否启用延迟模拟
            latency_range: 延迟范围（秒），格式为(min, max)
            **kwargs: 额外参数（为兼容性保留，如api_key, api_base等）
        """
        # 调用父类初始化（LLMClientBase）
        super().__init__(
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

        self.responses = responses or {}
        self.default_response = default_response
        self.enable_pattern_matching = enable_pattern_matching
        self.enable_latency_simulation = enable_latency_simulation
        self.latency_range = latency_range
        self.call_history = []  # 记录调用历史
        self.call_counter = 0  # 调用计数器

        # 存储额外参数（为兼容性）
        self.extra_kwargs = kwargs

        # 统计信息
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
            "last_call_time": None,
        }

        # 初始化默认响应模式
        self._init_default_responses()

    def _init_default_responses(self) -> None:
        """初始化默认响应模式"""
        if not self.responses:
            self.responses = {
                # 检索排序请求
                "请仅输出索引列表": "0,1,2",
                "请僅輸出索引列表": "0,1,2",
                # 动作选择 - 使用可调用函数
                "请选择动作": self._get_action_sequence,
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
        模拟LLM调用，与DeepSeekClient完全兼容

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数（支持DeepSeekClient的所有参数）
                - model_name: 模型名称
                - max_tokens: 最大生成令牌数
                - temperature: 温度参数
                - max_retries: 最大重试次数
                - 其他任意参数（为兼容性保留）

        Returns:
            模拟响应文本
        """
        start_time = time.time()

        # 模拟延迟（如果启用）
        if self.enable_latency_simulation:
            self._simulate_latency()

        # 验证提示词
        if not self._validate_prompt(prompt):
            logger.warning("提示词为空或无效")
            return ""

        # 记录调用历史
        self.call_history.append({
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "timestamp": time.time(),
            "kwargs": kwargs.copy(),
            "model_name": kwargs.get("model_name", self.model_name),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        })

        # 查找匹配的响应
        response = self._find_matching_response(prompt)

        # 计算延迟
        latency = time.time() - start_time

        # 更新统计信息
        self._update_stats(success=True, tokens=len(response.split()), latency=latency)

        logger.debug(
            f"MockLLM调用 - 模型: {self.model_name}, "
            f"提示词长度: {len(prompt)}, "
            f"响应长度: {len(response)}, "
            f"延迟: {latency:.3f}s"
        )

        return response

    def _simulate_latency(self) -> None:
        """模拟网络延迟"""
        import random
        min_latency, max_latency = self.latency_range
        latency = random.uniform(min_latency, max_latency)
        time.sleep(latency)

    def _find_matching_response(self, prompt: str) -> str:
        """查找匹配的响应文本"""
        prompt_lower = prompt.lower()

        # 首先检查是否是动作选择提示
        if "请选择下一步动作" in prompt_lower or "请选择动作" in prompt_lower:
            response = self.responses.get("请选择动作", self._get_action_sequence)
            return self._process_response(response)

        if self.enable_pattern_matching:
            # 模式匹配 - 检查是否包含关键词
            for pattern, response in self.responses.items():
                pattern_lower = pattern.lower()
                # 更宽松的匹配：检查是否包含关键词
                if pattern_lower in prompt_lower:
                    return self._process_response(response)

        # 检查是否包含特定关键词（更宽松的匹配）
        if "索引" in prompt_lower and "列表" in prompt_lower:
            response = self.responses.get("请仅输出索引列表", "0,1")
            return self._process_response(response)

        if "refine:" in prompt_lower:
            response = self.responses.get("refine:", "DELETE 0")
            return self._process_response(response)

        if "think:" in prompt_lower:
            response = self.responses.get("think:", "Think: 模拟推理过程")
            return self._process_response(response)

        if "act:" in prompt_lower:
            response = self.responses.get("act:", "Act: 模拟动作")
            return self._process_response(response)

        # 返回默认响应
        return self.default_response

    def _process_response(self, response: Any) -> str:
        """处理响应，确保返回字符串"""
        if callable(response):
            return response()
        elif isinstance(response, list):
            # 处理列表响应：根据调用计数器选择响应
            if self.call_counter < len(response):
                result = response[self.call_counter]
            else:
                result = response[-1] if response else self.default_response
            self.call_counter += 1
            return str(result)
        else:
            return str(response)

    def get_model_info(self) -> Dict[str, Any]:
        """获取模拟LLM信息，与DeepSeekClient兼容"""
        info = super().get_model_info()
        info.update({
            "provider": "Mock",
            "description": "模拟LLM用于测试和开发",
            "total_calls": len(self.call_history),
            "responses_configured": len(self.responses),
            "enable_pattern_matching": self.enable_pattern_matching,
            "enable_latency_simulation": self.enable_latency_simulation,
            "latency_range": self.latency_range,
            "extra_params": list(self.extra_kwargs.keys()),
        })
        return info

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计信息"""
        stats = self._stats.copy()
        if stats["total_calls"] > 0:
            stats["average_latency"] = stats["total_latency"] / stats["total_calls"]
            stats["success_rate"] = stats["successful_calls"] / stats["total_calls"]
        else:
            stats["average_latency"] = 0.0
            stats["success_rate"] = 0.0
        return stats

    def get_call_history(self) -> list:
        """获取调用历史"""
        return self.call_history.copy()

    def clear_history(self) -> None:
        """清空调用历史"""
        self.call_history = []
        self.call_counter = 0
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
            "last_call_time": None,
        }

    def add_response(self, pattern: str, response: Any) -> None:
        """
        添加响应模式

        Args:
            pattern: 匹配模式（关键词）
            response: 响应文本或可调用函数
        """
        self.responses[pattern] = response

    def set_default_response(self, response: str) -> None:
        """
        设置默认响应

        Args:
            response: 默认响应文本
        """
        self.default_response = response

    def _update_stats(self, success: bool, tokens: int, latency: float):
        """更新统计信息"""
        self._stats["total_calls"] += 1
        if success:
            self._stats["successful_calls"] += 1
            self._stats["total_tokens"] += tokens
            self._stats["total_latency"] += latency
        else:
            self._stats["failed_calls"] += 1
        self._stats["last_call_time"] = time.time()

    @classmethod
    def create_from_deepseek_config(cls, **kwargs) -> "MockLLM":
        """
        从DeepSeek配置创建MockLLM实例（适配器模式）

        Args:
            **kwargs: DeepSeekClient的配置参数
                - model_name: 模型名称
                - max_tokens: 最大生成令牌数
                - temperature: 温度参数
                - timeout: 超时时间
                - max_retries: 最大重试次数
                - api_key: API密钥（MockLLM会忽略）
                - api_base: API基础URL（MockLLM会忽略）
                - 其他MockLLM特定参数

        Returns:
            MockLLM实例，配置与DeepSeekClient兼容
        """
        # DeepSeekClient特定参数（MockLLM会忽略）
        deepseek_specific_params = ["api_key", "api_base"]

        # MockLLM特定参数
        mock_specific_params = ["responses", "default_response", "enable_pattern_matching",
                               "enable_latency_simulation", "latency_range"]

        # 分离参数
        mock_kwargs = {}
        extra_kwargs = {}

        for key, value in kwargs.items():
            if key in mock_specific_params:
                mock_kwargs[key] = value
            elif key not in deepseek_specific_params:
                # 其他参数（如model_name, max_tokens等）传递给构造函数
                extra_kwargs[key] = value
            # deepseek_specific_params被忽略

        # 创建MockLLM实例
        return cls(**extra_kwargs, **mock_kwargs)


class DeterministicMockLLM(MockLLM):
    """
    确定性模拟LLM

    总是返回相同的响应，用于需要可重复结果的测试。
    """

    def __init__(self, fixed_response: str = "固定响应", **kwargs):
        """
        初始化确定性模拟LLM

        Args:
            fixed_response: 固定响应文本
            **kwargs: 其他MockLLM参数
        """
        super().__init__(
            responses={},
            default_response=fixed_response,
            enable_pattern_matching=False,
            **kwargs
        )
        self.fixed_response = fixed_response

    def call(self, prompt: str, **kwargs) -> str:
        """总是返回固定响应"""
        start_time = time.time()

        # 模拟延迟（如果启用）
        if self.enable_latency_simulation:
            self._simulate_latency()

        # 验证提示词
        if not self._validate_prompt(prompt):
            logger.warning("提示词为空或无效")
            return ""

        # 记录调用历史
        self.call_history.append({
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "timestamp": time.time(),
            "kwargs": kwargs.copy(),
            "model_name": kwargs.get("model_name", self.model_name),
        })

        # 计算延迟
        latency = time.time() - start_time

        # 更新统计信息
        self._update_stats(success=True, tokens=len(self.fixed_response.split()), latency=latency)

        return self.fixed_response


class MockLLMAdapter:
    """
    MockLLM适配器，支持无缝切换

    允许在测试和生产环境之间切换，无需修改调用代码。
    """

    def __init__(self, use_mock: bool = True, mock_config: Optional[Dict] = None,
                 deepseek_config: Optional[Dict] = None):
        """
        初始化适配器

        Args:
            use_mock: 是否使用MockLLM（True=测试环境，False=生产环境）
            mock_config: MockLLM配置参数
            deepseek_config: DeepSeekClient配置参数
        """
        self.use_mock = use_mock
        self.mock_config = mock_config or {}
        self.deepseek_config = deepseek_config or {}
        self._client = None

    def get_client(self):
        """获取当前客户端实例"""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        """创建客户端实例"""
        if self.use_mock:
            # 创建MockLLM实例
            return MockLLM.create_from_deepseek_config(**self.mock_config)
        else:
            # 创建DeepSeekClient实例
            try:
                from .deepseek_client import DeepSeekClient
                # 为测试环境提供默认API密钥
                config = self.deepseek_config.copy()
                if "api_key" not in config:
                    config["api_key"] = "test-api-key-for-mock"
                return DeepSeekClient(**config)
            except ImportError:
                raise ImportError("无法导入DeepSeekClient，请确保已安装openai包")

    def switch_to_mock(self, config: Optional[Dict] = None):
        """切换到MockLLM（测试环境）"""
        self.use_mock = True
        if config:
            self.mock_config.update(config)
        self._client = None  # 强制重新创建客户端

    def switch_to_deepseek(self, config: Optional[Dict] = None):
        """切换到DeepSeekClient（生产环境）"""
        self.use_mock = False
        if config:
            self.deepseek_config.update(config)
        self._client = None  # 强制重新创建客户端

    def call(self, prompt: str, **kwargs) -> str:
        """调用当前客户端"""
        client = self.get_client()
        return client.call(prompt, **kwargs)

    def __call__(self, prompt: str, **kwargs) -> str:
        """使适配器可调用"""
        return self.call(prompt, **kwargs)

    def get_model_info(self) -> Dict[str, Any]:
        """获取当前客户端模型信息"""
        client = self.get_client()
        return client.get_model_info()