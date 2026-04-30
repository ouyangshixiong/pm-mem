import json
import re

from fastapi.testclient import TestClient

import app as app_module
from app import app
import memory_manager


def _fake_retrieval_json(prompt: str) -> str:
    results = []
    for match in re.finditer(
        r"\[(\d+)\]\n层: .+?\n标题路径: .+?\n内容:\n(.*?)(?=\n\n\[\d+\]\n层:|\Z)",
        prompt,
        flags=re.DOTALL,
    ):
        index = int(match.group(1))
        content = match.group(2)
        if "Flinken" in content or "系统故障" in content or "复盘会" in content:
            results.append(
                {
                    "index": index,
                    "relevance_score": 0.95,
                    "reason": "包含 Flinken、主要人物或系统故障情节。",
                    "matched_facts": ["Flinken 是核心技术人物"],
                }
            )
    return json.dumps({"results": results}, ensure_ascii=False)


class FakeRetrievalAdapter:
    def __init__(self):
        self.settings = type(
            "Settings",
            (),
            {
                "model": "fake-local",
                "max_prompt_chars": 24000,
                "deepseek_backup": type(
                    "Backup",
                    (),
                    {"model": "fake-deepseek"},
                )(),
            },
        )()
        self.last_provider = "fake-local"
        self.last_error = ""
        self.prompts = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "LLM 本地文档检索任务" in prompt:
            return _fake_retrieval_json(prompt)
        if "本地记忆问答任务" in prompt:
            return "Flinken 是核心技术人物；当前情节围绕被裁后系统故障、复盘会反制与顾问议价展开。"
        return "act"

    def get_model_info(self):
        return {"model": "fake-local", "context_length_tokens": 64000}


def test_llm_retrieve_endpoint_returns_answer_without_writing_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    monkeypatch.setattr(app_module, "_LocalGenerateAdapter", FakeRetrievalAdapter)
    client = TestClient(app)

    created = client.post("/api/works", json={"work_name": "职场见闻"})
    work_id = created.json()["work"]["work_id"]
    memory_manager.update_layer_content(
        work_id,
        "character_profile",
        "## Flinken\n- 核心后台系统工程师。\n- 被裁员后仍被公司依赖。",
        "用户手动修改",
    )
    memory_manager.update_layer_content(
        work_id,
        "plot_context",
        "## 当前主线\nFlinken 被裁后，公司系统故障爆发，随后进入复盘会反制。",
        "用户手动修改",
    )
    before = memory_manager.get_layer_content(work_id, "plot_context")["content"]

    response = client.post(
        f"/api/works/{work_id}/retrieve",
        json={
            "query": "职场见闻 当前主要人物和情节概要",
            "target_layers": ["character_profile", "plot_context"],
            "top_k": 3,
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Flinken" in data["answer"]
    assert data["results"]
    assert data["results"][0]["score"] == 0.95
    assert data["results"][0]["layer_id"] in {"character_profile", "plot_context"}
    assert data["stats"]["retrieval_mode"] == "llm"

    after = memory_manager.get_layer_content(work_id, "plot_context")["content"]
    assert after == before


def test_global_retrieve_endpoint_resolves_work_name(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    monkeypatch.setattr(app_module, "_LocalGenerateAdapter", FakeRetrievalAdapter)
    client = TestClient(app)

    created = client.post("/api/works", json={"work_name": "职场见闻"})
    work_id = created.json()["work"]["work_id"]
    memory_manager.update_layer_content(
        work_id,
        "character_profile",
        "## Flinken\nFlinken 是主要人物。",
        "用户手动修改",
    )

    response = client.post(
        "/api/retrieve",
        json={
            "work_name": "职场见闻",
            "query": "主要人物是谁",
            "target_layers": ["character_profile"],
            "include_answer": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["work"]["work_id"] == work_id
    assert data["results"][0]["layer_id"] == "character_profile"
