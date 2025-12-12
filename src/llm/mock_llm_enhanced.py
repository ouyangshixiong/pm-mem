"""
增强的模拟LLM实现

支持多种模拟模式、可配置的响应行为、延迟模拟、错误注入等高级功能。
"""

import time
import asyncio
import random
import json
from typing import Dict, Any, Optional, List, Union, Generator, AsyncGenerator
import logging
from dataclasses import dataclass
from enum import Enum
import re

from .llm_interface_enhanced import EnhancedLLMClientBase, LLMResponse, LLMCallMode

logger = logging.getLogger(__name__)


class MockMode(Enum):
    """模拟模式"""
    STATIC = "static"          # 静态响应
    RANDOM = "random"          # 随机响应
    TEMPLATE = "template"      # 模板响应
    SEQUENTIAL = "sequential"  # 顺序响应
    ERROR_INJECTION = "error_injection"  # 错误注入


class ErrorType(Enum):
    """错误类型"""
    TIMEOUT = "timeout"        # 超时
    RATE_LIMIT = "rate_limit"  # 速率限制
    API_ERROR = "api_error"    # API错误
    NETWORK_ERROR = "network_error"  # 网络错误


@dataclass
class MockResponseTemplate:
    """模拟响应模板"""
    template: str
    variables: Dict[str, Any]
    response_type: str = "text"


@dataclass
class ErrorInjectionConfig:
    """错误注入配置"""
    error_type: ErrorType
    probability: float = 0.1  # 错误发生概率
    error_message: Optional[str] = None
    delay_before_error: float = 0.0  # 错误前的延迟


