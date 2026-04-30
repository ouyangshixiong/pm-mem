"""
FastAPI Web manager for short-drama Markdown memories.

Run with:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import html
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import memory_manager
from import_coordinator import (
    ExternalWorkImportCoordinator,
    build_external_work_payload,
)
from local_llm_client import load_import_llm_settings
import role_manager


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


@app.get("/", response_class=HTMLResponse)
def index_page() -> HTMLResponse:
    return HTMLResponse(_layout("短剧创作系统 - 记忆管理", _home_body(), _home_script()))


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


def _ensure_work_exists(work_id: str) -> None:
    try:
        _find_work(work_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    h1 {{ font-size: 26px; line-height: 1.25; margin: 0; }}
    h2 {{ font-size: 20px; margin: 0 0 14px; }}
    .breadcrumb {{ margin-bottom: 16px; }}
    @media (max-width: 768px) {{
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .editor, .preview {{ min-height: 360px; max-height: none; }}
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
  <button class="btn btn-primary" onclick="createWork()">新增作品</button>
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
        <td>${escapeHtml(work.create_time)}</td>
        <td>${escapeHtml(work.update_time)}</td>
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
  <a class="btn btn-outline-secondary" href="/">返回首页</a>
</div>
<section class="panel mb-3">
  <div class="row g-3" id="workMeta"></div>
</section>
<section class="panel mb-3">
  <div class="d-flex align-items-start justify-content-between gap-3 mb-2">
    <h2>导入模型</h2>
    <span id="llmEnabledBadge" class="badge muted-badge">读取中</span>
  </div>
  <div class="row g-3" id="llmMeta"></div>
</section>
<section class="panel mb-3">
  <h2>角色 Prompt 配置</h2>
  <div class="role-grid" id="rolesBody"></div>
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
async function loadWork() {{
  try {{
    const [data, rolesData, llmConfig] = await Promise.all([
      requestJson('/api/works/' + encodeURIComponent(WORK_ID)),
      requestJson('/api/roles'),
      requestJson('/api/import/llm-config')
    ]);
    const work = data.work;
    document.getElementById('breadcrumbName').textContent = work.work_name;
    document.getElementById('workName').textContent = work.work_name;
    document.getElementById('workId').textContent = work.work_id;
    document.getElementById('workMeta').innerHTML = `
      <div class="col-md-4"><div class="text-secondary small">作品ID</div><div class="mono">${{escapeHtml(work.work_id)}}</div></div>
      <div class="col-md-4"><div class="text-secondary small">创建时间</div><div>${{escapeHtml(work.create_time)}}</div></div>
      <div class="col-md-4"><div class="text-secondary small">最后更新时间</div><div>${{escapeHtml(work.update_time)}}</div></div>
    `;
    renderLlmConfig(llmConfig);
    renderRoles(rolesData.roles || []);
    document.getElementById('layersBody').innerHTML = data.layers.map(layer => `
      <tr>
        <td>${{escapeHtml(layer.layer_name)}}</td>
        <td class="mono">${{escapeHtml(layer.layer_file)}}</td>
        <td>${{layer.locked ? '<span class="badge lock-badge">已锁定</span>' : '<span class="badge unlock-badge">未锁定</span>'}}</td>
        <td>${{renderLayerRole(layer)}}</td>
        <td>${{renderLayerLlm(layer)}}</td>
        <td>${{escapeHtml(layer.last_updated)}}</td>
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
function renderLlmConfig(config) {{
  const primary = config.primary || config;
  const backup = config.deepseek_backup || {{}};
  const badge = document.getElementById('llmEnabledBadge');
  badge.className = 'badge process-badge';
  badge.textContent = '默认调用';
  document.getElementById('llmMeta').innerHTML = `
    <div class="col-md-4"><div class="text-secondary small">Primary Endpoint</div><div class="mono">${{escapeHtml(primary.endpoint)}}</div></div>
    <div class="col-md-4"><div class="text-secondary small">Primary Model</div><div class="mono">${{escapeHtml(primary.model)}}</div></div>
    <div class="col-md-4"><div class="text-secondary small">DeepSeek Backup</div><div>${{backup.api_key_configured ? '已配置' : '未配置 API Key'}}</div><div class="mono small">${{escapeHtml(backup.model || '')}}</div></div>
    <div class="col-md-8"><div class="text-secondary small">DeepSeek Endpoint</div><div class="mono">${{escapeHtml(backup.endpoint || '')}}</div></div>
    <div class="col-md-4"><div class="text-secondary small">Fallback</div><div>${{config.fallback_to_deterministic ? '两路失败后保留确定性草稿' : '两路失败即中断'}}</div></div>
  `;
}}
function renderRoles(roles) {{
  const body = document.getElementById('rolesBody');
  if (!roles.length) {{
    body.innerHTML = '<div class="text-secondary">暂无角色配置</div>';
    return;
  }}
  body.innerHTML = roles.map(role => `
    <details class="role-item">
      <summary><strong>${{escapeHtml(role.role_name)}}</strong> <span class="mono text-secondary">${{escapeHtml(role.role_file)}}</span></summary>
      <div class="prompt-box mt-2">${{escapeHtml(role.prompt)}}</div>
    </details>
  `).join('');
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
