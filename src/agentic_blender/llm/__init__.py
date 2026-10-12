"""Model-agnostic LLM routing for Agentic Blender."""
from .router import (
    DEFAULT_MODELS,
    PROVIDER_ENDPOINTS,
    call_universal_llm,
    discover_local_ollama_models,
    extract_python_code,
    resolve_api_key,
)

__all__ = [
    "DEFAULT_MODELS",
    "PROVIDER_ENDPOINTS",
    "call_universal_llm",
    "discover_local_ollama_models",
    "extract_python_code",
    "resolve_api_key",
]
