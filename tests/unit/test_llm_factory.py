"""
LLM工厂测试

验证LLMFactory的完整功能实现。
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
import shutil

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from llm.llm_factory import (
    LLMFactory,
    LLMProvider,
    LLMEnvironment,
    get_llm_factory,
    create_llm,
    get_default_llm
)
from llm.llm_interface import LLMInterface
from llm.mock_llm import MockLLM, DeterministicMockLLM
from llm.deepseek_client_enhanced import EnhancedDeepSeekClient


class TestLLMFactory(unittest.TestCase):
    """测试LLM工厂"""

    def setUp(self):
        """测试前准备"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试配置
        self.test_config = {
            "provider": "mock",
            "environment": "testing",
            "model_name": "test-model",
            "max_tokens": 512,
            "temperature": 0.5,
            "timeout": 10,
            "max_retries": 2,
            "connection_pool_size": 3,
            "enable_mock_fallback": True,
        }

        # 创建工厂实例
        self.factory = LLMFactory(config=self.test_config)

    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """测试工厂初始化"""
        self.assertEqual(self.factory.config["provider"], "mock")
        self.assertEqual(self.factory.config["environment"], "testing")
        self.assertEqual(self.factory.config["model_name"], "test-model")
        self.assertEqual(self.factory.config["max_tokens"], 512)
        self.assertEqual(self.factory.config["temperature"], 0.5)
        self.assertEqual(self.factory.config["timeout"], 10)
        self.assertEqual(self.factory.config["max_retries"], 2)
        self.assertEqual(self.factory.config["connection_pool_size"], 3)
        self.assertTrue(self.factory.config["enable_mock_fallback"])

    def test_create_mock_llm(self):
        """测试创建模拟LLM"""
        llm = self.factory.create_llm(provider="mock", environment="testing")

        self.assertIsInstance(llm, MockLLM)
        self.assertEqual(llm.model_name, "test-model")
        self.assertEqual(llm.max_tokens, 512)
        self.assertEqual(llm.temperature, 0.5)
        self.assertEqual(llm.timeout, 10)
        self.assertEqual(llm.max_retries, 2)

    def test_create_deterministic_mock_llm(self):
        """测试创建确定性模拟LLM"""
        llm = self.factory.create_llm(
            provider="deterministic_mock",
            environment="testing",
            fixed_response="固定测试响应"
        )

        self.assertIsInstance(llm, DeterministicMockLLM)
        self.assertEqual(llm.fixed_response, "固定测试响应")

    @patch('llm.llm_factory.get_api_key')
    @patch('llm.llm_factory.EnhancedDeepSeekClient')
    def test_create_deepseek_llm(self, mock_deepseek_class, mock_get_api_key):
        """测试创建DeepSeek LLM"""
        # 模拟API密钥
        mock_get_api_key.return_value = "test-deepseek-api-key"

        # 模拟DeepSeek客户端
        mock_deepseek_instance = Mock(spec=EnhancedDeepSeekClient)
        mock_deepseek_class.return_value = mock_deepseek_instance

        # 创建DeepSeek LLM
        llm = self.factory.create_llm(
            provider="deepseek",
            environment="production",
            model_name="deepseek-chat-pro",
            max_tokens=1024
        )

        # 验证API密钥获取
        mock_get_api_key.assert_called_once_with("deepseek", "production")

        # 验证DeepSeek客户端创建
        mock_deepseek_class.assert_called_once()
        call_args = mock_deepseek_class.call_args[1]
        self.assertEqual(call_args["api_key"], "test-deepseek-api-key")
        self.assertEqual(call_args["model_name"], "deepseek-chat-pro")
        self.assertEqual(call_args["max_tokens"], 1024)
        self.assertEqual(call_args["temperature"], 0.5)
        self.assertEqual(call_args["timeout"], 10)
        self.assertEqual(call_args["max_retries"], 2)
        self.assertEqual(call_args["connection_pool_size"], 3)

        self.assertIs(llm, mock_deepseek_instance)

    @patch('llm.llm_factory.get_api_key')
    def test_create_deepseek_llm_no_api_key(self, mock_get_api_key):
        """测试创建DeepSeek LLM（无API密钥）"""
        # 模拟无API密钥
        mock_get_api_key.return_value = None

        # 应该降级到模拟LLM
        llm = self.factory.create_llm(provider="deepseek", environment="production")

        self.assertIsInstance(llm, MockLLM)
        mock_get_api_key.assert_called_once_with("deepseek", "production")

    def test_instance_caching(self):
        """测试实例缓存"""
        # 创建第一个实例
        llm1 = self.factory.create_llm(provider="mock", environment="testing")

        # 使用相同参数创建第二个实例（应该返回缓存的实例）
        llm2 = self.factory.create_llm(provider="mock", environment="testing")

        self.assertIs(llm1, llm2)
        self.assertEqual(len(self.factory._instances), 1)

        # 使用不同参数创建第三个实例（应该创建新实例）
        llm3 = self.factory.create_llm(
            provider="mock",
            environment="testing",
            model_name="different-model"
        )

        self.assertIsNot(llm1, llm3)
        self.assertEqual(len(self.factory._instances), 2)

    def test_create_adapter(self):
        """测试创建适配器"""
        # 测试使用模拟LLM的适配器
        adapter_mock = self.factory.create_adapter(use_mock=True)
        self.assertTrue(adapter_mock.use_mock)

        # 测试使用DeepSeek的适配器
        adapter_deepseek = self.factory.create_adapter(use_mock=False)
        self.assertFalse(adapter_deepseek.use_mock)

        # 测试自动判断（测试环境应该使用模拟）
        adapter_auto = self.factory.create_adapter(use_mock=None)
        self.assertTrue(adapter_auto.use_mock)  # 测试环境应该使用模拟

    def test_get_default_llm(self):
        """测试获取默认LLM"""
        llm = self.factory.get_default_llm()

        self.assertIsInstance(llm, MockLLM)
        self.assertEqual(llm.model_name, "test-model")

    def test_clear_cache(self):
        """测试清空缓存"""
        # 创建一些实例
        self.factory.create_llm(provider="mock", environment="testing")
        self.factory.create_llm(provider="mock", environment="development")

        self.assertEqual(len(self.factory._instances), 2)

        # 清空缓存
        self.factory.clear_cache()

        self.assertEqual(len(self.factory._instances), 0)

    def test_get_stats(self):
        """测试获取统计信息"""
        # 创建一些实例
        self.factory.create_llm(provider="mock", environment="testing")
        self.factory.create_llm(provider="mock", environment="development")

        stats = self.factory.get_stats()

        self.assertEqual(stats["total_instances"], 2)
        self.assertEqual(len(stats["cached_instances"]), 2)
        self.assertEqual(stats["config"]["provider"], "mock")
        self.assertEqual(stats["config"]["environment"], "testing")

    @patch('llm.llm_factory.get_config_manager')
    def test_from_config_manager(self, mock_get_config_manager):
        """测试从配置管理器创建工厂"""
        # 模拟配置管理器
        mock_config_manager = Mock()
        mock_config_manager.get.return_value = {
            "provider": "deepseek",
            "model_name": "config-model",
            "max_tokens": 4096,
        }
        mock_get_config_manager.return_value = mock_config_manager

        # 从配置管理器创建工厂
        factory = LLMFactory.from_config_manager()

        self.assertEqual(factory.config["provider"], "deepseek")
        self.assertEqual(factory.config["model_name"], "config-model")
        self.assertEqual(factory.config["max_tokens"], 4096)
        mock_get_config_manager.assert_called_once_with(None)

    def test_global_functions(self):
        """测试全局函数"""
        # 测试get_llm_factory
        factory1 = get_llm_factory(self.test_config)
        factory2 = get_llm_factory()  # 应该返回同一个实例

        self.assertIs(factory1, factory2)

        # 测试create_llm
        llm = create_llm(provider="mock", environment="testing")
        self.assertIsInstance(llm, MockLLM)

        # 测试get_default_llm
        default_llm = get_default_llm()
        self.assertIsInstance(default_llm, MockLLM)

    def test_health_check(self):
        """测试健康检查"""
        # 创建LLM实例
        llm = self.factory.create_llm(provider="mock", environment="testing")

        # 执行健康检查
        health_results = self.factory.check_health(llm)

        self.assertEqual(len(health_results), 1)
        instance_id = list(health_results.keys())[0]
        self.assertTrue(health_results[instance_id]["healthy"])
        self.assertIn("model_info", health_results[instance_id])

        # 测试检查所有实例
        all_health_results = self.factory.check_health()
        self.assertEqual(len(all_health_results), 1)

    def test_custom_kwargs(self):
        """测试自定义参数"""
        llm = self.factory.create_llm(
            provider="mock",
            environment="testing",
            custom_param="custom_value",
            enable_latency_simulation=False,
            latency_range=(0.0, 0.0)
        )

        self.assertIsInstance(llm, MockLLM)
        self.assertFalse(llm.enable_latency_simulation)
        self.assertEqual(llm.latency_range, (0.0, 0.0))
        # 自定义参数应该被忽略（不会传递给构造函数）
        self.assertFalse(hasattr(llm, "custom_param"))

    def test_environment_auto_detection(self):
        """测试环境自动检测"""
        # 测试环境应该使用模拟
        test_factory = LLMFactory(config={"environment": "testing"})
        adapter_test = test_factory.create_adapter(use_mock=None)
        self.assertTrue(adapter_test.use_mock)

        # 开发环境应该使用模拟
        dev_factory = LLMFactory(config={"environment": "development"})
        adapter_dev = dev_factory.create_adapter(use_mock=None)
        self.assertTrue(adapter_dev.use_mock)

        # 生产环境应该使用真实LLM
        prod_factory = LLMFactory(config={"environment": "production"})
        adapter_prod = prod_factory.create_adapter(use_mock=None)
        self.assertFalse(adapter_prod.use_mock)

        # 预发布环境应该使用真实LLM
        staging_factory = LLMFactory(config={"environment": "staging"})
        adapter_staging = staging_factory.create_adapter(use_mock=None)
        self.assertFalse(adapter_staging.use_mock)


if __name__ == '__main__':
    unittest.main()