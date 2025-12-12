"""
PM-95: API密钥安全存储设计与实现测试

验证APIKeyManager的完整功能实现。
"""

import os
import sys
import tempfile
import time
import json
import base64
import unittest
from unittest.mock import patch, mock_open
import shutil

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from config.api_key_manager import (
    APIKeyManager,
    APIKeyInfo,
    KeyStatus,
    get_api_key_manager,
    get_api_key
)


class TestAPIKeyManager(unittest.TestCase):
    """测试API密钥管理器"""

    def setUp(self):
        """测试前准备"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "test_keys.enc")
        self.encryption_key = "test-encryption-key-123"

        # 创建管理器实例
        self.manager = APIKeyManager(
            storage_path=self.storage_path,
            encryption_key=self.encryption_key,
            default_environment="test"
        )

    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """测试管理器初始化"""
        self.assertEqual(self.manager.storage_path, self.storage_path)
        self.assertEqual(self.manager.encryption_key, self.encryption_key)
        self.assertEqual(self.manager.default_environment, "test")
        self.assertEqual(len(self.manager._keys_cache), 0)

    def test_add_key(self):
        """测试添加API密钥"""
        key_id = self.manager.add_key(
            provider="deepseek",
            key_value="test-api-key-value-123",
            environment="development",
            expires_in=3600,  # 1小时后过期
            metadata={"description": "测试密钥"}
        )

        # 验证密钥ID格式
        self.assertIsNotNone(key_id)
        self.assertTrue(key_id.startswith("deepseek_development_"))

        # 验证密钥已添加到缓存
        self.assertIn(key_id, self.manager._keys_cache)
        key_info = self.manager._keys_cache[key_id]

        self.assertEqual(key_info.provider, "deepseek")
        self.assertEqual(key_info.key_value, "test-api-key-value-123")
        self.assertEqual(key_info.environment, "development")
        self.assertEqual(key_info.status, KeyStatus.ACTIVE)
        self.assertIsNotNone(key_info.created_at)
        self.assertIsNotNone(key_info.expires_at)
        self.assertEqual(key_info.metadata["description"], "测试密钥")

    def test_get_key(self):
        """测试获取API密钥"""
        # 添加密钥
        key_id = self.manager.add_key(
            provider="openai",
            key_value="openai-test-key-456",
            environment="production"
        )

        # 获取密钥
        key_info = self.manager.get_key(key_id)

        self.assertIsNotNone(key_info)
        self.assertEqual(key_info.key_id, key_id)
        self.assertEqual(key_info.provider, "openai")
        self.assertEqual(key_info.key_value, "openai-test-key-456")
        self.assertEqual(key_info.environment, "production")
        self.assertEqual(key_info.status, KeyStatus.ACTIVE)

        # 验证使用统计已更新
        self.assertEqual(key_info.usage_count, 1)
        self.assertIsNotNone(key_info.last_used)

    def test_get_keys_with_filters(self):
        """测试带过滤条件的密钥获取"""
        # 添加多个密钥
        key1_id = self.manager.add_key("deepseek", "key1", "development")
        key2_id = self.manager.add_key("deepseek", "key2", "production")
        key3_id = self.manager.add_key("openai", "key3", "development")

        # 设置一个密钥为过期状态
        self.manager.update_key_status(key3_id, KeyStatus.EXPIRED)

        # 测试按提供商过滤
        deepseek_keys = self.manager.get_keys(provider="deepseek")
        self.assertEqual(len(deepseek_keys), 2)

        # 测试按环境过滤
        dev_keys = self.manager.get_keys(environment="development")
        self.assertEqual(len(dev_keys), 2)  # 返回development环境的所有密钥（包括过期）

        # 测试按状态过滤
        active_keys = self.manager.get_keys(status=KeyStatus.ACTIVE)
        self.assertEqual(len(active_keys), 2)

        expired_keys = self.manager.get_keys(status=KeyStatus.EXPIRED)
        self.assertEqual(len(expired_keys), 1)

    def test_update_key_status(self):
        """测试更新密钥状态"""
        key_id = self.manager.add_key("test", "key-value", "test")

        # 更新状态为已撤销
        result = self.manager.update_key_status(key_id, KeyStatus.REVOKED)
        self.assertTrue(result)

        # 验证状态已更新
        key_info = self.manager.get_key(key_id, update_usage=False)
        self.assertIsNone(key_info)  # 已撤销的密钥不可用

        # 验证缓存中的状态
        self.assertEqual(self.manager._keys_cache[key_id].status, KeyStatus.REVOKED)

    def test_delete_key(self):
        """测试删除密钥"""
        key_id = self.manager.add_key("test", "key-value", "test")

        # 删除密钥
        result = self.manager.delete_key(key_id)
        self.assertTrue(result)

        # 验证密钥已删除
        self.assertNotIn(key_id, self.manager._keys_cache)
        key_info = self.manager.get_key(key_id)
        self.assertIsNone(key_info)

    def test_rotate_key(self):
        """测试密钥轮换"""
        # 添加旧密钥
        old_key_id = self.manager.add_key(
            provider="deepseek",
            key_value="old-key-value",
            environment="production",
            expires_in=7200,
            metadata={"owner": "test-user"}
        )

        # 轮换密钥
        new_key_id = self.manager.rotate_key(
            old_key_id=old_key_id,
            new_key_value="new-key-value",
            grace_period=10  # 10秒宽限期
        )

        self.assertIsNotNone(new_key_id)

        # 验证新密钥
        new_key_info = self.manager.get_key(new_key_id)
        self.assertIsNotNone(new_key_info)
        self.assertEqual(new_key_info.key_value, "new-key-value")
        self.assertEqual(new_key_info.metadata["owner"], "test-user")

        # 验证旧密钥状态
        old_key_info = self.manager._keys_cache[old_key_id]
        self.assertEqual(old_key_info.status, KeyStatus.PENDING_REFRESH)

        # 等待宽限期后验证旧密钥过期
        time.sleep(11)  # 等待超过宽限期
        self.assertEqual(old_key_info.status, KeyStatus.EXPIRED)

    def test_validate_key(self):
        """测试密钥验证"""
        # 添加未过期的密钥（设置较长的过期时间，确保不会很快过期）
        key_id = self.manager.add_key(
            provider="test",
            key_value="test-key",
            environment="test",
            expires_in=100000  # 100000秒后过期，远大于24小时
        )

        # 验证有效密钥
        validation = self.manager.validate_key(key_id)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["provider"], "test")
        self.assertEqual(validation["status"], "active")
        self.assertGreater(validation["expires_in"], 86400)  # 大于24小时
        self.assertFalse(validation["will_expire_soon"])  # 不会很快过期

        # 添加已过期的密钥
        expired_key_id = self.manager.add_key(
            provider="test",
            key_value="expired-key",
            environment="test",
            expires_in=1  # 1秒后过期
        )
        time.sleep(2)  # 等待过期

        # 验证过期密钥
        expired_validation = self.manager.validate_key(expired_key_id)
        self.assertFalse(expired_validation["valid"])
        # 更新期望值以匹配新的实现
        self.assertEqual(expired_validation["reason"], "密钥状态为 expired")
        self.assertEqual(expired_validation["key_id"], expired_key_id)
        self.assertEqual(expired_validation["status"], "expired")

    def test_get_stats(self):
        """测试获取统计信息"""
        # 添加多个密钥
        self.manager.add_key("deepseek", "key1", "dev")
        self.manager.add_key("deepseek", "key2", "prod")
        self.manager.add_key("openai", "key3", "dev")

        # 设置一个密钥为过期状态
        keys = self.manager.get_keys(provider="openai")
        if keys:
            self.manager.update_key_status(keys[0].key_id, KeyStatus.EXPIRED)

        # 获取统计信息
        stats = self.manager.get_stats()

        self.assertEqual(stats["total_keys"], 3)
        self.assertEqual(stats["active_keys"], 2)
        self.assertEqual(stats["expired_keys"], 1)
        self.assertEqual(stats["storage_path"], self.storage_path)
        self.assertTrue(stats["encryption_enabled"])

        # 验证提供商统计
        self.assertIn("deepseek", stats["providers"])
        self.assertIn("openai", stats["providers"])
        self.assertEqual(stats["providers"]["deepseek"]["total"], 2)
        self.assertEqual(stats["providers"]["deepseek"]["active"], 2)

    def test_backup_keys(self):
        """测试密钥备份"""
        # 添加测试密钥
        self.manager.add_key("test", "backup-key", "test")

        # 确保存储文件已保存
        self.manager._save_keys()

        # 创建备份
        backup_dir = os.path.join(self.temp_dir, "backups")
        backup_path = os.path.join(backup_dir, "keys_backup.enc")

        result = self.manager.backup_keys(backup_path)
        self.assertTrue(result)

        # 验证备份文件存在
        self.assertTrue(os.path.exists(backup_path))

        # 验证备份文件内容
        self.assertTrue(os.path.getsize(backup_path) > 0)

    def test_encryption_decryption(self):
        """测试加密解密功能"""
        test_data = "敏感API密钥数据"

        # 加密
        encrypted = self.manager._simple_encrypt(test_data)
        self.assertNotEqual(encrypted, test_data)
        self.assertIsInstance(encrypted, str)

        # 解密
        decrypted = self.manager._simple_decrypt(encrypted)
        self.assertEqual(decrypted, test_data)

        # 测试无加密密钥的情况
        manager_no_encrypt = APIKeyManager(
            storage_path=self.storage_path,
            encryption_key=None,
            default_environment="test"
        )

        # 无加密时返回原数据
        no_encrypt_result = manager_no_encrypt._simple_encrypt(test_data)
        self.assertEqual(no_encrypt_result, test_data)

    def test_persistence(self):
        """测试持久化存储"""
        # 添加密钥
        key_id = self.manager.add_key("persistence", "persist-key", "test")

        # 创建新管理器实例（模拟重启）
        new_manager = APIKeyManager(
            storage_path=self.storage_path,
            encryption_key=self.encryption_key,
            default_environment="test"
        )

        # 验证密钥已持久化
        self.assertIn(key_id, new_manager._keys_cache)
        key_info = new_manager.get_key(key_id)
        self.assertIsNotNone(key_info)
        self.assertEqual(key_info.key_value, "persist-key")

    def test_global_functions(self):
        """测试全局函数"""
        # 测试get_api_key_manager
        manager1 = get_api_key_manager(
            storage_path=self.storage_path,
            encryption_key=self.encryption_key
        )
        manager2 = get_api_key_manager()  # 应该返回同一个实例

        self.assertIs(manager1, manager2)

        # 添加测试密钥
        key_id = manager1.add_key("global", "global-key", "test")

        # 测试get_api_key
        api_key = get_api_key("global", "test")
        self.assertEqual(api_key, "global-key")

        # 测试不存在的密钥
        no_key = get_api_key("nonexistent", "test")
        self.assertIsNone(no_key)

    def test_key_expiration(self):
        """测试密钥过期"""
        # 添加即将过期的密钥
        key_id = self.manager.add_key(
            provider="expiring",
            key_value="expiring-key",
            environment="test",
            expires_in=1  # 1秒后过期
        )

        # 立即获取应该成功
        key_info = self.manager.get_key(key_id)
        self.assertIsNotNone(key_info)

        # 等待过期
        time.sleep(2)

        # 再次获取应该失败
        expired_key_info = self.manager.get_key(key_id)
        self.assertIsNone(expired_key_info)

        # 验证状态已更新为过期
        self.assertEqual(self.manager._keys_cache[key_id].status, KeyStatus.EXPIRED)

    def test_duplicate_key_warning(self):
        """测试重复密钥警告"""
        # 添加第一个密钥
        self.manager.add_key("duplicate", "key1", "test")

        # 添加相同提供者和环境的第二个密钥（应该产生警告）
        with self.assertLogs(level='WARNING') as log:
            self.manager.add_key("duplicate", "key2", "test")

        # 验证警告日志
        self.assertTrue(any("已存在 duplicate 在 test 环境的活跃密钥" in message for message in log.output))


if __name__ == '__main__':
    unittest.main()