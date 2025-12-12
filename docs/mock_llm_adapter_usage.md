# MockLLM适配器使用指南

## 概述

MockLLM适配器提供了与DeepSeek API完全兼容的模拟LLM接口，支持适配器模式无缝切换。它允许在测试和生产环境之间切换，无需修改调用代码。

## 主要特性

1. **完全兼容性**: 与DeepSeekClient接口完全兼容
2. **适配器模式**: 支持测试和生产环境无缝切换
3. **参数一致性**: 支持DeepSeekClient的所有调用参数
4. **测试友好**: 提供预设响应、调用记录、统计信息等功能
5. **延迟模拟**: 可选的网络延迟模拟

## 核心组件

### 1. MockLLM类
继承自`LLMClientBase`，提供与DeepSeekClient完全兼容的模拟实现。

### 2. DeterministicMockLLM类
确定性模拟LLM，总是返回相同的响应，用于需要可重复结果的测试。

### 3. MockLLMAdapter类
适配器模式实现，支持在MockLLM和DeepSeekClient之间无缝切换。

## 快速开始

### 基本使用

```python
from llm.mock_llm import MockLLM

# 创建MockLLM实例
mock_llm = MockLLM(
    model_name="mock-deepseek",
    max_tokens=1024,
    temperature=0.7,
    default_response="默认响应",
)

# 添加自定义响应
mock_llm.add_response("你好", "你好！我是模拟LLM。")
mock_llm.add_response("天气", "今天天气晴朗。")

# 调用（与DeepSeekClient完全兼容）
response = mock_llm.call("你好，今天怎么样？")
print(response)  # 输出: "你好！我是模拟LLM。"

# 使用DeepSeekClient风格的参数
response = mock_llm.call(
    "请回答问题",
    model_name="deepseek-chat",
    max_tokens=512,
    temperature=0.8,
    max_retries=2,
)
```

### 适配器模式使用

```python
from llm.mock_llm import MockLLMAdapter

# 创建适配器（默认使用MockLLM）
adapter = MockLLMAdapter(
    use_mock=True,  # 使用MockLLM（测试环境）
    mock_config={
        "model_name": "test-mock",
        "default_response": "测试响应",
    },
    deepseek_config={
        "model_name": "deepseek-chat",
        "max_tokens": 2048,
        "temperature": 0.7,
    }
)

# 调用（无论使用Mock还是DeepSeek，接口相同）
response = adapter.call("测试提示词")

# 切换到DeepSeek（生产环境）
adapter.switch_to_deepseek()

# 切换回MockLLM（测试环境）
adapter.switch_to_mock()
```

### 从DeepSeek配置创建MockLLM

```python
from llm.mock_llm import MockLLM

# DeepSeekClient的配置
deepseek_config = {
    "model_name": "deepseek-chat",
    "max_tokens": 2048,
    "temperature": 0.7,
    "timeout": 30,
    "max_retries": 3,
    "api_key": "fake-api-key",  # MockLLM会忽略
    "api_base": "https://api.deepseek.com",
}

# 添加MockLLM特定参数
deepseek_config.update({
    "default_response": "从DeepSeek配置创建",
    "responses": {"测试": "响应"},
})

# 从DeepSeek配置创建MockLLM
mock_llm = MockLLM.create_from_deepseek_config(**deepseek_config)
```

## 高级功能

### 1. 调用历史记录

```python
mock_llm = MockLLM()

# 多次调用
mock_llm.call("提示词1")
mock_llm.call("提示词2")

# 获取调用历史
history = mock_llm.get_call_history()
print(f"总调用次数: {len(history)}")
for call in history:
    print(f"提示词: {call['prompt']}")
    print(f"时间戳: {call['timestamp']}")
    print(f"参数: {call['kwargs']}")

# 清空历史
mock_llm.clear_history()
```

### 2. 统计信息

