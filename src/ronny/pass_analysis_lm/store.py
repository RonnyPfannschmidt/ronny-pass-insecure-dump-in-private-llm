"""Read entries from a pass (passwordstore.org) store via the pass CLI."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, SecretStr


class PassEntry(BaseModel):
    name: str
    plaintext: SecretStr


def get_store_dir() -> Path:
    env = os.environ.get("PASSWORD_STORE_DIR")
    return Path(env) if env else Path.home() / ".password-store"


class Store(ABC):
    """Abstract interface for reading pass store entries."""

    @abstractmethod
    def list_entry_names(self) -> list[str]: ...

    @abstractmethod
    async def show_entry(self, name: str) -> SecretStr: ...


class GpgStore(Store):
    """Real pass store backed by GPG-encrypted .gpg files."""

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir

    def list_entry_names(self) -> list[str]:
        return sorted(
            str(p.relative_to(self.store_dir).with_suffix(""))
            for p in self.store_dir.rglob("*.gpg")
        )

    async def show_entry(self, name: str) -> SecretStr:
        proc = await asyncio.create_subprocess_exec(
            "pass",
            "show",
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"pass show {name!r} failed with exit code {proc.returncode}"
            )
        return SecretStr(stdout.decode())


class InMemoryStore(Store):
    """In-memory store for testing without GPG."""

    def __init__(self, entries: dict[str, str]) -> None:
        self._entries = dict(entries)

    def list_entry_names(self) -> list[str]:
        return sorted(self._entries)

    async def show_entry(self, name: str) -> SecretStr:
        if name not in self._entries:
            raise KeyError(name)
        return SecretStr(self._entries[name])
