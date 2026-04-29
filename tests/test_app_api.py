from fastapi.testclient import TestClient

from app import app


def test_app_api_work_and_layer_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "短剧创作系统 - 记忆管理" in home.text

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
