from fastapi.testclient import TestClient
import re

import import_coordinator
import memory_manager
from app import app
from import_coordinator import ExternalWorkImportCoordinator, build_external_work_payload
from local_llm_client import DeepSeekBackupSettings, ImportLLMSettings


class FakeImportLLM:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, images=None):
        self.prompts.append(prompt)
        return "# LLM处理结果\n\n已根据角色 prompt 提炼导入记忆。"


class FakeBackupLLM:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, images=None):
        self.prompts.append(prompt)
        return "# DeepSeek备用处理结果\n\n已由备用模型提炼导入记忆。"


class FailingLLM:
    def generate(self, prompt, images=None):
        raise RuntimeError("primary unavailable")


def _payload(external_work_id="143"):
    return {
        "source_system": "外部创作系统",
        "external_work_id": external_work_id,
        "work_name": "职场见闻第一集",
        "source_url": f"http://example.local/works/{external_work_id}",
        "story": "新人林夏入职第一天，发现直属领导把功劳占为己有。",
        "script": "第1场 办公室 日。林夏：这份方案是我昨晚做的。",
        "storyboard_script": "镜头1：开放办公区全景。镜头2：林夏攥紧文件夹。",
        "raw_payload": {"source": "test"},
    }


def _force_local_llm_success(monkeypatch):
    def generate(self, prompt, images=None):
        external_id = re.search(r"外部作品 ID：(.+)", prompt)
        source_system = re.search(r"来源系统：(.+)", prompt)
        external_id = external_id.group(1).strip() if external_id else "143"
        source_system = source_system.group(1).strip() if source_system else "外部创作系统"
        if "「作品元数据层」" in prompt:
            return f"# 作品元数据\n\n来源系统：{source_system}\n来源workid：{external_id}"
        if "「剧本档案层」" in prompt:
            if "第2版剧本" in prompt:
                return "# 剧本档案\n\n第2版剧本：林夏在会议室反击。"
            return "# 剧本档案\n\n第1场 办公室 日。林夏：这份方案是我昨晚做的。"
        if "「分镜档案层」" in prompt:
            return "# 分镜档案\n\n镜头1：开放办公区全景。镜头2：林夏攥紧文件夹。"
        return "# LLM处理结果\n\n已根据角色 prompt 提炼导入记忆。"

    monkeypatch.setattr(
        import_coordinator.LocalResponsesLLMClient,
        "generate",
        generate,
    )


