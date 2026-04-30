"""
FastAPI Web manager for short-drama Markdown memories.

Run with:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import yaml

import memory_manager
from import_coordinator import (
    ExternalWorkImportCoordinator,
    build_external_work_payload,
)
from local_llm_client import LocalResponsesLLMClient, load_import_llm_settings
from local_llm_client import DeepSeekChatLLMClient
import role_manager
from src.agent.remem_agent import ReMemAgent
from src.agent.roles import RoleFactory
from src.memory.llm_retrieval import (
    DEFAULT_MAX_CHUNK_CHARS,
    DEFAULT_MAX_RESULT_CHARS,
    DEFAULT_TOP_K,
    LLMWorkRetriever,
)
from src.memory.schema import TaskContext
from src.memory.stores import MarkdownLayerMemoryStore, MarkdownTraceStore


app = FastAPI(title="短剧创作系统 - 记忆管理")


class CreateWorkRequest(BaseModel):
    work_name: str


class UpdateLayerRequest(BaseModel):
    content: str
    locked: Optional[bool] = None


class ExternalWorkImportRequest(BaseModel):
    external_work_id: str
    work_name: str
    source_system: str = "外部创作系统"
    source_url: str = ""
    story: str = ""
    script: str = ""
    storyboard_script: str = ""
    images: List[str] = Field(default_factory=list)
    raw_payload: Optional[Dict[str, Any]] = None
    dry_run: bool = False


class ReMemTaskRequest(BaseModel):
    task_type: str = "generic_workflow_step"
    role_id: str = "screenwriter"
    task: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    query: str
    work_id: str = ""
    work_name: str = ""
    role_id: str = "screenwriter"
    target_layers: List[str] = Field(default_factory=list)
    top_k: int = DEFAULT_TOP_K
    include_answer: bool = True
    include_content: bool = True
    answer_instructions: str = ""
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS
    min_score: float = 0.0


class DeepSeekApiKeyUpdateRequest(BaseModel):
    api_key: str = ""


class RolePromptUpdateRequest(BaseModel):
    prompt: str


@app.get("/", response_class=HTMLResponse)
def index_page() -> HTMLResponse:
    return HTMLResponse(_layout("短剧创作系统 - 记忆管理", _home_body(), _home_script()))


@app.get("/settings", response_class=HTMLResponse)
def settings_page() -> HTMLResponse:
    return HTMLResponse(_layout("系统配置", _settings_body(), _settings_script()))


@app.get("/work/{work_id}", response_class=HTMLResponse)
def work_page(work_id: str) -> HTMLResponse:
    _ensure_work_exists(work_id)
    return HTMLResponse(
        _layout(
            "作品管理",
            _work_body(),
            _work_script(work_id),
        )
    )


@app.get("/work/{work_id}/layer/{layer_id}", response_class=HTMLResponse)
def layer_page(work_id: str, layer_id: str) -> HTMLResponse:
    _ensure_work_exists(work_id)
    try:
        memory_manager.get_layer_content(work_id, layer_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return HTMLResponse(
        _layout(
            "记忆层编辑",
            _layer_body(),
            _layer_script(work_id, layer_id),
        )
    )


@app.get("/api/works")
def api_list_works() -> Any:
    return memory_manager.list_works()


@app.post("/api/works")
def api_create_work(payload: CreateWorkRequest) -> Dict[str, Any]:
    try:
        work_id = memory_manager.create_work(payload.work_name)
        return _work_payload(work_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/works/{work_id}")
def api_delete_work(work_id: str) -> Dict[str, Any]:
    try:
        return {"success": memory_manager.delete_work(work_id)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/works/{work_id}")
def api_get_work(work_id: str) -> Dict[str, Any]:
    try:
        return _work_payload(work_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/works/{work_id}/layers/{layer_id}")
def api_get_layer(work_id: str, layer_id: str) -> Dict[str, Any]:
    try:
        work = _find_work(work_id)
        layer = memory_manager.get_layer_content(work_id, layer_id)
        role_id = (
            layer.get("metadata", {}).get("processed_by_role_id")
            or role_manager.get_layer_role_id(layer_id)
        )
        role = role_manager.get_role_config(role_id)
        return {"work": work, "layer": layer, "role": role}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/works/{work_id}/layers/{layer_id}")
def api_update_layer(
    work_id: str,
    layer_id: str,
    payload: UpdateLayerRequest,
) -> Dict[str, Any]:
    try:
        success = memory_manager.update_layer_content(
            work_id=work_id,
            layer_id=layer_id,
            content=payload.content,
            operator="用户手动修改",
            lock_status=payload.locked,
        )
        return {
            "success": success,
            "layer": memory_manager.get_layer_content(work_id, layer_id),
        }
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/works/{work_id}/remem-task")
def api_run_remem_task(work_id: str, payload: ReMemTaskRequest) -> Dict[str, Any]:
    if not payload.task.strip():
        raise HTTPException(status_code=400, detail="task is required")

    try:
        _ensure_work_exists(work_id)
        role = RoleFactory.create(payload.role_id)
        metadata = dict(payload.metadata or {})
        metadata["work_id"] = work_id
        context = TaskContext(
            task_type=payload.task_type,
            source="web_api",
            role_id=role.role_id,
            metadata=metadata,
        )
        llm = _LocalGenerateAdapter()
        agent = ReMemAgent(
            llm=llm,
            memory_store=MarkdownLayerMemoryStore(),
            trace_store=MarkdownTraceStore(),
        )
        result = agent.run_task(payload.task, role=role, context=context)
        return {
            "success": True,
            "task_id": result.get("task_id"),
            "role": result.get("role"),
            "action_output": result.get("action_output"),
            "retrieved_memories": result.get("retrieved_memories", []),
            "think_traces": result.get("think_traces", []),
            "refine_operations": result.get("refine_operations", []),
            "applied_operations": result.get("applied_operations", []),
            "conflicts": result.get("conflicts", []),
            "memory_updated": result.get("memory_updated", False),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/works/{work_id}/retrieve")
def api_retrieve_work_memory(
    work_id: str,
    payload: RetrievalRequest,
) -> Dict[str, Any]:
    try:
        _ensure_work_exists(work_id)
        return _run_retrieval(work_id, payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/retrieve")
def api_retrieve_memory(payload: RetrievalRequest) -> Dict[str, Any]:
    try:
        work_id = payload.work_id.strip() or _find_work_id_by_name(payload.work_name)
        return _run_retrieval(work_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/works/{work_id}/traces")
def api_list_work_traces(work_id: str, limit: int = 20) -> Dict[str, Any]:
    try:
        _ensure_work_exists(work_id)
        return {"traces": memory_manager.get_work_traces(work_id, limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/works/{work_id}/traces/{task_id}")
def api_get_work_trace(work_id: str, task_id: str) -> Dict[str, Any]:
    try:
        _ensure_work_exists(work_id)
        return memory_manager.get_work_trace(work_id, task_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/import/external-work")
def api_import_external_work(payload: ExternalWorkImportRequest) -> Dict[str, Any]:
    if not payload.external_work_id.strip():
        raise HTTPException(status_code=400, detail="external_work_id is required")
    if not payload.work_name.strip():
        raise HTTPException(status_code=400, detail="work_name is required")

    try:
        normalized_payload = build_external_work_payload(
            source_system=payload.source_system,
            external_work_id=payload.external_work_id,
            work_name=payload.work_name,
            source_url=payload.source_url,
            story=payload.story,
            script=payload.script,
            storyboard_script=payload.storyboard_script,
            images=payload.images,
            raw_payload=payload.raw_payload,
        )
        return ExternalWorkImportCoordinator().import_work(
            normalized_payload,
            dry_run=payload.dry_run,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/roles")
def api_list_roles() -> Dict[str, Any]:
    return {
        "roles": role_manager.list_roles(),
        "layer_roles": role_manager.get_layer_role_assignments(),
    }


@app.get("/api/import/llm-config")
def api_get_import_llm_config() -> Dict[str, Any]:
    return load_import_llm_settings().public_dict()


@app.put("/api/import/deepseek-api-key")
def api_update_deepseek_api_key(
    payload: DeepSeekApiKeyUpdateRequest,
) -> Dict[str, Any]:
    try:
        _save_deepseek_api_key(payload.api_key)
        return load_import_llm_settings().public_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/roles/{role_id}")
def api_update_role_prompt(
    role_id: str,
    payload: RolePromptUpdateRequest,
) -> Dict[str, Any]:
    try:
        return {"role": role_manager.update_role_prompt(role_id, payload.prompt)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class _LocalGenerateAdapter:
    """Callable wrapper with local proxy primary and DeepSeek backup."""

    def __init__(self):
        self.settings = load_import_llm_settings()
        self.client = LocalResponsesLLMClient(self.settings)
        self.backup_client = DeepSeekChatLLMClient(self.settings.deepseek_backup)
        self.last_provider = "local_proxy_responses"
        self.last_error = ""

    def __call__(self, prompt: str) -> str:
        primary_error = ""
        try:
            text = self.client.generate(prompt)
            if text.strip():
                self.last_provider = "local_proxy_responses"
                self.last_error = ""
                return text
            primary_error = "local proxy LLM returned empty content"
        except Exception as exc:
            primary_error = str(exc)

        try:
            text = self.backup_client.generate(prompt)
            if text.strip():
                self.last_provider = "deepseek_backup"
                self.last_error = primary_error
                return text
            backup_error = "DeepSeek returned empty content"
        except Exception as exc:
            backup_error = str(exc)

        self.last_error = (
            f"local_proxy_responses: {primary_error}; "
            f"deepseek_backup: {backup_error}"
        )
        raise RuntimeError(self.last_error)

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model": self.settings.model,
            "provider": self.last_provider,
            "context_length_tokens": 64000,
        }


def _work_payload(work_id: str) -> Dict[str, Any]:
    return {
        "work": _find_work(work_id),
        "layers": [
            _enrich_layer(layer) for layer in memory_manager.get_work_layers(work_id)
        ],
    }


def _find_work(work_id: str) -> Dict[str, Any]:
    for work in memory_manager.list_works():
        if work.get("work_id") == work_id:
            return work
    raise FileNotFoundError(f"work not found: {work_id}")


def _find_work_id_by_name(work_name: str) -> str:
    name = str(work_name or "").strip()
    if not name:
        raise ValueError("work_id or work_name is required")
    matches = [
        work
        for work in memory_manager.list_works()
        if str(work.get("work_name") or "").strip() == name
    ]
    if not matches:
        raise FileNotFoundError(f"work not found by name: {name}")
    if len(matches) > 1:
        raise ValueError(f"multiple works found by name: {name}; use work_id instead")
    return str(matches[0]["work_id"])


def _ensure_work_exists(work_id: str) -> None:
    try:
        _find_work(work_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _run_retrieval(work_id: str, payload: RetrievalRequest) -> Dict[str, Any]:
    if not payload.query.strip():
        raise ValueError("query is required")

    work = _find_work(work_id)
    role = RoleFactory.create(payload.role_id)
    metadata = {"target_layers": payload.target_layers} if payload.target_layers else {}
    policy = role.retrieval_policy(
        TaskContext(
            task_type="memory_retrieval",
            source="web_api",
            role_id=role.role_id,
            metadata=metadata,
        )
    )
    target_layers = payload.target_layers or list(policy.get("target_layers") or [])

    llm = _LocalGenerateAdapter()
    retriever = LLMWorkRetriever(
        llm,
        max_prompt_chars=load_import_llm_settings().max_prompt_chars,
    )
    result = retriever.retrieve(
        work_id=work_id,
        query=payload.query,
        layer_ids=target_layers,
        top_k=payload.top_k,
        include_answer=payload.include_answer,
        answer_instructions=payload.answer_instructions,
        max_chunk_chars=payload.max_chunk_chars,
        min_score=payload.min_score,
    )
    data = result.to_dict(
        include_content=payload.include_content,
        max_result_chars=payload.max_result_chars,
    )
    data.update(
        {
            "success": True,
            "work": work,
            "role": role.to_dict(),
            "llm": {
                "provider": llm.last_provider,
                "model": llm.settings.model
                if llm.last_provider == "local_proxy_responses"
                else llm.settings.deepseek_backup.model,
                "primary_model": llm.settings.model,
                "deepseek_backup_model": llm.settings.deepseek_backup.model,
                "last_error": llm.last_error,
            },
        }
    )
    return data


def _save_deepseek_api_key(api_key: str) -> None:
    config_path = Path(os.getenv("PM_MEM_CONFIG") or "config.yaml").expanduser()
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            data = {}
    else:
        data = {}

    backup = data.setdefault("deepseek_backup", {})
    if not isinstance(backup, dict):
        backup = {}
        data["deepseek_backup"] = backup
    backup["api_key"] = str(api_key or "").strip()

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _enrich_layer(layer: Dict[str, Any]) -> Dict[str, Any]:
    role_id = layer.get("processed_by_role_id") or role_manager.get_layer_role_id(
        layer["layer_id"]
    )
    role = role_manager.get_role_config(role_id)
    enriched = dict(layer)
    enriched["default_role_id"] = role_id
    enriched["default_role_name"] = role.get("role_name", role_id) if role else role_id
    enriched["role_missing"] = bool(role.get("missing")) if role else True
    return enriched


def _layout(title: str, body: str, script: str) -> str:
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ background: #f6f7f9; color: #1f2933; }}
    .page-shell {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px 48px; }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }}
    .panel {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; }}
    .table td, .table th {{ vertical-align: middle; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    .preview {{ min-height: 520px; max-height: 72vh; overflow: auto; background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; }}
    .editor {{ min-height: 520px; max-height: 72vh; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .status-line {{ min-height: 24px; }}
    .lock-badge {{ color: #b42318; background: #fee4e2; border: 1px solid #fecdca; }}
    .unlock-badge {{ color: #027a48; background: #dcfae6; border: 1px solid #abefc6; }}
    .process-badge {{ color: #175cd3; background: #d1e9ff; border: 1px solid #84caff; }}
    .muted-badge {{ color: #475467; background: #f2f4f7; border: 1px solid #d0d5dd; }}
    .prompt-box {{ white-space: pre-wrap; background: #f8fafc; border: 1px solid #d9dee7; border-radius: 8px; padding: 12px; font-size: 13px; line-height: 1.55; }}
    .role-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    .role-item {{ border: 1px solid #d9dee7; border-radius: 8px; padding: 12px; background: #fff; }}
    .evolution-list {{ display: flex; flex-direction: column; border: 1px solid #eaecf0; border-radius: 8px; overflow: hidden; background: #fff; }}
    .evolution-row {{ width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 16px; align-items: center; border: 0; border-bottom: 1px solid #eaecf0; background: #fff; padding: 12px 14px; text-align: left; color: inherit; }}
    .evolution-row:last-child {{ border-bottom: 0; }}
    .evolution-row:hover, .evolution-row:focus {{ background: #f8fbff; outline: none; }}
    .evolution-row.is-updated {{ box-shadow: inset 4px 0 0 #2e90fa; }}
    .evolution-row-main {{ min-width: 0; }}
    .evolution-row-summary {{ color: #1f2933; font-weight: 700; line-height: 1.45; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .evolution-row-meta {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 6px; }}
    .evolution-row-action {{ color: #175cd3; font-weight: 700; white-space: nowrap; }}
    .task-input {{ margin-top: 10px; border-left: 3px solid #d0d5dd; background: #f8fafc; border-radius: 0 6px 6px 0; padding: 8px 10px; }}
    .task-input-label {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; color: #667085; font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
    .task-input-note {{ color: #667085; font-weight: 500; }}
    .task-input-text {{ color: #344054; line-height: 1.58; word-break: break-word; }}
    .trace-time {{ min-width: 138px; text-align: right; }}
    .trace-time-main {{ display: block; color: #1f2933; font-weight: 700; white-space: nowrap; }}
    .trace-time-sub {{ color: #667085; font-size: 12px; margin-top: 2px; }}
    .evolution-drawer-backdrop {{ position: fixed; inset: 0; background: rgba(16, 24, 40, 0.38); opacity: 0; pointer-events: none; transition: opacity 160ms ease; z-index: 1040; }}
    .evolution-drawer-backdrop.is-open {{ opacity: 1; pointer-events: auto; }}
    .evolution-drawer {{ position: fixed; top: 0; right: 0; width: min(760px, 92vw); height: 100vh; background: #fff; box-shadow: -18px 0 36px rgba(16, 24, 40, 0.18); transform: translateX(100%); transition: transform 180ms ease; z-index: 1041; display: flex; flex-direction: column; }}
    .evolution-drawer.is-open {{ transform: translateX(0); }}
    .drawer-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; padding: 18px 20px; border-bottom: 1px solid #eaecf0; }}
    .drawer-title {{ font-size: 20px; font-weight: 800; line-height: 1.35; margin: 0; }}
    .drawer-subtitle {{ color: #667085; margin-top: 6px; }}
    .drawer-body {{ padding: 18px 20px 28px; overflow: auto; }}
    .drawer-close {{ flex: 0 0 auto; }}
    .drawer-section {{ margin-bottom: 18px; }}
    .drawer-section-title {{ color: #475467; font-size: 13px; font-weight: 800; margin-bottom: 8px; }}
    .change-list {{ margin-top: 12px; border-top: 1px solid #eaecf0; }}
    .change-item {{ padding-top: 12px; }}
    .change-header {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }}
    .change-grid {{ display: grid; grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.25fr); gap: 12px; }}
    .change-pane {{ min-width: 0; border-left: 3px solid #cfd4dc; padding: 10px 12px; background: #f8fafc; border-radius: 0 6px 6px 0; }}
    .change-pane.after {{ border-left-color: #2e90fa; background: #f5fbff; }}
    .change-pane.before-empty {{ color: #667085; background: #fbfcfe; }}
    .change-label {{ color: #667085; font-size: 12px; font-weight: 700; margin-bottom: 6px; }}
    .change-text {{ color: #1f2933; line-height: 1.62; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; }}
    .change-empty-state {{ margin-top: 12px; color: #667085; background: #f8fafc; border-left: 3px solid #d0d5dd; border-radius: 0 6px 6px 0; padding: 10px 12px; }}
    h1 {{ font-size: 26px; line-height: 1.25; margin: 0; }}
    h2 {{ font-size: 20px; margin: 0 0 14px; }}
    .breadcrumb {{ margin-bottom: 16px; }}
    @media (max-width: 768px) {{
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .editor, .preview {{ min-height: 360px; max-height: none; }}
      .evolution-row {{ grid-template-columns: 1fr; }}
      .evolution-row-summary {{ white-space: normal; }}
      .trace-time {{ min-width: 0; text-align: left; }}
      .change-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page-shell">
    {body}
  </main>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    function escapeHtml(value) {{
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}
    function showMessage(id, text, tone = 'success') {{
      const el = document.getElementById(id);
      if (!el) return;
      el.className = 'status-line small ' + (tone === 'danger' ? 'text-danger' : 'text-success');
      el.textContent = text;
    }}
    async function requestJson(url, options = {{}}) {{
      const response = await fetch(url, options);
      const text = await response.text();
      let data = null;
      try {{ data = text ? JSON.parse(text) : null; }} catch (err) {{ data = text; }}
      if (!response.ok) {{
        const detail = data && data.detail ? data.detail : response.statusText;
        throw new Error(detail);
      }}
      return data;
    }}
    function renderMarkdown(source) {{
      let text = escapeHtml(source);
      text = text.replace(/^###\\s+(.+)$/gm, '<h5>$1</h5>');
      text = text.replace(/^##\\s+(.+)$/gm, '<h4>$1</h4>');
      text = text.replace(/^#\\s+(.+)$/gm, '<h3>$1</h3>');
      text = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
      text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
      text = text.replace(/^[-*]\\s+(.+)$/gm, '<div class="ms-3">• $1</div>');
      text = text.replace(/\\n/g, '<br>');
      return text || '<span class="text-secondary">暂无内容</span>';
    }}
    function parseDisplayDate(value) {{
      const source = String(value ?? '').trim();
      if (!source) return null;
      let normalized = source;
      if (normalized.includes('T') && !/[zZ]|[+-]\\d{{2}}:?\\d{{2}}$/.test(normalized)) {{
        normalized += 'Z';
      }} else if (!normalized.includes('T')) {{
        normalized = normalized.replace(' ', 'T');
      }}
      const date = new Date(normalized);
      if (Number.isNaN(date.getTime())) return null;
      return date;
    }}
    function formatDisplayTime(value) {{
      const date = parseDisplayDate(value);
      if (!date) return String(value ?? '');
      const dateText = new Intl.DateTimeFormat('zh-CN', {{
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }}).format(date).replaceAll('/', '-');
      const timeText = new Intl.DateTimeFormat('zh-CN', {{
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }}).format(date);
      return `${{dateText}} ${{timeText}}`;
    }}
    function formatTraceTime(value) {{
      const date = parseDisplayDate(value);
      if (!date) return String(value ?? '');
      const now = new Date();
      const sameDay = date.getFullYear() === now.getFullYear()
        && date.getMonth() === now.getMonth()
        && date.getDate() === now.getDate();
      const timeText = new Intl.DateTimeFormat('zh-CN', {{
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }}).format(date);
      if (sameDay) return `今天 ${{timeText}}`;
      return formatDisplayTime(value);
    }}
    function formatRelativeTime(value) {{
      const date = parseDisplayDate(value);
      if (!date) return '';
      const diffMs = Date.now() - date.getTime();
      const absMs = Math.abs(diffMs);
      if (absMs > 7 * 24 * 60 * 60 * 1000) return '';
      if (diffMs < -60 * 1000) return '稍后';
      if (diffMs < 60 * 1000) return '刚刚';
      const minutes = Math.floor(diffMs / (60 * 1000));
      if (minutes < 60) return `${{minutes}} 分钟前`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${{hours}} 小时前`;
      const days = Math.floor(hours / 24);
      return `${{days}} 天前`;
    }}
  </script>
  <script>{script}</script>
</body>
</html>"""


