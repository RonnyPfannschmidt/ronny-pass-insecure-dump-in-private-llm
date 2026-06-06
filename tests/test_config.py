"""Tests for provider/model resolution logic."""

import pytest

from ronny.pass_analysis_lm.config import (
    AppConfig,
    ProviderConfig,
    parse_provider_spec,
    resolve_target,
)


def _config() -> AppConfig:
    return AppConfig(
        default_provider="vllm-local",
        providers={
            "vllm-local": ProviderConfig(
                base_url="http://192.168.1.100:8000/v1",
                api_key="none",
                default_model="qwen/Qwen2.5-72B-Instruct",
                models=["qwen/Qwen2.5-72B-Instruct", "qwen/Qwen2.5-7B-Instruct"],
            ),
            "openai": ProviderConfig(
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
                default_model="gpt-4o",
            ),
        },
    )


def test_provider_only_uses_default_model() -> None:
    t = parse_provider_spec("vllm-local", _config(), None)
    assert t.provider_name == "vllm-local"
    assert t.model == "qwen/Qwen2.5-72B-Instruct"


def test_provider_slash_model_with_slash_in_model_name() -> None:
    t = parse_provider_spec("vllm-local/qwen/Qwen2.5-7B-Instruct", _config(), None)
    assert t.provider_name == "vllm-local"
    assert t.model == "qwen/Qwen2.5-7B-Instruct"


def test_model_override_wins_over_spec() -> None:
    t = parse_provider_spec("vllm-local/qwen/Qwen2.5-72B-Instruct", _config(), "qwen/Qwen2.5-7B-Instruct")
    assert t.model == "qwen/Qwen2.5-7B-Instruct"


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        parse_provider_spec("nonexistent", _config(), None)


def test_resolve_target_uses_default_provider() -> None:
    t = resolve_target(None, _config())
    assert t.provider_name == "vllm-local"


def test_resolve_target_no_default_raises() -> None:
    config = AppConfig(providers={"x": ProviderConfig(base_url="http://x", default_model="m")})
    with pytest.raises(ValueError, match="default_provider"):
        resolve_target(None, config)
