DEEPSEEK_MODELS = {
    "deepseek-chat": {
        "context_length_tokens": 64000,
        "default_max_output_tokens": 4096,
        "type": "chat",
        "notes": "Context window counts input+output; keep safety margin to avoid truncation.",
        "source": "https://www.datastudios.org/post/deepseek-context-window-token-limits-memory-policy-and-2025-rules",
    },
    "deepseek-reasoner": {
        "context_length_tokens": 64000,
        "default_max_output_tokens": 8192,
        "type": "reasoner",
        "notes": "Input limit ~64k; output may be longer; input budget excludes output.",
        "source": "https://www.datastudios.org/post/deepseek-context-window-token-limits-memory-policy-and-2025-rules",
    },
}

def get_model_context_length(model_name: str) -> int:
    info = DEEPSEEK_MODELS.get(model_name, {})
    return int(info.get("context_length_tokens", 64000))

