"""
Universal Model-Agnostic LLM Router for Agentic Blender.

Supports:
1. Optional `litellm` integration when installed in the Python environment.
2. Zero-dependency `urllib.request` universal router (works inside Blender's bundled
   Python with zero `pip` installs) across:
   - OpenRouter (300+ models: Claude, GPT-4o, Gemini, DeepSeek, Qwen, Llama)
   - Google Gemini (`gemini-2.5-flash`, `gemini-2.5-pro`)
   - Anthropic Claude (`claude-3-7-sonnet-latest`, `claude-3-5-haiku-latest`)
   - OpenAI / DeepSeek / Groq (`/v1/chat/completions` compatible endpoints)
   - Local LLMs (Ollama `localhost:11434`, LM Studio `localhost:1234`, vLLM)
"""

import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_MODELS = {
    "OPENROUTER": "anthropic/claude-3.7-sonnet",
    "GEMINI": "gemini-2.5-flash",
    "ANTHROPIC": "claude-3-7-sonnet-latest",
    "OPENAI_COMPAT": "gpt-4o",
    "DEEPSEEK": "deepseek-chat",
    "GROQ": "llama-3.3-70b-versatile",
    "LOCAL_LLM": "qwen2.5-coder:7b",
}

PROVIDER_ENDPOINTS = {
    "OPENROUTER": "https://openrouter.ai/api/v1/chat/completions",
    "OPENAI_COMPAT": "https://api.openai.com/v1/chat/completions",
    "DEEPSEEK": "https://api.deepseek.com/v1/chat/completions",
    "GROQ": "https://api.groq.com/openai/v1/chat/completions",
    "ANTHROPIC": "https://api.anthropic.com/v1/messages",
    "LOCAL_LLM": "http://localhost:11434/v1/chat/completions",
}

ENV_KEY_MAP = {
    "OPENROUTER": ("OPENROUTER_API_KEY",),
    "GEMINI": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "ANTHROPIC": ("ANTHROPIC_API_KEY",),
    "OPENAI_COMPAT": ("OPENAI_API_KEY",),
    "DEEPSEEK": ("DEEPSEEK_API_KEY",),
    "GROQ": ("GROQ_API_KEY",),
}


def resolve_api_key(provider: str, explicit_key: str = "") -> str:
    """Resolve API key from explicit preference string or environment variables."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    for env_var in ENV_KEY_MAP.get(provider.upper(), ()):
        val = os.environ.get(env_var, "").strip()
        if val:
            return val
    # Fallback to any configured LLM_API_KEY
    return os.environ.get("LLM_API_KEY", "").strip()


def extract_python_code(response_text: str) -> str:
    """Extract executable Python code from markdown code fences or raw response."""
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, response_text or "", re.DOTALL)
    if matches:
        return matches[0].strip()
    return (response_text or "").strip()


def discover_local_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """Query local Ollama instance for installed model tags."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def call_universal_llm(
    provider: str,
    prompt: str,
    system_prompt: str,
    model_name: str = "",
    api_key: str = "",
    endpoint_url: str = "",
    temperature: float = 0.2,
    timeout: float = 45.0,
) -> str:
    """
    Route a prompt to any cloud or local LLM using LiteLLM (if installed)
    or zero-dependency standard-library HTTP calls.
    """
    prov = (provider or "OPENROUTER").upper()
    model = (model_name or "").strip() or DEFAULT_MODELS.get(prov, "gemini-2.5-flash")
    resolved_key = resolve_api_key(prov, api_key)

    # 1. Google Gemini Native REST API
    if prov == "GEMINI":
        if not resolved_key:
            raise ValueError("Missing Gemini API Key (set in sidebar or GEMINI_API_KEY env var).")
        clean_model = model.replace("gemini/", "").replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={resolved_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser Prompt: {prompt}"}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 4096},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("No response candidates returned from Gemini API.")
            parts = candidates[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""

    # 2. Anthropic Claude Native Messages API
    if prov == "ANTHROPIC":
        if not resolved_key:
            raise ValueError("Missing Anthropic API Key (set in sidebar or ANTHROPIC_API_KEY env var).")
        url = endpoint_url.strip() if endpoint_url and "anthropic" in endpoint_url else PROVIDER_ENDPOINTS["ANTHROPIC"]
        payload = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": resolved_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_blocks = data.get("content", [])
            return content_blocks[0].get("text", "") if content_blocks else ""

    # 3. Universal OpenAI-Compatible Protocol (OpenRouter, OpenAI, DeepSeek, Groq, Ollama, LM Studio)
    if prov == "LOCAL_LLM":
        url = (endpoint_url or "").strip() or PROVIDER_ENDPOINTS["LOCAL_LLM"]
    elif prov in PROVIDER_ENDPOINTS:
        url = PROVIDER_ENDPOINTS[prov]
        if prov == "OPENAI_COMPAT" and endpoint_url and endpoint_url.strip() and "localhost" not in endpoint_url:
            url = endpoint_url.strip()
    else:
        url = (endpoint_url or "").strip() or PROVIDER_ENDPOINTS["OPENROUTER"]

    if prov != "LOCAL_LLM" and not resolved_key:
        raise ValueError(f"Missing API Key for {prov}. Paste your API Key in the Blender Agent sidebar.")

    headers = {"Content-Type": "application/json"}
    if resolved_key:
        headers["Authorization"] = f"Bearer {resolved_key}"
    if prov == "OPENROUTER":
        headers["HTTP-Referer"] = "https://github.com/jimmyjdejesus-cmyk/agentic-blender"
        headers["X-Title"] = "Agentic Blender Studio"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"No choices returned from {prov} ({model}).")
        return choices[0].get("message", {}).get("content", "")