def _home_body() -> str:
    return """
<div class="topbar">
  <div>
    <h1>短剧创作系统 - 记忆管理</h1>
    <div class="text-secondary mt-1">作品管理与分层记忆查看/修改</div>
  </div>
  <div class="d-flex align-items-center gap-2">
    <a class="btn btn-outline-secondary" href="/settings">系统配置</a>
    <button class="btn btn-primary" onclick="createWork()">新增作品</button>
  </div>
</div>
<section class="panel">
  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead>
        <tr>
          <th>作品名称</th>
          <th>作品ID</th>
          <th>创建时间</th>
          <th>最后更新时间</th>
          <th>状态</th>
          <th class="text-end">操作</th>
        </tr>
      </thead>
      <tbody id="worksBody"></tbody>
    </table>
  </div>
  <div id="status" class="status-line small"></div>
</section>
"""


def _home_script() -> str:
    return """
async function loadWorks() {
  const body = document.getElementById('worksBody');
  body.innerHTML = '<tr><td colspan="6" class="text-secondary">加载中...</td></tr>';
  try {
    const works = await requestJson('/api/works');
    if (!works.length) {
      body.innerHTML = '<tr><td colspan="6" class="text-secondary">暂无作品</td></tr>';
      return;
    }
    body.innerHTML = works.map(work => `
      <tr>
        <td>${escapeHtml(work.work_name)}</td>
        <td class="mono">${escapeHtml(work.work_id)}</td>
        <td>${escapeHtml(formatDisplayTime(work.create_time))}</td>
        <td>${escapeHtml(formatDisplayTime(work.update_time))}</td>
        <td><span class="badge text-bg-light">${escapeHtml(work.status)}</span></td>
        <td class="text-end">
          <a class="btn btn-sm btn-outline-primary" href="/work/${encodeURIComponent(work.work_id)}">进入管理</a>
          <button class="btn btn-sm btn-outline-danger ms-1" onclick="deleteWork('${escapeHtml(work.work_id)}')">删除</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    body.innerHTML = '<tr><td colspan="6" class="text-danger">加载失败：' + escapeHtml(err.message) + '</td></tr>';
  }
}
async function createWork() {
  const workName = window.prompt('请输入作品名称');
  if (!workName || !workName.trim()) return;
  try {
    await requestJson('/api/works', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({work_name: workName.trim()})
    });
    showMessage('status', '作品已创建');
    loadWorks();
  } catch (err) {
    showMessage('status', err.message, 'danger');
  }
}
async function deleteWork(workId) {
  if (!window.confirm('确认删除该作品？此操作会删除整个作品文件夹。')) return;
  try {
    await requestJson('/api/works/' + encodeURIComponent(workId), {method: 'DELETE'});
    showMessage('status', '作品已删除');
    loadWorks();
  } catch (err) {
    showMessage('status', err.message, 'danger');
  }
}
loadWorks();
"""


