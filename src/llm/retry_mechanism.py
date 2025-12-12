"""
LLM重试机制实现

支持指数退避、自适应重试、熔断器模式等高级重试策略。
"""

import time
import asyncio
import random
from typing import Callable, Any, Optional, Dict, Union, Type
import logging
from dataclasses import dataclass
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """重试策略"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    FIXED_INTERVAL = "fixed_interval"            # 固定间隔
    RANDOM_BACKOFF = "random_backoff"            # 随机退避
    ADAPTIVE = "adaptive"                        # 自适应重试


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态，请求通过
    OPEN = "open"          # 熔断状态，请求被拒绝
    HALF_OPEN = "half_open"  # 半开状态，允许部分请求通过


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 30.0  # 最大延迟（秒）
    jitter: bool = True      # 是否添加随机抖动
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retry_on_exceptions: tuple = (Exception,)  # 需要重试的异常类型


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5        # 失败阈值
    reset_timeout: float = 60.0       # 重置超时（秒）
    half_open_max_requests: int = 3   # 半开状态最大请求数
    failure_window: float = 60.0      # 失败统计窗口（秒）


class RetryManager:
    """重试管理器"""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._stats = {
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
            "total_retries": 0,
            "total_delay": 0.0,
        }

    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if attempt <= 0:
            return 0.0

        base_delay = self.config.base_delay
        max_delay = self.config.max_delay

        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        elif self.config.strategy == RetryStrategy.FIXED_INTERVAL:
            delay = base_delay
        elif self.config.strategy == RetryStrategy.RANDOM_BACKOFF:
            delay = random.uniform(base_delay, min(base_delay * 3, max_delay))
        elif self.config.strategy == RetryStrategy.ADAPTIVE:
            # 自适应策略：基于历史成功率调整延迟
            success_rate = self._get_success_rate()
            if success_rate < 0.5:
                delay = min(base_delay * 4, max_delay)  # 成功率低时增加延迟
            else:
                delay = base_delay
        else:
            delay = base_delay

        # 添加抖动
        if self.config.jitter:
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor

        return min(delay, max_delay)

    def _get_success_rate(self) -> float:
        """获取历史成功率"""
        if self._stats["total_attempts"] == 0:
            return 1.0
        return self._stats["successful_attempts"] / self._stats["total_attempts"]

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.config.max_retries:
            return False

        # 检查异常类型是否在重试列表中
        if not isinstance(exception, self.config.retry_on_exceptions):
            return False

        # 对于某些特定异常，不重试
        if hasattr(exception, 'status_code'):
            status_code = getattr(exception, 'status_code')
            if status_code and 400 <= status_code < 500:
                # 客户端错误（4xx）通常不重试
                return False

        return True

    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """同步重试装饰器实现"""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            self._stats["total_attempts"] += 1

            try:
                result = func(*args, **kwargs)
                self._stats["successful_attempts"] += 1
                return result

            except Exception as e:
                last_exception = e
                self._stats["failed_attempts"] += 1

                if not self.should_retry(e, attempt):
                    break

                # 计算延迟并等待
                delay = self.calculate_delay(attempt + 1)
                if delay > 0:
                    self._stats["total_delay"] += delay
                    self._stats["total_retries"] += 1
                    logger.warning(
                        f"重试 {func.__name__} 第 {attempt + 1} 次，"
                        f"延迟 {delay:.2f} 秒: {e}"
                    )
                    time.sleep(delay)

        # 所有重试都失败
        logger.error(
            f"{func.__name__} 重试 {self.config.max_retries} 次后失败: {last_exception}"
        )
        raise last_exception

    async def async_retry(self, func: Callable, *args, **kwargs) -> Any:
        """异步重试装饰器实现"""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            self._stats["total_attempts"] += 1

            try:
                result = await func(*args, **kwargs)
                self._stats["successful_attempts"] += 1
                return result

            except Exception as e:
                last_exception = e
                self._stats["failed_attempts"] += 1

                if not self.should_retry(e, attempt):
                    break

                # 计算延迟并等待
                delay = self.calculate_delay(attempt + 1)
                if delay > 0:
                    self._stats["total_delay"] += delay
                    self._stats["total_retries"] += 1
                    logger.warning(
                        f"异步重试 {func.__name__} 第 {attempt + 1} 次，"
                        f"延迟 {delay:.2f} 秒: {e}"
                    )
                    await asyncio.sleep(delay)

        # 所有重试都失败
        logger.error(
            f"{func.__name__} 异步重试 {self.config.max_retries} 次后失败: {last_exception}"
        )
        raise last_exception

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["total_attempts"] > 0:
            stats["success_rate"] = stats["successful_attempts"] / stats["total_attempts"]
            stats["average_delay"] = stats["total_delay"] / stats["total_retries"] if stats["total_retries"] > 0 else 0.0
        else:
            stats["success_rate"] = 0.0
            stats["average_delay"] = 0.0
        return stats


class CircuitBreaker:
    """熔断器模式实现"""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.half_open_attempts = 0
        self._lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

    def _reset(self):
        """重置熔断器"""
        self.failure_count = 0
        self.success_count = 0
        self.half_open_attempts = 0
        self.state = CircuitBreakerState.CLOSED
        logger.info("熔断器已重置")

    def record_failure(self):
        """记录失败"""
        current_time = time.time()

        # 检查失败窗口
        if current_time - self.last_failure_time > self.config.failure_window:
            self.failure_count = 0

        self.failure_count += 1
        self.last_failure_time = current_time

        # 检查是否达到失败阈值
        if self.failure_count >= self.config.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                self.state = CircuitBreakerState.OPEN
                self._schedule_reset()
                logger.warning(f"熔断器已打开，失败次数: {self.failure_count}")

    def record_success(self):
        """记录成功"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            self.half_open_attempts += 1

            # 检查是否可以关闭熔断器
            if self.success_count >= self.config.half_open_max_requests:
                self._reset()
        elif self.state == CircuitBreakerState.CLOSED:
            self.success_count = min(self.success_count + 1, 100)  # 限制最大值

    def _schedule_reset(self):
        """调度重置"""
        def reset_circuit():
            time.sleep(self.config.reset_timeout)
            if self.state == CircuitBreakerState.OPEN:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_attempts = 0
                logger.info("熔断器进入半开状态")

        import threading
        threading.Thread(target=reset_circuit, daemon=True).start()

    def is_request_allowed(self) -> bool:
        """检查是否允许请求"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # 半开状态下允许部分请求
            if self.half_open_attempts < self.config.half_open_max_requests:
                return True
            return False
        return False

    def __call__(self, func: Callable):
        """熔断器装饰器"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.is_request_allowed():
                raise Exception("熔断器已打开，请求被拒绝")

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        return wrapper

    async def async_call(self, func: Callable):
        """异步熔断器装饰器"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.is_request_allowed():
                raise Exception("熔断器已打开，请求被拒绝")

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        return wrapper


# 装饰器函数
def retry(config: Optional[RetryConfig] = None):
    """重试装饰器"""
    manager = RetryManager(config)

    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return manager.retry(func, *args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await manager.async_retry(func, *args, **kwargs)

        # 根据函数类型返回合适的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def circuit_breaker(config: Optional[CircuitBreakerConfig] = None):
    """熔断器装饰器"""
    breaker = CircuitBreaker(config)

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            return breaker.async_call(func)
        return breaker(func)

    return decorator


# 组合装饰器：重试 + 熔断器
def resilient_call(
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
):
    """弹性调用装饰器（重试 + 熔断器）"""
    retry_decorator = retry(retry_config)
    breaker_decorator = circuit_breaker(circuit_breaker_config)

    def decorator(func: Callable):
        # 先应用熔断器，再应用重试
        wrapped = retry_decorator(breaker_decorator(func))
        return wrapped

    return decorator


# 全局重试管理器实例
_default_retry_manager = RetryManager()


def retry_call(func: Callable, *args, **kwargs) -> Any:
    """快捷重试调用函数"""
    return _default_retry_manager.retry(func, *args, **kwargs)


async def async_retry_call(func: Callable, *args, **kwargs) -> Any:
    """快捷异步重试调用函数"""
    return await _default_retry_manager.async_retry(func, *args, **kwargs)