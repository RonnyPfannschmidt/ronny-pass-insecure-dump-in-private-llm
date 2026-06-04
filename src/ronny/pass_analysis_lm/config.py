"""App configuration loaded from a TOML file under the platform config dir."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import httpx
import platformdirs
from pydantic import BaseModel, Field

from ronny.pass_analysis_lm.secrets import get_api_key

_APP = "pass-analysis-lm"
_AUTHOR = "ronny"

_EXAMPLE_CONFIG = """\
# pass-analysis-lm configuration
# Run `pass-analysis-lm config show-path` to find this file.

# Provider used when --provider is omitted on the command line.
default_provider = "vllm-local"

# Each [providers.<name>] section defines an OpenAI-compatible endpoint.
# api_key is the fallback Bearer token value; use "none" for unauthenticated servers.
# Prefer storing real keys in the system keyring instead:
#   pass-analysis-lm config set-key <provider>
# default_model is required; models is an optional pinned list for reference.
# Select at runtime with:  --provider vllm-local/Qwen2.5-72B-Instruct

[providers.vllm-local]
base_url = "http://192.168.1.100:8000/v1"
api_key = "none"
default_model = "Qwen2.5-72B-Instruct"
models = [
  "Qwen2.5-72B-Instruct",
  "Qwen2.5-7B-Instruct",
]

[providers.ollama]
base_url = "http://localhost:11434/v1"
api_key = "ollama"
default_model = "llama3.2"

[providers.openai]
base_url = "https://api.openai.com/v1"
api_key = "sk-REPLACE_ME"
default_model = "gpt-4o"
models = ["gpt-4o", "gpt-4o-mini", "o1-mini"]
"""


class ProviderConfig(BaseModel):
    base_url: str
    api_key: str = "none"
    default_model: str
    models: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    default_provider: str | None = None
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)


@dataclass
class ResolvedTarget:
    provider_name: str
    provider: ProviderConfig
    model: str
    api_key: str  # resolved from keyring, falling back to provider.api_key


def parse_provider_spec(
    spec: str, config: AppConfig, model_override: str | None
) -> ResolvedTarget:
    """Parse 'name' or 'name/model' — the slash separates provider from model."""
    if "/" in spec:
        provider_name, model_from_spec = spec.split("/", 1)
    else:
        provider_name = spec
        model_from_spec = None

    if provider_name not in config.providers:
        available = ", ".join(config.providers) or "(none configured)"
        raise ValueError(
            f"Provider {provider_name!r} not found in config. Available: {available}"
        )

    provider = config.providers[provider_name]
    model = model_override or model_from_spec or provider.default_model
    api_key = get_api_key(provider_name, provider.api_key)
    return ResolvedTarget(
        provider_name=provider_name, provider=provider, model=model, api_key=api_key
    )


def resolve_target(
    spec: str | None,
    config: AppConfig,
    model_override: str | None = None,
) -> ResolvedTarget:
    """Resolve a provider/model target from CLI input and loaded config."""
    if spec is None:
        if config.default_provider is None:
            raise ValueError(
                "No --provider given and no default_provider set in config.\n"
                "Run `pass-analysis-lm config init` to create a starter config."
            )
        spec = config.default_provider
    return parse_provider_spec(spec, config, model_override)


async def fetch_models(target: ResolvedTarget) -> list[str]:
    """Fetch available model IDs from the provider's /models endpoint."""
    async with httpx.AsyncClient(
        base_url=target.provider.base_url,
        headers={"Authorization": f"Bearer {target.api_key}"},
        timeout=10.0,
    ) as client:
        response = await client.get("/models")
        response.raise_for_status()
    data = response.json()
    return sorted(item["id"] for item in data.get("data", []))


def config_path() -> Path:
    return Path(platformdirs.user_config_dir(_APP, _AUTHOR)) / "config.toml"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    with path.open("rb") as f:
        data = tomllib.load(f)
    providers = {
        name: ProviderConfig(**values)
        for name, values in data.get("providers", {}).items()
    }
    return AppConfig(
        default_provider=data.get("default_provider"),
        providers=providers,
    )


def write_example_config() -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_EXAMPLE_CONFIG)
    return path