def _settings_body() -> str:
    return """
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="/">首页</a></li>
    <li class="breadcrumb-item active">系统配置</li>
  </ol>
</nav>
<div class="topbar">
  <div>
    <h1>系统配置</h1>
    <div class="text-secondary mt-1">跨作品生效的模型调用与角色 Prompt 配置</div>
  </div>
  <a class="btn btn-outline-secondary" href="/">返回首页</a>
</div>
<section class="panel mb-3">
  <div class="d-flex align-items-start justify-content-between gap-3 mb-2">
    <h2>导入模型</h2>
    <span id="llmEnabledBadge" class="badge muted-badge">读取中</span>
  </div>
  <div class="row g-3" id="llmMeta"></div>
  <div class="row g-2 align-items-end mt-3">
    <div class="col-md-8">
      <label class="form-label text-secondary small" for="deepseekApiKey">DeepSeek API Key</label>
      <input class="form-control" id="deepseekApiKey" type="password" autocomplete="off" placeholder="输入新的 API Key；留空不修改">
    </div>
    <div class="col-md-4">
      <button class="btn btn-primary w-100" onclick="saveDeepSeekApiKey()">保存 DeepSeek Key</button>
    </div>
  </div>
  <div class="text-secondary small mt-2">出于安全考虑，页面只显示是否已配置，不回显已保存的 Key。</div>
</section>
<section class="panel">
  <h2>角色 Prompt 配置</h2>
  <div class="role-grid" id="rolesBody"></div>
</section>
<div id="status" class="status-line small mt-3"></div>
"""


