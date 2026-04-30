"""LLM clients used by external-work import agents."""

import base64
from dataclasses import dataclass, field
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests
import yaml


DEFAULT_ENDPOINT = "http://localhost:8317/v1/responses"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_LOCAL_LLM_TIMEOUT = 300.0
DEFAULT_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"


@dataclass
class DeepSeekBackupSettings:
    """Configuration for the DeepSeek chat/completions backup path."""

    endpoint: str = DEFAULT_DEEPSEEK_ENDPOINT
    model: str = DEFAULT_DEEPSEEK_MODEL
    api_key: str = ""
    timeout: float = 120.0
    thinking_enabled: bool = True
    reasoning_effort: str = "high"
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def public_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "timeout": self.timeout,
            "thinking_enabled": self.thinking_enabled,
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "api_key_configured": self.is_configured(),
        }


@dataclass
class ImportLLMSettings:
    """Configuration for role-based import refinement."""

    endpoint: str = DEFAULT_ENDPOINT
    model: str = DEFAULT_MODEL
    api_key: str = "your-api-key-1"
    timeout: float = DEFAULT_LOCAL_LLM_TIMEOUT
    stream: bool = True
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    fallback_to_deterministic: bool = True
    max_prompt_chars: int = 24000
    deepseek_backup: DeepSeekBackupSettings = field(
        default_factory=DeepSeekBackupSettings
    )

    def public_dict(self) -> Dict[str, Any]:
        backup = self.deepseek_backup or DeepSeekBackupSettings()
        return {
            "always_on": True,
            "endpoint": self.endpoint,
            "model": self.model,
            "timeout": self.timeout,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "fallback_to_deterministic": self.fallback_to_deterministic,
            "max_prompt_chars": self.max_prompt_chars,
            "api_key_configured": bool(self.api_key),
            "stream": self.stream,
            "primary": {
                "provider": "local_proxy_responses",
                "endpoint": self.endpoint,
                "model": self.model,
                "timeout": self.timeout,
                "max_output_tokens": self.max_output_tokens,
                "temperature": self.temperature,
                "api_key_configured": bool(self.api_key),
                "stream": self.stream,
            },
            "deepseek_backup": backup.public_dict(),
        }


class LocalResponsesLLMClient:
    """Small client for a local proxy `/v1/responses` endpoint."""

    def __init__(self, settings: ImportLLMSettings):
        self.settings = settings

    def generate(self, prompt: str, images: Optional[List[str]] = None) -> str:
        payload: Dict[str, Any] = {
            "model": self.settings.model,
            "input": [
                {
                    "role": "user",
                    "content": _build_input_content(prompt, images or []),
                }
            ],
            "stream": self.settings.stream,
        }
        if self.settings.max_output_tokens is not None:
            payload["max_output_tokens"] = self.settings.max_output_tokens
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature

        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        response = requests.post(
            self.settings.endpoint,
            headers=headers,
            json=payload,
            timeout=self.settings.timeout,
            stream=self.settings.stream,
        )
        response.raise_for_status()

        if self.settings.stream:
            return _extract_stream_response_text(response).strip()

        try:
            data = response.json()
        except ValueError:
            return response.text.strip()

        return _extract_response_text(data).strip()


class DeepSeekChatLLMClient:
    """Client for DeepSeek's `/chat/completions` backup endpoint."""

    def __init__(self, settings: DeepSeekBackupSettings):
        self.settings = settings

    def generate(self, prompt: str, images: Optional[List[str]] = None) -> str:
        if not self.settings.is_configured():
            raise RuntimeError(
                "DeepSeek API key is not configured; set DEEPSEEK_API_KEY or PM_MEM_DEEPSEEK_API_KEY"
            )

        user_prompt = prompt
        if images:
            image_lines = "\n".join(f"- {image}" for image in images)
            user_prompt = (
                f"{prompt}\n\n# 附加图片引用\n"
                "DeepSeek 备用通道使用文本 chat/completions 接口；以下图片以 URL/路径文本提供，"
                "请仅在可判断时使用，不确定则标注“待人工确认”。\n"
                f"{image_lines}"
            )

        payload: Dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 pm-mem 外部作品导入的备用大模型。请严格遵守用户提示，"
                        "只输出可直接写入目标记忆层的 Markdown 正文。"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            "thinking": {
                "type": "enabled" if self.settings.thinking_enabled else "disabled"
            },
            "reasoning_effort": self.settings.reasoning_effort,
            "stream": False,
        }
        if self.settings.max_tokens is not None:
            payload["max_tokens"] = self.settings.max_tokens
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature

        response = requests.post(
            self.settings.endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.api_key}",
            },
            json=payload,
            timeout=self.settings.timeout,
        )
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            return response.text.strip()
        return _extract_response_text(data).strip()


