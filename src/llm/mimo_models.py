MIMO_MODELS = {
    "mimo-v2-flash": {
        "context_length_tokens": 32000,
        "default_max_output_tokens": 4096,
        "type": "chat",
        "notes": "Context window counts input+output; keep safety margin to avoid truncation.",
        "source": "https://docs.mimo.com",
    },
}

def get_model_context_length(model_name: str) -> int:
    info = MIMO_MODELS.get(model_name, {})
    return int(info.get("context_length_tokens", 32000))
