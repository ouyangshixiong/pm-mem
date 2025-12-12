"""
MockLLM适配器使用示例

演示如何通过适配器模式在测试和生产环境之间无缝切换。
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from llm.mock_llm import MockLLM, MockLLMAdapter, DeterministicMockLLM
from llm.deepseek_client import DeepSeekClient


def example_basic_mock_llm():
    """示例1：基本MockLLM使用"""
    print("=" * 60)
    print("示例1：基本MockLLM使用")
    print("=" * 60)

    # 创建MockLLM实例
    mock_llm = MockLLM(
        model_name="mock-deepseek",
        max_tokens=1024,
        temperature=0.8,
        default_response="这是模拟LLM的默认响应",
        enable_latency_simulation=True,
    )

    # 添加自定义响应
    mock_llm.add_response("你好", "你好！我是模拟LLM。")
    mock_llm.add_response("天气", "今天天气晴朗，温度适宜。")

    # 测试调用
    prompts = [
        "你好，今天怎么样？",
        "今天的天气如何？",
        "请帮我写一段代码",
        "请仅输出索引列表",
        "Think: 如何解决这个问题？",
    ]

    for prompt in prompts:
        response = mock_llm.call(prompt)
        print(f"提示词: {prompt[:50]}...")
        print(f"响应: {response[:100]}...")
        print("-" * 40)

    # 查看模型信息
    info = mock_llm.get_model_info()
    print(f"模型信息: {info}")
    print(f"调用统计: {mock_llm.get_stats()}")
    print(f"调用历史数量: {len(mock_llm.get_call_history())}")


def example_deterministic_mock_llm():
    """示例2：确定性MockLLM使用"""
    print("\n" + "=" * 60)
    print("示例2：确定性MockLLM使用")
    print("=" * 60)

    # 创建确定性MockLLM
    deterministic_llm = DeterministicMockLLM(
        fixed_response="这是固定响应",
        model_name="deterministic-mock",
        temperature=0.5,
    )

    # 多次调用，总是返回相同响应
    for i in range(3):
        response = deterministic_llm.call(f"测试提示词 {i}")
        print(f"调用 {i+1}: {response}")

    print(f"模型信息: {deterministic_llm.get_model_info()}")


def example_mock_llm_adapter():
    """示例3：MockLLM适配器使用"""
    print("\n" + "=" * 60)
    print("示例3：MockLLM适配器使用")
    print("=" * 60)

    # 创建适配器（默认使用MockLLM）
    adapter = MockLLMAdapter(
        use_mock=True,
        mock_config={
            "model_name": "adapter-mock",
            "default_response": "适配器模式：模拟响应",
            "enable_latency_simulation": False,
        },
        deepseek_config={
            "model_name": "deepseek-chat",
            "max_tokens": 2048,
            "temperature": 0.7,
        }
    )

    print("当前使用MockLLM（测试环境）:")
    response = adapter.call("你好，测试适配器")
    print(f"响应: {response}")
    print(f"模型信息: {adapter.get_model_info()}")

    # 切换到DeepSeek（生产环境）
    print("\n切换到DeepSeek（生产环境）:")
    adapter.switch_to_deepseek()

    try:
        # 注意：这里需要真实的API密钥才能工作
        response = adapter.call("你好，测试真实API")
        print(f"响应: {response}")
    except Exception as e:
        print(f"DeepSeek调用失败（需要API密钥）: {e}")

    # 切换回MockLLM
    print("\n切换回MockLLM（测试环境）:")
    adapter.switch_to_mock()
    response = adapter.call("再次测试模拟模式")
    print(f"响应: {response}")


def example_compatibility_with_deepseek():
    """示例4：与DeepSeekClient的兼容性"""
    print("\n" + "=" * 60)
    print("示例4：与DeepSeekClient的兼容性")
    print("=" * 60)

    # 创建MockLLM，使用与DeepSeekClient相同的参数
    mock_llm = MockLLM(
        model_name="deepseek-chat",  # 相同的模型名称
        max_tokens=2048,             # 相同的最大令牌数
        temperature=0.7,             # 相同的温度参数
        timeout=30,                  # 相同的超时时间
        max_retries=3,               # 相同的重试次数
    )

    # 测试使用DeepSeekClient风格的参数调用
    response = mock_llm.call(
        "请回答这个问题",
        model_name="deepseek-chat",
        max_tokens=1024,
        temperature=0.8,
        max_retries=2,
        some_extra_param="extra"  # 额外的参数（兼容性）
    )

    print(f"使用DeepSeek参数调用结果: {response[:100]}...")

    # 检查调用历史中的参数
    history = mock_llm.get_call_history()
    if history:
        print(f"调用参数记录: {history[0]['kwargs']}")
        print(f"使用的模型名称: {history[0]['model_name']}")
        print(f"使用的最大令牌数: {history[0]['max_tokens']}")
        print(f"使用的温度参数: {history[0]['temperature']}")


def example_create_from_deepseek_config():
    """示例5：从DeepSeek配置创建MockLLM"""
    print("\n" + "=" * 60)
    print("示例5：从DeepSeek配置创建MockLLM")
    print("=" * 60)

    # DeepSeekClient的配置
    deepseek_config = {
        "model_name": "deepseek-chat",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 30,
        "max_retries": 3,
        "api_key": "fake-api-key",  # MockLLM会忽略这个
        "api_base": "https://api.deepseek.com",
    }

    # 添加MockLLM特定参数
    deepseek_config.update({
        "default_response": "从DeepSeek配置创建的MockLLM",
        "enable_pattern_matching": True,
        "responses": {
            "测试": "这是测试响应",
            "帮助": "我可以帮助你解决问题",
        }
    })

    # 从DeepSeek配置创建MockLLM
    mock_llm = MockLLM.create_from_deepseek_config(**deepseek_config)

    print(f"创建的MockLLM模型名称: {mock_llm.model_name}")
    print(f"最大令牌数: {mock_llm.max_tokens}")
    print(f"温度参数: {mock_llm.temperature}")
    print(f"默认响应: {mock_llm.default_response}")

    # 测试调用
    response = mock_llm.call("测试一下")
    print(f"测试调用响应: {response}")

    response = mock_llm.call("需要帮助")
    print(f"帮助调用响应: {response}")


def main():
    """主函数"""
    print("MockLLM适配器模式演示")
    print("=" * 60)

    example_basic_mock_llm()
    example_deterministic_mock_llm()
    example_mock_llm_adapter()
    example_compatibility_with_deepseek()
    example_create_from_deepseek_config()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()