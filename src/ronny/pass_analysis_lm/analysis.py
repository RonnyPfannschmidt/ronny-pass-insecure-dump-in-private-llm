"""Security analysis of pass entries via a pydantic-ai agent."""

from __future__ import annotations

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

_SYSTEM_PROMPT = """\
You are a security auditor reviewing decrypted password store entries.

Identify issues such as:
- Weak or short passwords
- Plain-text API keys, tokens, or private keys embedded in notes
- Missing or noted lack of MFA / TOTP
- Suspicious metadata or URLs
- Entries that look like they belong to a shared/team account

Be concise. Do NOT repeat secrets verbatim. Output a short bullet list per entry.
If there are no issues, say "No issues found."
"""


def make_agent(target: ResolvedTarget) -> Agent[None, str]:
    oai_provider = OpenAIProvider(
        base_url=target.provider.base_url,
        api_key=target.api_key,
    )
    model = OpenAIModel(model_name=target.model, provider=oai_provider)
    return Agent(model=model, system_prompt=_SYSTEM_PROMPT, output_type=str)


def _fake_retrieve_history(name: str, plaintext: str) -> list[ModelRequest | ModelResponse]:
    """
    Build a fake tool-call / tool-return exchange so the model receives the
    entry content as structured tool output rather than raw user text.
    This slightly reduces the risk of prompt injection from the entry contents.
    """
    tool_call_id = f"retrieve-{abs(hash(name))}"
    return [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="get_password_entry",
                    args={"entry_name": name},
                    tool_call_id=tool_call_id,
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="get_password_entry",
                    content=plaintext,
                    tool_call_id=tool_call_id,
                )
            ]
        ),
    ]


async def analyse_entry(
    name: str, plaintext: str, agent: Agent[None, str]
) -> str:
    history = _fake_retrieve_history(name, plaintext)
    result = await agent.run(
        "Analyse the retrieved password entry for security issues.",
        message_history=history,
    )
    return result.output
