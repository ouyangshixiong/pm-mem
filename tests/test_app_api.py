from fastapi.testclient import TestClient

import app as app_module
from app import app


def test_app_api_work_and_layer_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "短剧创作系统 - 记忆管理" in home.text

    roles = client.get("/api/roles")
    assert roles.status_code == 200
    assert any(role["role_name"] == "编剧" for role in roles.json()["roles"])

    llm_config = client.get("/api/import/llm-config")
    assert llm_config.status_code == 200
    assert llm_config.json()["model"] == "gpt-5.4"

    created = client.post("/api/works", json={"work_name": "Web测试短剧"})
    assert created.status_code == 200
    work_id = created.json()["work"]["work_id"]

    listed = client.get("/api/works")
    assert listed.status_code == 200
    assert listed.json()[0]["work_id"] == work_id

    detail = client.get(f"/api/works/{work_id}")
    assert detail.status_code == 200
    assert len(detail.json()["layers"]) == 6

    updated = client.put(
        f"/api/works/{work_id}/layers/script_archive",
        json={"content": "### 第1集\n女主回到旧宅。", "locked": True},
    )
    assert updated.status_code == 200
    assert updated.json()["layer"]["locked"] is True

    layer = client.get(f"/api/works/{work_id}/layers/script_archive")
    assert layer.status_code == 200
    assert "女主回到旧宅" in layer.json()["layer"]["content"]

    deleted = client.delete(f"/api/works/{work_id}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True


def test_app_remem_task_routes_memory_updates_through_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))

    class FakeLocalAdapter:
        def __call__(self, prompt):
            if "请选择下一步动作" in prompt or "请选择动作" in prompt:
                return "act"
            return """Act: ### 第1集 第2场
女主在会议室公开反击。

```json
{
  "memory_updates": [
    {
      "layer_id": "script_archive",
      "mode": "append",
      "content": "### 第1集 第2场\\n女主在会议室公开反击。"
    }
  ]
}
```"""

        def get_model_info(self):
            return {"model": "fake", "context_length_tokens": 64000}

    monkeypatch.setattr(app_module, "_LocalGenerateAdapter", FakeLocalAdapter)
    client = TestClient(app)

    created = client.post("/api/works", json={"work_name": "ReMem API测试"})
    work_id = created.json()["work"]["work_id"]

    response = client.post(
        f"/api/works/{work_id}/remem-task",
        json={
            "task_type": "script_generation",
            "role_id": "screenwriter",
            "task": "写第1集第2场，女主反击。",
            "metadata": {
                "target_layers": ["script_archive"],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["role"]["role_name"] == "编剧"
    assert data["memory_updated"] is True
    assert data["task_id"]
    assert data["applied_operations"]

    layer = client.get(f"/api/works/{work_id}/layers/script_archive").json()["layer"]
    assert "会议室公开反击" in layer["content"]

    traces = client.get(f"/api/works/{work_id}/traces").json()["traces"]
    assert traces
    assert traces[0]["task_id"] == data["task_id"]
    assert traces[0]["memory_updated"] is True
    assert traces[0]["target_layers"][0]["layer_id"] == "script_archive"
    assert traces[0]["target_layers"][0]["layer_file"] == "05_剧本档案层.md"
    assert traces[0]["changes"][0]["layer_file"] == "05_剧本档案层.md"
    assert traces[0]["changes"][0]["operation_label"] == "新增"
    assert traces[0]["changes"][0]["before_state"] == "empty"
    assert "会议室公开反击" in traces[0]["changes"][0]["after_excerpt"]
