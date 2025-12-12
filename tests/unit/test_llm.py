"""
LLM模块单元测试
"""

import pytest
import sys
import os
import time

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from llm.llm_interface import LLMInterface, LLMClientBase
from llm.mock_llm import MockLLM, DeterministicMockLLM, MockLLMAdapter


class TestLLMInterface:
    """LLM接口测试"""

    def test_interface_abstract(self):
        """测试接口是抽象的"""
        with pytest.raises(TypeError):
            LLMInterface()  # 不能实例化抽象类

    def test_client_base_abstract(self):
        """测试客户端基类是抽象的"""
        with pytest.raises(TypeError):
            LLMClientBase()  # 不能实例化抽象类


class TestMockLLM:
    """MockLLM类测试"""

    def test_initialization(self):
        """测试初始化"""
        llm = MockLLM(
            model_name="test-model",
            max_tokens=1024,
            temperature=0.5,
            timeout=60,
            max_retries=2,
            responses={"测试": "响应"},
            default_response="默认响应",
            enable_pattern_matching=True,
            enable_latency_simulation=True,
            latency_range=(0.01, 0.05),
        )

        assert llm.model_name == "test-model"
        assert llm.max_tokens == 1024
        assert llm.temperature == 0.5
        assert llm.timeout == 60
        assert llm.max_retries == 2
        assert llm.default_response == "默认响应"
        assert llm.enable_pattern_matching is True
        assert llm.enable_latency_simulation is True
        assert llm.latency_range == (0.01, 0.05)
        assert "测试" in llm.responses
        assert llm.responses["测试"] == "响应"
        assert len(llm.call_history) == 0

    def test_call_with_matching(self):
        """测试调用（模式匹配）"""
        llm = MockLLM(
            responses={"特定关键词": "匹配响应"},
            default_response="默认响应",
            enable_pattern_matching=True,
        )

        # 匹配关键词
        response = llm.call("这是一个包含特定关键词的提示词")
        assert response == "匹配响应"
        assert len(llm.call_history) == 1

        # 不匹配关键词（使用不同的词）
        response = llm.call("这个提示词不包含任何匹配内容")
        assert response == "默认响应"
        assert len(llm.call_history) == 2

    def test_call_without_matching(self):
        """测试调用（关闭模式匹配）"""
        llm = MockLLM(
            responses={"关键词": "匹配响应"},
            default_response="默认响应",
            enable_pattern_matching=False,
        )

        # 即使有关键词也不会匹配
        response = llm.call("这是一个包含关键词的提示词")
        assert response == "默认响应"

    def test_call_action_selection(self):
        """测试动作选择逻辑"""
        llm = MockLLM()
        llm.call_counter = 0

        # 测试动作序列
        responses = []
        for _ in range(5):
            responses.append(llm.call("请选择动作"))

        # 默认动作序列是 ["think", "refine", "act", "act", "act"]
        assert responses == ["think", "refine", "act", "act", "act"]

    def test_call_with_special_patterns(self):
        """测试特殊模式匹配"""
        llm = MockLLM()

        # 索引列表请求
        response = llm.call("请仅输出索引列表")
        assert response == "0,1,2"

        # Think请求
        response = llm.call("Think: 请推理")
        assert "Think:" in response

        # Refine请求
        response = llm.call("Refine: 请修改记忆")
        assert "DELETE" in response

        # Act请求
        response = llm.call("Act: 请执行动作")
        assert "Act:" in response

    def test_get_model_info(self):
        """测试获取模型信息"""
        llm = MockLLM(
            model_name="test-model",
            max_tokens=1024,
            temperature=0.5,
        )
        info = llm.get_model_info()

        assert info["model_name"] == "test-model"
        assert info["max_tokens"] == 1024
        assert info["temperature"] == 0.5
        assert info["provider"] == "Mock"
        assert info["total_calls"] == 0

        # 调用一次后检查
        llm.call("测试")
        info = llm.get_model_info()
        assert info["total_calls"] == 1

    def test_call_history(self):
        """测试调用历史记录"""
        llm = MockLLM()

        llm.call("提示词1")
        llm.call("提示词2")
        llm.call("提示词3")

        history = llm.get_call_history()
        assert len(history) == 3
        assert "提示词1" in history[0]["prompt"]
        assert "提示词2" in history[1]["prompt"]
        assert "提示词3" in history[2]["prompt"]

        # 清空历史
        llm.clear_history()
        assert len(llm.get_call_history()) == 0
        assert llm.call_counter == 0

    def test_add_response(self):
        """测试添加响应模式"""
        llm = MockLLM(default_response="默认")

        # 添加新响应
        llm.add_response("新关键词", "新响应")
        response = llm.call("包含新关键词的提示词")
        assert response == "新响应"

    def test_set_default_response(self):
        """测试设置默认响应"""
        llm = MockLLM(default_response="旧默认")

        llm.set_default_response("新默认")
        response = llm.call("无匹配提示词")
        assert response == "新默认"

    def test_call_with_kwargs(self):
        """测试调用时传递kwargs参数（与DeepSeekClient兼容）"""
        llm = MockLLM(
            model_name="default-model",
            max_tokens=2048,
            temperature=0.7,
        )

        # 使用kwargs参数调用
        response = llm.call(
            "测试提示词",
            model_name="custom-model",
            max_tokens=1024,
            temperature=0.5,
            max_retries=2,
            extra_param="extra_value"
        )

        # 检查响应
        assert response is not None

        # 检查调用历史中的参数
        history = llm.get_call_history()
        assert len(history) == 1
        assert history[0]["model_name"] == "custom-model"
        assert history[0]["max_tokens"] == 1024
        assert history[0]["temperature"] == 0.5
        assert history[0]["kwargs"]["model_name"] == "custom-model"
        assert history[0]["kwargs"]["max_tokens"] == 1024
        assert history[0]["kwargs"]["temperature"] == 0.5
        assert history[0]["kwargs"]["max_retries"] == 2
        assert history[0]["kwargs"]["extra_param"] == "extra_value"

    def test_get_stats(self):
        """测试获取统计信息"""
        llm = MockLLM()

        # 初始统计
        stats = llm.get_stats()
        assert stats["total_calls"] == 0
        assert stats["successful_calls"] == 0
        assert stats["failed_calls"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_latency"] == 0.0

        # 调用后统计
        llm.call("测试1")
        llm.call("测试2")

        stats = llm.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successful_calls"] == 2
        assert stats["total_tokens"] > 0
        assert stats["total_latency"] > 0.0
        assert "average_latency" in stats
        assert "success_rate" in stats

    def test_create_from_deepseek_config(self):
        """测试从DeepSeek配置创建MockLLM"""
        # DeepSeek配置
        config = {
            "model_name": "deepseek-chat",
            "max_tokens": 2048,
            "temperature": 0.7,
            "timeout": 30,
            "max_retries": 3,
            "api_key": "fake-key",
            "api_base": "https://api.deepseek.com",
            # MockLLM特定参数
            "default_response": "从配置创建",
            "enable_pattern_matching": False,
            "responses": {"测试": "响应"},
        }

        # 创建MockLLM
        llm = MockLLM.create_from_deepseek_config(**config)

        # 验证参数
        assert llm.model_name == "deepseek-chat"
        assert llm.max_tokens == 2048
        assert llm.temperature == 0.7
        assert llm.timeout == 30
        assert llm.max_retries == 3
        assert llm.default_response == "从配置创建"
        assert llm.enable_pattern_matching is False
        assert "测试" in llm.responses
        assert llm.responses["测试"] == "响应"

        # 测试调用 - 由于enable_pattern_matching=False，应该返回默认响应
        response = llm.call("测试")
        assert response == "从配置创建"

        # 启用模式匹配后测试
        llm.enable_pattern_matching = True
        response = llm.call("测试")
        assert response == "响应"


class TestDeterministicMockLLM:
    """DeterministicMockLLM类测试"""

    def test_initialization(self):
        """测试初始化"""
        llm = DeterministicMockLLM(
            fixed_response="固定响应",
            model_name="deterministic-model",
            temperature=0.5,
        )
        assert llm.fixed_response == "固定响应"
        assert llm.model_name == "deterministic-model"
        assert llm.temperature == 0.5
        assert llm.enable_pattern_matching is False

    def test_call_always_same(self):
        """测试总是返回相同响应"""
        llm = DeterministicMockLLM(fixed_response="固定响应")

        responses = [
            llm.call("提示词1"),
            llm.call("提示词2"),
            llm.call("提示词3"),
        ]

        assert all(r == "固定响应" for r in responses)
        assert len(llm.get_call_history()) == 3

    def test_get_model_info(self):
        """测试获取模型信息"""
        llm = DeterministicMockLLM(fixed_response="固定响应")
        info = llm.get_model_info()

        assert info["model_name"] == "mock-llm"  # 默认值
        assert info["provider"] == "Mock"


class TestMockLLMAdapter:
    """MockLLMAdapter类测试"""

    def test_initialization(self):
        """测试初始化"""
        adapter = MockLLMAdapter(
            use_mock=True,
            mock_config={
                "model_name": "test-mock",
                "default_response": "测试响应",
            },
            deepseek_config={
                "model_name": "deepseek-chat",
                "max_tokens": 2048,
            }
        )

        assert adapter.use_mock is True
        assert adapter.mock_config["model_name"] == "test-mock"
        assert adapter.deepseek_config["model_name"] == "deepseek-chat"
        assert adapter._client is None

    def test_get_client_mock_mode(self):
        """测试获取客户端（Mock模式）"""
        adapter = MockLLMAdapter(use_mock=True)
        client = adapter.get_client()

        assert client is not None
        assert isinstance(client, MockLLM)
        assert adapter._client is client  # 缓存检查

    def test_get_client_deepseek_mode(self):
        """测试获取客户端（DeepSeek模式）"""
        adapter = MockLLMAdapter(use_mock=False)

        # 由于MockLLMAdapter为测试环境提供了默认API密钥，应该能创建客户端
        client = adapter.get_client()
        assert client is not None
        # 注意：这里实际上创建的是DeepSeekClient，但由于提供了测试API密钥，不会抛出异常

    def test_switch_modes(self):
        """测试模式切换"""
        adapter = MockLLMAdapter(use_mock=True)

        # 初始为Mock模式
        client1 = adapter.get_client()
        assert isinstance(client1, MockLLM)

        # 切换到DeepSeek模式
        adapter.switch_to_deepseek()
        assert adapter.use_mock is False
        assert adapter._client is None

        # 切换回Mock模式
        adapter.switch_to_mock()
        assert adapter.use_mock is True
        assert adapter._client is None

        # 获取新客户端
        client2 = adapter.get_client()
        assert isinstance(client2, MockLLM)
        assert client2 is not client1  # 应该是新实例

    def test_call_method(self):
        """测试call方法"""
        adapter = MockLLMAdapter(use_mock=True)

        response = adapter.call("测试提示词")
        assert response is not None

        # 检查调用历史
        client = adapter.get_client()
        assert len(client.get_call_history()) == 1

    def test_callable_interface(self):
        """测试可调用接口"""
        adapter = MockLLMAdapter(use_mock=True)

        response = adapter("测试提示词")
        assert response is not None

    def test_get_model_info(self):
        """测试获取模型信息"""
        adapter = MockLLMAdapter(use_mock=True)

        info = adapter.get_model_info()
        assert info is not None
        assert "model_name" in info
        assert "provider" in info


def test_llm_interface_implementation():
    """测试LLM接口实现"""
    # MockLLM应该正确实现LLMInterface接口
    llm = MockLLM()

    # 检查是否实现了必需的方法
    assert hasattr(llm, 'call')
    assert hasattr(llm, 'get_model_info')
    assert hasattr(llm, '__call__')

    # 测试__call__方法
    response = llm("测试提示词")
    assert response is not None

    # 测试get_model_info返回字典
    info = llm.get_model_info()
    assert isinstance(info, dict)
    assert "model_name" in info


def test_compatibility_with_llmclientbase():
    """测试与LLMClientBase的兼容性"""
    # MockLLM应该继承自LLMClientBase
    llm = MockLLM(
        model_name="test-model",
        max_tokens=1024,
        temperature=0.5,
        timeout=30,
        max_retries=3,
    )

    # 检查继承关系
    assert isinstance(llm, LLMClientBase)
    assert isinstance(llm, MockLLM)

    # 检查父类方法
    assert hasattr(llm, '_validate_prompt')
    assert hasattr(llm, '_log_call')

    # 测试父类方法
    assert llm._validate_prompt("有效提示词") is True
    assert llm._validate_prompt("") is False
    assert llm._validate_prompt("   ") is False

    # 测试模型信息包含父类字段
    info = llm.get_model_info()
    assert info["model_name"] == "test-model"
    assert info["max_tokens"] == 1024
    assert info["temperature"] == 0.5
    assert info["timeout"] == 30
    assert info["max_retries"] == 3