def load_import_llm_settings() -> ImportLLMSettings:
    """Load import LLM settings from YAML config and environment variables."""
    config = _load_project_config()
    import_llm = _as_dict(config.get("import_llm"))
    local_llm = _as_dict(config.get("local_llm"))
    deepseek_backup = _load_deepseek_backup_config(config)

    settings = ImportLLMSettings(
        endpoint=str(local_llm.get("endpoint") or DEFAULT_ENDPOINT),
        model=str(local_llm.get("model") or DEFAULT_MODEL),
        api_key=str(local_llm.get("api_key") or "your-api-key-1"),
        timeout=_as_float(local_llm.get("timeout"), DEFAULT_LOCAL_LLM_TIMEOUT),
        stream=_as_bool(local_llm.get("stream"), True),
        max_output_tokens=_as_optional_int(local_llm.get("max_output_tokens")),
        temperature=_as_optional_float(local_llm.get("temperature")),
        fallback_to_deterministic=_as_bool(
            import_llm.get("fallback_to_deterministic"),
            True,
        ),
        max_prompt_chars=_as_int(import_llm.get("max_prompt_chars"), 24000),
        deepseek_backup=deepseek_backup,
    )

    _apply_env_overrides(settings)
    return settings


def _load_deepseek_backup_config(config: Dict[str, Any]) -> DeepSeekBackupSettings:
    backup = _as_dict(config.get("deepseek_backup"))
    top_level = _as_dict(config.get("deepseek"))
    llm = _as_dict(config.get("llm"))
    llm_deepseek = _as_dict(llm.get("deepseek"))

    endpoint = (
        backup.get("endpoint")
        or backup.get("api_base")
        or top_level.get("endpoint")
        or top_level.get("api_base")
        or llm_deepseek.get("endpoint")
        or llm_deepseek.get("api_base")
        or DEFAULT_DEEPSEEK_ENDPOINT
    )
    model = (
        backup.get("model")
        or backup.get("model_name")
        or top_level.get("model")
        or top_level.get("model_name")
        or llm.get("model_name")
        or DEFAULT_DEEPSEEK_MODEL
    )
    return DeepSeekBackupSettings(
        endpoint=_normalise_deepseek_endpoint(str(endpoint)),
        model=str(model),
        api_key=str(
            backup.get("api_key")
            or top_level.get("api_key")
            or llm_deepseek.get("api_key")
            or ""
        ),
        timeout=_as_float(backup.get("timeout"), _as_float(llm.get("timeout"), 120.0)),
        thinking_enabled=_as_bool(backup.get("thinking_enabled"), True),
        reasoning_effort=str(backup.get("reasoning_effort") or "high"),
        max_tokens=_as_optional_int(backup.get("max_tokens")),
        temperature=_as_optional_float(backup.get("temperature")),
    )


def _normalise_deepseek_endpoint(value: str) -> str:
    endpoint = (value or DEFAULT_DEEPSEEK_ENDPOINT).strip().rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return f"{endpoint}/chat/completions"


def _load_project_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    for path in [
        os.getenv("PM_MEM_CONFIG"),
        "config.yaml",
        "config.yml",
        "configs/local.yaml",
        "configs/local.yml",
    ]:
        if not path:
            continue
        config_path = Path(path).expanduser()
        if not config_path.exists():
            continue
        data = _read_yaml(config_path)
        if data:
            _merge_dicts(config, data)
    return config


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _merge_dicts(base: Dict[str, Any], overlay: Dict[str, Any]) -> None:
    for key, value in overlay.items():
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _merge_dicts(base[key], value)
        else:
            base[key] = value


