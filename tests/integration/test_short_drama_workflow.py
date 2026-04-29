import memory_manager
from workflow import ShortDramaWorkflow


class StaticLLM:
    def __init__(self):
        self.last_prompt = ""

    def __call__(self, prompt):
        self.last_prompt = prompt
        return """### 第1集 第1场
林澈在旧码头救下女主，但没有改写核心设定。

```json
{
  "memory_updates": [
    {
      "layer_id": "core_setting",
      "mode": "append",
      "content": "林澈其实从不怕水。"
    },
    {
      "layer_id": "script_archive",
      "mode": "append",
      "content": "### 第1集 第1场\\n林澈在旧码头救下女主。"
    }
  ]
}
```
"""


def test_short_drama_workflow_injects_memory_and_respects_locks(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    llm = StaticLLM()
    workflow = ShortDramaWorkflow(llm)
    work_id = workflow.create_work("一致性短剧")

    memory_manager.update_layer_content(
        work_id,
        "core_setting",
        "林澈怕水，这是贯穿全剧的核心创伤。",
        "制片人",
    )
    workflow.lock_layer(work_id, "core_setting", True)

    result = workflow.create_script_episode(work_id, "写第1集开场，地点为旧码头。")

    assert "林澈怕水" in llm.last_prompt
    assert result["memory_updated"] is True

    core_setting = memory_manager.get_layer_content(work_id, "core_setting")
    script_archive = memory_manager.get_layer_content(work_id, "script_archive")
    assert "从不怕水" not in core_setting["content"]
    assert "旧码头救下女主" in script_archive["content"]
