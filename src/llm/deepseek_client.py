"""
DeepSeek API客户端

实现统一的LLM调用接口，支持API密钥配置管理、请求超时和重试机制。
"""

import os
import time
from typing import Optional, Dict, Any
import logging

try:
    from openai import OpenAI
    from openai import APIError, APITimeoutError, RateLimitError
except ImportError:
    raise ImportError(
        "请安装openai包: pip install openai>=1.12.0"
    )

from .llm_interface import LLMClientBase

logger = logging.getLogger(__name__)


class DeepSeekClient(LLMClientBase):
    """DeepSeek API客户端"""

    # 默认API基础URL
    DEFAULT_API_BASE = "https://api.deepseek.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: str = "deepseek-chat",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        初始化DeepSeek客户端

        Args:
            api_key: DeepSeek API密钥，如为None则从环境变量DEEPSEEK_API_KEY读取
            api_base: API基础URL，如为None则使用默认值
            model_name: 模型名称
            max_tokens: 最大生成令牌数
            temperature: 温度参数
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        super().__init__(model_name, max_tokens, temperature, timeout, max_retries)

        # 获取API密钥
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError(
                "未提供DeepSeek API密钥。请通过参数提供或设置环境变量DEEPSEEK_API_KEY"
            )

        # 设置API基础URL
        self.api_base = api_base or os.getenv("DEEPSEEK_API_BASE") or self.DEFAULT_API_BASE

        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=self.timeout,
        )

        logger.info(f"DeepSeek客户端已初始化 - 模型: {model_name}, API基础URL: {self.api_base}")

    def call(self, prompt: str, **kwargs) -> str:
        """
        调用DeepSeek API生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数，可覆盖默认参数

        Returns:
            LLM生成的文本

        Raises:
            Exception: 当所有重试都失败时抛出异常
        """
        if not self._validate_prompt(prompt):
            return ""

        # 合并参数：kwargs优先，然后是实例参数
        model_name = kwargs.get("model_name", self.model_name)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        max_retries = kwargs.get("max_retries", self.max_retries)

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                )

                result = response.choices[0].message.content.strip()
                self._log_call(prompt, result)
                return result

            except RateLimitError as e:
                last_error = e
                wait_time = 2 ** attempt  # 指数退避
                logger.warning(
                    f"API速率限制，第{attempt + 1}次重试，等待{wait_time}秒: {e}"
                )
                time.sleep(wait_time)

            except APITimeoutError as e:
                last_error = e
                logger.warning(
                    f"API请求超时，第{attempt + 1}次重试: {e}"
                )
                time.sleep(1)  # 短时间等待后重试

            except APIError as e:
                last_error = e
                logger.error(f"API错误: {e}")
                # 对于非重试性错误，直接跳出
                if e.status_code and e.status_code >= 400 and e.status_code < 500:
                    break
                time.sleep(1)

            except Exception as e:
                last_error = e
                logger.error(f"未知错误: {e}")
                break

        # 所有重试都失败
        error_msg = f"DeepSeek API调用失败，已重试{max_retries}次: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def get_model_info(self) -> Dict[str, Any]:
        """获取DeepSeek模型信息"""
        info = super().get_model_info()
        info.update({
            "provider": "DeepSeek",
            "api_base": self.api_base,
            "supports_streaming": True,
        })
        return info

    @classmethod
    def from_env(cls, **kwargs) -> "DeepSeekClient":
        """
        从环境变量创建DeepSeek客户端

        Args:
            **kwargs: 传递给构造函数的额外参数

        Returns:
            DeepSeekClient实例
        """
        api_key = os.getenv("DEEPSEEK_API_KEY")
        api_base = os.getenv("DEEPSEEK_API_BASE")

        if not api_key:
            raise ValueError(
                "环境变量DEEPSEEK_API_KEY未设置。请在.env文件中设置或导出环境变量"
            )

        return cls(api_key=api_key, api_base=api_base, **kwargs)