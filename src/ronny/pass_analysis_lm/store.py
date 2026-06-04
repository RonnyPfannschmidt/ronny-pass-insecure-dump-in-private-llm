"""Read entries from a pass (passwordstore.org) store via the pass CLI."""

from __future__ import annotations

import asyncio
import os
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


async def show_entry(name: str) -> str:
    """Decrypt and return a pass entry using the pass CLI."""
    proc = await asyncio.create_subprocess_exec(
        "pass", "show", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"pass show {name!r} failed with exit code {proc.returncode}"
        )
    return stdout.decode()
