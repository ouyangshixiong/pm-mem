"""
Markdown-backed work memory manager for short-drama creation.

The public functions in this module are intentionally small and file-based so
the memory store can be inspected and edited by humans without a database.
"""

import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_WORKS_DIR = "works"
AUTHORIZED_LOCK_OPERATORS = {"制片人", "用户手动修改"}

LAYER_DEFINITIONS: List[Dict[str, str]] = [
    {
        "layer_id": "work_metadata",
        "layer_name": "作品元数据层",
        "layer_file": "01_作品元数据层.md",
    },
    {
        "layer_id": "core_setting",
        "layer_name": "核心设定层",
        "layer_file": "02_核心设定层.md",
    },
    {
        "layer_id": "character_profile",
        "layer_name": "人物档案层",
        "layer_file": "03_人物档案层.md",
    },
    {
        "layer_id": "plot_context",
        "layer_name": "情节脉络层",
        "layer_file": "04_情节脉络层.md",
    },
    {
        "layer_id": "script_archive",
        "layer_name": "剧本档案层",
        "layer_file": "05_剧本档案层.md",
    },
    {
        "layer_id": "storyboard_archive",
        "layer_name": "分镜档案层",
        "layer_file": "06_分镜档案层.md",
    },
]

_LAYER_BY_ID = {layer["layer_id"]: layer for layer in LAYER_DEFINITIONS}
_LAYER_BY_NAME = {layer["layer_name"]: layer for layer in LAYER_DEFINITIONS}
_LAYER_BY_FILE = {layer["layer_file"]: layer for layer in LAYER_DEFINITIONS}
_LAYER_BY_STEM = {Path(layer["layer_file"]).stem: layer for layer in LAYER_DEFINITIONS}


def init_work_space() -> bool:
    """Initialize the works directory and global works index."""
    try:
        works_dir = _works_dir()
        works_dir.mkdir(parents=True, exist_ok=True)
        index_path = works_dir / "works_index.yaml"
        if not index_path.exists():
            _write_yaml(index_path, {"works": []})
        return True
    except Exception:
        return False


def create_work(work_name: str) -> str:
    """Create a physically isolated work folder with all six memory layers."""
    if not isinstance(work_name, str) or not work_name.strip():
        raise ValueError("work_name must be a non-empty string")

    if not init_work_space():
        raise RuntimeError("failed to initialize works directory")

    now = _now()
    work_id = str(uuid.uuid4())
    clean_name = work_name.strip()
    work_dir = _work_dir(work_id, must_exist=False)
    work_dir.mkdir(parents=False, exist_ok=False)

    config = {
        "work_id": work_id,
        "work_name": clean_name,
        "create_time": now,
        "update_time": now,
        "status": "active",
        "layer_lock_status": {
            _lock_key(layer): False for layer in LAYER_DEFINITIONS
        },
    }
    _write_yaml(work_dir / ".work_config.yaml", config)

    for layer in LAYER_DEFINITIONS:
        metadata = {
            "layer_id": layer["layer_id"],
            "layer_name": layer["layer_name"],
            "layer_file": layer["layer_file"],
            "locked": False,
            "last_updated": now,
            "updated_by": "系统初始化",
        }
        _write_layer_file(work_dir / layer["layer_file"], metadata, "")

    index = _read_index()
    index.setdefault("works", []).append(
        {
            "work_id": work_id,
            "work_name": clean_name,
            "create_time": now,
            "update_time": now,
            "status": "active",
        }
    )
    _write_index(index)
    return work_id


def list_works() -> List[Dict[str, Any]]:
    """Return all works sorted by update_time descending."""
    init_work_space()
    works = _read_index().get("works", [])
    return sorted(
        works,
        key=lambda item: item.get("update_time", ""),
        reverse=True,
    )


def get_work_layers(work_id: str) -> List[Dict[str, Any]]:
    """Read every layer for a work and return metadata plus content summary."""
    work_dir = _work_dir(work_id)
    layers = []
    for layer in LAYER_DEFINITIONS:
        metadata, content = _read_layer_file(work_dir / layer["layer_file"])
        layers.append(
            {
                "layer_id": metadata["layer_id"],
                "layer_name": metadata["layer_name"],
                "layer_file": metadata["layer_file"],
                "locked": bool(metadata.get("locked", False)),
                "last_updated": metadata.get("last_updated", ""),
                "updated_by": metadata.get("updated_by", ""),
                "import_agent_name": metadata.get("import_agent_name", ""),
                "processed_by_role_id": metadata.get("processed_by_role_id", ""),
                "processed_by_role_name": metadata.get("processed_by_role_name", ""),
                "role_prompt_file": metadata.get("role_prompt_file", ""),
                "role_prompt_hash": metadata.get("role_prompt_hash", ""),
                "llm_provider": metadata.get("llm_provider", ""),
                "llm_processed": bool(metadata.get("llm_processed", False)),
                "llm_model": metadata.get("llm_model", ""),
                "llm_endpoint": metadata.get("llm_endpoint", ""),
                "llm_primary_error": metadata.get("llm_primary_error", ""),
                "llm_error": metadata.get("llm_error", ""),
                "summary": _summarize(content),
                "metadata": metadata,
            }
        )
    return layers


