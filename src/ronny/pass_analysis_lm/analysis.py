"""Security analysis of pass entries via a pydantic-ai agent."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model


class EntryFinding(BaseModel):
    entry_name: str
    findings: str


class BatchFindings(BaseModel):
    entries: list[EntryFinding]


_SYSTEM_PROMPT = """\
You are a security auditor reviewing decrypted password store entries.
You will receive multiple password store entries. For each one, identify issues such as:
- Weak or short passwords
- Plain-text API keys, tokens, or private keys embedded in notes
- Missing or noted lack of MFA / TOTP
- Suspicious metadata or URLs
- Entries that look like they belong to a shared/team account

Be concise. Do NOT repeat secrets verbatim. Output a short bullet list per entry.
If there are no issues for an entry, write "No issues found."
Return results for every entry provided.
"""


def make_agent(model: Model) -> Agent[None, BatchFindings]:
    return Agent(model=model, system_prompt=_SYSTEM_PROMPT, output_type=BatchFindings)


async def analyse_batch(
    entries: list[tuple[str, str]],
    agent: Agent[None, BatchFindings],
) -> list[EntryFinding]:
    lines = [f"=== Entry: {name} ===\n{plaintext}" for name, plaintext in entries]
    result = await agent.run("\n\n".join(lines))
    return result.output.entries