class EnhancedMockLLM(EnhancedLLMClientBase):
    """增强的模拟LLM"""

    # 预定义的响应模板
    DEFAULT_TEMPLATES = {
        "greeting": "你好！我是模拟AI助手。有什么可以帮助你的吗？",
        "question": "这是一个关于'{topic}'的问题。我的回答是：{answer}",
        "summary": "根据你提供的信息，我总结如下：\n{summary}",
        "code": "以下是实现{function}的代码：\n```{language}\n{code}\n```",
        "list": "以下是你请求的列表：\n{items}",
        "error": "抱歉，处理你的请求时出现了错误：{error}",
    }

    def __init__(
        self,
        model_name: str = "mock-llm",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 30,
        max_retries: int = 3,
        connection_pool_size: int = 5,
        mock_mode: MockMode = MockMode.TEMPLATE,
        response_templates: Optional[Dict[str, str]] = None,
        default_latency: float = 0.5,  # 默认延迟（秒）
        latency_variance: float = 0.2,  # 延迟方差
        error_config: Optional[ErrorInjectionConfig] = None,
    ):
        """
        初始化增强的模拟LLM

        Args:
            model_name: 模型名称
            max_tokens: 最大生成令牌数
            temperature: 温度参数
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            connection_pool_size: 连接池大小
            mock_mode: 模拟模式
            response_templates: 响应模板字典
            default_latency: 默认响应延迟
            latency_variance: 延迟方差
            error_config: 错误注入配置
        """
        super().__init__(
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
            connection_pool_size=connection_pool_size,
        )

        self.mock_mode = mock_mode
        self.response_templates = response_templates or self.DEFAULT_TEMPLATES.copy()
        self.default_latency = default_latency
        self.latency_variance = latency_variance
        self.error_config = error_config

        # 顺序响应模式的状态
        self._sequential_index = 0
        self._sequential_responses = []

        # 随机种子
        random.seed(time.time())

        # 使用统计
        self._mock_stats = {
            "total_mock_calls": 0,
            "static_responses": 0,
            "random_responses": 0,
            "template_responses": 0,
            "sequential_responses": 0,
            "injected_errors": 0,
            "total_simulated_latency": 0.0,
        }

        logger.info(f"增强的模拟LLM已初始化 - 模式: {mock_mode.value}")

    def _simulate_latency(self):
        """模拟网络延迟"""
        latency = self.default_latency + random.uniform(
            -self.latency_variance, self.latency_variance
        )
        latency = max(0.01, latency)  # 确保最小延迟
        time.sleep(latency)
        self._mock_stats["total_simulated_latency"] += latency
        return latency

    async def _async_simulate_latency(self):
        """异步模拟网络延迟"""
        latency = self.default_latency + random.uniform(
            -self.latency_variance, self.latency_variance
        )
        latency = max(0.01, latency)
        await asyncio.sleep(latency)
        self._mock_stats["total_simulated_latency"] += latency
        return latency

    def _inject_error(self):
        """注入错误（如果配置了错误注入）"""
        if not self.error_config:
            return False

        if random.random() < self.error_config.probability:
            self._mock_stats["injected_errors"] += 1
            error_type = self.error_config.error_type

            if self.error_config.delay_before_error > 0:
                time.sleep(self.error_config.delay_before_error)

            error_message = self.error_config.error_message or f"模拟错误: {error_type.value}"

            if error_type == ErrorType.TIMEOUT:
                raise TimeoutError(error_message)
            elif error_type == ErrorType.RATE_LIMIT:
                raise Exception(f"速率限制: {error_message}")
            elif error_type == ErrorType.API_ERROR:
                raise Exception(f"API错误: {error_message}")
            elif error_type == ErrorType.NETWORK_ERROR:
                raise ConnectionError(error_message)

        return False

    async def _async_inject_error(self):
        """异步注入错误"""
        if not self.error_config:
            return False

        if random.random() < self.error_config.probability:
            self._mock_stats["injected_errors"] += 1
            error_type = self.error_config.error_type

            if self.error_config.delay_before_error > 0:
                await asyncio.sleep(self.error_config.delay_before_error)

            error_message = self.error_config.error_message or f"模拟错误: {error_type.value}"

            if error_type == ErrorType.TIMEOUT:
                raise TimeoutError(error_message)
            elif error_type == ErrorType.RATE_LIMIT:
                raise Exception(f"速率限制: {error_message}")
            elif error_type == ErrorType.API_ERROR:
                raise Exception(f"API错误: {error_message}")
            elif error_type == ErrorType.NETWORK_ERROR:
                raise ConnectionError(error_message)

        return False

    def _generate_static_response(self, prompt: str) -> str:
        """生成静态响应"""
        self._mock_stats["static_responses"] += 1
        return f"这是对以下提示的静态响应：\n{prompt}\n\n响应：这是一个预定义的静态响应。"

    def _generate_random_response(self, prompt: str) -> str:
        """生成随机响应"""
        self._mock_stats["random_responses"] += 1

        responses = [
            f"我理解了你的问题：'{prompt}'。我的随机回答是：{random.randint(1, 100)}",
            f"基于你的输入，我认为答案是：{random.choice(['是', '否', '可能', '不确定'])}",
            f"这是一个有趣的提示。让我思考一下... 我的回应是：{random.choice(['好的', '明白了', '收到', '了解'])}",
            f"提示词分析完成。生成响应：模拟数据 {random.uniform(0, 1):.2f}",
            f"随机响应模式激活。输入：{prompt[:50]}... 输出：模拟结果 #{random.randint(1000, 9999)}",
        ]

        return random.choice(responses)

    def _generate_template_response(self, prompt: str) -> str:
        """生成模板响应"""
        self._mock_stats["template_responses"] += 1

        # 尝试匹配模板
        for template_name, template in self.response_templates.items():
            if template_name.lower() in prompt.lower():
                # 提取变量并填充模板
                variables = self._extract_variables(prompt, template_name)
                response = self._fill_template(template, variables)
                return response

        # 如果没有匹配的模板，使用默认模板
        default_template = self.response_templates.get("greeting", "你好！")
        return default_template

    def _generate_sequential_response(self, prompt: str) -> str:
        """生成顺序响应"""
        self._mock_stats["sequential_responses"] += 1

        if not self._sequential_responses:
            # 初始化顺序响应列表
            self._sequential_responses = [
                "这是第一个顺序响应。",
                "这是第二个顺序响应。",
                "这是第三个顺序响应。",
                "这是第四个顺序响应。",
                "这是第五个顺序响应。",
            ]

        response = self._sequential_responses[self._sequential_index]
        self._sequential_index = (self._sequential_index + 1) % len(self._sequential_responses)

        return f"顺序响应 #{self._sequential_index + 1}: {response}\n\n提示词: {prompt}"

    def _extract_variables(self, prompt: str, template_name: str) -> Dict[str, Any]:
        """从提示词中提取变量"""
        variables = {}

        if template_name == "question":
            # 提取主题和答案
            variables["topic"] = self._extract_topic(prompt)
            variables["answer"] = self._generate_answer(prompt)
        elif template_name == "summary":
            variables["summary"] = self._generate_summary(prompt)
        elif template_name == "code":
            variables["function"] = self._extract_function_name(prompt)
            variables["language"] = self._detect_language(prompt)
            variables["code"] = self._generate_mock_code(prompt)
        elif template_name == "list":
            variables["items"] = self._generate_list_items(prompt)
        elif template_name == "error":
            variables["error"] = "模拟错误"

        return variables

    def _fill_template(self, template: str, variables: Dict[str, Any]) -> str:
        """填充模板"""
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"模板变量缺失: {e}")
            # 用默认值替换缺失的变量
            for key in variables:
                template = template.replace(f"{{{key}}}", str(variables[key]))
            return template

    def _extract_topic(self, prompt: str) -> str:
        """提取主题"""
        # 简单的关键词提取
        keywords = ["什么", "如何", "为什么", "哪里", "何时", "谁"]
        for keyword in keywords:
            if keyword in prompt:
                return keyword
        return "未知主题"

    def _generate_answer(self, prompt: str) -> str:
        """生成答案"""
        answers = [
            "根据我的分析，答案是肯定的。",
            "经过计算，结果是否定的。",
            "这个问题需要更多上下文信息。",
            "答案取决于具体条件。",
            "我建议进一步研究这个问题。",
        ]
        return random.choice(answers)

    def _generate_summary(self, prompt: str) -> str:
        """生成摘要"""
        sentences = prompt.split("。")[:3]
        summary = "。".join(sentences)
        if len(summary) > 100:
            summary = summary[:100] + "..."
        return summary

    def _extract_function_name(self, prompt: str) -> str:
        """提取函数名"""
        patterns = [
            r"实现(.*?)函数",
            r"编写(.*?)代码",
            r"创建(.*?)功能",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                return match.group(1).strip()
        return "示例函数"

    def _detect_language(self, prompt: str) -> str:
        """检测编程语言"""
        languages = {
            "python": ["python", "py"],
            "javascript": ["javascript", "js"],
            "java": ["java"],
            "cpp": ["c++", "cpp"],
            "go": ["go", "golang"],
        }

        prompt_lower = prompt.lower()
        for lang, keywords in languages.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    return lang

        return "python"

    def _generate_mock_code(self, prompt: str) -> str:
        """生成模拟代码"""
        language = self._detect_language(prompt)

        code_templates = {
            "python": '''def example_function():
    """示例函数"""
    result = 42
    return result

if __name__ == "__main__":
    print(example_function())''',
            "javascript": '''function exampleFunction() {
    // 示例函数
    const result = 42;
    return result;
}

console.log(exampleFunction());''',
            "java": '''public class Example {
    public static int exampleFunction() {
        // 示例函数
        int result = 42;
        return result;
    }

    public static void main(String[] args) {
        System.out.println(exampleFunction());
    }
}''',
        }

        return code_templates.get(language, code_templates["python"])

    def _generate_list_items(self, prompt: str) -> str:
        """生成列表项"""
        items = []
        for i in range(1, 6):
            items.append(f"{i}. 项目 {i}: 模拟数据 {random.randint(1, 100)}")
        return "\n".join(items)

    def _execute_call(self, prompt: str, connection, **kwargs) -> str:
        """执行模拟LLM调用"""
        self._mock_stats["total_mock_calls"] += 1

        # 检查是否注入错误
        self._inject_error()

        # 模拟延迟
        latency = self._simulate_latency()

        # 根据模式生成响应
        if self.mock_mode == MockMode.STATIC:
            response = self._generate_static_response(prompt)
        elif self.mock_mode == MockMode.RANDOM:
            response = self._generate_random_response(prompt)
        elif self.mock_mode == MockMode.TEMPLATE:
            response = self._generate_template_response(prompt)
        elif self.mock_mode == MockMode.SEQUENTIAL:
            response = self._generate_sequential_response(prompt)
        elif self.mock_mode == MockMode.ERROR_INJECTION:
            # 错误注入模式可能已经在上面的_inject_error中抛出异常
            response = self._generate_template_response(prompt)
        else:
            response = f"默认响应: {prompt}"

        # 记录调用
        self._log_call(prompt, response, LLMCallMode.SYNC)

        return response

    async def async_call(self, prompt: str, **kwargs) -> LLMResponse:
        """异步调用实现"""
        start_time = time.time()

        try:
            # 验证提示词
            if not self._validate_prompt(prompt):
                raise ValueError("无效的提示词")

            # 检查是否注入错误
            await self._async_inject_error()

            # 模拟延迟
            latency = await self._async_simulate_latency()

            # 根据模式生成响应
            if self.mock_mode == MockMode.STATIC:
                response_content = self._generate_static_response(prompt)
            elif self.mock_mode == MockMode.RANDOM:
                response_content = self._generate_random_response(prompt)
            elif self.mock_mode == MockMode.TEMPLATE:
                response_content = self._generate_template_response(prompt)
            elif self.mock_mode == MockMode.SEQUENTIAL:
                response_content = self._generate_sequential_response(prompt)
            else:
                response_content = f"默认响应: {prompt}"

            # 计算总延迟
            total_latency = time.time() - start_time

            # 更新统计
            self._update_stats(success=True, tokens=len(response_content.split()), latency=total_latency)

            # 创建响应对象
            response = LLMResponse(
                content=response_content,
                model=self.model_name,
                tokens_used=len(response_content.split()),
                latency=total_latency,
                metadata={
                    "mode": LLMCallMode.ASYNC.value,
                    "mock_mode": self.mock_mode.value,
                    "simulated_latency": latency,
                    "timestamp": start_time,
                }
            )

            self._log_call(prompt, response_content, LLMCallMode.ASYNC)
            return response

        except Exception as e:
            # 更新统计
            self._update_stats(success=False, tokens=0, latency=time.time() - start_time)
            logger.error(f"模拟LLM异步调用失败: {e}")
            raise

    def stream_call(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式调用实现"""
        # 生成完整响应
        full_response = self._execute_call(prompt, None, **kwargs)

        # 分割成块模拟流式响应
        words = full_response.split()
        chunk_size = max(1, len(words) // 10)  # 分成大约10个块

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            yield chunk + " "

            # 模拟流式延迟
            time.sleep(0.05)

    async def async_stream_call(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """异步流式调用实现"""
        # 生成完整响应
        full_response = self._execute_call(prompt, None, **kwargs)

        # 分割成块模拟流式响应
        words = full_response.split()
        chunk_size = max(1, len(words) // 10)

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            yield chunk + " "

            # 模拟流式延迟
            await asyncio.sleep(0.05)

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = super().get_model_info()
        info.update({
            "provider": "MockLLM",
            "mock_mode": self.mock_mode.value,
            "default_latency": self.default_latency,
            "latency_variance": self.latency_variance,
            "error_injection_enabled": self.error_config is not None,
            "template_count": len(self.response_templates),
        })
        return info

    def get_mock_stats(self) -> Dict[str, Any]:
        """获取模拟统计信息"""
        stats = self._mock_stats.copy()
        if stats["total_mock_calls"] > 0:
            stats["average_simulated_latency"] = (
                stats["total_simulated_latency"] / stats["total_mock_calls"]
            )
        else:
            stats["average_simulated_latency"] = 0.0
        return stats

    def add_template(self, name: str, template: str) -> None:
        """添加响应模板"""
        self.response_templates[name] = template
        logger.info(f"已添加模板: {name}")

    def remove_template(self, name: str) -> bool:
        """移除响应模板"""
        if name in self.response_templates:
            del self.response_templates[name]
            logger.info(f"已移除模板: {name}")
            return True
        return False

    def set_mock_mode(self, mode: MockMode) -> None:
        """设置模拟模式"""
        self.mock_mode = mode
        logger.info(f"模拟模式已设置为: {mode.value}")

    def set_error_config(self, config: ErrorInjectionConfig) -> None:
        """设置错误注入配置"""
        self.error_config = config
        logger.info(f"错误注入配置已更新: {config.error_type.value}")


# 工厂函数
def create_mock_llm(
    mode: Union[str, MockMode] = "template",
    **kwargs
) -> EnhancedMockLLM:
    """
    创建模拟LLM实例

    Args:
        mode: 模拟模式（字符串或MockMode枚举）
        **kwargs: 传递给EnhancedMockLLM构造函数的参数

    Returns:
        EnhancedMockLLM实例
    """
    if isinstance(mode, str):
        try:
            mode = MockMode(mode.lower())
        except ValueError:
            logger.warning(f"未知的模拟模式: {mode}，使用默认模式")
            mode = MockMode.TEMPLATE

    return EnhancedMockLLM(mock_mode=mode, **kwargs)