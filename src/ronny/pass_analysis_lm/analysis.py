"""Security analysis of pass entries via a pydantic-ai agent."""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ronny.pass_analysis_lm.config import ResolvedTarget


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


def make_agent(target: ResolvedTarget) -> Agent[None, BatchFindings]:
    oai_provider = OpenAIProvider(
        base_url=target.provider.base_url,
        api_key=target.api_key.get_secret_value()
        if target.api_key is not None
        else None,
    )
    model = OpenAIModel(model_name=target.model, provider=oai_provider)
    return Agent(model=model, system_prompt=_SYSTEM_PROMPT, output_type=BatchFindings)


async def analyse_batch(
    entries: list[tuple[str, str]],
    agent: Agent[None, BatchFindings],
) -> list[EntryFinding]:
    lines = [f"=== Entry: {name} ===\n{plaintext}" for name, plaintext in entries]
    result = await agent.run("\n\n".join(lines))
    return result.output.entries


def _fake_retrieve_history(entry_name: str, plaintext: str) -> list:
    tool_call_id = str(uuid.uuid4())
    response = ModelResponse(
        parts=[
            ToolCallPart(
                tool_name="get_password_entry",
                tool_call_id=tool_call_id,
                args=f"{entry_name}",
            )
        ],
    )
    request = ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name="get_password_entry",
                tool_call_id=tool_call_id,
                content=plaintext,
            )
        ],
    )
    return [response, request]