def _apply_env_overrides(settings: ImportLLMSettings) -> None:
    if "PM_MEM_IMPORT_LLM_FALLBACK" in os.environ:
        settings.fallback_to_deterministic = _as_bool(
            os.environ["PM_MEM_IMPORT_LLM_FALLBACK"],
            settings.fallback_to_deterministic,
        )
    if "PM_MEM_IMPORT_LLM_MAX_PROMPT_CHARS" in os.environ:
        settings.max_prompt_chars = _as_int(
            os.environ["PM_MEM_IMPORT_LLM_MAX_PROMPT_CHARS"],
            settings.max_prompt_chars,
        )
    if "PM_MEM_LOCAL_LLM_ENDPOINT" in os.environ:
        settings.endpoint = os.environ["PM_MEM_LOCAL_LLM_ENDPOINT"]
    if "PM_MEM_LOCAL_LLM_MODEL" in os.environ:
        settings.model = os.environ["PM_MEM_LOCAL_LLM_MODEL"]
    if "PM_MEM_LOCAL_LLM_API_KEY" in os.environ:
        settings.api_key = os.environ["PM_MEM_LOCAL_LLM_API_KEY"]
    if "PM_MEM_LOCAL_LLM_TIMEOUT" in os.environ:
        settings.timeout = _as_float(
            os.environ["PM_MEM_LOCAL_LLM_TIMEOUT"],
            settings.timeout,
        )
    if "PM_MEM_LOCAL_LLM_STREAM" in os.environ:
        settings.stream = _as_bool(
            os.environ["PM_MEM_LOCAL_LLM_STREAM"],
            settings.stream,
        )
    backup = settings.deepseek_backup or DeepSeekBackupSettings()
    if "DEEPSEEK_API_KEY" in os.environ:
        backup.api_key = os.environ["DEEPSEEK_API_KEY"]
    if "PM_MEM_DEEPSEEK_API_KEY" in os.environ:
        backup.api_key = os.environ["PM_MEM_DEEPSEEK_API_KEY"]
    if "DEEPSEEK_API_BASE" in os.environ:
        backup.endpoint = _normalise_deepseek_endpoint(os.environ["DEEPSEEK_API_BASE"])
    if "DEEPSEEK_API_ENDPOINT" in os.environ:
        backup.endpoint = _normalise_deepseek_endpoint(
            os.environ["DEEPSEEK_API_ENDPOINT"]
        )
    if "PM_MEM_DEEPSEEK_ENDPOINT" in os.environ:
        backup.endpoint = _normalise_deepseek_endpoint(
            os.environ["PM_MEM_DEEPSEEK_ENDPOINT"]
        )
    if "DEEPSEEK_MODEL" in os.environ:
        backup.model = os.environ["DEEPSEEK_MODEL"]
    if "PM_MEM_DEEPSEEK_MODEL" in os.environ:
        backup.model = os.environ["PM_MEM_DEEPSEEK_MODEL"]
    if "PM_MEM_DEEPSEEK_TIMEOUT" in os.environ:
        backup.timeout = _as_float(os.environ["PM_MEM_DEEPSEEK_TIMEOUT"], backup.timeout)
    if "PM_MEM_DEEPSEEK_THINKING_ENABLED" in os.environ:
        backup.thinking_enabled = _as_bool(
            os.environ["PM_MEM_DEEPSEEK_THINKING_ENABLED"],
            backup.thinking_enabled,
        )
    if "PM_MEM_DEEPSEEK_REASONING_EFFORT" in os.environ:
        backup.reasoning_effort = os.environ["PM_MEM_DEEPSEEK_REASONING_EFFORT"]
    settings.deepseek_backup = backup


def _build_input_content(prompt: str, images: List[str]) -> List[Dict[str, str]]:
    content = [{"type": "input_text", "text": prompt}]
    for image in images:
        content.append({"type": "input_image", "image_url": _normalise_image_url(image)})
    return content


