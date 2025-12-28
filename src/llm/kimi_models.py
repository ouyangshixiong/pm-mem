KIMI_MODELS = {
    "kimi-k2-0905-preview": {
        "context_length_tokens": 128000,
        "default_max_output_tokens": 4096,
        "type": "chat",
        "notes": "Context window counts input+output; keep safety margin to avoid truncation.",
        "source": "https://platform.moonshot.cn/docs",
    },
}

def get_model_context_length(model_name: str) -> int:
    info = KIMI_MODELS.get(model_name, {})
    return int(info.get("context_length_tokens", 128000))
