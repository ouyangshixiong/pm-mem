"""
增强的模板管理器

支持模板的版本控制、分类管理、继承关系、依赖分析等高级功能。
"""

import os
import json
import yaml
import hashlib
from typing import Dict, Any, Optional, List, Set, Tuple, Union
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import re

from .template_engine_enhanced import EnhancedTemplateEngine, render_template

logger = logging.getLogger(__name__)


class TemplateCategory(Enum):
    """模板分类"""
    SYSTEM = "system"          # 系统模板
    USER = "user"              # 用户模板
    CUSTOM = "custom"          # 自定义模板
    SHARED = "shared"          # 共享模板


class TemplateStatus(Enum):
    """模板状态"""
    ACTIVE = "active"          # 活跃
    DEPRECATED = "deprecated"  # 已弃用
    DRAFT = "draft"            # 草稿
    ARCHIVED = "archived"      # 已归档


@dataclass
class TemplateMetadata:
    """模板元数据"""
    template_id: str
    name: str
    description: str
    category: TemplateCategory
    status: TemplateStatus
    version: str
    author: str
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    dependencies: List[str]  # 依赖的其他模板ID
    variables: Dict[str, Any]  # 模板变量定义
    validation_rules: Dict[str, Any]  # 验证规则
    usage_count: int = 0
    last_used: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["category"] = self.category.value
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        if self.last_used:
            data["last_used"] = self.last_used.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateMetadata":
        """从字典创建"""
        data = data.copy()
        data["category"] = TemplateCategory(data["category"])
        data["status"] = TemplateStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("last_used"):
            data["last_used"] = datetime.fromisoformat(data["last_used"])
        return cls(**data)


