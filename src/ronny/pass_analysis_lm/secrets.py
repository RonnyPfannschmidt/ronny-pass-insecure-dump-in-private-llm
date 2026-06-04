"""API key storage via the system keyring (GNOME Keyring / KWallet via secretstorage)."""

from __future__ import annotations

import keyring

_SERVICE = "pass-analysis-lm"


def get_api_key(provider_name: str, config_value: str) -> str:
    """Return the keyring-stored key for provider_name, or config_value if none is stored."""
    stored = keyring.get_password(_SERVICE, provider_name)
    return stored if stored is not None else config_value


def set_api_key(provider_name: str, api_key: str) -> None:
    keyring.set_password(_SERVICE, provider_name, api_key)


def delete_api_key(provider_name: str) -> None:
    if keyring.get_password(_SERVICE, provider_name) is None:
        raise KeyError(f"No keyring entry found for provider {provider_name!r}")
    keyring.delete_password(_SERVICE, provider_name)
