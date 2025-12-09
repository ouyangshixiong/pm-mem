"""
配置管理系统

支持YAML/JSON格式配置文件，提供默认配置和用户配置合并，支持配置热重载。
"""

import os
import yaml
import json
from typing import Dict, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""

    def __init__(
        self,
        config_path: Optional[str] = None,
        default_config: Optional[Dict[str, Any]] = None,
        env_prefix: str = "PM_MEM_",
    ):
        """
        初始化配置管理器

        Args:
            config_path: 用户配置文件路径，如为None则自动查找
            default_config: 默认配置字典，如为None则使用内置默认配置
            env_prefix: 环境变量前缀
        """
        self.config_path = config_path
        self.env_prefix = env_prefix
        self.config: Dict[str, Any] = {}
        self.default_config = default_config or self._get_default_config()
        self._last_modified = 0

        # 加载配置
        self.load()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取内置默认配置"""
        # 注意：这里应该从defaults.yaml加载，但为了避免循环导入，我们硬编码关键配置
        # 实际实现中会加载defaults.yaml文件
        return {
            "llm": {
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "max_tokens": 2048,
                "temperature": 0.7,
                "timeout": 30,
                "max_retries": 3,
            },
            "memory": {
                "max_entries": 1000,
                "persistence_path": "./data/memory.json",
                "backup_dir": "./backups",
                "prune_ratio": 0.2,
            },
            "agent": {
                "max_iterations": 8,
                "retrieval_k": 5,
                "enable_persistence": True,
                "auto_save": True,
                "save_interval": 10,
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file_path": "./logs/pm-mem.log",
                "max_file_size": 10485760,
                "backup_count": 5,
            },
        }

    def load(self) -> bool:
        """
        加载配置

        Returns:
            加载是否成功
        """
        try:
            # 从默认配置开始
            self.config = self.default_config.copy()

            # 加载用户配置文件
            user_config = self._load_user_config()
            if user_config:
                self._merge_configs(self.config, user_config)

            # 加载环境变量
            self._load_from_env()

            logger.info(f"配置加载完成，用户配置文件: {self.config_path or '无'}")
            return True

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 使用默认配置
            self.config = self.default_config.copy()
            return False

    def _load_user_config(self) -> Optional[Dict[str, Any]]:
        """加载用户配置文件"""
        config_paths = []

        # 如果指定了配置文件路径
        if self.config_path:
            config_paths.append(self.config_path)

        # 自动查找常见位置的配置文件
        config_paths.extend([
            "./configs/local.yaml",
            "./configs/local.yml",
            "./configs/local.json",
            "./config.yaml",
            "./config.yml",
            "./config.json",
            "~/.config/pm-mem/config.yaml",
        ])

        for path in config_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                self.config_path = expanded_path
                self._last_modified = os.path.getmtime(expanded_path)
                return self._read_config_file(expanded_path)

        return None

    def _read_config_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        """读取配置文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if filepath.endswith('.json'):
                    return json.load(f)
                else:  # yaml/yml
                    return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败 {filepath}: {e}")
            return None

    def _merge_configs(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> None:
        """递归合并配置字典"""
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        env_vars = {
            # LLM配置
            "DEEPSEEK_API_KEY": "llm.deepseek.api_key",
            "DEEPSEEK_API_BASE": "llm.deepseek.api_base",
            "LLM_PROVIDER": "llm.provider",
            "LLM_MODEL_NAME": "llm.model_name",
            "LLM_MAX_TOKENS": "llm.max_tokens",
            "LLM_TEMPERATURE": "llm.temperature",
            "LLM_TIMEOUT": "llm.timeout",
            "LLM_MAX_RETRIES": "llm.max_retries",

            # 记忆库配置
            "MEMORY_MAX_ENTRIES": "memory.max_entries",
            "MEMORY_PERSISTENCE_PATH": "memory.persistence_path",
            "MEMORY_BACKUP_DIR": "memory.backup_dir",
            "MEMORY_PRUNE_RATIO": "memory.prune_ratio",

            # Agent配置
            "AGENT_MAX_ITERATIONS": "agent.max_iterations",
            "AGENT_RETRIEVAL_K": "agent.retrieval_k",
            "AGENT_ENABLE_PERSISTENCE": "agent.enable_persistence",
            "AGENT_AUTO_SAVE": "agent.auto_save",
            "AGENT_SAVE_INTERVAL": "agent.save_interval",

            # 日志配置
            "LOG_LEVEL": "logging.level",
            "LOG_FILE_PATH": "logging.file_path",
            "LOG_MAX_FILE_SIZE": "logging.max_file_size",
            "LOG_BACKUP_COUNT": "logging.backup_count",
        }

        for env_key, config_path in env_vars.items():
            value = os.getenv(f"{self.env_prefix}{env_key}", os.getenv(env_key))
            if value is not None:
                self._set_nested_config(self.config, config_path, value)

    def _set_nested_config(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """设置嵌套配置值"""
        keys = path.split('.')
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # 类型转换
        last_key = keys[-1]
        if isinstance(current.get(last_key), bool):
            value = str(value).lower() in ('true', '1', 'yes', 'y')
        elif isinstance(current.get(last_key), int):
            try:
                value = int(value)
            except ValueError:
                pass
        elif isinstance(current.get(last_key), float):
            try:
                value = float(value)
            except ValueError:
                pass

        current[last_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔（如 "llm.model_name"）
            default: 默认值

        Returns:
            配置值
        """
        try:
            keys = key.split('.')
            current = self.config
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键，支持点号分隔
            value: 配置值
        """
        self._set_nested_config(self.config, key, value)
        logger.debug(f"设置配置 {key} = {value}")

    def save(self, filepath: Optional[str] = None) -> bool:
        """
        保存配置到文件

        Args:
            filepath: 文件路径，如为None则使用当前配置文件路径

        Returns:
            保存是否成功
        """
        try:
            path = filepath or self.config_path
            if not path:
                logger.error("未指定配置文件路径")
                return False

            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                if path.endswith('.json'):
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"配置已保存到: {path}")
            return True

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def reload_if_changed(self) -> bool:
        """
        如果配置文件有修改则重新加载

        Returns:
            是否重新加载了配置
        """
        if not self.config_path or not os.path.exists(self.config_path):
            return False

        current_modified = os.path.getmtime(self.config_path)
        if current_modified > self._last_modified:
            logger.info(f"配置文件已修改，重新加载: {self.config_path}")
            self.load()
            return True

        return False

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()

    def validate(self) -> bool:
        """验证配置完整性"""
        required_keys = [
            "llm.provider",
            "memory.max_entries",
            "agent.max_iterations",
        ]

        for key in required_keys:
            if self.get(key) is None:
                logger.error(f"缺少必需配置: {key}")
                return False

        return True


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(
    config_path: Optional[str] = None,
    reload: bool = False,
) -> ConfigManager:
    """
    获取全局配置管理器实例

    Args:
        config_path: 配置文件路径
        reload: 是否重新加载

    Returns:
        配置管理器实例
    """
    global _config_manager

    if _config_manager is None or reload:
        _config_manager = ConfigManager(config_path)

    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """
    获取配置值（快捷函数）

    Args:
        key: 配置键
        default: 默认值

    Returns:
        配置值
    """
    return get_config_manager().get(key, default)