@dataclass
class TemplateVersion:
    """模板版本"""
    version: str
    content: str
    metadata: TemplateMetadata
    created_at: datetime
    checksum: str
    change_log: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version": self.version,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
            "change_log": self.change_log,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateVersion":
        """从字典创建"""
        data = data.copy()
        data["metadata"] = TemplateMetadata.from_dict(data["metadata"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class EnhancedTemplateManager:
    """增强的模板管理器"""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        template_dirs: Optional[List[str]] = None,
        auto_load: bool = True,
    ):
        """
        初始化模板管理器

        Args:
            storage_path: 模板存储路径
            template_dirs: 模板目录列表
            auto_load: 是否自动加载模板
        """
        self.storage_path = storage_path or os.path.expanduser("~/.pm-mem/templates")
        self.template_dirs = template_dirs or ["./templates"]
        self.engine = EnhancedTemplateEngine(template_dirs)

        # 模板存储
        self._templates: Dict[str, TemplateVersion] = {}
        self._metadata_index: Dict[str, TemplateMetadata] = {}
        self._category_index: Dict[TemplateCategory, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}

        # 初始化索引
        for category in TemplateCategory:
            self._category_index[category] = set()

        # 自动加载模板
        if auto_load:
            self.load_templates()

        logger.info(f"增强的模板管理器已初始化，存储路径: {self.storage_path}")

    def _ensure_storage_dir(self) -> None:
        """确保存储目录存在"""
        os.makedirs(self.storage_path, exist_ok=True)

    def _get_template_path(self, template_id: str) -> str:
        """获取模板文件路径"""
        return os.path.join(self.storage_path, f"{template_id}.json")

    def _calculate_checksum(self, content: str) -> str:
        """计算内容校验和"""
        return hashlib.md5(content.encode()).hexdigest()

    def _generate_template_id(self, name: str, category: TemplateCategory) -> str:
        """生成模板ID"""
        # 使用名称、分类和时间戳生成唯一ID
        timestamp = int(datetime.now().timestamp() * 1000)
        base_id = f"{category.value}_{name.lower().replace(' ', '_')}"
        hash_input = f"{base_id}_{timestamp}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def _update_indices(self, metadata: TemplateMetadata, add: bool = True) -> None:
        """更新索引"""
        template_id = metadata.template_id

        if add:
            # 添加到索引
            self._metadata_index[template_id] = metadata
            self._category_index[metadata.category].add(template_id)

            for tag in metadata.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(template_id)
        else:
            # 从索引移除
            if template_id in self._metadata_index:
                old_metadata = self._metadata_index[template_id]

                # 从分类索引移除
                self._category_index[old_metadata.category].discard(template_id)

                # 从标签索引移除
                for tag in old_metadata.tags:
                    if tag in self._tag_index:
                        self._tag_index[tag].discard(template_id)
                        if not self._tag_index[tag]:
                            del self._tag_index[tag]

                del self._metadata_index[template_id]

    def load_templates(self) -> int:
        """加载所有模板"""
        self._ensure_storage_dir()

        loaded_count = 0
        template_files = list(Path(self.storage_path).glob("*.json"))

        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                template_version = TemplateVersion.from_dict(data)
                template_id = template_version.metadata.template_id

                # 存储模板
                self._templates[template_id] = template_version
                self._update_indices(template_version.metadata, add=True)

                loaded_count += 1
                logger.debug(f"已加载模板: {template_id}")

            except Exception as e:
                logger.error(f"加载模板文件失败 {template_file}: {e}")

        logger.info(f"已加载 {loaded_count} 个模板")
        return loaded_count

    def save_template(self, template_version: TemplateVersion) -> bool:
        """保存模板"""
        try:
            self._ensure_storage_dir()

            template_id = template_version.metadata.template_id
            template_path = self._get_template_path(template_id)

            # 转换为字典并保存
            data = template_version.to_dict()
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # 更新内存中的模板
            self._templates[template_id] = template_version
            self._update_indices(template_version.metadata, add=True)

            logger.info(f"已保存模板: {template_id} (版本: {template_version.version})")
            return True

        except Exception as e:
            logger.error(f"保存模板失败: {e}")
            return False

    def create_template(
        self,
        name: str,
        content: str,
        description: str = "",
        category: TemplateCategory = TemplateCategory.CUSTOM,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        variables: Optional[Dict[str, Any]] = None,
        validation_rules: Optional[Dict[str, Any]] = None,
        author: str = "system",
        version: str = "1.0.0",
        change_log: str = "初始版本",
    ) -> Optional[str]:
        """
        创建新模板

        Args:
            name: 模板名称
            content: 模板内容
            description: 模板描述
            category: 模板分类
            tags: 标签列表
            dependencies: 依赖的模板ID列表
            variables: 变量定义
            validation_rules: 验证规则
            author: 作者
            version: 版本号
            change_log: 变更日志

        Returns:
            模板ID，如失败返回None
        """
        try:
            # 生成模板ID
            template_id = self._generate_template_id(name, category)

            # 检查是否已存在
            if template_id in self._templates:
                logger.warning(f"模板已存在: {template_id}")
                return template_id

            # 创建元数据
            now = datetime.now()
            metadata = TemplateMetadata(
                template_id=template_id,
                name=name,
                description=description,
                category=category,
                status=TemplateStatus.ACTIVE,
                version=version,
                author=author,
                created_at=now,
                updated_at=now,
                tags=tags or [],
                dependencies=dependencies or [],
                variables=variables or {},
                validation_rules=validation_rules or {},
                usage_count=0,
                last_used=None,
            )

            # 创建版本
            checksum = self._calculate_checksum(content)
            template_version = TemplateVersion(
                version=version,
                content=content,
                metadata=metadata,
                created_at=now,
                checksum=checksum,
                change_log=change_log,
            )

            # 保存模板
            if self.save_template(template_version):
                return template_id
            else:
                return None

        except Exception as e:
            logger.error(f"创建模板失败: {e}")
            return None

    def get_template(self, template_id: str, version: Optional[str] = None) -> Optional[TemplateVersion]:
        """获取模板"""
        if template_id not in self._templates:
            return None

        template_version = self._templates[template_id]

        # 如果指定了版本，检查版本是否匹配
        if version and template_version.version != version:
            logger.warning(f"请求的版本 {version} 与当前版本 {template_version.version} 不匹配")
            # 在实际实现中，这里应该支持多版本管理

        # 更新使用统计
        template_version.metadata.usage_count += 1
        template_version.metadata.last_used = datetime.now()

        return template_version

    def render_template(
        self,
        template_id: str,
        context: Dict[str, Any],
        version: Optional[str] = None,
        validate: bool = True,
    ) -> Optional[str]:
        """
        渲染模板

        Args:
            template_id: 模板ID
            context: 上下文变量
            version: 模板版本
            validate: 是否验证上下文

        Returns:
            渲染后的字符串，如失败返回None
        """
        try:
            # 获取模板
            template_version = self.get_template(template_id, version)
            if not template_version:
                logger.error(f"模板未找到: {template_id}")
                return None

            # 验证上下文（如果启用）
            if validate:
                validation_result = self.validate_context(
                    template_version.metadata, context
                )
                if not validation_result["valid"]:
                    logger.error(f"上下文验证失败: {validation_result['errors']}")
                    return None

            # 渲染模板
            result = self.engine.render(template_version.content, context)

            # 保存更新后的元数据
            self.save_template(template_version)

            return result

        except Exception as e:
            logger.error(f"渲染模板失败 {template_id}: {e}")
            return None

    def update_template(
        self,
        template_id: str,
        content: Optional[str] = None,
        metadata_updates: Optional[Dict[str, Any]] = None,
        version: str = "auto",
        change_log: str = "更新",
    ) -> bool:
        """
        更新模板

        Args:
            template_id: 模板ID
            content: 新的模板内容
            metadata_updates: 元数据更新
            version: 新版本号，"auto"表示自动递增
            change_log: 变更日志

        Returns:
            更新是否成功
        """
        if template_id not in self._templates:
            logger.error(f"模板未找到: {template_id}")
            return False

        try:
            old_version = self._templates[template_id]
            old_metadata = old_version.metadata

            # 准备新版本
            new_content = content if content is not None else old_version.content

            # 自动生成版本号
            if version == "auto":
                current_version = old_version.version
                if "." in current_version:
                    parts = current_version.split(".")
                    parts[-1] = str(int(parts[-1]) + 1)
                    new_version = ".".join(parts)
                else:
                    new_version = f"{current_version}.1"
            else:
                new_version = version

            # 更新元数据
            new_metadata_dict = old_metadata.to_dict()
            if metadata_updates:
                # 合并更新
                for key, value in metadata_updates.items():
                    if key in new_metadata_dict:
                        if key == "category":
                            value = TemplateCategory(value)
                        elif key == "status":
                            value = TemplateStatus(value)
                        elif key == "tags" and isinstance(value, str):
                            value = [tag.strip() for tag in value.split(",")]
                        new_metadata_dict[key] = value

            new_metadata_dict["updated_at"] = datetime.now().isoformat()
            new_metadata_dict["version"] = new_version

            new_metadata = TemplateMetadata.from_dict(new_metadata_dict)

            # 创建新版本
            checksum = self._calculate_checksum(new_content)
            new_version_obj = TemplateVersion(
                version=new_version,
                content=new_content,
                metadata=new_metadata,
                created_at=datetime.now(),
                checksum=checksum,
                change_log=change_log,
            )

            # 保存新版本
            if self.save_template(new_version_obj):
                logger.info(f"已更新模板: {template_id} (版本: {new_version})")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"更新模板失败 {template_id}: {e}")
            return False

    def delete_template(self, template_id: str, permanent: bool = False) -> bool:
        """
        删除模板

        Args:
            template_id: 模板ID
            permanent: 是否永久删除（否则标记为已归档）

        Returns:
            删除是否成功
        """
        if template_id not in self._templates:
            logger.error(f"模板未找到: {template_id}")
            return False

        try:
            if permanent:
                # 永久删除
                template_path = self._get_template_path(template_id)
                if os.path.exists(template_path):
                    os.remove(template_path)

                # 从内存中移除
                self._update_indices(self._templates[template_id].metadata, add=False)
                del self._templates[template_id]

                logger.info(f"已永久删除模板: {template_id}")
            else:
                # 标记为已归档
                self.update_template(
                    template_id,
                    metadata_updates={"status": TemplateStatus.ARCHIVED.value},
                    change_log="标记为已归档",
                )
                logger.info(f"已归档模板: {template_id}")

            return True

        except Exception as e:
            logger.error(f"删除模板失败 {template_id}: {e}")
            return False

    def search_templates(
        self,
        query: Optional[str] = None,
        category: Optional[TemplateCategory] = None,
        tags: Optional[List[str]] = None,
        status: Optional[TemplateStatus] = None,
        author: Optional[str] = None,
        limit: int = 50,
    ) -> List[TemplateMetadata]:
        """搜索模板"""
        results = []

        for template_id, metadata in self._metadata_index.items():
            # 应用过滤器
            if category and metadata.category != category:
                continue
            if status and metadata.status != status:
                continue
            if author and metadata.author != author:
                continue
            if tags and not any(tag in metadata.tags for tag in tags):
                continue

            # 文本搜索
            if query:
                query_lower = query.lower()
                text_to_search = f"{metadata.name} {metadata.description} {' '.join(metadata.tags)}".lower()
                if query_lower not in text_to_search:
                    continue

            results.append(metadata)

            # 限制结果数量
            if len(results) >= limit:
                break

        # 按使用次数排序
        results.sort(key=lambda x: x.usage_count, reverse=True)

        return results

    def validate_context(
        self, metadata: TemplateMetadata, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证上下文变量"""
        errors = []
        warnings = []

        # 检查必需变量
        for var_name, var_def in metadata.variables.items():
            if isinstance(var_def, dict) and var_def.get("required", False):
                if var_name not in context:
                    errors.append(f"缺少必需变量: {var_name}")

        # 检查变量类型
        for var_name, var_value in context.items():
            if var_name in metadata.variables:
                var_def = metadata.variables[var_name]
                expected_type = var_def.get("type")

                if expected_type:
                    type_ok = False
                    if expected_type == "string":
                        type_ok = isinstance(var_value, str)
                    elif expected_type == "number":
                        type_ok = isinstance(var_value, (int, float))
                    elif expected_type == "boolean":
                        type_ok = isinstance(var_value, bool)
                    elif expected_type == "list":
                        type_ok = isinstance(var_value, list)
                    elif expected_type == "dict":
                        type_ok = isinstance(var_value, dict)

                    if not type_ok:
                        warnings.append(f"变量 {var_name} 类型不匹配，期望 {expected_type}")

        # 应用验证规则
        if metadata.validation_rules:
            # 这里可以添加更复杂的验证逻辑
            pass

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def get_template_stats(self) -> Dict[str, Any]:
        """获取模板统计信息"""
        total_templates = len(self._templates)

        # 按分类统计
        by_category = {}
        for category, template_ids in self._category_index.items():
            by_category[category.value] = len(template_ids)

        # 按状态统计
        by_status = {}
        status_counts = {}
        for metadata in self._metadata_index.values():
            status = metadata.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        by_status = status_counts

        # 最常用的模板
        most_used = sorted(
            self._metadata_index.values(),
            key=lambda x: x.usage_count,
            reverse=True
        )[:5]

        most_used_list = [
            {"id": m.template_id, "name": m.name, "usage_count": m.usage_count}
            for m in most_used
        ]

        return {
            "total_templates": total_templates,
            "by_category": by_category,
            "by_status": by_status,
            "most_used": most_used_list,
            "storage_path": self.storage_path,
        }

    def export_templates(
        self,
        output_path: str,
        template_ids: Optional[List[str]] = None,
        include_metadata: bool = True,
    ) -> bool:
        """导出模板"""
        try:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "templates": [],
            }

            templates_to_export = template_ids or list(self._templates.keys())

            for template_id in templates_to_export:
                if template_id in self._templates:
                    template_version = self._templates[template_id]
                    export_data["templates"].append(template_version.to_dict())

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"已导出 {len(export_data['templates'])} 个模板到 {output_path}")
            return True

        except Exception as e:
            logger.error(f"导出模板失败: {e}")
            return False

    def import_templates(self, import_path: str, overwrite: bool = False) -> int:
        """导入模板"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            imported_count = 0

            for template_data in import_data.get("templates", []):
                try:
                    template_version = TemplateVersion.from_dict(template_data)
                    template_id = template_version.metadata.template_id

                    # 检查是否已存在
                    if template_id in self._templates and not overwrite:
                        logger.warning(f"模板已存在，跳过: {template_id}")
                        continue

                    # 保存模板
                    if self.save_template(template_version):
                        imported_count += 1

                except Exception as e:
                    logger.error(f"导入单个模板失败: {e}")
                    continue

            logger.info(f"已导入 {imported_count} 个模板")
            return imported_count

        except Exception as e:
            logger.error(f"导入模板失败: {e}")
            return 0


# 全局模板管理器实例
_template_manager: Optional[EnhancedTemplateManager] = None


def get_template_manager(
    storage_path: Optional[str] = None,
    reload: bool = False,
) -> EnhancedTemplateManager:
    """
    获取全局模板管理器实例

    Args:
        storage_path: 存储路径
        reload: 是否重新加载

    Returns:
        模板管理器实例
    """
    global _template_manager

    if _template_manager is None or reload:
        _template_manager = EnhancedTemplateManager(storage_path)

    return _template_manager


def render_template_by_id(
    template_id: str,
    context: Dict[str, Any],
    version: Optional[str] = None,
) -> Optional[str]:
    """
    通过ID渲染模板（快捷函数）

    Args:
        template_id: 模板ID
        context: 上下文变量
        version: 模板版本

    Returns:
        渲染后的字符串
    """
    manager = get_template_manager()
    return manager.render_template(template_id, context, version)


# 预定义系统模板
SYSTEM_TEMPLATES = {
    "llm_prompt_basic": {
        "name": "基础LLM提示词模板",
        "description": "用于基础LLM交互的模板",
        "content": """你是一个AI助手。请根据以下上下文回答问题：

上下文：
{{ context }}

问题：{{ question }}

请提供详细、准确的回答。""",
        "variables": {
            "context": {"type": "string", "required": True},
            "question": {"type": "string", "required": True},
        },
        "tags": ["llm", "prompt", "basic"],
    },
    "code_generation": {
        "name": "代码生成模板",
        "description": "用于生成代码的模板",
        "content": """请为以下需求生成{{ language }}代码：

需求描述：
{{ requirement }}

具体要求：
{{ requirements }}

请生成完整、可运行的代码，并添加适当的注释。""",
        "variables": {
            "language": {"type": "string", "required": True, "default": "python"},
            "requirement": {"type": "string", "required": True},
            "requirements": {"type": "string", "required": False},
        },
        "tags": ["code", "generation", "programming"],
    },
    "summary_generation": {
        "name": "摘要生成模板",
        "description": "用于生成文本摘要的模板",
        "content": """请为以下文本生成摘要：

原文：
{{ text }}

摘要要求：
- 长度：{{ length }}字以内
- 语言：{{ language }}
- 重点：{{ focus }}

请生成简洁、准确的摘要。""",
        "variables": {
            "text": {"type": "string", "required": True},
            "length": {"type": "number", "required": False, "default": 200},
            "language": {"type": "string", "required": False, "default": "中文"},
            "focus": {"type": "string", "required": False},
        },
        "tags": ["summary", "text", "generation"],
    },
}


def initialize_system_templates(manager: Optional[EnhancedTemplateManager] = None) -> int:
    """初始化系统模板"""
    if manager is None:
        manager = get_template_manager()

    created_count = 0

    for template_id, template_def in SYSTEM_TEMPLATES.items():
        # 检查是否已存在
        if manager.get_template(template_id):
            continue

        # 创建模板
        template_id_created = manager.create_template(
            name=template_def["name"],
            content=template_def["content"],
            description=template_def["description"],
            category=TemplateCategory.SYSTEM,
            tags=template_def["tags"],
            variables=template_def.get("variables", {}),
            author="system",
            version="1.0.0",
            change_log="系统初始化",
        )

        if template_id_created:
            created_count += 1

    logger.info(f"已初始化 {created_count} 个系统模板")
    return created_count