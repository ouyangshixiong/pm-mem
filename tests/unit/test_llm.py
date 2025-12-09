"""
LLM模块单元测试
"""

import pytest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from llm.llm_interface import LLMInterface, LLMClientBase
from llm.mock_llm import MockLLM, DeterministicMockLLM


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
            responses={"测试": "响应"},
            default_response="默认响应",
            enable_pattern_matching=True,
        )

        assert llm.default_response == "默认响应"
        assert llm.enable_pattern_matching is True
        assert "测试" in llm.responses
        assert llm.responses["测试"] == "响应"
        assert len(llm.call_history) == 0

    def test_call_with_matching(self):
        """测试调用（模式匹配）"""
        llm = MockLLM(
            responses={"关键词": "匹配响应"},
            default_response="默认响应",
            enable_pattern_matching=True,
        )

        # 匹配关键词
        response = llm.call("这是一个包含关键词的提示词")
        assert response == "匹配响应"
        assert len(llm.call_history) == 1

        # 不匹配关键词
        response = llm.call("这个提示词不包含任何关键词")
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
        llm = MockLLM()
        info = llm.get_model_info()

        assert info["model_name"] == "mock-llm"
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


class TestDeterministicMockLLM:
    """DeterministicMockLLM类测试"""

    def test_initialization(self):
        """测试初始化"""
        llm = DeterministicMockLLM(fixed_response="固定响应")
        assert llm.fixed_response == "固定响应"

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

        assert info["model_name"] == "mock-llm"
        assert info["provider"] == "Mock"


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