def _settings_script() -> str:
    return """
async function loadSettings() {
  try {
    const [rolesData, llmConfig] = await Promise.all([
      requestJson('/api/roles'),
      requestJson('/api/import/llm-config')
    ]);
    renderLlmConfig(llmConfig);
    renderRoles(rolesData.roles || []);
  } catch (err) {
    showMessage('status', err.message, 'danger');
  }
}
function renderLlmConfig(config) {
  const primary = config.primary || config;
  const backup = config.deepseek_backup || {};
  const badge = document.getElementById('llmEnabledBadge');
  badge.className = 'badge process-badge';
  badge.textContent = '默认调用';
  document.getElementById('llmMeta').innerHTML = `
    <div class="col-md-4"><div class="text-secondary small">Primary Endpoint</div><div class="mono">${escapeHtml(primary.endpoint)}</div></div>
    <div class="col-md-4"><div class="text-secondary small">Primary Model</div><div class="mono">${escapeHtml(primary.model)}</div></div>
    <div class="col-md-4"><div class="text-secondary small">DeepSeek Backup</div><div>${backup.api_key_configured ? '已配置' : '未配置 API Key'}</div><div class="mono small">${escapeHtml(backup.model || '')}</div></div>
    <div class="col-md-8"><div class="text-secondary small">DeepSeek Endpoint</div><div class="mono">${escapeHtml(backup.endpoint || '')}</div></div>
    <div class="col-md-4"><div class="text-secondary small">Fallback</div><div>两路失败即中断</div></div>
  `;
}
async function saveDeepSeekApiKey() {
  const input = document.getElementById('deepseekApiKey');
  const value = input.value.trim();
  if (!value) {
    showMessage('status', '请输入新的 DeepSeek API Key', 'danger');
    return;
  }
  try {
    const config = await requestJson('/api/import/deepseek-api-key', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({api_key: value})
    });
    input.value = '';
    renderLlmConfig(config);
    showMessage('status', 'DeepSeek API Key 已保存');
  } catch (err) {
    showMessage('status', err.message, 'danger');
  }
}
function renderRoles(roles) {
  const body = document.getElementById('rolesBody');
  if (!roles.length) {
    body.innerHTML = '<div class="text-secondary">暂无角色配置</div>';
    return;
  }
  body.innerHTML = roles.map(role => `
    <details class="role-item" data-role-id="${escapeHtml(role.role_id)}">
      <summary><strong>${escapeHtml(role.role_name)}</strong> <span class="mono text-secondary">${escapeHtml(role.role_file)}</span></summary>
      <textarea class="form-control editor mt-2" id="rolePrompt_${escapeHtml(role.role_id)}" spellcheck="false">${escapeHtml(role.prompt)}</textarea>
      <div class="d-flex align-items-center gap-2 mt-2">
        <button class="btn btn-sm btn-primary" onclick="saveRolePrompt('${escapeHtml(role.role_id)}')">保存 Prompt</button>
        <span class="status-line small" id="roleStatus_${escapeHtml(role.role_id)}"></span>
      </div>
    </details>
  `).join('');
}
async function saveRolePrompt(roleId) {
  const editor = document.getElementById('rolePrompt_' + roleId);
  const status = document.getElementById('roleStatus_' + roleId);
  if (!editor) return;
  try {
    const data = await requestJson('/api/roles/' + encodeURIComponent(roleId), {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: editor.value})
    });
    editor.value = (data.role || {}).prompt || editor.value;
    if (status) {
      status.className = 'status-line small text-success';
      status.textContent = '已保存';
    }
  } catch (err) {
    if (status) {
      status.className = 'status-line small text-danger';
      status.textContent = err.message;
    } else {
      showMessage('status', err.message, 'danger');
    }
  }
}
loadSettings();
"""