def _normalise_image_url(image: str) -> str:
    image = str(image or "").strip()
    if not image:
        return image
    if image.startswith(("http://", "https://", "data:")):
        return image

    if image.startswith("file://"):
        path = Path(unquote(urlparse(image).path))
    else:
        path = Path(image).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_file():
        return image

    mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_stream_response_text(response: requests.Response) -> str:
    output_text_done: List[str] = []
    output_item_done: List[str] = []
    completed_text: List[str] = []
    delta_parts: List[str] = []

    # Keep requests from decoding SSE bytes with a guessed Latin-1 encoding.
    # Some UTF-8 Chinese byte sequences contain C1 bytes such as 0x85; if those
    # are decoded before line splitting, they can be treated as line breaks and
    # leak raw Responses protocol JSON into the memory layer content.
    for event_name, data_text in _iter_stream_events(
        response.iter_lines(decode_unicode=False)
    ):
        if not data_text or data_text == "[DONE]":
            continue
        try:
            data = json.loads(data_text)
        except ValueError:
            fallback_text = _plain_stream_text_fragment(data_text)
            if fallback_text:
                delta_parts.append(fallback_text)
            continue

        event_type = data.get("type") or event_name or ""
        if event_type in {"error", "response.failed"}:
            raise RuntimeError(_extract_stream_error(data))

        if event_type == "response.output_text.delta":
            delta = data.get("delta")
            if isinstance(delta, str):
                delta_parts.append(delta)
            continue

        if event_type == "response.output_text.done":
            text = data.get("text")
            if isinstance(text, str):
                output_text_done.append(text)
            continue

        if event_type == "response.output_item.done":
            item = data.get("item")
            if isinstance(item, dict):
                output_item_done.extend(_extract_output_parts([item]))
            continue

        if event_type in {
            "response.content_part.done",
            "response.output_content.done",
        }:
            text = _extract_content_part_text(data.get("part") or data.get("content"))
            if text:
                output_item_done.append(text)
            continue

        if event_type == "response.completed":
            response_data = data.get("response")
            text = _extract_response_text(response_data)
            if text:
                completed_text.append(text)

    for candidates in (output_text_done, output_item_done, completed_text):
        text = _join_unique_text(candidates)
        if text.strip():
            return text
    return "".join(delta_parts)


def _iter_stream_events(
    lines: Iterable[Any],
) -> Iterator[Tuple[Optional[str], str]]:
    event_name: Optional[str] = None
    data_lines: List[str] = []

    for raw_line in lines:
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace")
        else:
            line = str(raw_line)
        line = line.rstrip("\r")

        if line == "":
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = None
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
            continue

        stripped = line.strip()
        if not stripped:
            continue
        if data_lines:
            data_lines.append(stripped)
        else:
            yield event_name, stripped

    if data_lines:
        yield event_name, "\n".join(data_lines)


def _plain_stream_text_fragment(data_text: str) -> str:
    """Return non-protocol fallback text from a malformed stream fragment."""
    text = (data_text or "").strip()
    if not text:
        return ""
    protocol_markers = (
        '"type":"response.',
        '"type": "response.',
        "response.output_text.",
        "response.output_item.",
        "response.completed",
        "response.failed",
    )
    if any(marker in text for marker in protocol_markers):
        return ""
    if text.startswith(("event:", "data:", "{")):
        return ""
    return text


def _extract_stream_error(data: Dict[str, Any]) -> str:
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("code")
        if message:
            return str(message)
    if isinstance(error, str):
        return error
    response = data.get("response")
    if isinstance(response, dict):
        response_error = response.get("error")
        if isinstance(response_error, dict):
            message = response_error.get("message") or response_error.get("code")
            if message:
                return str(message)
        if isinstance(response_error, str):
            return response_error
    return "Local Responses stream failed"


def _extract_content_part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    text = part.get("text") or part.get("content")
    return text if isinstance(text, str) else ""


def _join_unique_text(parts: List[str]) -> str:
    unique_parts: List[str] = []
    seen = set()
    for part in parts:
        normalized = part.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_parts.append(normalized)
    return "\n".join(unique_parts)


def _extract_response_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return ""

    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]

    output = data.get("output")
    if isinstance(output, list):
        parts = _extract_output_parts(output)
        if parts:
            return "\n".join(parts)

    content = data.get("content")
    if isinstance(content, str):
        return content
    return ""


def _extract_output_parts(output: List[Any]) -> List[str]:
    parts: List[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text") or block.get("content")
                if isinstance(text, str):
                    parts.append(text)
        text = item.get("text") or item.get("content")
        if isinstance(text, str):
            parts.append(text)
    return parts


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
