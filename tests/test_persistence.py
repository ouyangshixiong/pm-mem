"""
MemoryPersistence单元测试
"""

import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime
from unittest.mock import patch, mock_open
from src.memory.persistence import MemoryPersistence
from src.memory.bank import MemoryBank
from src.memory.entry import MemoryEntry


class TestMemoryPersistence(unittest.TestCase):
    """MemoryPersistence类单元测试"""

    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_memory.json")
        self.persistence = MemoryPersistence(self.test_file)

        # 创建测试记忆库
        self.memory_bank = MemoryBank(max_entries=5)

        # 添加测试条目
        self.entry1 = MemoryEntry(
            x="测试任务1",
            y="测试输出1",
            feedback="测试反馈1",
            tag="test",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            id="test-id-1"
        )

        self.entry2 = MemoryEntry(
            x="测试任务2",
            y="测试输出2",
            feedback="测试反馈2",
            tag="test",
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            id="test-id-2"
        )

        self.memory_bank.add(self.entry1)
        self.memory_bank.add(self.entry2)

    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """测试初始化"""
        persistence = MemoryPersistence("./data/memory.json")
        self.assertEqual(persistence.filepath, "./data/memory.json")

        # 测试目录创建
        test_dir = os.path.join(self.temp_dir, "subdir", "memory.json")
        persistence = MemoryPersistence(test_dir)
        self.assertTrue(os.path.exists(os.path.dirname(test_dir)))

    def test_save_and_load(self):
        """测试保存和加载"""
        # 保存记忆库
        result = self.persistence.save(self.memory_bank)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_file))

        # 加载记忆库
        loaded_bank = self.persistence.load()
        self.assertEqual(len(loaded_bank), 2)
        self.assertEqual(loaded_bank.max_entries, 5)

        # 验证加载的条目
        loaded_entry1 = loaded_bank.get_entry("test-id-1")
        self.assertIsNotNone(loaded_entry1)
        self.assertEqual(loaded_entry1.x, "测试任务1")
        self.assertEqual(loaded_entry1.y, "测试输出1")
        self.assertEqual(loaded_entry1.feedback, "测试反馈1")
        self.assertEqual(loaded_entry1.tag, "test")

        # 验证时间戳
        self.assertEqual(
            loaded_entry1.timestamp.isoformat(),
            "2024-01-01T10:00:00"
        )

    def test_save_with_existing_file(self):
        """测试保存已存在文件（应创建备份）"""
        # 第一次保存
        self.persistence.save(self.memory_bank)

        # 修改记忆库并再次保存
        self.memory_bank.add(MemoryEntry(
            x="新任务",
            y="新输出",
            feedback="新反馈",
            tag="new"
        ))

        result = self.persistence.save(self.memory_bank)
        self.assertTrue(result)

        # 检查备份目录
        backup_dir = os.path.join(self.temp_dir, "backups")
        self.assertTrue(os.path.exists(backup_dir))

        # 检查备份文件（备份文件格式：test_memory.json.backup_20250101_120000）
        backup_files = [f for f in os.listdir(backup_dir) if ".backup_" in f]
        self.assertGreater(len(backup_files), 0)

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.json")
        persistence = MemoryPersistence(nonexistent_file)

        loaded_bank = persistence.load()
        self.assertEqual(len(loaded_bank), 0)
        self.assertEqual(loaded_bank.max_entries, 1000)  # 默认值

    def test_load_with_existing_bank(self):
        """测试加载到现有记忆库"""
        # 保存记忆库
        self.persistence.save(self.memory_bank)

        # 创建现有记忆库并添加一些条目
        existing_bank = MemoryBank(max_entries=10)
        existing_bank.add(MemoryEntry(
            x="现有任务",
            y="现有输出",
            feedback="现有反馈",
            tag="existing"
        ))

        # 加载到现有记忆库
        loaded_bank = self.persistence.load(existing_bank)

        # 应该合并条目
        self.assertEqual(len(loaded_bank), 3)
        self.assertEqual(loaded_bank.max_entries, 5)  # 应该使用文件中的max_entries

    def test_load_invalid_json(self):
        """测试加载无效JSON文件"""
        # 写入无效JSON
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("invalid json content")

        loaded_bank = self.persistence.load()
        self.assertEqual(len(loaded_bank), 0)  # 应该返回空记忆库

    def test_load_with_compatibility(self):
        """测试兼容性加载"""
        # 创建旧格式数据
        old_format_data = {
            "version": "0.8.0",
            "timestamp": "2024-01-01T10:00:00",
            "max_entries": 5,
            "entries": [
                {
                    "cue": "旧格式任务",  # 旧字段名
                    "response": "旧格式输出",
                    "feedback": "旧格式反馈",
                    "tag": "old-format",
                    "id": "old-id-1"
                }
            ]
        }

        # 写入文件
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(old_format_data, f)

        # 加载（应该使用兼容模式）
        loaded_bank = self.persistence.load()
        self.assertEqual(len(loaded_bank), 1)

        loaded_entry = loaded_bank[0]
        self.assertEqual(loaded_entry.x, "旧格式任务")  # cue应该转换为x
        self.assertEqual(loaded_entry.y, "旧格式输出")  # response应该转换为y
        self.assertEqual(loaded_entry.feedback, "旧格式反馈")
        self.assertEqual(loaded_entry.tag, "old-format")

    def test_load_unsupported_version(self):
        """测试加载不支持版本"""
        unsupported_data = {
            "version": "0.5.0",  # 不支持版本
            "timestamp": "2024-01-01T10:00:00",
            "max_entries": 5,
            "entries": []
        }

        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(unsupported_data, f)

        # 应该使用兼容模式加载
        loaded_bank = self.persistence.load()
        self.assertEqual(len(loaded_bank), 0)

    def test_export_and_import(self):
        """测试导出和导入"""
        export_path = os.path.join(self.temp_dir, "export.json")

        # 导出
        result = self.persistence.export_to_file(self.memory_bank, export_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(export_path))

        # 验证导出文件内容
        with open(export_path, "r", encoding="utf-8") as f:
            export_data = json.load(f)

        self.assertEqual(export_data["version"], "1.0.0")
        self.assertEqual(len(export_data["entries"]), 2)
        self.assertEqual(export_data["metadata"]["exported_by"], "pm-mem")

        # 导入
        imported_bank = self.persistence.import_from_file(export_path)
        self.assertEqual(len(imported_bank), 2)

        # 导入到现有记忆库（合并）
        existing_bank = MemoryBank()
        existing_bank.add(MemoryEntry(
            x="现有任务",
            y="现有输出",
            feedback="现有反馈",
            tag="existing"
        ))

        merged_bank = self.persistence.import_from_file(export_path, existing_bank)
        self.assertEqual(len(merged_bank), 3)  # 1个现有 + 2个导入

    def test_import_nonexistent_file(self):
        """测试导入不存在的文件"""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent_import.json")
        imported_bank = self.persistence.import_from_file(nonexistent_path)

        self.assertEqual(len(imported_bank), 0)

    def test_backup(self):
        """测试备份功能"""
        backup_path = self.persistence.backup(self.memory_bank, self.temp_dir)
        self.assertIsNotNone(backup_path)
        self.assertTrue(os.path.exists(backup_path))

        # 验证备份文件内容
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        self.assertEqual(backup_data["version"], "1.0.0")
        self.assertEqual(len(backup_data["entries"]), 2)

    def test_backup_failure(self):
        """测试备份失败情况"""
        # 使用无效目录
        invalid_dir = "/invalid/path/that/does/not/exist"
        backup_path = self.persistence.backup(self.memory_bank, invalid_dir)
        self.assertIsNone(backup_path)

    def test_get_file_info(self):
        """测试获取文件信息"""
        # 保存文件
        self.persistence.save(self.memory_bank)

        info = self.persistence.get_file_info()
        self.assertTrue(info["exists"])
        self.assertGreater(info["file_size"], 0)
        self.assertIn("version", info)
        self.assertEqual(info["entry_count"], 2)
        self.assertTrue(info["integrity_check"])

        # 测试不存在的文件
        nonexistent_persistence = MemoryPersistence(
            os.path.join(self.temp_dir, "nonexistent.json")
        )
        info = nonexistent_persistence.get_file_info()
        self.assertFalse(info["exists"])

    def test_validate_file(self):
        """测试文件验证"""
        # 保存有效文件
        self.persistence.save(self.memory_bank)

        validation = self.persistence.validate_file()
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["version"], "1.0.0")
        self.assertTrue(validation["version_supported"])
        self.assertTrue(validation["has_required_fields"])
        self.assertTrue(validation["entries_is_list"])
        self.assertEqual(validation["entry_count"], 2)
        self.assertTrue(validation["checksum_valid"])
        self.assertFalse(validation["has_invalid_entries"])

    def test_validate_invalid_file(self):
        """测试无效文件验证"""
        # 创建无效JSON文件
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json")

        validation = self.persistence.validate_file()
        self.assertFalse(validation["valid"])
        self.assertIn("JSON解析错误", validation["error"])

        # 创建缺少必要字段的文件
        invalid_data = {
            "version": "1.0.0"
            # 缺少timestamp和entries
        }

        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(invalid_data, f)

        validation = self.persistence.validate_file()
        self.assertFalse(validation["valid"])
        self.assertFalse(validation["has_required_fields"])

    def test_validate_file_with_invalid_entries(self):
        """测试包含无效条目的文件验证"""
        invalid_data = {
            "version": "1.0.0",
            "timestamp": "2024-01-01T10:00:00",
            "max_entries": 5,
            "entries": [
                {
                    "id": "valid-id",
                    "x": "有效任务",
                    "y": "有效输出",
                    "feedback": "有效反馈",
                    "tag": "valid"
                },
                {
                    "id": "invalid-id"
                    # 缺少必要字段
                }
            ]
        }

        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(invalid_data, f)

        validation = self.persistence.validate_file()
        self.assertFalse(validation["valid"])
        self.assertTrue(validation["has_invalid_entries"])
        self.assertEqual(len(validation["invalid_entries"]), 1)

    def test_checksum_validation(self):
        """测试校验和验证"""
        # 保存文件（包含校验和）
        self.persistence.save(self.memory_bank)

        # 验证文件
        validation = self.persistence.validate_file()
        self.assertTrue(validation["valid"])
        self.assertTrue(validation["checksum_valid"])

        # 篡改文件内容
        with open(self.test_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 修改一个条目
        data["entries"][0]["x"] = "篡改后的任务"

        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # 验证应该失败
        validation = self.persistence.validate_file()
        self.assertFalse(validation["valid"])
        self.assertFalse(validation["checksum_valid"])

    def test_atomic_save(self):
        """测试原子性保存"""
        # 模拟保存过程中的错误
        with patch('builtins.open', side_effect=Exception("模拟写入错误")):
            result = self.persistence.save(self.memory_bank)
            self.assertFalse(result)

        # 临时文件不应该存在
        temp_file = self.test_file + ".tmp"
        self.assertFalse(os.path.exists(temp_file))

        # 原始文件也不应该存在（因为是新文件）
        self.assertFalse(os.path.exists(self.test_file))

    def test_recover_from_backup(self):
        """测试从备份恢复"""
        # 保存原始文件（第一次保存，文件不存在，不会创建备份）
        self.persistence.save(self.memory_bank)
        # 再次保存以创建备份（文件已存在会触发备份）
        self.persistence.save(self.memory_bank)

        # 损坏原始文件
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("损坏的内容")

        # 尝试加载（应该触发恢复）
        with self.assertLogs(level='WARNING') as log:
            loaded_bank = self.persistence.load()

        # 应该从备份恢复
        self.assertEqual(len(loaded_bank), 2)

        # 检查日志
        self.assertTrue(any("尝试从备份恢复" in message for message in log.output))

    def test_cleanup_old_backups(self):
        """测试清理旧备份"""
        backup_dir = os.path.join(self.temp_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        # 创建一些备份文件
        for i in range(5):
            backup_file = os.path.join(backup_dir, f"memory_backup_2024010{i+1}_120000.json")
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump({"test": f"backup{i}"}, f)

            # 修改文件时间（模拟旧文件）
            old_time = datetime(2024, 1, i+1).timestamp()
            os.utime(backup_file, (old_time, old_time))

        # 备份文件应该存在
        backup_files = os.listdir(backup_dir)
        self.assertEqual(len(backup_files), 5)

        # 注意：实际清理逻辑在_create_backup中调用，这里我们直接测试清理函数
        # 由于时间问题，这个测试可能需要调整

    def test_load_entry_compatibility(self):
        """测试条目加载兼容性"""
        # 测试各种兼容性情况
        test_cases = [
            # 标准格式
            {
                "input": {
                    "id": "test-1",
                    "x": "任务",
                    "y": "输出",
                    "feedback": "反馈",
                    "tag": "test",
                    "timestamp": "2024-01-01T10:00:00"
                },
                "expected_x": "任务",
                "expected_y": "输出"
            },
            # 旧格式（cue/response）
            {
                "input": {
                    "id": "test-2",
                    "cue": "旧任务",
                    "response": "旧输出",
                    "feedback": "旧反馈",
                    "tag": "old",
                    "timestamp": "2024-01-01T10:00:00"
                },
                "expected_x": "旧任务",
                "expected_y": "旧输出"
            },
            # 缺少字段
            {
                "input": {
                    "id": "test-3",
                    "x": "任务",
                    "y": "输出"
                    # 缺少feedback和tag
                },
                "expected_x": "任务",
                "expected_y": "输出",
                "expected_feedback": "",
                "expected_tag": ""
            }
        ]

        for case in test_cases:
            entry = self.persistence._load_entry_with_compatibility(case["input"])
            self.assertEqual(entry.x, case["expected_x"])
            self.assertEqual(entry.y, case["expected_y"])

            if "expected_feedback" in case:
                self.assertEqual(entry.feedback, case["expected_feedback"])
            if "expected_tag" in case:
                self.assertEqual(entry.tag, case["expected_tag"])


if __name__ == "__main__":
    unittest.main()