def _work_body() -> str:
    return """
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="/">首页</a></li>
    <li class="breadcrumb-item active" id="breadcrumbName">作品</li>
  </ol>
</nav>
<div class="topbar">
  <div>
    <h1 id="workName">作品管理</h1>
    <div class="text-secondary mt-1 mono" id="workId"></div>
  </div>
  <div class="d-flex align-items-center gap-2">
    <a class="btn btn-outline-secondary" href="/settings">系统配置</a>
    <a class="btn btn-outline-secondary" href="/">返回首页</a>
  </div>
</div>
<section class="panel mb-3">
  <div class="row g-3" id="workMeta"></div>
</section>
<section class="panel mb-3">
  <div class="d-flex align-items-start justify-content-between gap-3 mb-2">
    <h2>记忆演化</h2>
    <button class="btn btn-sm btn-outline-secondary" onclick="loadTraces()">刷新</button>
  </div>
  <div class="evolution-list" id="tracesBody"></div>
  <div class="evolution-drawer-backdrop" id="traceDrawerBackdrop" onclick="closeTraceDrawer()"></div>
  <aside class="evolution-drawer" id="traceDrawer" aria-hidden="true" aria-label="记忆演化详情">
    <div class="drawer-head">
      <div>
        <div class="drawer-title" id="traceDrawerTitle">记忆演化详情</div>
        <div class="drawer-subtitle" id="traceDrawerSubtitle"></div>
      </div>
      <button class="btn btn-sm btn-outline-secondary drawer-close" onclick="closeTraceDrawer()">关闭</button>
    </div>
    <div class="drawer-body" id="traceDrawerBody"></div>
  </aside>
</section>
<section class="panel">
  <h2>分层记忆</h2>
  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead>
        <tr>
          <th>分层名称</th>
          <th>文件名</th>
          <th>锁定状态</th>
          <th>处理角色</th>
          <th>模型处理</th>
          <th>最后更新时间</th>
          <th>操作人</th>
          <th class="text-end">操作</th>
        </tr>
      </thead>
      <tbody id="layersBody"></tbody>
    </table>
  </div>
  <div id="status" class="status-line small"></div>
</section>
"""


