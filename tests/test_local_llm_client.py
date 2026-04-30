import base64
import json

import local_llm_client
from local_llm_client import (
    DeepSeekBackupSettings,
    DeepSeekChatLLMClient,
    ImportLLMSettings,
    LocalResponsesLLMClient,
)


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = lines
        self.text = ""
        self.decode_unicode_values = []

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=False):
        self.decode_unicode_values.append(decode_unicode)
        yield from self.lines


class FakeJsonResponse:
    def __init__(self, data):
        self.data = data
        self.text = json.dumps(data, ensure_ascii=False)

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


def _sse_event(event_type, payload):
    return [
        f"event: {event_type}",
        "data: " + json.dumps(payload, ensure_ascii=False),
        "",
    ]


def _sse_event_bytes(event_type, payload):
    return [
        f"event: {event_type}".encode("utf-8"),
        ("data: " + json.dumps(payload, ensure_ascii=False)).encode("utf-8"),
        b"",
    ]


def _settings():
    return ImportLLMSettings(
        endpoint="http://localhost:8317/v1/responses",
        model="gpt-5.4",
        api_key="your-api-key-1",
        stream=True,
    )


def test_stream_generate_uses_responses_input_and_output_text_done(monkeypatch):
    calls = {}
    lines = []
    lines.extend(
        _sse_event(
            "response.output_text.delta",
            {"type": "response.output_text.delta", "delta": "半截"},
        )
    )
    lines.extend(
        _sse_event(
            "response.output_text.done",
            {"type": "response.output_text.done", "text": "完整 LLM 文本"},
        )
    )
    lines.extend(
        _sse_event(
            "response.completed",
            {"type": "response.completed", "response": {"output": []}},
        )
    )

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return FakeStreamResponse(lines)

    monkeypatch.setattr(local_llm_client.requests, "post", fake_post)

    result = LocalResponsesLLMClient(_settings()).generate("请整理作品")

    assert result == "完整 LLM 文本"
    assert calls["url"] == "http://localhost:8317/v1/responses"
    assert calls["stream"] is True
    assert calls["json"]["stream"] is True
    assert calls["json"]["model"] == "gpt-5.4"
    message = calls["json"]["input"][0]
    assert message["role"] == "user"
    assert message["content"] == [{"type": "input_text", "text": "请整理作品"}]


def test_stream_generate_falls_back_to_output_item_done(monkeypatch):
    lines = _sse_event(
        "response.output_item.done",
        {
            "type": "response.output_item.done",
            "item": {
                "type": "message",
                "content": [{"type": "output_text", "text": "item 完整文本"}],
            },
        },
    )
    lines.extend(
        _sse_event(
            "response.completed",
            {"type": "response.completed", "response": {"output": []}},
        )
    )

    monkeypatch.setattr(
        local_llm_client.requests,
        "post",
        lambda *args, **kwargs: FakeStreamResponse(lines),
    )

    result = LocalResponsesLLMClient(_settings()).generate("请整理作品")

    assert result == "item 完整文本"


def test_stream_generate_decodes_utf8_bytes_before_extracting_text(monkeypatch):
    response = FakeStreamResponse(
        _sse_event_bytes(
            "response.output_text.done",
            {"type": "response.output_text.done", "text": "# 作品元数据\n\n来源系统：nanobanana"},
        )
    )

    monkeypatch.setattr(
        local_llm_client.requests,
        "post",
        lambda *args, **kwargs: response,
    )

    result = LocalResponsesLLMClient(_settings()).generate("请整理作品")

    assert result == "# 作品元数据\n\n来源系统：nanobanana"
    assert response.decode_unicode_values == [False]


def test_stream_generate_does_not_return_responses_protocol_fragments(monkeypatch):
    lines = [
        'data: {"type":"response.output_text.delta","content_index":0,"delta":"å',
        '¥","item_id":"msg_1","output_index":0}',
        "",
        "data: plain text fallback",
        "",
    ]

    monkeypatch.setattr(
        local_llm_client.requests,
        "post",
        lambda *args, **kwargs: FakeStreamResponse(lines),
    )

    result = LocalResponsesLLMClient(_settings()).generate("请整理作品")

    assert result == "plain text fallback"
    assert "response.output_text.delta" not in result


def test_generate_converts_local_images_to_base64_data_urls(tmp_path, monkeypatch):
    image_path = tmp_path / "frame.png"
    image_bytes = b"\x89PNG\r\n"
    image_path.write_bytes(image_bytes)
    calls = {}
    lines = _sse_event(
        "response.output_text.done",
        {"type": "response.output_text.done", "text": "ok"},
    )

    def fake_post(url, **kwargs):
        calls.update(kwargs)
        return FakeStreamResponse(lines)

    monkeypatch.setattr(local_llm_client.requests, "post", fake_post)

    result = LocalResponsesLLMClient(_settings()).generate(
        "这张图里有什么？",
        images=[str(image_path)],
    )

    expected_url = (
        "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    )
    content = calls["json"]["input"][0]["content"]
    assert result == "ok"
    assert content[0] == {"type": "input_text", "text": "这张图里有什么？"}
    assert content[1] == {"type": "input_image", "image_url": expected_url}


def test_deepseek_backup_uses_chat_completions_payload(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return FakeJsonResponse(
            {"choices": [{"message": {"content": "DeepSeek 备用结果"}}]}
        )

    monkeypatch.setattr(local_llm_client.requests, "post", fake_post)

    settings = DeepSeekBackupSettings(
        endpoint="https://api.deepseek.com/chat/completions",
        model="deepseek-v4-pro",
        api_key="deepseek-test-key",
        timeout=120,
        thinking_enabled=True,
        reasoning_effort="high",
    )
    result = DeepSeekChatLLMClient(settings).generate("Hello!")

    assert result == "DeepSeek 备用结果"
    assert calls["url"] == "https://api.deepseek.com/chat/completions"
    assert calls["headers"]["Authorization"] == "Bearer deepseek-test-key"
    assert calls["json"]["model"] == "deepseek-v4-pro"
    assert calls["json"]["messages"] == [
        {
            "role": "system",
            "content": (
                "你是 pm-mem 外部作品导入的备用大模型。请严格遵守用户提示，"
                "只输出可直接写入目标记忆层的 Markdown 正文。"
            ),
        },
        {"role": "user", "content": "Hello!"},
    ]
    assert calls["json"]["thinking"] == {"type": "enabled"}
    assert calls["json"]["reasoning_effort"] == "high"
    assert calls["json"]["stream"] is False


def test_deepseek_backup_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-deepseek-key")

    settings = local_llm_client.load_import_llm_settings()

    assert settings.deepseek_backup.api_key == "env-deepseek-key"
