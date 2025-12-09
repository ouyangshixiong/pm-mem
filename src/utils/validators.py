"""
验证器模块

提供通用的验证函数，用于配置、输入、命令等的验证。
"""

import re
import os
from typing import Any, Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def validate_config(config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    验证配置字典

    Args:
        config: 配置字典

    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 检查必需配置项
        required_keys = [
            "llm.provider",
            "memory.max_entries",
            "agent.max_iterations",
        ]

        for key in required_keys:
            if get_nested_value(config, key) is None:
                return False, f"缺少必需配置项: {key}"

        # 验证LLM配置
        llm_config = config.get("llm", {})
        if not isinstance(llm_config, dict):
            return False, "llm配置必须是字典"

        provider = llm_config.get("provider", "").lower()
        if provider not in ["deepseek", "mock"]:
            return False, f"不支持的LLM提供商: {provider}"

        if provider == "deepseek" and not llm_config.get("deepseek", {}).get("api_key"):
            # 检查环境变量
            if not os.getenv("DEEPSEEK_API_KEY"):
                return False, "DeepSeek API密钥未配置"

        # 验证记忆库配置
        memory_config = config.get("memory", {})
        max_entries = memory_config.get("max_entries")
        if not isinstance(max_entries, int) or max_entries <= 0:
            return False, "memory.max_entries必须是正整数"

        prune_ratio = memory_config.get("prune_ratio", 0.2)
        if not isinstance(prune_ratio, float) or prune_ratio <= 0 or prune_ratio > 1:
            return False, "memory.prune_ratio必须是0到1之间的浮点数"

        # 验证Agent配置
        agent_config = config.get("agent", {})
        max_iterations = agent_config.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            return False, "agent.max_iterations必须是正整数"

        retrieval_k = agent_config.get("retrieval_k", 5)
        if not isinstance(retrieval_k, int) or retrieval_k <= 0:
            return False, "agent.retrieval_k必须是正整数"

        return True, "配置有效"

    except Exception as e:
        return False, f"验证配置时发生错误: {e}"


def validate_task_input(task_input: str) -> Tuple[bool, str]:
    """
    验证任务输入

    Args:
        task_input: 任务输入字符串

    Returns:
        (是否有效, 错误信息)
    """
    if not task_input or not task_input.strip():
        return False, "任务输入不能为空"

    if len(task_input.strip()) > 10000:
        return False, "任务输入过长（最大10000字符）"

    # 检查是否有危险字符（基本防护）
    dangerous_patterns = [
        r"<script.*?>.*?</script>",
        r"on\w+\s*=",
        r"javascript:",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, task_input, re.IGNORECASE):
            return False, "任务输入包含潜在危险内容"

    return True, "任务输入有效"


def validate_memory_entry_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    验证记忆条目数据

    Args:
        data: 记忆条目数据字典

    Returns:
        (是否有效, 错误信息)
    """
    required_fields = ["x", "y", "feedback"]
    for field in required_fields:
        if field not in data:
            return False, f"缺少必需字段: {field}"

        if not isinstance(data[field], str):
            return False, f"字段 {field} 必须是字符串"

        if not data[field].strip():
            return False, f"字段 {field} 不能为空"

    # 验证时间戳（如果存在）
    if "timestamp" in data:
        try:
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False, "timestamp格式无效，应为ISO格式"

    # 验证标签（如果存在）
    if "tag" in data and not isinstance(data["tag"], str):
        return False, "tag必须是字符串"

    return True, "记忆条目数据有效"


def validate_refine_command(cmd: str) -> Tuple[bool, str]:
    """
    验证Refine命令语法

    Args:
        cmd: Refine命令字符串

    Returns:
        (是否有效, 错误信息)
    """
    if not cmd or not cmd.strip():
        return True, "空命令"

    normalized = cmd.strip().lower()
    segments = [s.strip() for s in normalized.split(";") if s.strip()]

    for i, segment in enumerate(segments):
        if segment.startswith("delete"):
            if not re.match(r"delete\s+[\d\s,]+$", segment):
                return False, f"第{i+1}段DELETE命令格式错误: {segment}"

            # 验证索引是否有效
            indices_match = re.search(r"delete\s+([\d\s,]+)", segment)
            if indices_match:
                indices_str = indices_match.group(1)
                indices = [idx.strip() for idx in indices_str.split(",")]
                for idx in indices:
                    if idx and not idx.isdigit():
                        return False, f"第{i+1}段DELETE命令包含无效索引: {idx}"

        elif segment.startswith("add{"):
            if not re.match(r"add\{[^}]+\}$", segment):
                return False, f"第{i+1}段ADD命令格式错误: {segment}"

            # 验证内容不为空
            content_match = re.search(r"add\{([^}]+)\}", segment)
            if not content_match or not content_match.group(1).strip():
                return False, f"第{i+1}段ADD命令内容为空"

        elif segment.startswith("merge"):
            if not re.match(r"merge\s*\d+\s*&\s*\d+$", segment):
                return False, f"第{i+1}段MERGE命令格式错误: {segment}"

            # 验证两个索引不同
            indices_match = re.search(r"merge\s*(\d+)\s*&\s*(\d+)", segment)
            if indices_match:
                idx1, idx2 = indices_match.groups()
                if idx1 == idx2:
                    return False, f"第{i+1}段MERGE命令索引相同: {idx1}"

        elif segment.startswith("relabel"):
            if not re.match(r"relabel\s+\d+\s+.+$", segment):
                return False, f"第{i+1}段RELABEL命令格式错误: {segment}"

            # 验证新标签不为空
            label_match = re.search(r"relabel\s+\d+\s+(.+)", segment)
            if not label_match or not label_match.group(1).strip():
                return False, f"第{i+1}段RELABEL命令标签为空"

        else:
            return False, f"第{i+1}段包含未知命令: {segment}"

    return True, "命令格式合法"


def validate_file_path(filepath: str, check_writable: bool = False) -> Tuple[bool, str]:
    """
    验证文件路径

    Args:
        filepath: 文件路径
        check_writable: 是否检查可写性

    Returns:
        (是否有效, 错误信息)
    """
    if not filepath or not filepath.strip():
        return False, "文件路径不能为空"

    # 检查路径是否合法
    try:
        # 标准化路径
        normalized = os.path.normpath(filepath)
        if normalized != filepath:
            logger.warning(f"文件路径已标准化: {filepath} -> {normalized}")

        # 检查目录部分是否可访问
        dir_path = os.path.dirname(normalized)
        if dir_path and not os.path.exists(dir_path):
            # 尝试创建目录（如果检查可写性）
            if check_writable:
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except OSError:
                    return False, f"无法创建目录: {dir_path}"
            else:
                return False, f"目录不存在: {dir_path}"

        # 检查可写性（如果需要）
        if check_writable and os.path.exists(normalized):
            if not os.access(normalized, os.W_OK):
                return False, f"文件不可写: {normalized}"

        return True, "文件路径有效"

    except Exception as e:
        return False, f"文件路径验证失败: {e}"


def get_nested_value(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    获取嵌套字典中的值

    Args:
        data: 字典
        key: 点号分隔的键（如 "llm.model_name"）
        default: 默认值

    Returns:
        键对应的值
    """
    keys = key.split('.')
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current


def set_nested_value(data: Dict[str, Any], key: str, value: Any) -> bool:
    """
    设置嵌套字典中的值

    Args:
        data: 字典
        key: 点号分隔的键
        value: 要设置的值

    Returns:
        是否设置成功
    """
    keys = key.split('.')
    current = data
    for i, k in enumerate(keys[:-1]):
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]

    current[keys[-1]] = value
    return True


def is_valid_uuid(uuid_str: str) -> bool:
    """
    验证UUID格式

    Args:
        uuid_str: UUID字符串

    Returns:
        是否为有效的UUID
    """
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_str))


def validate_api_key(api_key: str) -> Tuple[bool, str]:
    """
    验证API密钥格式

    Args:
        api_key: API密钥字符串

    Returns:
        (是否有效, 错误信息)
    """
    if not api_key or not api_key.strip():
        return False, "API密钥不能为空"

    if len(api_key.strip()) < 10:
        return False, "API密钥过短"

    # 基本格式检查（通常包含字母、数字、符号）
    if not re.match(r'^[A-Za-z0-9_\-\.]+$', api_key):
        return False, "API密钥包含无效字符"

    return True, "API密钥格式有效"