def _work_script(work_id: str) -> str:
    return f"""
const WORK_ID = {json.dumps(work_id, ensure_ascii=False)};
let currentTraces = [];
async function loadWork() {{
  try {{
    const [data, tracesData] = await Promise.all([
      requestJson('/api/works/' + encodeURIComponent(WORK_ID)),
      requestJson('/api/works/' + encodeURIComponent(WORK_ID) + '/traces')
    ]);
    const work = data.work;
    document.getElementById('breadcrumbName').textContent = work.work_name;
    document.getElementById('workName').textContent = work.work_name;
    document.getElementById('workId').textContent = work.work_id;
    document.getElementById('workMeta').innerHTML = `
      <div class="col-md-4"><div class="text-secondary small">作品ID</div><div class="mono">${{escapeHtml(work.work_id)}}</div></div>
      <div class="col-md-4"><div class="text-secondary small">创建时间</div><div>${{escapeHtml(formatDisplayTime(work.create_time))}}</div></div>
      <div class="col-md-4"><div class="text-secondary small">最后更新时间</div><div>${{escapeHtml(formatDisplayTime(work.update_time))}}</div></div>
    `;
    renderTraces(tracesData.traces || []);
    document.getElementById('layersBody').innerHTML = data.layers.map(layer => `
      <tr>
        <td>${{escapeHtml(layer.layer_name)}}</td>
        <td class="mono">${{escapeHtml(layer.layer_file)}}</td>
        <td>${{layer.locked ? '<span class="badge lock-badge">已锁定</span>' : '<span class="badge unlock-badge">未锁定</span>'}}</td>
        <td>${{renderLayerRole(layer)}}</td>
        <td>${{renderLayerLlm(layer)}}</td>
        <td>${{escapeHtml(formatDisplayTime(layer.last_updated))}}</td>
        <td>${{escapeHtml(layer.updated_by)}}</td>
        <td class="text-end">
          <a class="btn btn-sm btn-outline-primary" href="/work/${{encodeURIComponent(WORK_ID)}}/layer/${{encodeURIComponent(layer.layer_id)}}">编辑</a>
        </td>
      </tr>
    `).join('');
  }} catch (err) {{
    showMessage('status', err.message, 'danger');
  }}
}}
function renderLayerRole(layer) {{
  const roleName = layer.processed_by_role_name || layer.default_role_name || layer.default_role_id || '';
  if (!roleName) return '<span class="text-secondary">未配置</span>';
  const suffix = layer.processed_by_role_name ? '' : '<div class="small text-secondary">默认角色</div>';
  return `${{escapeHtml(roleName)}}${{suffix}}`;
}}
function renderLayerLlm(layer) {{
  if (layer.llm_processed) {{
    const provider = layer.llm_provider ? `<div class="small text-secondary">${{escapeHtml(layer.llm_provider)}}</div>` : '';
    return `<span class="badge process-badge">${{escapeHtml(layer.llm_model || '已调用')}}</span>${{provider}}`;
  }}
  if (layer.llm_error) {{
    return '<span class="badge lock-badge">调用失败</span>';
  }}
  return '<span class="badge muted-badge">未记录</span>';
}}
async function loadTraces() {{
  try {{
    const data = await requestJson('/api/works/' + encodeURIComponent(WORK_ID) + '/traces');
    renderTraces(data.traces || []);
  }} catch (err) {{
    showMessage('status', err.message, 'danger');
  }}
}}
function renderTraces(traces) {{
  const body = document.getElementById('tracesBody');
  currentTraces = traces;
  closeTraceDrawer();
  if (!traces.length) {{
    body.innerHTML = '<div class="change-empty-state">暂无演化轨迹</div>';
    return;
  }}
  body.innerHTML = traces.map((trace, index) => `
    <button class="evolution-row ${{trace.memory_updated ? 'is-updated' : ''}}" type="button" onclick="openTraceDrawer(${{index}})">
      <div class="evolution-row-main">
        <div class="evolution-row-summary">${{escapeHtml(traceSummary(trace))}}</div>
        <div class="evolution-row-meta">
          ${{renderTraceLayers(trace)}}
          <span class="badge ${{trace.memory_updated ? 'unlock-badge' : 'muted-badge'}}">${{trace.memory_updated ? '已写入记忆' : '未写入'}}</span>
          <span class="badge process-badge">${{escapeHtml(trace.status || 'unknown')}}</span>
          <span class="text-secondary small">${{escapeHtml((trace.role || {{}}).role_name || (trace.role || {{}}).role_id || '未记录角色')}}</span>
          <span class="text-secondary small">${{escapeHtml(trace.event_count || 0)}} 个事件</span>
        </div>
      </div>
      <div>
        ${{renderTraceTime(trace.finished_at || trace.started_at)}}
        <div class="evolution-row-action">查看详情</div>
      </div>
    </button>
  `).join('');
}}
function traceSummary(trace) {{
  const roleName = (trace.role || {{}}).role_name || (trace.role || {{}}).role_id || '未知角色';
  const change = (trace.changes || [])[0] || {{}};
  const layerName = change.layer_name || ((trace.target_layers || [])[0] || {{}}).layer_name || '未知分层';
  const layerFile = change.layer_file || ((trace.target_layers || [])[0] || {{}}).layer_file || layerName;
  const operation = change.operation_label || (trace.memory_updated ? '写入' : '处理');
  const lengthText = change.content_length ? `，约 ${{change.content_length}} 字` : '';
  return `${{roleName}} 向 ${{layerFile}} ${{operation}}了记忆${{lengthText}}`;
}}
function renderTraceLayers(trace) {{
  const layers = trace.target_layers || [];
  if (!layers.length) return '<span class="badge muted-badge">未记录分层</span>';
  return layers.map(layer => `
    <span class="badge muted-badge">${{escapeHtml(layer.layer_name || layer.layer_id || '未知分层')}}</span>
  `).join('');
}}
function renderTraceTime(value) {{
  const raw = escapeHtml(value || '');
  const display = escapeHtml(formatTraceTime(value));
  const relative = formatRelativeTime(value);
  return `
    <div class="trace-time">
      <time class="trace-time-main" datetime="${{raw}}" title="${{raw}}">${{display}}</time>
      ${{relative ? `<div class="trace-time-sub">${{escapeHtml(relative)}}</div>` : ''}}
    </div>
  `;
}}
function openTraceDrawer(index) {{
  const trace = currentTraces[index];
  if (!trace) return;
  const title = traceSummary(trace);
  const subtitle = `${{formatTraceTime(trace.finished_at || trace.started_at)}} · ${{escapeHtml((trace.role || {{}}).role_name || (trace.role || {{}}).role_id || '未记录角色')}} · ${{escapeHtml(trace.task_id || '')}}`;
  document.getElementById('traceDrawerTitle').textContent = title;
  document.getElementById('traceDrawerSubtitle').textContent = subtitle;
  document.getElementById('traceDrawerBody').innerHTML = `
    <div class="drawer-section">
      <div class="drawer-section-title">演化任务输入</div>
      <div class="task-input">
        <div class="task-input-label">
          <span>工作流给 ReMem 的任务目标</span>
          <span class="task-input-note">不是角色 Prompt</span>
        </div>
        <div class="task-input-text">${{escapeHtml(trace.task_input || '未记录任务')}}</div>
      </div>
    </div>
    <div class="drawer-section">
      <div class="drawer-section-title">文字变化</div>
      ${{renderTraceChanges(trace)}}
    </div>
  `;
  document.getElementById('traceDrawerBackdrop').classList.add('is-open');
  document.getElementById('traceDrawer').classList.add('is-open');
  document.getElementById('traceDrawer').setAttribute('aria-hidden', 'false');
}}
function closeTraceDrawer() {{
  const drawer = document.getElementById('traceDrawer');
  const backdrop = document.getElementById('traceDrawerBackdrop');
  if (!drawer || !backdrop) return;
  drawer.classList.remove('is-open');
  backdrop.classList.remove('is-open');
  drawer.setAttribute('aria-hidden', 'true');
}}
function renderTraceChanges(trace) {{
  const changes = trace.changes || [];
  if (!changes.length) {{
    return '<div class="change-empty-state">本次轨迹没有记录新的记忆文字。</div>';
  }}
  const overflow = trace.change_count > changes.length
    ? `<div class="text-secondary small mt-2">还有 ${{trace.change_count - changes.length}} 条写入未在列表中展开。</div>`
    : '';
  return `<div class="change-list">${{changes.map(renderTraceChange).join('')}}${{overflow}}</div>`;
}}
function renderTraceChange(change) {{
  const beforeClass = change.before_empty ? 'change-pane before-empty' : 'change-pane';
  const beforeLabel = change.before_empty ? '演化前为空' : '演化前检索快照';
  const beforeText = change.before_empty
    ? '本次演化开始前，该分层没有正文内容；右侧是本次新增写入的文字。'
    : (change.before_excerpt || '未记录演化前快照');
  const lengthText = change.content_length ? `${{change.content_length}} 字` : '';
  return `
    <div class="change-item">
      <div class="change-header">
        <span class="badge unlock-badge">${{escapeHtml(change.operation_label || '演化')}}</span>
        <strong>${{escapeHtml(change.layer_name || change.layer_id || '未知分层')}}</strong>
        ${{lengthText ? `<span class="text-secondary small">写入 ${{escapeHtml(lengthText)}}</span>` : ''}}
      </div>
      <div class="change-grid">
        <div class="${{beforeClass}}">
          <div class="change-label">${{escapeHtml(beforeLabel)}}</div>
          <div class="change-text">${{escapeHtml(beforeText)}}</div>
        </div>
        <div class="change-pane after">
          <div class="change-label">本次写入文字</div>
          <div class="change-text">${{escapeHtml(change.after_excerpt || '未记录写入文本')}}</div>
        </div>
      </div>
    </div>
  `;
}}
loadWork();
"""


