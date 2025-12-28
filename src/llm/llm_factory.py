"""
LLM工厂类

提供统一的LLM实例创建和管理，支持配置化、多环境、自动降级等功能。
"""

import os
import logging
from typing import Dict, Any, Optional, Union, Type
from enum import Enum

from .llm_interface import LLMInterface
from .llm_interface_enhanced import EnhancedLLMInterface
from .mock_llm import MockLLM, MockLLMAdapter, DeterministicMockLLM
from config.config_manager import get_config_manager
from config.api_key_manager import get_api_key_manager, get_api_key

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM提供商枚举"""
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    MIMO = "mimo"
    MOCK = "mock"
    DETERMINISTIC_MOCK = "deterministic_mock"


class LLMEnvironment(Enum):
    """LLM环境枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMFactory:
    """LLM工厂类，提供统一的LLM实例创建和管理"""

    # 默认配置
    DEFAULT_CONFIG = {
        "provider": LLMProvider.DEEPSEEK.value,
        "environment": LLMEnvironment.DEVELOPMENT.value,
        "model_name": "deepseek-chat",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 30,
        "max_retries": 3,
        "connection_pool_size": 5,
        "enable_mock_fallback": True,
        "mock_fallback_delay": 0.1,
        "enable_health_check": True,
        "health_check_interval": 60,
    }

    # 实例缓存
    _instances: Dict[str, LLMInterface] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化LLM工厂

        Args:
            config: 配置字典，会与默认配置合并
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 从全局配置管理器获取配置
        self._load_config_from_manager()

        # 健康检查状态
        self._health_status: Dict[str, Dict[str, Any]] = {}
        self._last_health_check: Dict[str, float] = {}

        logger.info(f"LLM工厂已初始化 - 提供商: {self.config['provider']}, 环境: {self.config['environment']}")

    def _load_config_from_manager(self):
        """从配置管理器加载配置"""
        try:
            config_manager = get_config_manager()

            # 加载LLM配置
            llm_config = config_manager.get("llm", {})
            if llm_config:
                # 更新配置
                for key, value in llm_config.items():
                    if key in self.config:
                        self.config[key] = value

                # 特殊处理provider
                if "provider" in llm_config:
                    self.config["provider"] = llm_config["provider"]

                logger.debug(f"从配置管理器加载LLM配置: {llm_config}")
        except Exception as e:
            logger.warning(f"从配置管理器加载配置失败: {e}")

    def create_llm(
        self,
        provider: Optional[str] = None,
        environment: Optional[str] = None,
        **kwargs
    ) -> LLMInterface:
        """
        创建LLM实例

        Args:
            provider: LLM提供商，如为None则使用配置中的provider
            environment: 环境，如为None则使用配置中的environment
            **kwargs: 额外参数，会传递给具体的LLM构造函数

        Returns:
            LLMInterface实例
        """
        provider_name = provider or self.config["provider"]
        env = environment or self.config["environment"]

        # 生成缓存键
        cache_key = self._generate_cache_key(provider_name, env, kwargs)

        # 检查缓存
        if cache_key in self._instances:
            logger.debug(f"使用缓存的LLM实例: {cache_key}")
            return self._instances[cache_key]

        # 创建新实例
        llm_instance = self._create_new_llm(provider_name, env, kwargs)

        # 缓存实例
        self._instances[cache_key] = llm_instance
        logger.info(f"创建新的LLM实例: {cache_key}")

        return llm_instance

    def _generate_cache_key(self, provider: str, environment: str, kwargs: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 简化的缓存键生成，实际生产环境可能需要更复杂的逻辑
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = str(sorted_kwargs)
        return f"{provider}_{environment}_{hash(kwargs_str)}"

    def _create_new_llm(self, provider: str, environment: str, kwargs: Dict[str, Any]) -> LLMInterface:
        """创建新的LLM实例"""
        # 合并配置
        merged_kwargs = self.config.copy()
        merged_kwargs.update(kwargs)

        try:
            if provider == LLMProvider.DEEPSEEK.value:
                return self._create_deepseek_llm(environment, merged_kwargs)
            elif provider == LLMProvider.KIMI.value:
                return self._create_kimi_llm(environment, merged_kwargs)
            elif provider == LLMProvider.MIMO.value:
                return self._create_mimo_llm(environment, merged_kwargs)
            elif provider == LLMProvider.MOCK.value:
                return self._create_mock_llm(environment, merged_kwargs)
            elif provider == LLMProvider.DETERMINISTIC_MOCK.value:
                return self._create_deterministic_mock_llm(environment, merged_kwargs)
            else:
                raise ValueError(f"不支持的LLM提供商: {provider}")
        except Exception as e:
            logger.error(f"创建LLM实例失败: {e}")

            # 如果启用了模拟降级，则创建模拟LLM
            if self.config.get("enable_mock_fallback", True):
                logger.warning(f"创建{provider}失败，降级到模拟LLM")
                return self._create_mock_llm(environment, merged_kwargs)
            else:
                raise

    def _create_deepseek_llm(self, environment: str, kwargs: Dict[str, Any]) -> LLMInterface:
        """创建DeepSeek LLM实例"""
        try:
            from .deepseek_client_enhanced import EnhancedDeepSeekClient  # 延迟导入以避免测试环境依赖
        except Exception as e:
            raise RuntimeError(f"DeepSeek客户端不可用: {e}")
        # 获取API密钥
        api_key = self._get_api_key("deepseek", environment)

        if not api_key:
            raise ValueError(f"未找到DeepSeek在{environment}环境的API密钥")

        # 创建增强的DeepSeek客户端
        llm_kwargs = {
            "api_key": api_key,
            "model_name": kwargs.get("model_name", "deepseek-chat"),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "timeout": kwargs.get("timeout", 30),
            "max_retries": kwargs.get("max_retries", 3),
            "connection_pool_size": kwargs.get("connection_pool_size", 5),
        }

        # 可选参数
        if "api_base" in kwargs:
            llm_kwargs["api_base"] = kwargs["api_base"]

        logger.info(f"创建DeepSeek LLM实例 - 环境: {environment}, 模型: {llm_kwargs['model_name']}")
        return EnhancedDeepSeekClient(**llm_kwargs)

    def _create_kimi_llm(self, environment: str, kwargs: Dict[str, Any]) -> LLMInterface:
        """创建Kimi LLM实例"""
        try:
            from .kimi_client_enhanced import EnhancedKimiClient  # 延迟导入以避免测试环境依赖
        except Exception as e:
            raise RuntimeError(f"Kimi客户端不可用: {e}")
        # 获取API密钥
        api_key = self._get_api_key("kimi", environment)

        if not api_key:
            raise ValueError(f"未找到Kimi在{environment}环境的API密钥")

        # 创建增强的Kimi客户端
        llm_kwargs = {
            "api_key": api_key,
            "model_name": kwargs.get("model_name", "kimi-k2-0905-preview"),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "timeout": kwargs.get("timeout", 30),
            "max_retries": kwargs.get("max_retries", 3),
            "connection_pool_size": kwargs.get("connection_pool_size", 5),
        }

        # 可选参数
        if "api_base" in kwargs:
            llm_kwargs["api_base"] = kwargs["api_base"]

        logger.info(f"创建Kimi LLM实例 - 环境: {environment}, 模型: {llm_kwargs['model_name']}")
        return EnhancedKimiClient(**llm_kwargs)

    def _create_mimo_llm(self, environment: str, kwargs: Dict[str, Any]) -> LLMInterface:
        """创建Mimo LLM实例"""
        try:
            from .mimo_client_enhanced import EnhancedMimoClient  # 延迟导入以避免测试环境依赖
        except Exception as e:
            raise RuntimeError(f"Mimo客户端不可用: {e}")
        # 获取API密钥
        api_key = self._get_api_key("mimo", environment)

        if not api_key:
            raise ValueError(f"未找到Mimo在{environment}环境的API密钥")

        # 创建增强的Mimo客户端
        llm_kwargs = {
            "api_key": api_key,
            "model_name": kwargs.get("model_name", "mimo-v2-flash"),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "timeout": kwargs.get("timeout", 30),
            "max_retries": kwargs.get("max_retries", 3),
            "connection_pool_size": kwargs.get("connection_pool_size", 5),
        }

        # 可选参数
        if "api_base" in kwargs:
            llm_kwargs["api_base"] = kwargs["api_base"]

        logger.info(f"创建Mimo LLM实例 - 环境: {environment}, 模型: {llm_kwargs['model_name']}")
        return EnhancedMimoClient(**llm_kwargs)

    def _create_mock_llm(self, environment: str, kwargs: Dict[str, Any]) -> LLMInterface:
        """创建模拟LLM实例"""
        llm_kwargs = {
            "model_name": kwargs.get("model_name", "mock-llm"),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "timeout": kwargs.get("timeout", 30),
            "max_retries": kwargs.get("max_retries", 3),
            "enable_latency_simulation": kwargs.get("enable_latency_simulation", True),
            "latency_range": kwargs.get("latency_range", (0.01, 0.1)),
        }

        logger.info(f"创建模拟LLM实例 - 环境: {environment}, 模型: {llm_kwargs['model_name']}")
        return MockLLM(**llm_kwargs)

    def _create_deterministic_mock_llm(self, environment: str, kwargs: Dict[str, Any]) -> LLMInterface:
        """创建确定性模拟LLM实例"""
        llm_kwargs = {
            "model_name": kwargs.get("model_name", "deterministic-mock-llm"),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "timeout": kwargs.get("timeout", 30),
            "max_retries": kwargs.get("max_retries", 3),
            "fixed_response": kwargs.get("fixed_response", "确定性模拟响应"),
        }

        logger.info(f"创建确定性模拟LLM实例 - 环境: {environment}")
        return DeterministicMockLLM(**llm_kwargs)

    def _get_api_key(self, provider: str, environment: str) -> Optional[str]:
        """获取API密钥"""
        try:
            # 首先尝试从API密钥管理器获取
            api_key = get_api_key(provider, environment)
            if api_key:
                return api_key

            # 然后尝试从环境变量获取
            env_var_name = f"{provider.upper()}_API_KEY"
            api_key = os.getenv(env_var_name)
            if api_key:
                return api_key

            # 最后尝试从配置获取
            config_manager = get_config_manager()
            config_key = f"llm.{provider}.api_key"
            api_key = config_manager.get(config_key)
            if api_key:
                return api_key

            logger.warning(f"未找到{provider}在{environment}环境的API密钥")
            return None

        except Exception as e:
            logger.error(f"获取API密钥失败: {e}")
            return None

    def create_adapter(
        self,
        use_mock: Optional[bool] = None,
        mock_config: Optional[Dict[str, Any]] = None,
        deepseek_config: Optional[Dict[str, Any]] = None,
    ) -> MockLLMAdapter:
        """
        创建LLM适配器，支持测试和生产环境切换

        Args:
            use_mock: 是否使用模拟LLM，如为None则根据环境自动判断
            mock_config: 模拟LLM配置
            deepseek_config: DeepSeek配置

        Returns:
            MockLLMAdapter实例
        """
        if use_mock is None:
            # 根据环境自动判断
            environment = self.config["environment"]
            use_mock = environment in [LLMEnvironment.DEVELOPMENT.value, LLMEnvironment.TESTING.value]

        # 默认配置
        default_mock_config = {
            "model_name": "mock-llm",
            "max_tokens": self.config["max_tokens"],
            "temperature": self.config["temperature"],
            "enable_latency_simulation": True,
            "latency_range": (0.01, 0.1),
        }

        default_deepseek_config = {
            "model_name": self.config["model_name"],
            "max_tokens": self.config["max_tokens"],
            "temperature": self.config["temperature"],
            "timeout": self.config["timeout"],
            "max_retries": self.config["max_retries"],
        }

        # 合并配置
        final_mock_config = default_mock_config.copy()
        if mock_config:
            final_mock_config.update(mock_config)

        final_deepseek_config = default_deepseek_config.copy()
        if deepseek_config:
            final_deepseek_config.update(deepseek_config)

        logger.info(f"创建LLM适配器 - 使用模拟: {use_mock}")
        return MockLLMAdapter(
            use_mock=use_mock,
            mock_config=final_mock_config,
            deepseek_config=final_deepseek_config,
        )

    def check_health(self, llm_instance: Optional[LLMInterface] = None) -> Dict[str, Any]:
        """
        检查LLM健康状态

        Args:
            llm_instance: LLM实例，如为None则检查所有缓存的实例

        Returns:
            健康状态字典
        """
        if llm_instance:
            instances = {id(llm_instance): llm_instance}
        else:
            instances = {key: instance for key, instance in self._instances.items()}

        results = {}
        for instance_id, instance in instances.items():
            try:
                # 执行简单的健康检查
                start_time = time.time() if 'time' in globals() else 0

                # 尝试获取模型信息
                model_info = instance.get_model_info()

                latency = (time.time() - start_time) if 'time' in globals() else 0

                results[instance_id] = {
                    "healthy": True,
                    "model_info": model_info,
                    "latency": latency,
                    "timestamp": time.time() if 'time' in globals() else 0,
                }

                logger.debug(f"LLM健康检查通过: {instance_id}")

            except Exception as e:
                results[instance_id] = {
                    "healthy": False,
                    "error": str(e),
                    "timestamp": time.time() if 'time' in globals() else 0,
                }

                logger.warning(f"LLM健康检查失败: {instance_id}, 错误: {e}")

        # 更新健康状态缓存
        self._health_status.update(results)
        self._last_health_check = {instance_id: time.time() if 'time' in globals() else 0
                                  for instance_id in instances.keys()}

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取工厂统计信息"""
        return {
            "total_instances": len(self._instances),
            "cached_instances": list(self._instances.keys()),
            "config": self.config.copy(),
            "health_status": self._health_status.copy(),
            "last_health_check": self._last_health_check.copy(),
        }

    def clear_cache(self) -> None:
        """清空实例缓存"""
        self._instances.clear()
        logger.info("LLM实例缓存已清空")

    def get_default_llm(self) -> LLMInterface:
        """获取默认的LLM实例"""
        return self.create_llm()

    @classmethod
    def from_config_manager(cls, config_path: Optional[str] = None) -> "LLMFactory":
        """
        从配置管理器创建LLM工厂

        Args:
            config_path: 配置文件路径

        Returns:
            LLMFactory实例
        """
        config_manager = get_config_manager(config_path)
        llm_config = config_manager.get("llm", {})

        return cls(config=llm_config)


# 全局LLM工厂实例
_llm_factory: Optional[LLMFactory] = None


def get_llm_factory(config: Optional[Dict[str, Any]] = None) -> LLMFactory:
    """
    获取全局LLM工厂实例

    Args:
        config: 配置字典

    Returns:
        LLMFactory实例
    """
    global _llm_factory

    if _llm_factory is None:
        _llm_factory = LLMFactory(config)

    return _llm_factory


def create_llm(
    provider: Optional[str] = None,
    environment: Optional[str] = None,
    **kwargs
) -> LLMInterface:
    """
    创建LLM实例（快捷函数）

    Args:
        provider: LLM提供商
        environment: 环境
        **kwargs: 额外参数

    Returns:
        LLMInterface实例
    """
    factory = get_llm_factory()
    return factory.create_llm(provider, environment, **kwargs)


def get_default_llm() -> LLMInterface:
    """获取默认的LLM实例（快捷函数）"""
    factory = get_llm_factory()
    return factory.get_default_llm()


# 导入time模块用于健康检查
import time
