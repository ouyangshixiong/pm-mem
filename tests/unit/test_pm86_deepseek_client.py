"""
PM-86: DeepSeek API客户端封装实现测试

验证EnhancedDeepSeekClient的完整功能实现。
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from llm.deepseek_client_enhanced import EnhancedDeepSeekClient
from llm.llm_interface_enhanced import LLMResponse, LLMCallMode


class TestEnhancedDeepSeekClient(unittest.TestCase):
    """测试增强的DeepSeek客户端"""

    def setUp(self):
        """测试前准备"""
        # 使用测试API密钥
        self.api_key = "test-api-key-123"
        self.client = EnhancedDeepSeekClient(
            api_key=self.api_key,
            model_name="deepseek-chat-test",
            max_tokens=512,
            temperature=0.5,
            timeout=10,
            max_retries=2,
            connection_pool_size=3
        )

    def test_initialization(self):
        """测试客户端初始化"""
        self.assertEqual(self.client.model_name, "deepseek-chat-test")
        self.assertEqual(self.client.max_tokens, 512)
        self.assertEqual(self.client.temperature, 0.5)
        self.assertEqual(self.client.timeout, 10)
        self.assertEqual(self.client.max_retries, 2)
        self.assertEqual(self.client.connection_pool_size, 3)
        self.assertEqual(self.client.api_key, self.api_key)

    def test_get_model_info(self):
        """测试获取模型信息"""
        info = self.client.get_model_info()

        self.assertEqual(info["model_name"], "deepseek-chat-test")
        self.assertEqual(info["max_tokens"], 512)
        self.assertEqual(info["temperature"], 0.5)
        self.assertEqual(info["timeout"], 10)
        self.assertEqual(info["max_retries"], 2)
        self.assertEqual(info["connection_pool_size"], 3)
        self.assertEqual(info["provider"], "DeepSeek")
        self.assertTrue(info["supports_streaming"])
        self.assertTrue(info["supports_async"])

    @patch('llm.deepseek_client_enhanced.OpenAI')
    def test_sync_call_success(self, mock_openai):
        """测试同步调用成功"""
        # 模拟OpenAI响应
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="测试响应内容"))]

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance

        # 创建新客户端（避免缓存）
        client = EnhancedDeepSeekClient(api_key="test-key")

        # 执行调用
        response = client.call("测试提示词")

        # 验证响应
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.content, "测试响应内容")
        self.assertEqual(response.model, "deepseek-chat")

        # 验证调用参数
        mock_client_instance.chat.completions.create.assert_called_once()
        call_args = mock_client_instance.chat.completions.create.call_args
        self.assertEqual(call_args[1]['model'], "deepseek-chat")
        self.assertEqual(call_args[1]['messages'][0]['content'], "测试提示词")

    @patch('llm.deepseek_client_enhanced.OpenAI')
    def test_sync_call_with_custom_params(self, mock_openai):
        """测试带自定义参数的同步调用"""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="自定义响应"))]

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance

        client = EnhancedDeepSeekClient(api_key="test-key")

        # 使用自定义参数调用
        response = client.call(
            "测试提示词",
            model_name="custom-model",
            max_tokens=1024,
            temperature=0.8,
            max_retries=5
        )

        # 验证调用参数
        call_args = mock_client_instance.chat.completions.create.call_args
        self.assertEqual(call_args[1]['model'], "custom-model")
        self.assertEqual(call_args[1]['max_tokens'], 1024)
        self.assertEqual(call_args[1]['temperature'], 0.8)

    @patch('llm.deepseek_client_enhanced.OpenAI')
    def test_sync_call_retry_on_rate_limit(self, mock_openai):
        """测试速率限制时的重试机制"""
        mock_client_instance = Mock()

        # 第一次调用抛出RateLimitError，第二次成功
        from openai import RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429

        mock_client_instance.chat.completions.create.side_effect = [
            RateLimitError("Rate limit exceeded", response=mock_response, body={}),
            Mock(choices=[Mock(message=Mock(content="重试成功响应"))])
        ]

        mock_openai.return_value = mock_client_instance

        client = EnhancedDeepSeekClient(api_key="test-key", max_retries=3)

        response = client.call("测试提示词")

        # 验证重试了2次
        self.assertEqual(mock_client_instance.chat.completions.create.call_count, 2)
        self.assertEqual(response.content, "重试成功响应")

    @patch('llm.deepseek_client_enhanced.AsyncOpenAI')
    def test_async_call_success(self, mock_async_openai):
        """测试异步调用成功"""
        # 模拟异步响应
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content="异步响应内容"))]

        mock_async_client_instance = AsyncMock()
        mock_async_client_instance.chat.completions.create.return_value = mock_response
        mock_async_openai.return_value = mock_async_client_instance

        client = EnhancedDeepSeekClient(api_key="test-key")

        # 执行异步调用
        async def test_async_call():
            response = await client.async_call("异步测试提示词")
            return response

        response = asyncio.run(test_async_call())

        # 验证响应
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.content, "异步响应内容")
        self.assertEqual(response.metadata["mode"], LLMCallMode.ASYNC.value)

    @patch('llm.deepseek_client_enhanced.OpenAI')
    def test_stream_call(self, mock_openai):
        """测试流式调用"""
        # 模拟流式响应
        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock(delta=Mock(content="流式"))]

        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock(delta=Mock(content="响应"))]

        mock_chunk3 = Mock()
        mock_chunk3.choices = [Mock(delta=Mock(content="内容"))]

        mock_stream = [mock_chunk1, mock_chunk2, mock_chunk3]

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_stream
        mock_openai.return_value = mock_client_instance

        client = EnhancedDeepSeekClient(api_key="test-key")

        # 执行流式调用
        chunks = list(client.stream_call("流式测试提示词"))

        # 验证流式响应
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], "流式")
        self.assertEqual(chunks[1], "响应")
        self.assertEqual(chunks[2], "内容")

        # 验证调用参数
        call_args = mock_client_instance.chat.completions.create.call_args
        self.assertTrue(call_args[1]['stream'])

    def test_from_env_classmethod(self):
        """测试从环境变量创建客户端"""
        # 设置环境变量
        os.environ["DEEPSEEK_API_KEY"] = "env-test-key"
        os.environ["DEEPSEEK_API_BASE"] = "https://test.api.deepseek.com"

        try:
            client = EnhancedDeepSeekClient.from_env(
                model_name="env-model",
                max_tokens=256
            )

            self.assertEqual(client.api_key, "env-test-key")
            self.assertEqual(client.api_base, "https://test.api.deepseek.com")
            self.assertEqual(client.model_name, "env-model")
            self.assertEqual(client.max_tokens, 256)

        finally:
            # 清理环境变量
            del os.environ["DEEPSEEK_API_KEY"]
            del os.environ["DEEPSEEK_API_BASE"]

    def test_stats_tracking(self):
        """测试统计信息跟踪"""
        # 使用模拟客户端测试统计
        with patch.object(self.client, '_execute_call') as mock_execute:
            mock_execute.return_value = "测试响应"

            # 执行多次调用
            for i in range(3):
                self.client.call(f"测试提示词{i}")

            # 获取统计信息
            stats = self.client.get_stats()

            self.assertEqual(stats["total_calls"], 3)
            self.assertEqual(stats["successful_calls"], 3)
            self.assertEqual(stats["failed_calls"], 0)
            self.assertGreater(stats["total_tokens"], 0)
            self.assertGreater(stats["total_latency"], 0)
            self.assertIsNotNone(stats["last_call_time"])

    def test_validate_prompt(self):
        """测试提示词验证"""
        # 有效提示词
        self.assertTrue(self.client._validate_prompt("有效的提示词"))
        self.assertTrue(self.client._validate_prompt("  带空格的提示词  "))

        # 无效提示词
        self.assertFalse(self.client._validate_prompt(""))
        self.assertFalse(self.client._validate_prompt("   "))
        self.assertFalse(self.client._validate_prompt("a" * 10001))  # 过长

    def test_error_handling(self):
        """测试错误处理"""
        with patch.object(self.client, '_execute_call') as mock_execute:
            mock_execute.side_effect = Exception("模拟错误")

            # 验证异常被抛出
            with self.assertRaises(Exception) as context:
                self.client.call("测试提示词")

            self.assertIn("模拟错误", str(context.exception))

            # 验证统计信息
            stats = self.client.get_stats()
            self.assertEqual(stats["failed_calls"], 1)


if __name__ == '__main__':
    unittest.main()