def _layer_body() -> str:
    return """
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="/">首页</a></li>
    <li class="breadcrumb-item"><a id="workLink" href="#">作品</a></li>
    <li class="breadcrumb-item active" id="breadcrumbLayer">记忆层</li>
  </ol>
</nav>
<div class="topbar">
  <div>
    <h1 id="layerName">记忆层编辑</h1>
    <div class="text-secondary mt-1" id="layerMeta"></div>
  </div>
  <div class="d-flex align-items-center gap-3">
    <div class="form-check form-switch">
      <input class="form-check-input" type="checkbox" role="switch" id="lockSwitch">
      <label class="form-check-label" for="lockSwitch">锁定</label>
    </div>
    <a class="btn btn-outline-secondary" id="backLink" href="#">返回作品详情</a>
  </div>
</div>
<section class="panel mb-3">
  <h2>导入处理</h2>
  <div class="row g-3 mb-3" id="processMeta"></div>
  <div id="rolePromptBlock"></div>
</section>
<div class="row g-3">
  <div class="col-lg-6">
    <textarea class="form-control editor" id="contentEditor" spellcheck="false"></textarea>
  </div>
  <div class="col-lg-6">
    <div class="preview" id="preview"></div>
  </div>
</div>
<div class="d-flex align-items-center gap-2 mt-3">
  <button class="btn btn-primary" onclick="saveLayer(false)">保存修改</button>
  <span id="status" class="status-line small"></span>
</div>
"""


