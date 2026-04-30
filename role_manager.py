"""Role prompt configuration helpers for pm-mem import agents."""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_ROLES_DIR = "roles"

LAYER_ROLE_ASSIGNMENTS: Dict[str, str] = {
    "work_metadata": "制片人",
    "core_setting": "制片人",
    "character_profile": "编剧",
    "plot_context": "编剧",
    "script_archive": "编剧",
    "storyboard_archive": "分镜师",
}


def list_roles() -> List[Dict[str, Any]]:
    """Return all configured role prompts from the roles directory."""
    roles_dir = _roles_dir()
    if not roles_dir.is_dir():
        return []

    roles = []
    for path in sorted(roles_dir.glob("*.md"), key=lambda item: item.stem):
        role = _role_from_path(path)
        if role is not None:
            roles.append(role)
    return roles


def get_role_config(role_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Read one role prompt by role id, usually the filename stem."""
    if not role_id:
        return None

    safe_role_id = Path(str(role_id)).name.replace(".md", "")
    role_path = _roles_dir() / f"{safe_role_id}.md"
    if not role_path.is_file():
        return {
            "role_id": safe_role_id,
            "role_name": safe_role_id,
            "role_file": str(role_path),
            "prompt": "",
            "prompt_hash": "",
            "missing": True,
        }
    return _role_from_path(role_path)


def get_layer_role_id(layer_id: str) -> str:
    """Return the default configured role for a memory layer."""
    return LAYER_ROLE_ASSIGNMENTS.get(layer_id, "")


def get_layer_role_assignments() -> Dict[str, str]:
    """Return a copy of the layer-to-role mapping for API display."""
    return dict(LAYER_ROLE_ASSIGNMENTS)


def _roles_dir() -> Path:
    env_path = os.getenv("PM_MEM_ROLES_DIR") or os.getenv("ROLES_DIR")
    if env_path:
        return Path(env_path).expanduser()
    return Path(DEFAULT_ROLES_DIR)


def _role_from_path(path: Path) -> Optional[Dict[str, Any]]:
    try:
        prompt = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None

    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest() if prompt else ""
    return {
        "role_id": path.stem,
        "role_name": path.stem,
        "role_file": str(path),
        "prompt": prompt,
        "prompt_hash": prompt_hash,
        "missing": False,
    }