```python
mock_llm = MockLLM()

# 多次调用
mock_llm.call("测试1")
mock_llm.call("测试2")

# 获取统计信息
stats = mock_llm.get_stats()
print(f"总调用次数: {stats['total_calls']}")
print(f"成功调用: {stats['successful_calls']}")
print(f"失败调用: {stats['failed_calls']}")
print(f"平均延迟: {stats['average_latency']:.3f}s")
print(f"成功率: {stats['success_rate']:.2%}")
```

### 3. 延迟模拟

```python
# 启用延迟模拟
mock_llm = MockLLM(
    enable_latency_simulation=True,
    latency_range=(0.05, 0.2),  # 延迟范围：50-200ms
)

# 调用时会模拟网络延迟
response = mock_llm.call("测试提示词")
```

### 4. 确定性测试

```python
from llm.mock_llm import DeterministicMockLLM

# 创建确定性MockLLM
deterministic_llm = DeterministicMockLLM(
    fixed_response="固定响应",
    model_name="deterministic-test",
)

# 总是返回相同响应
response1 = deterministic_llm.call("提示词1")
response2 = deterministic_llm.call("提示词2")
assert response1 == response2 == "固定响应"
```

## 与DeepSeekClient的兼容性

### 参数兼容性

MockLLM支持DeepSeekClient的所有参数：

```python
# DeepSeekClient调用方式
from llm.deepseek_client import DeepSeekClient
deepseek_client = DeepSeekClient(
    model_name="deepseek-chat",
    max_tokens=2048,
    temperature=0.7,
    timeout=30,
    max_retries=3,
)
response = deepseek_client.call("提示词")

# MockLLM调用方式（完全相同）
from llm.mock_llm import MockLLM
mock_llm = MockLLM(
    model_name="deepseek-chat",  # 相同的参数
    max_tokens=2048,
    temperature=0.7,
    timeout=30,
    max_retries=3,
)
response = mock_llm.call("提示词")  # 相同的调用方式
```

### 方法兼容性

MockLLM实现了DeepSeekClient的所有公共方法：

- `call(prompt, **kwargs)`: 调用LLM生成文本
- `get_model_info()`: 获取模型信息
- `__call__(prompt, **kwargs)`: 使实例可调用

## 测试用例示例

### 单元测试

```python
import pytest
from llm.mock_llm import MockLLM, MockLLMAdapter

def test_mock_llm_basic():
    """测试基本功能"""
    llm = MockLLM(default_response="测试响应")
    response = llm.call("测试提示词")
    assert response == "测试响应"

def test_mock_llm_with_kwargs():
    """测试kwargs参数兼容性"""
    llm = MockLLM(model_name="default-model")

    # 使用DeepSeekClient风格的参数
    response = llm.call(
        "提示词",
        model_name="custom-model",
        max_tokens=1024,
        temperature=0.8,
    )

    # 检查调用历史中的参数
    history = llm.get_call_history()
    assert history[0]["model_name"] == "custom-model"
    assert history[0]["max_tokens"] == 1024
    assert history[0]["temperature"] == 0.8

def test_adapter_switching():
    """测试适配器模式切换"""
    adapter = MockLLMAdapter(use_mock=True)

    # 初始为Mock模式
    response1 = adapter.call("测试")
    assert response1 is not None

    # 切换到DeepSeek模式
    adapter.switch_to_deepseek()

    # 切换回Mock模式
    adapter.switch_to_mock()
    response2 = adapter.call("测试")
    assert response2 is not None
```

### 集成测试

```python
def test_compatibility_with_real_code():
    """测试与真实代码的兼容性"""

    # 假设这是你的业务代码
    def process_with_llm(llm_client, prompt):
        """使用LLM客户端处理提示词"""
        return llm_client.call(prompt, max_tokens=512, temperature=0.7)

    # 使用MockLLM测试
    mock_llm = MockLLM()
    mock_result = process_with_llm(mock_llm, "测试提示词")
    assert mock_result is not None

    # 使用DeepSeekClient（需要API密钥）
    # deepseek_client = DeepSeekClient()
    # real_result = process_with_llm(deepseek_client, "测试提示词")
    # assert real_result is not None
```

## 配置选项