def _layer_script(work_id: str, layer_id: str) -> str:
    return f"""
const WORK_ID = {json.dumps(work_id, ensure_ascii=False)};
const LAYER_ID = {json.dumps(layer_id, ensure_ascii=False)};
const editor = document.getElementById('contentEditor');
const preview = document.getElementById('preview');
const lockSwitch = document.getElementById('lockSwitch');
function refreshPreview() {{
  preview.innerHTML = renderMarkdown(editor.value);
}}
async function loadLayer() {{
  try {{
    const data = await requestJson('/api/works/' + encodeURIComponent(WORK_ID) + '/layers/' + encodeURIComponent(LAYER_ID));
    const work = data.work;
    const layer = data.layer;
    document.getElementById('workLink').textContent = work.work_name;
    document.getElementById('workLink').href = '/work/' + encodeURIComponent(WORK_ID);
    document.getElementById('backLink').href = '/work/' + encodeURIComponent(WORK_ID);
    document.getElementById('breadcrumbLayer').textContent = layer.layer_name;
    document.getElementById('layerName').textContent = layer.layer_name;
    document.getElementById('layerMeta').innerHTML = `${{escapeHtml(layer.layer_file)}} · ${{layer.locked ? '<span class="badge lock-badge">已锁定</span>' : '<span class="badge unlock-badge">未锁定</span>'}}`;
    renderProcessMeta(layer, data.role);
    editor.value = layer.content;
    lockSwitch.checked = Boolean(layer.locked);
    refreshPreview();
  }} catch (err) {{
    showMessage('status', err.message, 'danger');
  }}
}}
async function saveLayer(silent) {{
  try {{
    await requestJson('/api/works/' + encodeURIComponent(WORK_ID) + '/layers/' + encodeURIComponent(LAYER_ID), {{
      method: 'PUT',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{content: editor.value, locked: lockSwitch.checked}})
    }});
    if (!silent) showMessage('status', '修改已保存');
  }} catch (err) {{
    showMessage('status', err.message, 'danger');
  }}
}}
function renderProcessMeta(layer, role) {{
  const meta = layer.metadata || {{}};
  const roleName = meta.processed_by_role_name || (role ? role.role_name : '');
  const processed = Boolean(meta.llm_processed);
  const error = meta.llm_error || '';
  document.getElementById('processMeta').innerHTML = `
    <div class="col-md-3"><div class="text-secondary small">处理角色</div><div>${{escapeHtml(roleName || '未记录')}}</div></div>
    <div class="col-md-3"><div class="text-secondary small">导入智能体</div><div>${{escapeHtml(meta.import_agent_name || '未记录')}}</div></div>
    <div class="col-md-3"><div class="text-secondary small">模型</div><div class="mono">${{escapeHtml(meta.llm_model || '未记录')}}</div><div class="small text-secondary">${{escapeHtml(meta.llm_provider || '')}}</div></div>
    <div class="col-md-3"><div class="text-secondary small">处理状态</div><div>${{processed ? '<span class="badge process-badge">已调用模型</span>' : (error ? '<span class="badge lock-badge">调用失败</span>' : '<span class="badge muted-badge">未记录</span>')}}</div></div>
  `;
  const promptBlock = document.getElementById('rolePromptBlock');
  const prompt = role && role.prompt ? role.prompt : '';
  const errorLine = error ? `<div class="small text-danger mt-2">${{escapeHtml(error)}}</div>` : '';
  promptBlock.innerHTML = `
    <div class="text-secondary small mb-1">角色 Prompt</div>
    <div class="prompt-box">${{escapeHtml(prompt || '暂无角色 prompt 配置')}}</div>
    ${{errorLine}}
  `;
}}
editor.addEventListener('input', refreshPreview);
lockSwitch.addEventListener('change', () => saveLayer(true));
loadLayer();
"""
