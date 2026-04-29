"""
FastAPI Web manager for short-drama Markdown memories.

Run with:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import html
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import memory_manager


app = FastAPI(title="短剧创作系统 - 记忆管理")


class CreateWorkRequest(BaseModel):
    work_name: str


class UpdateLayerRequest(BaseModel):
    content: str
    locked: Optional[bool] = None


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
        return {"work": work, "layer": layer}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/works/{work_id}/layers/{layer_id}")
def api_update_layer(work_id: str, layer_id: str, payload: UpdateLayerRequest) -> Dict[str, Any]:
    try:
        success = memory_manager.update_layer_content(
            work_id=work_id,
            layer_id=layer_id,
            content=payload.content,
            operator="用户手动修改",
            lock_status=payload.locked,
        )
        return {"success": success, "layer": memory_manager.get_layer_content(work_id, layer_id)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _work_payload(work_id: str) -> Dict[str, Any]:
    return {
        "work": _find_work(work_id),
        "layers": memory_manager.get_work_layers(work_id),
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
<section class="panel">
  <h2>分层记忆</h2>
  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead>
        <tr>
          <th>分层名称</th>
          <th>文件名</th>
          <th>锁定状态</th>
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
    const data = await requestJson('/api/works/' + encodeURIComponent(WORK_ID));
    const work = data.work;
    document.getElementById('breadcrumbName').textContent = work.work_name;
    document.getElementById('workName').textContent = work.work_name;
    document.getElementById('workId').textContent = work.work_id;
    document.getElementById('workMeta').innerHTML = `
      <div class="col-md-4"><div class="text-secondary small">作品ID</div><div class="mono">${{escapeHtml(work.work_id)}}</div></div>
      <div class="col-md-4"><div class="text-secondary small">创建时间</div><div>${{escapeHtml(work.create_time)}}</div></div>
      <div class="col-md-4"><div class="text-secondary small">最后更新时间</div><div>${{escapeHtml(work.update_time)}}</div></div>
    `;
    document.getElementById('layersBody').innerHTML = data.layers.map(layer => `
      <tr>
        <td>${{escapeHtml(layer.layer_name)}}</td>
        <td class="mono">${{escapeHtml(layer.layer_file)}}</td>
        <td>${{layer.locked ? '<span class="badge lock-badge">已锁定</span>' : '<span class="badge unlock-badge">未锁定</span>'}}</td>
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
editor.addEventListener('input', refreshPreview);
lockSwitch.addEventListener('change', () => saveLayer(true));
loadLayer();
"""
