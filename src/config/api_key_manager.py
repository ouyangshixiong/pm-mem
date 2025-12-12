"""
API密钥安全管理模块

支持API密钥的加密存储、多环境配置、密钥轮换和自动刷新等功能。
"""

import os
import json
import base64
import hashlib
import time
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class KeyStorageMethod(Enum):
    """密钥存储方法"""
    ENCRYPTED_FILE = "encrypted_file"  # 加密文件存储
    ENVIRONMENT = "environment"        # 环境变量
    KEYCHAIN = "keychain"              # 系统密钥链（未来支持）


class KeyStatus(Enum):
    """密钥状态"""
    ACTIVE = "active"          # 活跃可用
    EXPIRED = "expired"        # 已过期
    REVOKED = "revoked"        # 已撤销
    PENDING_REFRESH = "pending_refresh"  # 待刷新


@dataclass
class APIKeyInfo:
    """API密钥信息"""
    key_id: str
    provider: str
    key_value: str
    environment: str
    status: KeyStatus
    created_at: float
    expires_at: Optional[float]
    last_used: Optional[float]
    usage_count: int
    metadata: Dict[str, Any]


class APIKeyManager:
    """API密钥管理器"""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        encryption_key: Optional[str] = None,
        default_environment: str = "development",
    ):
        """
        初始化API密钥管理器

        Args:
            storage_path: 密钥存储文件路径
            encryption_key: 加密密钥，如为None则从环境变量读取
            default_environment: 默认环境
        """
        self.storage_path = storage_path or os.path.expanduser("~/.pm-mem/keys.enc")
        self.encryption_key = encryption_key or os.getenv("PM_MEM_ENCRYPTION_KEY")
        self.default_environment = default_environment

        # 确保存储目录存在
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        # 密钥缓存
        self._keys_cache: Dict[str, APIKeyInfo] = {}
        self._load_keys()

    def _simple_encrypt(self, data: str) -> str:
        """简单加密（实际生产环境应使用更安全的加密方法）"""
        if not self.encryption_key:
            return data  # 无加密密钥时返回明文

        # 使用base64和简单异或加密（仅用于演示）
        key_bytes = self.encryption_key.encode()
        data_bytes = data.encode()

        # 简单异或加密
        encrypted = bytearray()
        for i, byte in enumerate(data_bytes):
            key_byte = key_bytes[i % len(key_bytes)]
            encrypted.append(byte ^ key_byte)

        return base64.b64encode(encrypted).decode()

    def _simple_decrypt(self, encrypted_data: str) -> str:
        """简单解密，错误密钥时抛出ValueError异常"""
        if not self.encryption_key:
            return encrypted_data  # 无加密密钥时返回原数据

        try:
            # 验证输入数据
            if not encrypted_data or not isinstance(encrypted_data, str):
                raise ValueError("加密数据为空或类型错误")

            # 验证base64格式
            try:
                encrypted_bytes = base64.b64decode(encrypted_data)
            except Exception as e:
                raise ValueError(f"Base64解码失败: {e}")

            key_bytes = self.encryption_key.encode()

            # 简单异或解密
            decrypted = bytearray()
            for i, byte in enumerate(encrypted_bytes):
                key_byte = key_bytes[i % len(key_bytes)]
                decrypted.append(byte ^ key_byte)

            result = decrypted.decode()

            # 验证解密结果是否为有效的JSON格式
            try:
                json.loads(result)
            except json.JSONDecodeError:
                raise ValueError("解密结果不是有效的JSON格式，可能是错误的加密密钥")

            return result

        except ValueError as e:
            # 重新抛出ValueError
            raise
        except Exception as e:
            raise ValueError(f"解密失败: {e}")

    def _load_keys(self) -> None:
        """从存储文件加载密钥"""
        if not os.path.exists(self.storage_path):
            logger.info(f"密钥存储文件不存在，创建新文件: {self.storage_path}")
            self._keys_cache = {}
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()

            if not encrypted_data:
                self._keys_cache = {}
                return

            # 解密数据
            try:
                json_data = self._simple_decrypt(encrypted_data)
                keys_data = json.loads(json_data)
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"解密或解析失败: {e}")
                self._keys_cache = {}
                return

            # 转换为APIKeyInfo对象
            self._keys_cache = {}
            for key_id, key_data in keys_data.items():
                try:
                    # 处理空值
                    expires_at = key_data.get("expires_at")
                    last_used = key_data.get("last_used")

                    key_info = APIKeyInfo(
                        key_id=key_id,
                        provider=key_data.get("provider", "unknown"),
                        key_value=key_data["key_value"],
                        environment=key_data.get("environment", self.default_environment),
                        status=KeyStatus(key_data.get("status", "active")),
                        created_at=key_data.get("created_at", time.time()),
                        expires_at=float(expires_at) if expires_at is not None else None,
                        last_used=float(last_used) if last_used is not None else None,
                        usage_count=key_data.get("usage_count", 0),
                        metadata=key_data.get("metadata", {})
                    )
                    self._keys_cache[key_id] = key_info
                except Exception as e:
                    logger.error(f"加载密钥 {key_id} 失败: {e}")

            logger.info(f"已加载 {len(self._keys_cache)} 个API密钥")

        except Exception as e:
            logger.error(f"加载密钥存储文件失败: {e}")
            self._keys_cache = {}

    def _save_keys(self) -> bool:
        """保存密钥到存储文件"""
        try:
            # 转换为可序列化的字典
            keys_data = {}
            for key_id, key_info in self._keys_cache.items():
                keys_data[key_id] = {
                    "provider": key_info.provider,
                    "key_value": key_info.key_value,
                    "environment": key_info.environment,
                    "status": key_info.status.value,
                    "created_at": key_info.created_at,
                    "expires_at": key_info.expires_at,
                    "last_used": key_info.last_used,
                    "usage_count": key_info.usage_count,
                    "metadata": key_info.metadata
                }

            # 加密数据
            json_data = json.dumps(keys_data, ensure_ascii=False)
            encrypted_data = self._simple_encrypt(json_data)

            # 写入文件
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)

            logger.debug(f"已保存 {len(self._keys_cache)} 个API密钥到 {self.storage_path}")
            return True

        except Exception as e:
            logger.error(f"保存密钥失败: {e}")
            return False

    def _generate_key_id(self, provider: str, environment: str) -> str:
        """生成唯一的密钥ID"""
        timestamp = int(time.time() * 1000)
        hash_input = f"{provider}_{environment}_{timestamp}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{provider}_{environment}_{hash_value}"

    def add_key(
        self,
        provider: str,
        key_value: str,
        environment: Optional[str] = None,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        添加API密钥

        Args:
            provider: 服务提供商（如 "deepseek", "openai"）
            key_value: API密钥值
            environment: 环境（如 "development", "production"）
            expires_in: 过期时间（秒），None表示永不过期
            metadata: 额外元数据

        Returns:
            密钥ID
        """
        env = environment or self.default_environment
        key_id = self._generate_key_id(provider, env)

        # 检查是否已存在相同提供者和环境的活跃密钥
        existing_keys = self.get_keys(provider=provider, environment=env, status=KeyStatus.ACTIVE)
        if existing_keys:
            logger.warning(f"已存在 {provider} 在 {env} 环境的活跃密钥")

        # 创建密钥信息
        created_at = time.time()
        expires_at = created_at + expires_in if expires_in else None

        key_info = APIKeyInfo(
            key_id=key_id,
            provider=provider,
            key_value=key_value,
            environment=env,
            status=KeyStatus.ACTIVE,
            created_at=created_at,
            expires_at=expires_at,
            last_used=None,
            usage_count=0,
            metadata=metadata or {}
        )

        # 保存到缓存
        self._keys_cache[key_id] = key_info

        # 持久化存储
        self._save_keys()

        logger.info(f"已添加API密钥: {key_id}")
        return key_id

    def get_key(self, key_id: str, update_usage: bool = True, check_status: bool = None) -> Optional[APIKeyInfo]:
        """
        获取API密钥

        Args:
            key_id: 密钥ID
            update_usage: 是否更新使用统计
            check_status: 是否检查密钥状态（如为None，则当update_usage=True时检查，否则不检查）

        Returns:
            APIKeyInfo对象，如不存在返回None
        """
        if key_id not in self._keys_cache:
            return None

        key_info = self._keys_cache[key_id]

        # 检查key_info是否为None
        if key_info is None:
            logger.error(f"密钥 {key_id} 存在但值为None")
            return None

        # 确定是否检查状态
        if check_status is None:
            check_status = update_usage  # 默认：更新使用时检查状态，不更新使用时返回所有状态

        # 检查密钥状态（如果要求检查）
        if check_status and key_info.status != KeyStatus.ACTIVE:
            logger.warning(f"密钥 {key_id} 状态为 {key_info.status.value}")
            return None

        # 检查是否过期
        if key_info.expires_at and time.time() > key_info.expires_at:
            logger.warning(f"密钥 {key_id} 已过期")
            key_info.status = KeyStatus.EXPIRED
            self._save_keys()
            if check_status:
                return None

        # 更新使用统计
        if update_usage:
            key_info.last_used = time.time()
            key_info.usage_count += 1
            self._save_keys()

        return key_info

    def get_keys(
        self,
        provider: Optional[str] = None,
        environment: Optional[str] = None,
        status: Optional[KeyStatus] = None,
    ) -> List[APIKeyInfo]:
        """
        获取符合条件的API密钥列表

        Args:
            provider: 服务提供商
            environment: 环境
            status: 密钥状态

        Returns:
            APIKeyInfo列表
        """
        filtered_keys = []

        for key_info in self._keys_cache.values():
            # 检查key_info是否为None
            if key_info is None:
                continue

            # 过滤条件
            if provider and key_info.provider != provider:
                continue
            if environment and key_info.environment != environment:
                continue
            if status and key_info.status != status:
                continue

            filtered_keys.append(key_info)

        return filtered_keys

    def update_key_status(self, key_id: str, status: KeyStatus) -> bool:
        """
        更新密钥状态

        Args:
            key_id: 密钥ID
            status: 新状态

        Returns:
            更新是否成功
        """
        if key_id not in self._keys_cache:
            logger.error(f"密钥 {key_id} 不存在")
            return False

        key_info = self._keys_cache[key_id]
        if key_info is None:
            logger.error(f"密钥 {key_id} 存在但值为None")
            return False

        old_status = key_info.status
        key_info.status = status

        if self._save_keys():
            logger.info(f"密钥 {key_id} 状态已从 {old_status.value} 更新为 {status.value}")
            return True
        else:
            return False

    def delete_key(self, key_id: str) -> bool:
        """
        删除API密钥

        Args:
            key_id: 密钥ID

        Returns:
            删除是否成功
        """
        if key_id not in self._keys_cache:
            logger.error(f"密钥 {key_id} 不存在")
            return False

        del self._keys_cache[key_id]

        if self._save_keys():
            logger.info(f"已删除API密钥: {key_id}")
            return True
        else:
            return False

    def rotate_key(
        self,
        old_key_id: str,
        new_key_value: str,
        grace_period: int = 3600,  # 1小时宽限期
    ) -> Optional[str]:
        """
        轮换API密钥

        Args:
            old_key_id: 旧密钥ID
            new_key_value: 新密钥值
            grace_period: 宽限期（秒），在此期间新旧密钥都可用

        Returns:
            新密钥ID，如失败返回None
        """
        if old_key_id not in self._keys_cache:
            logger.error(f"旧密钥 {old_key_id} 不存在")
            return None

        old_key = self._keys_cache[old_key_id]
        if old_key is None:
            logger.error(f"旧密钥 {old_key_id} 存在但值为None")
            return None

        # 计算新密钥的过期时间
        expires_in = None
        if old_key.expires_at:
            remaining = old_key.expires_at - time.time()
            # 确保过期时间不为负数
            expires_in = max(0, int(remaining))

        # 添加新密钥
        new_key_id = self.add_key(
            provider=old_key.provider,
            key_value=new_key_value,
            environment=old_key.environment,
            expires_in=expires_in,
            metadata=old_key.metadata
        )

        if not new_key_id:
            return None

        # 验证新密钥ID与旧密钥ID不同
        if new_key_id == old_key_id:
            logger.error(f"新密钥ID与旧密钥ID相同: {new_key_id}")
            return None

        # 设置旧密钥为待刷新状态
        self._keys_cache[old_key_id].status = KeyStatus.PENDING_REFRESH
        self._save_keys()

        # 设置宽限期后自动过期
        if grace_period > 0:
            def _expire_old_key():
                time.sleep(grace_period)
                if old_key_id in self._keys_cache:
                    old_key_info = self._keys_cache[old_key_id]
                    if old_key_info is not None:
                        old_key_info.status = KeyStatus.EXPIRED
                        self._save_keys()
                        logger.info(f"宽限期结束，旧密钥 {old_key_id} 已过期")

            import threading
            threading.Thread(target=_expire_old_key, daemon=True).start()

        logger.info(f"已轮换密钥: {old_key_id} -> {new_key_id}")
        return new_key_id

    def validate_key(self, key_id: str) -> Dict[str, Any]:
        """
        验证API密钥有效性

        Args:
            key_id: 密钥ID

        Returns:
            验证结果字典
        """
        # 验证时总是检查状态
        key_info = self.get_key(key_id, update_usage=False, check_status=True)

        if not key_info:
            # 检查密钥是否存在但状态不是ACTIVE
            if key_id in self._keys_cache:
                key_info = self._keys_cache[key_id]
                if key_info is not None:
                    return {
                        "valid": False,
                        "reason": f"密钥状态为 {key_info.status.value}",
                        "key_id": key_id,
                        "status": key_info.status.value,
                        "provider": key_info.provider,
                        "environment": key_info.environment
                    }

            return {
                "valid": False,
                "reason": "密钥不存在或不可用",
                "key_id": key_id
            }

        result = {
            "valid": True,
            "key_id": key_id,
            "provider": key_info.provider,
            "environment": key_info.environment,
            "status": key_info.status.value,
            "created_at": key_info.created_at,
            "expires_at": key_info.expires_at,
            "last_used": key_info.last_used,
            "usage_count": key_info.usage_count,
        }

        # 检查过期时间
        if key_info.expires_at:
            remaining = key_info.expires_at - time.time()
            result["expires_in"] = remaining
            result["will_expire_soon"] = remaining < 86400  # 24小时内过期

        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取密钥统计信息"""
        total_keys = len(self._keys_cache)
        active_keys = len([k for k in self._keys_cache.values() if k is not None and k.status == KeyStatus.ACTIVE])
        expired_keys = len([k for k in self._keys_cache.values() if k is not None and k.status == KeyStatus.EXPIRED])

        # 按提供商统计
        providers = {}
        for key_info in self._keys_cache.values():
            if key_info is None:
                continue

            provider = key_info.provider
            if provider not in providers:
                providers[provider] = {"total": 0, "active": 0, "expired": 0}
            providers[provider]["total"] += 1
            if key_info.status == KeyStatus.ACTIVE:
                providers[provider]["active"] += 1
            elif key_info.status == KeyStatus.EXPIRED:
                providers[provider]["expired"] += 1

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "providers": providers,
            "storage_path": self.storage_path,
            "encryption_enabled": bool(self.encryption_key),
        }

    def backup_keys(self, backup_path: Optional[str] = None) -> bool:
        """
        备份密钥

        Args:
            backup_path: 备份文件路径

        Returns:
            备份是否成功
        """
        try:
            if not backup_path:
                backup_dir = os.path.join(os.path.dirname(self.storage_path), "backups")
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"keys_backup_{timestamp}.enc")
            else:
                # 确保备份目录存在
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            # 直接复制文件
            import shutil
            shutil.copy2(self.storage_path, backup_path)

            logger.info(f"密钥已备份到: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"备份密钥失败: {e}")
            return False


# 全局API密钥管理器实例
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager(
    storage_path: Optional[str] = None,
    encryption_key: Optional[str] = None,
) -> APIKeyManager:
    """
    获取全局API密钥管理器实例

    Args:
        storage_path: 密钥存储文件路径
        encryption_key: 加密密钥

    Returns:
        APIKeyManager实例
    """
    global _api_key_manager

    if _api_key_manager is None:
        _api_key_manager = APIKeyManager(storage_path, encryption_key)

    return _api_key_manager


def get_api_key(provider: str, environment: Optional[str] = None) -> Optional[str]:
    """
    获取API密钥（快捷函数）

    Args:
        provider: 服务提供商
        environment: 环境

    Returns:
        API密钥值，如不存在返回None
    """
    manager = get_api_key_manager()
    keys = manager.get_keys(provider=provider, environment=environment, status=KeyStatus.ACTIVE)

    if not keys:
        return None

    # 返回第一个活跃密钥
    key_info = manager.get_key(keys[0].key_id)
    return key_info.key_value if key_info else None