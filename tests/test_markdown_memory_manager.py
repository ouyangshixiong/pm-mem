import os
from pathlib import Path

import pytest
import yaml

import memory_manager


def test_create_work_generates_isolated_markdown_layers(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))

    first_id = memory_manager.create_work("都市逆袭")
    second_id = memory_manager.create_work("悬疑甜宠")

    works = memory_manager.list_works()
    assert {item["work_id"] for item in works} == {first_id, second_id}

    for work_id in (first_id, second_id):
        work_dir = tmp_path / "works" / work_id
        assert work_dir.is_dir()
        assert (work_dir / ".work_config.yaml").exists()

        layers = memory_manager.get_work_layers(work_id)
        assert len(layers) == 6
        assert [layer["layer_id"] for layer in layers] == [
            "work_metadata",
            "core_setting",
            "character_profile",
            "plot_context",
            "script_archive",
            "storyboard_archive",
        ]

        for layer in layers:
            layer_path = work_dir / layer["layer_file"]
            text = layer_path.read_text(encoding="utf-8")
            assert text.startswith("---\n")
            assert "layer_id:" in text
            assert "updated_by:" in text


def test_update_layer_lock_permission_and_config_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    work_id = memory_manager.create_work("锁定测试")

    assert memory_manager.update_layer_content(
        work_id,
        "core_setting",
        "女主不能离开海岛。",
        "编剧",
    )
    assert memory_manager.toggle_layer_lock(work_id, "core_setting", True)

    with pytest.raises(PermissionError):
        memory_manager.update_layer_content(
            work_id,
            "core_setting",
            "女主可以离开海岛。",
            "编剧",
        )

    assert memory_manager.update_layer_content(
        work_id,
        "core_setting",
        "女主不能离开海岛，除非得到制片人批准。",
        "制片人",
    )
    layer = memory_manager.get_layer_content(work_id, "core_setting")
    assert layer["locked"] is True
    assert "制片人批准" in layer["content"]

    config_path = tmp_path / "works" / work_id / ".work_config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["layer_lock_status"]["02_核心设定层"] is True


def test_prompt_content_filters_front_matter_and_llm_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    work_id = memory_manager.create_work("记忆自进化")

    memory_manager.update_layer_content(
        work_id,
        "character_profile",
        "林澈：前消防员，怕水。",
        "编剧",
    )
    prompt_memory = memory_manager.get_layer_content_for_prompt(
        work_id,
        ["character_profile"],
    )
    assert "林澈：前消防员" in prompt_memory
    assert "layer_id:" not in prompt_memory
    assert "locked:" not in prompt_memory

    output = """
第一集场景完成。

## 情节脉络层
林澈在暴雨夜第一次进入旧码头。

## 剧本档案层
### 第1集 第1场
外景，旧码头，夜。
"""
    assert memory_manager.update_memory_from_llm_output(work_id, output, "编剧")
    plot = memory_manager.get_layer_content(work_id, "plot_context")
    script = memory_manager.get_layer_content(work_id, "script_archive")
    assert "旧码头" in plot["content"]
    assert "第1集 第1场" in script["content"]


def test_delete_work_removes_folder_and_index(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_MEM_WORKS_DIR", str(tmp_path / "works"))
    work_id = memory_manager.create_work("待删除作品")
    work_dir = tmp_path / "works" / work_id

    assert work_dir.exists()
    assert memory_manager.delete_work(work_id)
    assert not work_dir.exists()
    assert all(item["work_id"] != work_id for item in memory_manager.list_works())