def get_layer_content(work_id: str, layer_id: str) -> Dict[str, Any]:
    """Read one layer and return parsed front matter plus Markdown body."""
    layer = _layer_by_id(layer_id)
    layer_path = _work_dir(work_id) / layer["layer_file"]
    metadata, content = _read_layer_file(layer_path)
    return {
        "work_id": work_id,
        "layer_id": metadata["layer_id"],
        "layer_name": metadata["layer_name"],
        "layer_file": metadata["layer_file"],
        "locked": bool(metadata.get("locked", False)),
        "last_updated": metadata.get("last_updated", ""),
        "updated_by": metadata.get("updated_by", ""),
        "metadata": metadata,
        "content": content,
        "raw_markdown": _format_layer_file(metadata, content),
    }


def update_layer_content(
    work_id: str,
    layer_id: str,
    content: str,
    operator: str,
    lock_status: bool = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Update a layer body and metadata while enforcing layer lock rules."""
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError("operator must be a non-empty string")

    layer = _layer_by_id(layer_id)
    work_dir = _work_dir(work_id)
    layer_path = work_dir / layer["layer_file"]
    metadata, _ = _read_layer_file(layer_path)

    if metadata.get("locked", False) and operator not in AUTHORIZED_LOCK_OPERATORS:
        raise PermissionError("locked layer can only be modified by 制片人 or 用户手动修改")

    now = _now()
    metadata["locked"] = bool(
        metadata.get("locked", False) if lock_status is None else lock_status
    )
    metadata["last_updated"] = now
    metadata["updated_by"] = operator
    if extra_metadata:
        metadata.update(extra_metadata)
    _write_layer_file(layer_path, metadata, content)
    _sync_config_lock_status(work_id, layer["layer_id"], metadata["locked"], now)
    _touch_index(work_id, now)
    return True


def get_layer_definition(layer_id: str) -> Dict[str, str]:
    """Return static layer metadata by layer id."""
    return dict(_layer_by_id(layer_id))


def toggle_layer_lock(work_id: str, layer_id: str, locked: bool) -> bool:
    """Toggle one layer lock state and synchronize work config."""
    layer = _layer_by_id(layer_id)
    work_dir = _work_dir(work_id)
    layer_path = work_dir / layer["layer_file"]
    metadata, content = _read_layer_file(layer_path)
    now = _now()
    metadata["locked"] = bool(locked)
    metadata["last_updated"] = now
    metadata["updated_by"] = "用户手动修改"
    _write_layer_file(layer_path, metadata, content)
    _sync_config_lock_status(work_id, layer_id, bool(locked), now)
    _touch_index(work_id, now)
    return True


def delete_work(work_id: str) -> bool:
    """Delete a work folder and remove it from the global index."""
    work_dir = _work_dir(work_id)
    index = _read_index()
    works = index.get("works", [])
    if not any(item.get("work_id") == work_id for item in works):
        raise FileNotFoundError(f"work not found in index: {work_id}")

    shutil.rmtree(work_dir)
    index["works"] = [item for item in works if item.get("work_id") != work_id]
    _write_index(index)
    return True


def get_layer_content_for_prompt(work_id: str, layer_id_list: list) -> str:
    """Return selected layer bodies formatted for direct prompt injection."""
    if not isinstance(layer_id_list, list):
        raise TypeError("layer_id_list must be a list")

    blocks = []
    for layer_id in layer_id_list:
        layer = _layer_by_id(layer_id)
        layer_data = get_layer_content(work_id, layer_id)
        body = layer_data["content"].strip()
        if body:
            blocks.append(f"## {layer['layer_name']}\n{body}")
        else:
            blocks.append(f"## {layer['layer_name']}\n（暂无内容）")
    return "\n\n".join(blocks)


def update_memory_from_llm_output(work_id: str, llm_output: str, operator: str) -> bool:
    """Parse structured LLM output and evolve unlocked Markdown memory layers."""
    if not isinstance(llm_output, str):
        raise TypeError("llm_output must be a string")
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError("operator must be a non-empty string")

    updates = _extract_memory_updates(llm_output)
    if not updates:
        updates = [
            {
                "layer_id": "script_archive",
                "content": llm_output,
                "mode": "append",
            }
        ]

    changed = False
    for update in updates:
        layer_id = update.get("layer_id")
        content = update.get("content", "")
        mode = update.get("mode", "append")
        if not layer_id or layer_id not in _LAYER_BY_ID or not isinstance(content, str):
            continue

        current = get_layer_content(work_id, layer_id)
        if current.get("locked") and operator not in AUTHORIZED_LOCK_OPERATORS:
            continue

        if mode == "replace":
            next_content = content
        else:
            old_content = current["content"].rstrip()
            next_content = content if not old_content else f"{old_content}\n\n{content.strip()}"

        update_layer_content(work_id, layer_id, next_content, operator)
        changed = True
    return changed


def _works_dir() -> Path:
    env_path = os.getenv("PM_MEM_WORKS_DIR") or os.getenv("WORKS_DIR")
    if env_path:
        return Path(env_path).expanduser()

    config_path = Path("config.yaml")
    if config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            works_dir = (
                data.get("memory", {}).get("works_dir")
                or data.get("memory", {}).get("storage_path")
                or data.get("short_drama", {}).get("works_dir")
            )
            if works_dir:
                return Path(str(works_dir)).expanduser()
        except Exception:
            pass

    return Path(DEFAULT_WORKS_DIR)


def _index_path() -> Path:
    return _works_dir() / "works_index.yaml"


def _read_index() -> Dict[str, Any]:
    init_work_space()
    data = _read_yaml(_index_path())
    if not isinstance(data, dict):
        data = {}
    data.setdefault("works", [])
    return data


def _write_index(index: Dict[str, Any]) -> None:
    _write_yaml(_index_path(), {"works": index.get("works", [])})


def _work_dir(work_id: str, must_exist: bool = True) -> Path:
    _validate_work_id(work_id)
    root = _works_dir().resolve()
    path = (root / work_id).resolve()
    if path != root / work_id and root not in path.parents:
        raise ValueError("invalid work path")
    if must_exist and not path.is_dir():
        raise FileNotFoundError(f"work not found: {work_id}")
    return path


def _validate_work_id(work_id: str) -> None:
    if not isinstance(work_id, str):
        raise TypeError("work_id must be a string")
    try:
        parsed = uuid.UUID(work_id)
    except ValueError as exc:
        raise ValueError(f"invalid work_id: {work_id}") from exc
    if str(parsed) != work_id:
        raise ValueError(f"invalid work_id: {work_id}")


def _layer_by_id(layer_id: str) -> Dict[str, str]:
    if layer_id not in _LAYER_BY_ID:
        raise ValueError(f"unknown layer_id: {layer_id}")
    return _LAYER_BY_ID[layer_id]


def _lock_key(layer: Dict[str, str]) -> str:
    return Path(layer["layer_file"]).stem


def _now() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _write_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)


def _read_layer_file(path: Path) -> Tuple[Dict[str, Any], str]:
    if not path.exists():
        raise FileNotFoundError(f"layer file not found: {path}")

    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"invalid layer front matter: {path}")

    metadata = yaml.safe_load(match.group(1)) or {}
    content = match.group(2)
    _validate_layer_metadata(path, metadata)
    return metadata, content


def _validate_layer_metadata(path: Path, metadata: Dict[str, Any]) -> None:
    layer = _LAYER_BY_FILE.get(metadata.get("layer_file"))
    if not layer:
        raise ValueError(f"unknown layer_file in metadata: {path}")
    for key in ("layer_id", "layer_name", "layer_file", "locked", "last_updated", "updated_by"):
        if key not in metadata:
            raise ValueError(f"missing front matter field {key}: {path}")
    if metadata["layer_id"] != layer["layer_id"] or metadata["layer_name"] != layer["layer_name"]:
        raise ValueError(f"layer metadata does not match fixed mapping: {path}")


def _write_layer_file(path: Path, metadata: Dict[str, Any], content: str) -> None:
    path.write_text(_format_layer_file(metadata, content), encoding="utf-8")


def _format_layer_file(metadata: Dict[str, Any], content: str) -> str:
    ordered = {
        "layer_id": metadata["layer_id"],
        "layer_name": metadata["layer_name"],
        "layer_file": metadata["layer_file"],
        "locked": bool(metadata.get("locked", False)),
        "last_updated": metadata["last_updated"],
        "updated_by": metadata["updated_by"],
    }
    for key, value in metadata.items():
        if key not in ordered:
            ordered[key] = value
    front_matter = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{front_matter}\n---\n{content}"


def _sync_config_lock_status(work_id: str, layer_id: str, locked: bool, update_time: str) -> None:
    work_dir = _work_dir(work_id)
    config_path = work_dir / ".work_config.yaml"
    config = _read_yaml(config_path)
    layer = _layer_by_id(layer_id)
    config.setdefault("layer_lock_status", {})
    config["layer_lock_status"][_lock_key(layer)] = bool(locked)
    config["update_time"] = update_time
    _write_yaml(config_path, config)


def _touch_index(work_id: str, update_time: str) -> None:
    index = _read_index()
    for item in index.get("works", []):
        if item.get("work_id") == work_id:
            item["update_time"] = update_time
            break
    _write_index(index)


def _summarize(content: str, max_length: int = 160) -> str:
    summary = re.sub(r"\s+", " ", content).strip()
    return summary if len(summary) <= max_length else summary[:max_length] + "..."


def _extract_memory_updates(llm_output: str) -> List[Dict[str, str]]:
    json_updates = _extract_json_memory_updates(llm_output)
    if json_updates:
        return json_updates

    tag_updates = _extract_tag_memory_updates(llm_output)
    if tag_updates:
        return tag_updates

    return _extract_heading_memory_updates(llm_output)


def _extract_json_memory_updates(llm_output: str) -> List[Dict[str, str]]:
    candidates = []
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", llm_output, flags=re.DOTALL)
    candidates.extend(fenced)

    start = llm_output.find("{")
    end = llm_output.rfind("}")
    if start != -1 and end > start:
        candidates.append(llm_output[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        raw_updates = data.get("memory_updates") if isinstance(data, dict) else None
        if raw_updates is None and isinstance(data, dict):
            raw_updates = [
                {"layer_id": key, "content": value, "mode": "append"}
                for key, value in data.items()
                if key in _LAYER_BY_ID and isinstance(value, str)
            ]
        if isinstance(raw_updates, list):
            normalized = []
            for item in raw_updates:
                if not isinstance(item, dict):
                    continue
                layer_id = _normalize_layer_ref(str(item.get("layer_id", "")))
                content = item.get("content", "")
                mode = item.get("mode", "append")
                if layer_id and isinstance(content, str):
                    normalized.append(
                        {
                            "layer_id": layer_id,
                            "content": content.strip(),
                            "mode": "replace" if mode == "replace" else "append",
                        }
                    )
            if normalized:
                return normalized
    return []


def _extract_tag_memory_updates(llm_output: str) -> List[Dict[str, str]]:
    updates = []
    for layer in LAYER_DEFINITIONS:
        layer_id = layer["layer_id"]
        pattern = rf"<{layer_id}>(.*?)</{layer_id}>"
        for match in re.findall(pattern, llm_output, flags=re.DOTALL | re.IGNORECASE):
            updates.append(
                {
                    "layer_id": layer_id,
                    "content": match.strip(),
                    "mode": "append",
                }
            )
    return updates


def _extract_heading_memory_updates(llm_output: str) -> List[Dict[str, str]]:
    heading_pattern = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)
    matches = [
        (match, _normalize_layer_ref(match.group(1).strip()))
        for match in heading_pattern.finditer(llm_output)
    ]
    matches = [(match, layer_id) for match, layer_id in matches if layer_id]
    updates = []
    for index, (match, layer_id) in enumerate(matches):
        start = match.end()
        end = matches[index + 1][0].start() if index + 1 < len(matches) else len(llm_output)
        content = llm_output[start:end].strip()
        if content:
            updates.append(
                {
                    "layer_id": layer_id,
                    "content": content,
                    "mode": "append",
                }
            )
    return updates


def _normalize_layer_ref(value: str) -> Optional[str]:
    cleaned = value.strip().strip(":：").strip()
    if cleaned in _LAYER_BY_ID:
        return cleaned
    if cleaned in _LAYER_BY_NAME:
        return _LAYER_BY_NAME[cleaned]["layer_id"]
    if cleaned in _LAYER_BY_FILE:
        return _LAYER_BY_FILE[cleaned]["layer_id"]
    if cleaned in _LAYER_BY_STEM:
        return _LAYER_BY_STEM[cleaned]["layer_id"]
    for layer in LAYER_DEFINITIONS:
        if layer["layer_id"] in cleaned or layer["layer_name"] in cleaned:
            return layer["layer_id"]
    return None
