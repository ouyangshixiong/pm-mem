"""
提示词模板管理器

管理模板的存储、版本控制、分类和检索。
"""

import os
import json
import yaml
import hashlib
from typing import Dict, Any, Optional, List, Union
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from .template_engine import TemplateEngine, TemplateSyntax

logger = logging.getLogger(__name__)


class TemplateCategory(Enum):
    """模板分类"""
    MEMORY_RETRIEVAL = "memory_retrieval"      # 记忆检索
    MEMORY_EDITING = "memory_editing"          # 记忆编辑
    MEMORY_ANALYSIS = "memory_analysis"        # 记忆分析
    AGENT_INTERACTION = "agent_interaction"    # 智能体交互
    SYSTEM_PROMPT = "system_prompt"            # 系统提示
    CUSTOM = "custom"                          # 自定义


class TemplateVersion:
    """模板版本"""

    def __init__(
        self,
        version: str,
        content: str,
        author: str,
        description: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self.version = version
        self.content = content
        self.author = author
        self.description = description or ""
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version": self.version,
            "content": self.content,
            "author": self.author,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateVersion":
        """从字典创建"""
        return cls(
            version=data["version"],
            content=data["content"],
            author=data["author"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class TemplateMetadata:
    """模板元数据"""
    name: str
    category: TemplateCategory
    description: str
    author: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    variables: List[str]
    syntax: TemplateSyntax
    default_context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "variables": self.variables,
            "syntax": self.syntax.value,
            "default_context": self.default_context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateMetadata":
        """从字典创建"""
        return cls(
            name=data["name"],
            category=TemplateCategory(data["category"]),
            description=data["description"],
            author=data["author"],
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            variables=data.get("variables", []),
            syntax=TemplateSyntax(data.get("syntax", "simple")),
            default_context=data.get("default_context", {}),
        )


class Template:
    """模板类"""

    def __init__(
        self,
        template_id: str,
        metadata: TemplateMetadata,
        versions: List[TemplateVersion],
        current_version: str,
    ):
        self.template_id = template_id
        self.metadata = metadata
        self.versions = {v.version: v for v in versions}
        self.current_version = current_version

    def get_version(self, version: Optional[str] = None) -> TemplateVersion:
        """获取指定版本的模板"""
        version_key = version or self.current_version
        if version_key not in self.versions:
            raise ValueError(f"版本 {version_key} 不存在")
        return self.versions[version_key]

    def get_current_content(self) -> str:
        """获取当前版本的内容"""
        return self.get_version().content

    def add_version(
        self,
        content: str,
        author: str,
        description: Optional[str] = None,
        version: Optional[str] = None,
    ) -> str:
        """添加新版本"""
        if not version:
            # 自动生成版本号 (语义化版本: major.minor.patch)
            current = self.current_version
            if current:
                parts = current.split('.')
                if len(parts) == 3:
                    try:
                        major, minor, patch = map(int, parts)
                        patch += 1
                        version = f"{major}.{minor}.{patch}"
                    except ValueError:
                        version = "1.0.0"
                else:
                    version = "1.0.0"
            else:
                version = "1.0.0"

        new_version = TemplateVersion(
            version=version,
            content=content,
            author=author,
            description=description,
        )

        self.versions[version] = new_version
        self.current_version = version
        self.metadata.updated_at = datetime.now()

        # 更新变量列表
        engine = TemplateEngine(self.metadata.syntax)
        self.metadata.variables = engine.get_required_variables(content)

        return version

    def render(self, context: Dict[str, Any], version: Optional[str] = None) -> str:
        """渲染模板"""
        template_content = self.get_version(version).content
        engine = TemplateEngine(self.metadata.syntax)

        # 合并默认上下文
        full_context = self.metadata.default_context.copy()
        full_context.update(context)

        return engine.render(template_content, full_context)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "template_id": self.template_id,
            "metadata": self.metadata.to_dict(),
            "versions": [v.to_dict() for v in self.versions.values()],
            "current_version": self.current_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Template":
        """从字典创建"""
        metadata = TemplateMetadata.from_dict(data["metadata"])
        versions = [TemplateVersion.from_dict(v) for v in data["versions"]]
        return cls(
            template_id=data["template_id"],
            metadata=metadata,
            versions=versions,
            current_version=data["current_version"],
        )


class TemplateManager:
    """模板管理器"""

    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化模板管理器

        Args:
            storage_path: 存储目录路径
        """
        self.storage_path = storage_path or os.path.expanduser("~/.pm-mem/templates")
        self.templates: Dict[str, Template] = {}
        self._engine_cache: Dict[TemplateSyntax, TemplateEngine] = {}

        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)

        # 加载现有模板
        self._load_templates()

    def _get_engine(self, syntax: TemplateSyntax) -> TemplateEngine:
        """获取模板引擎（缓存）"""
        if syntax not in self._engine_cache:
            self._engine_cache[syntax] = TemplateEngine(syntax)
        return self._engine_cache[syntax]

    def _load_templates(self) -> None:
        """从存储目录加载模板"""
        template_files = list(Path(self.storage_path).glob("*.json"))

        for filepath in template_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                template = Template.from_dict(data)
                self.templates[template.template_id] = template

                logger.debug(f"加载模板: {template.template_id}")

            except Exception as e:
                logger.error(f"加载模板文件失败 {filepath}: {e}")

        logger.info(f"已加载 {len(self.templates)} 个模板")

    def _save_template(self, template: Template) -> bool:
        """保存模板到文件"""
        try:
            filepath = os.path.join(self.storage_path, f"{template.template_id}.json")

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)

            logger.debug(f"保存模板: {template.template_id}")
            return True

        except Exception as e:
            logger.error(f"保存模板失败 {template.template_id}: {e}")
            return False

    def _generate_template_id(self, name: str, category: TemplateCategory) -> str:
        """生成模板ID"""
        import uuid
        base_name = f"{category.value}_{name}".lower().replace(' ', '_')
        unique_id = str(uuid.uuid4())[:8]
        return f"{base_name}_{unique_id}"

    def create_template(
        self,
        name: str,
        content: str,
        category: TemplateCategory,
        author: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        syntax: TemplateSyntax = TemplateSyntax.SIMPLE,
        default_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建新模板

        Args:
            name: 模板名称
            content: 模板内容
            category: 模板分类
            author: 作者
            description: 描述
            tags: 标签列表
            syntax: 模板语法
            default_context: 默认上下文

        Returns:
            模板ID
        """
        # 生成模板ID
        template_id = self._generate_template_id(name, category)

        # 检查是否已存在
        if template_id in self.templates:
            raise ValueError(f"模板ID已存在: {template_id}")

        # 创建元数据
        now = datetime.now()
        engine = self._get_engine(syntax)
        variables = engine.get_required_variables(content)

        metadata = TemplateMetadata(
            name=name,
            category=category,
            description=description or "",
            author=author,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            variables=variables,
            syntax=syntax,
            default_context=default_context or {},
        )

        # 创建初始版本
        initial_version = TemplateVersion(
            version="1.0.0",
            content=content,
            author=author,
            description="Initial version",
        )

        # 创建模板
        template = Template(
            template_id=template_id,
            metadata=metadata,
            versions=[initial_version],
            current_version="1.0.0",
        )

        # 保存
        self.templates[template_id] = template
        self._save_template(template)

        logger.info(f"创建模板: {template_id} ({name})")
        return template_id

    def get_template(self, template_id: str) -> Optional[Template]:
        """获取模板"""
        return self.templates.get(template_id)

    def update_template(
        self,
        template_id: str,
        content: str,
        author: str,
        description: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[str]:
        """
        更新模板（添加新版本）

        Args:
            template_id: 模板ID
            content: 新内容
            author: 作者
            description: 版本描述
            version: 版本号（如为None则自动生成）

        Returns:
            新版本号，如失败返回None
        """
        template = self.get_template(template_id)
        if not template:
            logger.error(f"模板不存在: {template_id}")
            return None

        try:
            new_version = template.add_version(
                content=content,
                author=author,
                description=description,
                version=version,
            )

            # 保存
            self._save_template(template)

            logger.info(f"更新模板: {template_id} -> 版本 {new_version}")
            return new_version

        except Exception as e:
            logger.error(f"更新模板失败 {template_id}: {e}")
            return None

    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        if template_id not in self.templates:
            logger.error(f"模板不存在: {template_id}")
            return False

        # 删除文件
        filepath = os.path.join(self.storage_path, f"{template_id}.json")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"删除模板文件失败 {filepath}: {e}")

        # 从内存中删除
        del self.templates[template_id]

        logger.info(f"删除模板: {template_id}")
        return True

    def render_template(
        self,
        template_id: str,
        context: Dict[str, Any],
        version: Optional[str] = None,
    ) -> Optional[str]:
        """
        渲染模板

        Args:
            template_id: 模板ID
            context: 上下文数据
            version: 版本号（如为None使用当前版本）

        Returns:
            渲染后的字符串，如失败返回None
        """
        template = self.get_template(template_id)
        if not template:
            logger.error(f"模板不存在: {template_id}")
            return None

        try:
            return template.render(context, version)
        except Exception as e:
            logger.error(f"渲染模板失败 {template_id}: {e}")
            return None

    def search_templates(
        self,
        query: Optional[str] = None,
        category: Optional[TemplateCategory] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
    ) -> List[Template]:
        """
        搜索模板

        Args:
            query: 搜索关键词（匹配名称和描述）
            category: 分类
            tags: 标签列表
            author: 作者

        Returns:
            匹配的模板列表
        """
        results = []

        for template in self.templates.values():
            # 分类过滤
            if category and template.metadata.category != category:
                continue

            # 作者过滤
            if author and template.metadata.author != author:
                continue

            # 标签过滤
            if tags:
                if not all(tag in template.metadata.tags for tag in tags):
                    continue

            # 关键词搜索
            if query:
                query_lower = query.lower()
                name_match = query_lower in template.metadata.name.lower()
                desc_match = query_lower in template.metadata.description.lower()
                tag_match = any(query_lower in tag.lower() for tag in template.metadata.tags)

                if not (name_match or desc_match or tag_match):
                    continue

            results.append(template)

        # 按更新时间排序（最新的在前）
        results.sort(key=lambda t: t.metadata.updated_at, reverse=True)
        return results

    def get_template_stats(self) -> Dict[str, Any]:
        """获取模板统计信息"""
        total_templates = len(self.templates)

        # 按分类统计
        categories = {}
        for template in self.templates.values():
            category = template.metadata.category.value
            if category not in categories:
                categories[category] = 0
            categories[category] += 1

        # 按语法统计
        syntax_stats = {}
        for template in self.templates.values():
            syntax = template.metadata.syntax.value
            if syntax not in syntax_stats:
                syntax_stats[syntax] = 0
            syntax_stats[syntax] += 1

        # 版本统计
        total_versions = sum(len(t.versions) for t in self.templates.values())

        return {
            "total_templates": total_templates,
            "total_versions": total_versions,
            "categories": categories,
            "syntax_stats": syntax_stats,
            "storage_path": self.storage_path,
        }

    def export_template(self, template_id: str, export_path: str) -> bool:
        """导出模板到文件"""
        template = self.get_template(template_id)
        if not template:
            logger.error(f"模板不存在: {template_id}")
            return False

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"导出模板 {template_id} 到 {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出模板失败 {template_id}: {e}")
            return False

    def import_template(self, import_path: str) -> Optional[str]:
        """从文件导入模板"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            template = Template.from_dict(data)

            # 检查是否已存在
            if template.template_id in self.templates:
                logger.warning(f"模板已存在: {template.template_id}")
                return None

            # 保存
            self.templates[template.template_id] = template
            self._save_template(template)

            logger.info(f"导入模板: {template.template_id}")
            return template.template_id

        except Exception as e:
            logger.error(f"导入模板失败 {import_path}: {e}")
            return None

    def backup_templates(self, backup_dir: Optional[str] = None) -> bool:
        """备份所有模板"""
        try:
            if not backup_dir:
                backup_dir = os.path.join(self.storage_path, "backups")
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"templates_backup_{timestamp}.json")

            # 导出所有模板
            all_templates = {
                template_id: template.to_dict()
                for template_id, template in self.templates.items()
            }

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(all_templates, f, indent=2, ensure_ascii=False)

            logger.info(f"模板已备份到: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"备份模板失败: {e}")
            return False