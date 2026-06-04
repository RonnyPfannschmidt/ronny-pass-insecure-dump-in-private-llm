"""Read entries from a pass (passwordstore.org) store via the pass CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, SecretStr


class PassEntry(BaseModel):
    name: str
    plaintext: SecretStr


def get_store_dir() -> Path:
    env = os.environ.get("PASSWORD_STORE_DIR")
    return Path(env) if env else Path.home() / ".password-store"


def list_entry_names(store_dir: Path) -> list[str]:
    """Return all entry names by walking the store directory."""
    return sorted(
        str(p.relative_to(store_dir).with_suffix(""))
        for p in store_dir.rglob("*.gpg")
    )


def show_entry(name: str) -> str:
    """Decrypt and return a pass entry using the pass CLI."""
    result = subprocess.run(
        ["pass", "show", name],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def load_entries(store_dir: Path) -> list[PassEntry]:
    return [
        PassEntry(name=name, plaintext=show_entry(name))
        for name in list_entry_names(store_dir)
    ]
