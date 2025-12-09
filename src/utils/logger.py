"""
日志与监控模块

结构化日志记录（DEBUG/INFO/WARNING/ERROR），关键操作审计日志，性能指标收集，日志文件轮转管理。
"""

import os
import sys
import logging
import logging.handlers
from typing import Optional, Dict, Any
from datetime import datetime
import time

from ..config.config_manager import get_config


def setup_logger(
    name: str = "pm-mem",
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别，如为None则从配置读取
        log_file: 日志文件路径，如为None则从配置读取
        max_file_size: 日志文件最大大小（字节）
        backup_count: 备份文件数量

    Returns:
        配置好的日志记录器
    """
    # 获取配置
    config = get_config("logging", {})
    if level is None:
        level = config.get("level", "INFO")
    if log_file is None:
        log_file = config.get("file_path", "./logs/pm-mem.log")
    if "max_file_size" in config:
        max_file_size = config["max_file_size"]
    if "backup_count" in config:
        backup_count = config["backup_count"]

    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # 移除现有处理器，避免重复
    logger.handlers.clear()

    # 日志格式
    log_format = config.get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    formatter = logging.Formatter(log_format)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, level.upper()))
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # 使用RotatingFileHandler实现日志轮转
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8',
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(getattr(logging, level.upper()))
            logger.addHandler(file_handler)

            logger.debug(f"日志文件处理器已设置: {log_file} (最大大小: {max_file_size} bytes, 备份数: {backup_count})")
        except Exception as e:
            logger.error(f"设置日志文件处理器失败: {e}")

    # 不传播到根日志记录器
    logger.propagate = False

    return logger


class AuditLogger:
    """审计日志记录器，用于记录关键操作"""

    def __init__(self, logger_name: str = "pm-mem.audit"):
        """
        初始化审计日志记录器

        Args:
            logger_name: 审计日志记录器名称
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.propagate = False

        # 如果还没有处理器，添加一个
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - AUDIT - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_operation(
        self,
        operation: str,
        user: str = "system",
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> None:
        """
        记录操作审计日志

        Args:
            operation: 操作名称
            user: 执行用户
            details: 操作详情
            status: 操作状态（success/failure）
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "user": user,
            "status": status,
            "details": details or {},
        }

        if status == "success":
            self.logger.info(f"操作审计: {log_entry}")
        else:
            self.logger.error(f"操作审计: {log_entry}")

    def log_memory_operation(
        self,
        operation: str,
        entry_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        记录记忆库操作审计日志

        Args:
            operation: 操作类型（add/delete/merge/relabel/retrieve）
            entry_id: 记忆条目ID
            details: 操作详情
        """
        self.log_operation(
            operation=f"memory.{operation}",
            user="system",
            details={
                "entry_id": entry_id,
                **(details or {})
            },
            status="success",
        )

    def log_agent_operation(
        self,
        task_id: str,
        operation: str,
        iteration: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        记录Agent操作审计日志

        Args:
            task_id: 任务ID
            operation: 操作类型（think/refine/act）
            iteration: 迭代次数
            details: 操作详情
        """
        self.log_operation(
            operation=f"agent.{operation}",
            user="system",
            details={
                "task_id": task_id,
                "iteration": iteration,
                **(details or {})
            },
            status="success",
        )


class PerformanceMetrics:
    """性能指标收集器"""

    def __init__(self):
        """初始化性能指标收集器"""
        self.metrics: Dict[str, Any] = {
            "start_time": time.time(),
            "operations": {},
            "counters": {},
            "timers": {},
        }
        self.logger = logging.getLogger("pm-mem.metrics")

    def start_timer(self, operation: str) -> None:
        """
        开始计时

        Args:
            operation: 操作名称
        """
        self.metrics["timers"][operation] = {
            "start": time.time(),
            "end": None,
            "duration": None,
        }

    def stop_timer(self, operation: str) -> float:
        """
        停止计时并返回持续时间

        Args:
            operation: 操作名称

        Returns:
            持续时间（秒）
        """
        if operation not in self.metrics["timers"]:
            self.logger.warning(f"未找到计时器: {operation}")
            return 0.0

        timer = self.metrics["timers"][operation]
        timer["end"] = time.time()
        duration = timer["end"] - timer["start"]
        timer["duration"] = duration

        return duration

    def increment_counter(self, name: str, value: int = 1) -> None:
        """
        递增计数器

        Args:
            name: 计数器名称
            value: 递增值
        """
        self.metrics["counters"][name] = self.metrics["counters"].get(name, 0) + value

    def record_operation(
        self,
        name: str,
        duration: float,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        记录操作指标

        Args:
            name: 操作名称
            duration: 持续时间（秒）
            status: 操作状态
            details: 操作详情
        """
        if name not in self.metrics["operations"]:
            self.metrics["operations"][name] = {
                "count": 0,
                "total_duration": 0.0,
                "success_count": 0,
                "failure_count": 0,
                "avg_duration": 0.0,
                "min_duration": float('inf'),
                "max_duration": 0.0,
                "last_operation": None,
            }

        op_metrics = self.metrics["operations"][name]
        op_metrics["count"] += 1
        op_metrics["total_duration"] += duration
        op_metrics["avg_duration"] = op_metrics["total_duration"] / op_metrics["count"]

        if duration < op_metrics["min_duration"]:
            op_metrics["min_duration"] = duration
        if duration > op_metrics["max_duration"]:
            op_metrics["max_duration"] = duration

        if status == "success":
            op_metrics["success_count"] += 1
        else:
            op_metrics["failure_count"] += 1

        op_metrics["last_operation"] = {
            "timestamp": time.time(),
            "duration": duration,
            "status": status,
            "details": details,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """获取所有性能指标"""
        uptime = time.time() - self.metrics["start_time"]
        metrics = self.metrics.copy()
        metrics["uptime"] = uptime
        metrics["current_time"] = time.time()
        return metrics

    def log_metrics(self) -> None:
        """记录性能指标到日志"""
        metrics = self.get_metrics()
        self.logger.info(f"性能指标: {metrics}")

    def save_metrics(self, filepath: str) -> bool:
        """
        保存性能指标到文件

        Args:
            filepath: 文件路径

        Returns:
            保存是否成功
        """
        try:
            metrics = self.get_metrics()
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)
            self.logger.debug(f"性能指标已保存到: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"保存性能指标失败: {e}")
            return False

    def reset(self) -> None:
        """重置性能指标"""
        self.metrics = {
            "start_time": time.time(),
            "operations": {},
            "counters": {},
            "timers": {},
        }


# 全局日志记录器实例
_audit_logger: Optional[AuditLogger] = None
_performance_metrics: Optional[PerformanceMetrics] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_performance_metrics() -> PerformanceMetrics:
    """获取全局性能指标收集器"""
    global _performance_metrics
    if _performance_metrics is None:
        _performance_metrics = PerformanceMetrics()
    return _performance_metrics