def _force_all_llms_failure(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("PM_MEM_DEEPSEEK_API_KEY", raising=False)

    def fail_generate(self, prompt, images=None):
        raise RuntimeError("test llm unavailable")

    monkeypatch.setattr(
        import_coordinator.LocalResponsesLLMClient,
        "generate",
        fail_generate,
    )
    monkeypatch.setattr(
        import_coordinator.DeepSeekChatLLMClient,
        "generate",
        fail_generate,
    )


def test_external_work_import_creates_visible_markdown_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    _force_local_llm_success(monkeypatch)
    client = TestClient(app)

    response = client.post("/api/import/external-work", json=_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["created"] is True
    assert data["work_id"]
    assert data["web_url"] == f"/work/{data['work_id']}"

    works_response = client.get("/api/works")
    assert works_response.status_code == 200
    assert works_response.json()[0]["work_name"] == "职场见闻第一集"

    metadata = memory_manager.get_layer_content(data["work_id"], "work_metadata")
    script = memory_manager.get_layer_content(data["work_id"], "script_archive")
    storyboard = memory_manager.get_layer_content(data["work_id"], "storyboard_archive")

    assert "来源workid：143" in metadata["content"]
    assert "外部创作系统" in metadata["content"]
    assert "林夏：这份方案" in script["content"]
    assert "开放办公区全景" in storyboard["content"]


def test_external_work_import_upserts_by_external_work_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    _force_local_llm_success(monkeypatch)
    client = TestClient(app)

    first = client.post("/api/import/external-work", json=_payload()).json()
    second_payload = _payload()
    second_payload["script"] = "第2版剧本：林夏在会议室反击。"
    second = client.post("/api/import/external-work", json=second_payload).json()

    assert second["created"] is False
    assert second["work_id"] == first["work_id"]
    assert len(memory_manager.list_works()) == 1

    script = memory_manager.get_layer_content(first["work_id"], "script_archive")
    assert "第2版剧本" in script["content"]


def test_external_work_import_dry_run_returns_drafts_without_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    _force_local_llm_success(monkeypatch)
    client = TestClient(app)
    payload = _payload("999")
    payload["dry_run"] = True

    response = client.post("/api/import/external-work", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["work_id"] is None
    assert "work_metadata" in data["layers"]
    assert memory_manager.list_works() == []


def test_external_work_import_calls_configured_role_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    fake_llm = FakeImportLLM()
    settings = ImportLLMSettings(
        endpoint="http://localhost:8317/v1/responses",
        model="gpt-5.4",
    )
    payload = build_external_work_payload(**_payload("llm-1"))

    result = ExternalWorkImportCoordinator(
        llm_client=fake_llm,
        llm_settings=settings,
    ).import_work(payload)

    assert len(fake_llm.prompts) == 6
    assert any("你是一位专业电影导演兼AI视频提示词编剧" in prompt for prompt in fake_llm.prompts)
    assert result["layers"]["script_archive"]["llm_processed"] is True
    assert result["layers"]["script_archive"]["role_name"] == "编剧"

    script = memory_manager.get_layer_content(result["work_id"], "script_archive")
    core_setting = memory_manager.get_layer_content(result["work_id"], "core_setting")
    metadata = memory_manager.get_layer_content(result["work_id"], "work_metadata")
    assert "LLM处理结果" in script["content"]
    assert script["metadata"]["processed_by_role_name"] == "编剧"
    assert script["metadata"]["llm_processed"] is True
    assert script["metadata"]["llm_model"] == "gpt-5.4"
    assert "LLM处理结果" in core_setting["content"]
    assert core_setting["metadata"]["processed_by_role_name"] == "制片人"
    assert core_setting["metadata"]["import_agent_name"] == "核心设定整理智能体"
    assert core_setting["metadata"]["llm_processed"] is True
    assert core_setting["metadata"]["llm_model"] == "gpt-5.4"
    assert metadata["metadata"]["import_agent_name"] == "作品元数据导入智能体"


def test_external_work_import_uses_deepseek_backup_after_primary_failure(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    settings = ImportLLMSettings(
        endpoint="http://localhost:8317/v1/responses",
        model="gpt-5.4",
        deepseek_backup=DeepSeekBackupSettings(
            endpoint="https://api.deepseek.com/chat/completions",
            model="deepseek-v4-pro",
            api_key="test-key",
        ),
    )
    backup_llm = FakeBackupLLM()
    payload = build_external_work_payload(**_payload("backup-1"))

    result = ExternalWorkImportCoordinator(
        llm_client=FailingLLM(),
        backup_llm_client=backup_llm,
        llm_settings=settings,
    ).import_work(payload)

    assert len(backup_llm.prompts) == 6
    assert result["layers"]["script_archive"]["llm_processed"] is True
    assert result["layers"]["script_archive"]["llm_provider"] == "deepseek_backup"
    assert result["layers"]["script_archive"]["llm_primary_error"] == "primary unavailable"

    script = memory_manager.get_layer_content(result["work_id"], "script_archive")
    assert "DeepSeek备用处理结果" in script["content"]
    assert script["metadata"]["llm_provider"] == "deepseek_backup"
    assert script["metadata"]["llm_model"] == "deepseek-v4-pro"


def test_external_work_import_returns_error_when_all_llms_fail(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    _force_all_llms_failure(monkeypatch)
    client = TestClient(app)

    response = client.post("/api/import/external-work", json=_payload("fail-1"))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "local_proxy_responses" in detail
    assert "deepseek_backup" in detail
    assert memory_manager.list_works() == []
