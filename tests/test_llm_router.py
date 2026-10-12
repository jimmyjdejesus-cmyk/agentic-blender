"""Unit tests for the Universal Model-Agnostic LLM Router."""

import json
from unittest.mock import MagicMock, patch
import pytest

from agentic_blender.llm.router import (
    DEFAULT_MODELS,
    call_universal_llm,
    extract_python_code,
    resolve_api_key,
)


def test_default_models_mapping():
    assert DEFAULT_MODELS["OPENROUTER"] == "anthropic/claude-3.7-sonnet"
    assert DEFAULT_MODELS["GEMINI"] == "gemini-2.5-flash"
    assert DEFAULT_MODELS["ANTHROPIC"] == "claude-3-7-sonnet-latest"
    assert DEFAULT_MODELS["DEEPSEEK"] == "deepseek-chat"
    assert DEFAULT_MODELS["LOCAL_LLM"] == "qwen2.5-coder:7b"


def test_resolve_api_key_priority(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-or-key")
    assert resolve_api_key("OPENROUTER", "explicit-key") == "explicit-key"
    assert resolve_api_key("OPENROUTER", "") == "env-or-key"


def test_extract_python_code():
    raw = "Here is code:\n```python\nimport bpy\nbpy.ops.mesh.primitive_cube_add()\n```\n"
    assert extract_python_code(raw) == "import bpy\nbpy.ops.mesh.primitive_cube_add()"


@patch("urllib.request.urlopen")
def test_call_universal_llm_openrouter(mock_urlopen):
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(
        {"choices": [{"message": {"content": "```python\nimport bpy\n```"}}]}
    ).encode("utf-8")
    fake_resp.__enter__.return_value = fake_resp
    mock_urlopen.return_value = fake_resp

    res = call_universal_llm(
        provider="OPENROUTER",
        prompt="Make a cube",
        system_prompt="You are a CAD assistant",
        model_name="deepseek/deepseek-chat",
        api_key="sk-or-test",
    )
    assert "import bpy" in res


@patch("urllib.request.urlopen")
def test_call_universal_llm_anthropic(mock_urlopen):
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(
        {"content": [{"text": "```python\nimport bpy\n```"}]}
    ).encode("utf-8")
    fake_resp.__enter__.return_value = fake_resp
    mock_urlopen.return_value = fake_resp

    res = call_universal_llm(
        provider="ANTHROPIC",
        prompt="Make a cylinder",
        system_prompt="You are a CAD assistant",
        model_name="claude-3-7-sonnet-latest",
        api_key="sk-ant-test",
    )
    assert "import bpy" in res


def test_call_universal_llm_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Missing Gemini API Key"):
        call_universal_llm("GEMINI", "Make a cube", "System", api_key="")
