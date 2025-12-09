"""
持久化存储模块

基于JSON文件的自动保存/加载，支持记忆库的完整导出/导入。
"""

import json
import os
from typing import Optional
import logging
from datetime import datetime

from .bank import MemoryBank
from .entry import MemoryEntry

logger = logging.getLogger(__name__)


class MemoryPersistence:
    """记忆持久化存储管理器"""

    # 当前存储格式版本
    FORMAT_VERSION = "1.0.0"

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
            data = {
                "version": self.FORMAT_VERSION,
                "timestamp": datetime.utcnow().isoformat(),
                "max_entries": memory_bank.max_entries,
                "entries": memory_bank.to_dict(),
                "metadata": {
                    "total_entries": len(memory_bank),
                    "generated_by": "pm-mem",
                },
            }

            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

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
            if version != self.FORMAT_VERSION:
                logger.warning(
                    f"存储文件版本不匹配: {version} (当前版本: {self.FORMAT_VERSION})"
                )

            # 加载记忆条目
            max_entries = data.get("max_entries", 1000)
            entries_data = data.get("entries", [])

            if memory_bank is None:
                memory_bank = MemoryBank(max_entries=max_entries)
            else:
                memory_bank.max_entries = max_entries

            # 清空现有条目并加载新条目
            memory_bank.entries = []
            for entry_data in entries_data:
                try:
                    # 兼容旧格式
                    if "x" not in entry_data and "cue" in entry_data:
                        entry_data["x"] = entry_data["cue"]
                        entry_data["y"] = entry_data.get("response", "")
                        entry_data["feedback"] = entry_data.get("feedback", "")

                    entry = MemoryEntry.from_dict(entry_data)
                    memory_bank.entries.append(entry)
                except Exception as e:
                    logger.warning(f"加载记忆条目失败，跳过: {e}")

            logger.info(f"从 {self.filepath} 加载了 {len(memory_bank)} 条记忆")
            return memory_bank

        except json.JSONDecodeError as e:
            logger.error(f"存储文件格式错误: {e}")
            # 创建新的记忆库
            return memory_bank or MemoryBank()
        except Exception as e:
            logger.error(f"加载记忆库失败: {e}")
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
                "export_timestamp": datetime.utcnow().isoformat(),
                "max_entries": memory_bank.max_entries,
                "entries": memory_bank.to_dict(),
                "metadata": {
                    "total_entries": len(memory_bank),
                    "exported_by": "pm-mem",
                    "purpose": "manual_export",
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
            if version != self.FORMAT_VERSION:
                logger.warning(
                    f"导入文件版本不匹配: {version} (当前版本: {self.FORMAT_VERSION})"
                )

            max_entries = data.get("max_entries", 1000)
            entries_data = data.get("entries", [])

            if memory_bank is None:
                memory_bank = MemoryBank(max_entries=max_entries)
            else:
                # 合并记忆库
                existing_ids = {e.id for e in memory_bank.entries}
                for entry_data in entries_data:
                    try:
                        entry = MemoryEntry.from_dict(entry_data)
                        if entry.id not in existing_ids:
                            memory_bank.add(entry)
                            existing_ids.add(entry.id)
                    except Exception as e:
                        logger.warning(f"导入记忆条目失败，跳过: {e}")

                logger.info(f"从 {import_path} 导入了 {len(entries_data)} 条记忆（合并后新增 {len(memory_bank) - len(existing_ids) + len(entries_data)} 条）")
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