"""
持久化存储模块

基于JSON文件的自动保存/加载，支持记忆库的完整导出/导入。
"""

import json
import os
import shutil
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import hashlib

from .bank import MemoryBank
from .entry import MemoryEntry

logger = logging.getLogger(__name__)


class MemoryPersistence:
    """记忆持久化存储管理器"""

    # 当前存储格式版本
    FORMAT_VERSION = "1.0.0"
    # 支持的旧版本（用于向后兼容）
    SUPPORTED_VERSIONS = ["1.0.0", "0.9.0", "0.8.0"]

    def __init__(self, filepath: str = "./data/memory.json"):
        """
        初始化持久化管理器

        Args:
            filepath: 存储文件路径
        """
        self.filepath = filepath
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """确保存储目录存在"""
        directory = os.path.dirname(self.filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"创建存储目录: {directory}")

    def save(self, memory_bank: MemoryBank) -> bool:
        """
        保存记忆库到文件

        Args:
            memory_bank: 要保存的记忆库

        Returns:
            保存是否成功
        """
        try:
            # 创建备份（如果文件已存在）
            if os.path.exists(self.filepath):
                self._create_backup(self.filepath)

            data = {
                "version": self.FORMAT_VERSION,
                "timestamp": datetime.utcnow().isoformat(),
                "max_entries": memory_bank.max_entries,
                "entries": memory_bank.to_dict(),
                "metadata": {
                    "total_entries": len(memory_bank),
                    "generated_by": "pm-mem",
                    "checksum": self._calculate_checksum(memory_bank.to_dict()),
                },
            }

            # 写入临时文件，然后原子性地重命名
            temp_filepath = self.filepath + ".tmp"
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 原子性地重命名临时文件
            os.replace(temp_filepath, self.filepath)

            logger.info(f"记忆库已保存到: {self.filepath} (共 {len(memory_bank)} 条记忆)")
            return True

        except Exception as e:
            logger.error(f"保存记忆库失败: {e}")
            return False

    def load(self, memory_bank: Optional[MemoryBank] = None) -> MemoryBank:
        """
        从文件加载记忆库

        Args:
            memory_bank: 可选的现有记忆库实例，如为None则创建新实例

        Returns:
            加载后的记忆库实例
        """
        if not os.path.exists(self.filepath):
            logger.warning(f"存储文件不存在: {self.filepath}，返回空记忆库")
            return memory_bank or MemoryBank()

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查版本兼容性
            version = data.get("version", "1.0.0")
            if version not in self.SUPPORTED_VERSIONS:
                logger.warning(
                    f"存储文件版本不支持: {version} (支持版本: {self.SUPPORTED_VERSIONS})"
                )
                # 尝试使用兼容模式加载
                return self._load_with_compatibility(data, memory_bank)

            # 验证数据完整性
            if not self._validate_data_integrity(data):
                logger.error("存储文件数据完整性验证失败")
                # 尝试从备份恢复
                return self._recover_from_backup(memory_bank)

            # 加载记忆条目
            max_entries = data.get("max_entries", 1000)
            entries_data = data.get("entries", [])

            if memory_bank is None:
                memory_bank = MemoryBank(max_entries=max_entries)
                # 添加所有条目到新创建的记忆库
                loaded_count = 0
                for entry_data in entries_data:
                    try:
                        entry = self._load_entry_with_compatibility(entry_data)
                        memory_bank.add(entry)
                        loaded_count += 1
                    except Exception as e:
                        logger.warning(f"加载记忆条目失败，跳过: {e}")
                logger.info(f"从 {self.filepath} 加载了 {loaded_count} 条记忆到新记忆库")
            else:
                memory_bank.max_entries = max_entries
                # 合并记忆库（基于ID去重）
                existing_ids = {e.id for e in memory_bank.entries}
                loaded_count = 0
                for entry_data in entries_data:
                    try:
                        entry = self._load_entry_with_compatibility(entry_data)
                        if entry.id not in existing_ids:
                            memory_bank.add(entry)
                            existing_ids.add(entry.id)
                            loaded_count += 1
                    except Exception as e:
                        logger.warning(f"加载记忆条目失败，跳过: {e}")
                logger.info(f"从 {self.filepath} 加载了 {loaded_count} 条记忆到现有记忆库（合并后总数: {len(memory_bank)}）")
            return memory_bank

        except json.JSONDecodeError as e:
            logger.error(f"存储文件格式错误: {e}")
            # 尝试从备份恢复
            return self._recover_from_backup(memory_bank)
        except Exception as e:
            logger.error(f"加载记忆库失败: {e}")
            return memory_bank or MemoryBank()

    def _load_entry_with_compatibility(self, entry_data: Dict[str, Any]) -> MemoryEntry:
        """
        兼容性加载记忆条目

        Args:
            entry_data: 记忆条目数据

        Returns:
            MemoryEntry实例
        """
        # 兼容旧格式
        if "x" not in entry_data and "cue" in entry_data:
            entry_data["x"] = entry_data["cue"]
            entry_data["y"] = entry_data.get("response", "")
            entry_data["feedback"] = entry_data.get("feedback", "")

        # 确保必要字段存在
        required_fields = ["x", "y", "feedback"]
        for field in required_fields:
            if field not in entry_data:
                entry_data[field] = ""

        return MemoryEntry.from_dict(entry_data)

    def _load_with_compatibility(self, data: Dict[str, Any], memory_bank: Optional[MemoryBank]) -> MemoryBank:
        """
        兼容模式加载

        Args:
            data: 加载的数据
            memory_bank: 可选的现有记忆库

        Returns:
            加载后的记忆库
        """
        try:
            max_entries = data.get("max_entries", 1000)
            entries_data = data.get("entries", [])

            if memory_bank is None:
                memory_bank = MemoryBank(max_entries=max_entries)
            else:
                memory_bank.max_entries = max_entries

            memory_bank.entries = []
            for entry_data in entries_data:
                try:
                    entry = self._load_entry_with_compatibility(entry_data)
                    memory_bank.entries.append(entry)
                except Exception as e:
                    logger.warning(f"兼容模式加载记忆条目失败，跳过: {e}")

            logger.warning(f"使用兼容模式加载了 {len(memory_bank)} 条记忆")
            return memory_bank
        except Exception as e:
            logger.error(f"兼容模式加载失败: {e}")
            return memory_bank or MemoryBank()

    def _validate_data_integrity(self, data: Dict[str, Any]) -> bool:
        """
        验证数据完整性

        Args:
            data: 要验证的数据

        Returns:
            数据是否完整
        """
        try:
            # 检查必要字段
            required_fields = ["version", "timestamp", "entries"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"数据缺少必要字段: {field}")
                    return False

            # 检查entries是否为列表
            if not isinstance(data["entries"], list):
                logger.error("entries字段必须是列表")
                return False

            # 验证checksum（如果存在）
            metadata = data.get("metadata", {})
            if "checksum" in metadata:
                expected_checksum = metadata["checksum"]
                actual_checksum = self._calculate_checksum(data["entries"])
                if expected_checksum != actual_checksum:
                    logger.error(f"数据校验和不匹配: 期望={expected_checksum}, 实际={actual_checksum}")
                    return False

            return True
        except Exception as e:
            logger.error(f"数据完整性验证失败: {e}")
            return False

    def _calculate_checksum(self, data: List[Dict[str, Any]]) -> str:
        """
        计算数据校验和

        Args:
            data: 要计算校验和的数据

        Returns:
            MD5校验和
        """
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode("utf-8")).hexdigest()

    def _create_backup(self, filepath: str) -> bool:
        """
        创建文件备份

        Args:
            filepath: 要备份的文件路径

        Returns:
            备份是否成功
        """
        try:
            backup_dir = os.path.join(os.path.dirname(filepath), "backups")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{os.path.basename(filepath)}.backup_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_filename)

            shutil.copy2(filepath, backup_path)
            logger.debug(f"创建备份: {backup_path}")

            # 清理旧的备份文件（保留最近7天）
            self._cleanup_old_backups(backup_dir)

            return True
        except Exception as e:
            logger.warning(f"创建备份失败: {e}")
            return False

    def _cleanup_old_backups(self, backup_dir: str, days_to_keep: int = 7) -> None:
        """
        清理旧的备份文件

        Args:
            backup_dir: 备份目录
            days_to_keep: 保留天数
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)

            for filename in os.listdir(backup_dir):
                if filename.endswith(".backup_"):
                    filepath = os.path.join(backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

                    if file_time < cutoff_time:
                        os.remove(filepath)
                        logger.debug(f"清理旧备份: {filename}")
        except Exception as e:
            logger.warning(f"清理旧备份失败: {e}")

    def _recover_from_backup(self, memory_bank: Optional[MemoryBank]) -> MemoryBank:
        """
        从备份恢复

        Args:
            memory_bank: 可选的现有记忆库

        Returns:
            恢复后的记忆库
        """
        try:
            backup_dir = os.path.join(os.path.dirname(self.filepath), "backups")
            if not os.path.exists(backup_dir):
                logger.error("备份目录不存在")
                return memory_bank or MemoryBank()

            # 查找最新的备份文件
            backup_files = []
            for filename in os.listdir(backup_dir):
                if filename.startswith(os.path.basename(self.filepath) + ".backup_"):
                    filepath = os.path.join(backup_dir, filename)
                    backup_files.append((filepath, os.path.getmtime(filepath)))

            if not backup_files:
                logger.error("没有找到备份文件")
                return memory_bank or MemoryBank()

            # 使用最新的备份
            latest_backup = max(backup_files, key=lambda x: x[1])[0]
            logger.warning(f"尝试从备份恢复: {latest_backup}")

            # 加载备份文件
            with open(latest_backup, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            return self._load_with_compatibility(backup_data, memory_bank)

        except Exception as e:
            logger.error(f"从备份恢复失败: {e}")
            return memory_bank or MemoryBank()

    def export_to_file(self, memory_bank: MemoryBank, export_path: str) -> bool:
        """
        导出记忆库到指定文件

        Args:
            memory_bank: 要导出的记忆库
            export_path: 导出文件路径

        Returns:
            导出是否成功
        """
        try:
            # 确保导出目录存在
            export_dir = os.path.dirname(export_path)
            if export_dir and not os.path.exists(export_dir):
                os.makedirs(export_dir, exist_ok=True)

            data = {
                "version": self.FORMAT_VERSION,
                "timestamp": datetime.utcnow().isoformat(),  # 使用timestamp而不是export_timestamp
                "max_entries": memory_bank.max_entries,
                "entries": memory_bank.to_dict(),
                "metadata": {
                    "total_entries": len(memory_bank),
                    "exported_by": "pm-mem",
                    "purpose": "manual_export",
                    "checksum": self._calculate_checksum(memory_bank.to_dict()),
                },
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"记忆库已导出到: {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出记忆库失败: {e}")
            return False

    def import_from_file(self, import_path: str, memory_bank: Optional[MemoryBank] = None) -> MemoryBank:
        """
        从文件导入记忆库

        Args:
            import_path: 导入文件路径
            memory_bank: 可选的现有记忆库实例，如为None则创建新实例

        Returns:
            导入后的记忆库实例
        """
        if not os.path.exists(import_path):
            logger.error(f"导入文件不存在: {import_path}")
            return memory_bank or MemoryBank()

        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查版本
            version = data.get("version", "1.0.0")
            if version not in self.SUPPORTED_VERSIONS:
                logger.warning(
                    f"导入文件版本不支持: {version} (支持版本: {self.SUPPORTED_VERSIONS})"
                )

            # 验证数据完整性
            if not self._validate_data_integrity(data):
                logger.error("导入文件数据完整性验证失败")
                return memory_bank or MemoryBank()

            max_entries = data.get("max_entries", 1000)
            entries_data = data.get("entries", [])

            if memory_bank is None:
                memory_bank = MemoryBank(max_entries=max_entries)
                # 添加所有条目到新创建的记忆库
                imported_count = 0
                for entry_data in entries_data:
                    try:
                        entry = self._load_entry_with_compatibility(entry_data)
                        memory_bank.add(entry)
                        imported_count += 1
                    except Exception as e:
                        logger.warning(f"导入记忆条目失败，跳过: {e}")
                logger.info(f"从 {import_path} 导入了 {imported_count} 条记忆到新记忆库")
            else:
                # 合并记忆库
                existing_ids = {e.id for e in memory_bank.entries}
                imported_count = 0
                for entry_data in entries_data:
                    try:
                        entry = self._load_entry_with_compatibility(entry_data)
                        if entry.id not in existing_ids:
                            memory_bank.add(entry)
                            existing_ids.add(entry.id)
                            imported_count += 1
                    except Exception as e:
                        logger.warning(f"导入记忆条目失败，跳过: {e}")

                logger.info(f"从 {import_path} 导入了 {imported_count} 条记忆到现有记忆库")
            return memory_bank

        except Exception as e:
            logger.error(f"导入记忆库失败: {e}")
            return memory_bank or MemoryBank()

    def backup(self, memory_bank: MemoryBank, backup_dir: str = "./backups") -> Optional[str]:
        """
        创建记忆库备份

        Args:
            memory_bank: 要备份的记忆库
            backup_dir: 备份目录

        Returns:
            备份文件路径，失败时返回None
        """
        try:
            # 创建备份目录
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)

            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"memory_backup_{timestamp}.json")

            if self.export_to_file(memory_bank, backup_path):
                logger.info(f"记忆库备份已创建: {backup_path}")
                return backup_path

        except Exception as e:
            logger.error(f"创建备份失败: {e}")

        return None

    def get_file_info(self) -> Dict[str, Any]:
        """
        获取存储文件信息

        Returns:
            文件信息字典
        """
        if not os.path.exists(self.filepath):
            return {"exists": False, "error": "文件不存在"}

        try:
            stat_info = os.stat(self.filepath)
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            return {
                "exists": True,
                "file_size": stat_info.st_size,
                "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "version": data.get("version", "unknown"),
                "entry_count": len(data.get("entries", [])),
                "max_entries": data.get("max_entries", 1000),
                "integrity_check": self._validate_data_integrity(data),
            }
        except Exception as e:
            return {"exists": True, "error": str(e)}

    def validate_file(self) -> Dict[str, Any]:
        """
        验证存储文件

        Returns:
            验证结果字典
        """
        if not os.path.exists(self.filepath):
            return {"valid": False, "error": "文件不存在"}

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            validation_results = {
                "valid": True,
                "version": data.get("version", "unknown"),
                "version_supported": data.get("version", "unknown") in self.SUPPORTED_VERSIONS,
                "has_required_fields": all(field in data for field in ["version", "timestamp", "entries"]),
                "entries_is_list": isinstance(data.get("entries"), list),
                "entry_count": len(data.get("entries", [])),
                "checksum_valid": True,
            }

            # 验证checksum
            metadata = data.get("metadata", {})
            if "checksum" in metadata:
                expected_checksum = metadata["checksum"]
                actual_checksum = self._calculate_checksum(data["entries"])
                validation_results["checksum_valid"] = expected_checksum == actual_checksum
                validation_results["checksum_match"] = expected_checksum == actual_checksum

            # 检查是否有无效条目
            invalid_entries = []
            for i, entry_data in enumerate(data.get("entries", [])):
                # 先检查必需字段（在_load_entry_with_compatibility修改数据之前）
                required_fields = ["x", "y", "feedback"]
                missing_fields = [field for field in required_fields if field not in entry_data]
                if missing_fields:
                    invalid_entries.append({
                        "index": i,
                        "error": f"缺少必需字段: {missing_fields}",
                        "type": "missing_fields"
                    })
                    continue  # 如果缺少必需字段，跳过加载尝试

                try:
                    # 尝试加载
                    self._load_entry_with_compatibility(entry_data)
                except Exception as e:
                    invalid_entries.append({"index": i, "error": str(e), "type": "load_exception"})

            validation_results["invalid_entries"] = invalid_entries
            validation_results["has_invalid_entries"] = len(invalid_entries) > 0

            # 总体有效性
            validation_results["valid"] = (
                validation_results["version_supported"] and
                validation_results["has_required_fields"] and
                validation_results["entries_is_list"] and
                validation_results["checksum_valid"] and
                not validation_results["has_invalid_entries"]
            )

            return validation_results

        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"JSON解析错误: {e}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}