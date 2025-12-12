"""
增强的LLM抽象接口定义

在现有llm_interface.py基础上，增加异步支持、流式响应、连接池管理等功能。
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator, Generator, Union
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LLMCallMode(Enum):
    """LLM调用模式"""
    SYNC = "sync"      # 同步调用
    ASYNC = "async"    # 异步调用
    STREAM = "stream"  # 流式调用


@dataclass
class LLMResponse:
    """LLM响应数据结构"""
    content: str
    model: str
    tokens_used: int
    latency: float  # 响应延迟（秒）
    metadata: Dict[str, Any]


class EnhancedLLMInterface(ABC):
    """增强的LLM抽象接口，支持同步、异步和流式调用"""

    @abstractmethod
    def call(self, prompt: str, **kwargs) -> LLMResponse:
        """
        同步调用LLM生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数

        Returns:
            LLMResponse: 包含响应内容和元数据
        """
        pass

    @abstractmethod
    async def async_call(self, prompt: str, **kwargs) -> LLMResponse:
        """
        异步调用LLM生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数

        Returns:
            LLMResponse: 包含响应内容和元数据
        """
        pass

    @abstractmethod
    def stream_call(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式调用LLM，逐块生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数

        Yields:
            str: 文本块
        """
        pass

    @abstractmethod
    async def async_stream_call(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        异步流式调用LLM，逐块生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数

        Yields:
            str: 文本块
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

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        获取调用统计信息

        Returns:
            包含调用统计的字典
        """
        pass

    def __call__(self, prompt: str, **kwargs) -> Union[LLMResponse, str]:
        """使实例可调用，返回LLMResponse或字符串"""
        response = self.call(prompt, **kwargs)
        return response.content if kwargs.get("raw", False) else response


class EnhancedLLMClientBase(EnhancedLLMInterface):
    """增强的LLM客户端基类，提供通用功能"""

    def __init__(
        self,
        model_name: str = "deepseek-chat",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 30,
        max_retries: int = 3,
        connection_pool_size: int = 5,
    ):
        """
        初始化增强的LLM客户端

        Args:
            model_name: 模型名称
            max_tokens: 最大生成令牌数
            temperature: 温度参数
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            connection_pool_size: 连接池大小
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.connection_pool_size = connection_pool_size

        # 统计信息
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
            "last_call_time": None,
        }

        # 连接池（简化实现）
        self._connection_pool = []
        self._init_connection_pool()

    def _init_connection_pool(self):
        """初始化连接池"""
        logger.info(f"初始化连接池，大小: {self.connection_pool_size}")
        # 在实际实现中，这里会创建实际的连接
        self._connection_pool = [None] * self.connection_pool_size

    def _get_connection(self):
        """从连接池获取连接（简化实现）"""
        # 在实际实现中，这里会实现连接池管理
        return None

    def _release_connection(self, connection):
        """释放连接到连接池"""
        pass

    def call(self, prompt: str, **kwargs) -> LLMResponse:
        """同步调用实现"""
        start_time = time.time()

        try:
            # 验证提示词
            if not self._validate_prompt(prompt):
                raise ValueError("无效的提示词")

            # 获取连接
            connection = self._get_connection()

            # 执行调用
            response_content = self._execute_call(prompt, connection, **kwargs)

            # 计算延迟
            latency = time.time() - start_time

            # 更新统计
            self._update_stats(success=True, tokens=len(response_content.split()), latency=latency)

            # 创建响应对象
            response = LLMResponse(
                content=response_content,
                model=self.model_name,
                tokens_used=len(response_content.split()),
                latency=latency,
                metadata={
                    "mode": LLMCallMode.SYNC.value,
                    "retries": 0,
                    "timestamp": start_time,
                }
            )

            return response

        except Exception as e:
            # 更新统计
            self._update_stats(success=False, tokens=0, latency=time.time() - start_time)
            logger.error(f"LLM调用失败: {e}")
            raise

    async def async_call(self, prompt: str, **kwargs) -> LLMResponse:
        """异步调用实现"""
        # 简化实现：在线程池中执行同步调用
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.call(prompt, **kwargs))

    def stream_call(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式调用实现"""
        # 简化实现：模拟流式响应
        response = self.call(prompt, **kwargs)
        words = response.content.split()

        for i in range(0, len(words), 3):
            chunk = " ".join(words[i:i+3])
            yield chunk + " "

            # 模拟延迟
            time.sleep(0.1)

    async def async_stream_call(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """异步流式调用实现"""
        # 简化实现
        for chunk in self.stream_call(prompt, **kwargs):
            yield chunk

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "connection_pool_size": self.connection_pool_size,
            "supports_async": True,
            "supports_streaming": True,
        }

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

    def _validate_prompt(self, prompt: str) -> bool:
        """验证提示词是否有效"""
        if not prompt or not prompt.strip():
            logger.warning("提示词为空")
            return False
        if len(prompt) > 10000:  # 简单长度检查
            logger.warning("提示词过长")
            return False
        return True

    def _execute_call(self, prompt: str, connection, **kwargs) -> str:
        """执行实际的LLM调用（由子类实现）"""
        raise NotImplementedError("子类必须实现_execute_call方法")

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

    def _log_call(self, prompt: str, response: str, mode: LLMCallMode) -> None:
        """记录LLM调用日志"""
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        response_preview = response[:100] + "..." if len(response) > 100 else response

        logger.debug(
            f"LLM调用 - 模式: {mode.value}, 模型: {self.model_name}\n"
            f"提示词预览: {prompt_preview}\n"
            f"响应预览: {response_preview}"
        )