### MockLLM配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_name` | str | `"mock-llm"` | 模型名称 |
| `max_tokens` | int | `2048` | 最大生成令牌数 |
| `temperature` | float | `0.7` | 温度参数 |
| `timeout` | int | `30` | 请求超时时间（秒） |
| `max_retries` | int | `3` | 最大重试次数 |
| `responses` | Dict[str, Any] | `None` | 预设响应映射 |
| `default_response` | str | `"模拟LLM响应"` | 默认响应文本 |
| `enable_pattern_matching` | bool | `True` | 是否启用模式匹配 |
| `enable_latency_simulation` | bool | `False` | 是否启用延迟模拟 |
| `latency_range` | tuple | `(0.01, 0.1)` | 延迟范围（秒） |

### MockLLMAdapter配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_mock` | bool | `True` | 是否使用MockLLM |
| `mock_config` | Dict | `{}` | MockLLM配置参数 |
| `deepseek_config` | Dict | `{}` | DeepSeekClient配置参数 |

## 最佳实践

### 1. 测试环境配置

```python
# 在测试环境中使用MockLLM
def get_llm_client_for_testing():
    """获取测试用的LLM客户端"""
    return MockLLM(
        model_name="test-model",
        default_response="测试响应",
        enable_latency_simulation=False,  # 测试时关闭延迟模拟
        responses={
            "特定场景": "预设响应",
            "错误处理": "错误响应",
        }
    )
```

### 2. 生产环境配置

```python
# 在生产环境中使用适配器
def get_llm_client_for_production(use_mock=False):
    """获取生产用的LLM客户端"""
    return MockLLMAdapter(
        use_mock=use_mock,  # 可通过环境变量控制
        mock_config={
            "model_name": "mock-deepseek",
            "default_response": "维护模式响应",
        },
        deepseek_config={
            "model_name": "deepseek-chat",
            "max_tokens": 2048,
            "temperature": 0.7,
            # API密钥从环境变量读取
        }
    )
```

### 3. 错误处理

```python
try:
    # 使用适配器调用
    response = adapter.call("提示词")
except Exception as e:
    # 记录错误
    logger.error(f"LLM调用失败: {e}")

    # 如果是生产环境且使用DeepSeek，可以切换到Mock模式
    if not adapter.use_mock:
        logger.warning("切换到Mock模式")
        adapter.switch_to_mock()

        # 重试
        response = adapter.call("提示词")
```

## 常见问题

### Q1: MockLLM与DeepSeekClient的兼容性如何？
A: 完全兼容。MockLLM继承自`LLMClientBase`（与DeepSeekClient相同），支持相同的参数和方法。

### Q2: 如何在测试和生产环境之间切换？
A: 使用`MockLLMAdapter`类，通过`switch_to_mock()`和`switch_to_deepseek()`方法切换。

### Q3: MockLLM的性能如何？
A: MockLLM非常轻量，适合单元测试和集成测试。可以启用延迟模拟来测试网络延迟场景。

### Q4: 如何添加自定义响应？
A: 使用`add_response(pattern, response)`方法添加响应模式，或通过`responses`参数初始化时设置。

### Q5: 如何获取调用统计？
A: 使用`get_stats()`方法获取调用统计信息，包括总调用次数、成功率、平均延迟等。

## 总结

MockLLM适配器提供了完整的模拟LLM解决方案，具有以下优势：

1. **无缝切换**: 通过适配器模式在测试和生产环境之间切换
2. **完全兼容**: 与DeepSeekClient接口完全一致
3. **测试友好**: 提供丰富的测试功能（预设响应、调用记录、统计信息等）
4. **易于使用**: 简单的API设计，易于集成到现有代码中
5. **可扩展**: 支持自定义响应模式和高级配置

通过使用MockLLM适配器，你可以：
- 在开发阶段使用MockLLM进行快速测试
- 在CI/CD流水线中使用MockLLM进行自动化测试
- 在生产环境出现问题时快速切换到Mock模式
- 收集和分析LLM调用统计信息